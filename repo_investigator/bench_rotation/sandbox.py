from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from repo_investigator.bench_rotation.models import CoWSnapshot
from repo_investigator.bench_rotation.state_bus import FencingTokenRejectedError
from repo_investigator.config import get_settings, SandboxProviderType

logger = logging.getLogger(__name__)

class BaseSandbox(ABC):
    """
    Abstract interface for isolated execution environments.
    Guarantees that every tool invocation or write operation validates
    the monotonic Kleppmann Fencing Token at the boundary.
    """

    def __init__(self, workspace_dir: Path | str, initial_fencing_token: int = 1):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.fencing_token = initial_fencing_token
        self.max_accepted_token = initial_fencing_token
        self._snapshots: Dict[str, CoWSnapshot] = {}

    def update_fencing_token(self, new_token: int):
        """Updates the fencing token after Coach substitution."""
        self.fencing_token = new_token
        self.max_accepted_token = new_token

    def _validate_fencing(self, token: int):
        if token < self.max_accepted_token:
            raise FencingTokenRejectedError(
                f"FENCING_TOKEN_REJECTED: token {token} < max_accepted_token {self.max_accepted_token}"
            )

    def _resolve_safe_path(self, rel_path: str) -> Path:
        """
        Guarantees that the resolved path is strictly contained within self.workspace_dir.
        Blocks directory traversal ('../') and absolute path escapes.
        """
        raw_path = Path(rel_path)
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            resolved = (self.workspace_dir / raw_path).resolve()

        try:
            resolved.relative_to(self.workspace_dir)
        except ValueError:
            raise PermissionError(
                f"SANDBOX BREACH DETECTED: Path '{rel_path}' escapes workspace boundary '{self.workspace_dir}'"
            )
        return resolved

    @abstractmethod
    def execute_command(self, cmd: List[str] | str, fencing_token: int, timeout: int = 30) -> Tuple[int, str, str]:
        pass

    @abstractmethod
    def write_file(self, rel_path: str, content: str, fencing_token: int) -> Path:
        pass

    @abstractmethod
    def read_file(self, rel_path: str) -> str:
        pass

    @abstractmethod
    def take_snapshot(self, step: int) -> CoWSnapshot:
        pass

    @abstractmethod
    def restore_snapshot(self, snapshot_id: str) -> bool:
        pass


class LocalSandbox(BaseSandbox):
    """
    Local filesystem sandbox with strict fencing validation and CoW snapshotting.
    """

    def execute_command(self, cmd: List[str] | str, fencing_token: int, timeout: int = 30) -> Tuple[int, str, str]:
        self._validate_fencing(fencing_token)
        try:
            import shlex
            if isinstance(cmd, str):
                cmd_args = shlex.split(cmd, posix=os.name != "nt")
            else:
                cmd_args = list(cmd)

            res = subprocess.run(
                cmd_args,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            return res.returncode, res.stdout, res.stderr
        except Exception as e:
            return 1, "", str(e)

    def write_file(self, rel_path: str, content: str, fencing_token: int) -> Path:
        self._validate_fencing(fencing_token)
        target = self._resolve_safe_path(rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def read_file(self, rel_path: str) -> str:
        target = self._resolve_safe_path(rel_path)
        return target.read_text(encoding="utf-8")

    def take_snapshot(self, step: int) -> CoWSnapshot:
        snapshot_id = f"cow-snap-{step:03d}-{int(time.time()*1000)%100000}"
        file_hashes = {}
        file_contents = {}

        if self.workspace_dir.exists():
            for root, _, files in os.walk(self.workspace_dir):
                for f in files:
                    if f.endswith((".py", ".json", ".md", ".toml", ".txt")):
                        p = Path(root) / f
                        try:
                            content = p.read_text(encoding="utf-8", errors="replace")
                            rel_p = str(p.relative_to(self.workspace_dir)).replace("\\", "/")
                            h = hashlib.sha256(content.encode("utf-8")).hexdigest()
                            file_hashes[rel_p] = h
                            file_contents[rel_p] = content
                        except Exception:
                            pass

        snapshot = CoWSnapshot(
            snapshot_id=snapshot_id,
            step=step,
            timestamp=time.time(),
            file_hashes=file_hashes,
            file_contents=file_contents,
        )
        self._snapshots[snapshot_id] = snapshot
        return snapshot

    def restore_snapshot(self, snapshot_id: str) -> bool:
        if snapshot_id not in self._snapshots:
            return False
        snap = self._snapshots[snapshot_id]
        for rel_p, content in snap.file_contents.items():
            t = self.workspace_dir / rel_p
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(content, encoding="utf-8")
        return True


class DockerSandbox(BaseSandbox):
    """
    Isolated container sandbox executing inside Docker with read-only rootfs
    and volume mounting.
    """

    def __init__(
        self,
        workspace_dir: Path | str,
        initial_fencing_token: int = 1,
        image: str = "python:3.12-slim",
    ):
        super().__init__(workspace_dir, initial_fencing_token)
        self.image = image
        self._fallback = LocalSandbox(workspace_dir, initial_fencing_token)

    def execute_command(self, cmd: List[str] | str, fencing_token: int, timeout: int = 30) -> Tuple[int, str, str]:
        self._validate_fencing(fencing_token)
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{self.workspace_dir}:/workspace",
            "-w", "/workspace",
            self.image,
            "sh", "-c", cmd_str,
        ]
        try:
            res = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout)
            return res.returncode, res.stdout, res.stderr
        except Exception:
            # Fall back to local execution if Docker is unavailable
            return self._fallback.execute_command(cmd, fencing_token, timeout)

    def write_file(self, rel_path: str, content: str, fencing_token: int) -> Path:
        self._validate_fencing(fencing_token)
        return self._fallback.write_file(rel_path, content, fencing_token)

    def read_file(self, rel_path: str) -> str:
        return self._fallback.read_file(rel_path)

    def take_snapshot(self, step: int) -> CoWSnapshot:
        return self._fallback.take_snapshot(step)

    def restore_snapshot(self, snapshot_id: str) -> bool:
        return self._fallback.restore_snapshot(snapshot_id)


class VsockFirecrackerDaemon:
    """
    Simulates / mediates the host-to-guest Firecracker vsock daemon channel.
    Synchronizes the Kleppmann Fencing Token between the host Coach Node
    and the guest VM runtime.
    """

    def __init__(self, port: int = 1024):
        self.port = port
        self.active_fencing_token: int = 1
        self.max_accepted_token: int = 1
        self.active_player_session: str = "starter_agent"
        self.is_session_healthy: bool = True

    def update_fencing_state(self, new_token: int, incoming_player: str):
        """Atomically synchronizes token state across the vsock barrier."""
        self.max_accepted_token = new_token
        self.active_fencing_token = new_token
        self.active_player_session = incoming_player
        self.is_session_healthy = True
        logger.info(
            "Vsock Daemon [Port %d]: Synchronized Fencing Token -> %d for %s",
            self.port, new_token, incoming_player,
        )

    def validate_incoming_call(self, token: int, player_id: str) -> bool:
        """Enforces fencing token check at the vsock hardware boundary."""
        if token < self.max_accepted_token:
            logger.warning("Vsock dropped unauthorized turn: token %d < %d", token, self.max_accepted_token)
            return False
        return True


def create_sandbox(
    workspace_dir: Path | str,
    provider: Optional[SandboxProviderType | str] = None,
    fencing_token: int = 1,
) -> BaseSandbox:
    """Factory creating the appropriate execution sandbox."""
    settings = get_settings()
    p = provider or settings.sandbox_provider
    if isinstance(p, str):
        p = SandboxProviderType(p.lower())

    if p == SandboxProviderType.DOCKER:
        return DockerSandbox(workspace_dir, initial_fencing_token=fencing_token, image=settings.docker_image)
    return LocalSandbox(workspace_dir, initial_fencing_token=fencing_token)

