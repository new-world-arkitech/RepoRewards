from __future__ import annotations

import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Common remote Git URL patterns: https://, http://, git@, ssh://, git://
GIT_URL_PATTERNS = [
    re.compile(r"^(https?|git|ssh)://[^\s/$.?#].[^\s]*$", re.IGNORECASE),
    re.compile(r"^git@[a-zA-Z0-9._-]+:[a-zA-Z0-9._/-]+(\.git)?$", re.IGNORECASE),
    re.compile(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+:[a-zA-Z0-9._/-]+(\.git)?$", re.IGNORECASE),
]

def is_git_remote_url(target: str) -> bool:
    """
    Determines if the given target string represents a remote Git repository URL.
    """
    if not isinstance(target, str):
        return False
    target = target.strip()
    if not target:
        return False
    # If it exists on local filesystem as an existing directory or file, treat as local
    try:
        p = Path(target)
        if p.exists():
            return False
    except Exception:
        pass

    for pattern in GIT_URL_PATTERNS:
        if pattern.match(target):
            return True
    return False

def _handle_remove_readonly(func, path, exc_info):
    """Windows-safe error handler for shutil.rmtree on read-only git files."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        logger.warning("Failed to remove readonly attribute on %s: %s", path, e)

def cleanup_repo_dir(dir_path: Path) -> None:
    """Safely cleans up a cloned temporary repository directory."""
    if dir_path.exists() and dir_path.is_dir():
        try:
            shutil.rmtree(dir_path, onerror=_handle_remove_readonly)
            logger.info("Cleaned up temporary repository at %s", dir_path)
        except Exception as e:
            logger.warning("Could not cleanly delete %s: %s", dir_path, e)

def clone_remote_repo(
    url: str,
    dest_dir: Optional[Path] = None,
    depth: int = 50,
    branch: Optional[str] = None,
) -> Path:
    """
    Clones a remote Git repository into a destination directory (or a secure temp directory).
    Enforces shallow clone (--depth) for rapid ingestion.
    """
    target = dest_dir or Path(tempfile.mkdtemp(prefix="flowmind_repo_"))
    target.mkdir(parents=True, exist_ok=True)

    # Prevent Git flag/argument injection attacks
    if url.strip().startswith("-"):
        cleanup_repo_dir(target)
        raise ValueError(f"Security Alert: Malformed remote URL cannot start with a dash: '{url}'")

    cmd = ["git", "clone"]
    if depth > 0:
        cmd.extend(["--depth", str(depth)])
    if branch:
        cmd.extend(["--branch", branch])
    # The '--' separator ensures all subsequent arguments are treated as positionals, not options
    cmd.extend(["--", url, str(target)])

    logger.info("Executing git clone: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            shell=False,
            timeout=180,
        )
    except subprocess.CalledProcessError as cpe:
        # Clean up failed clone directory before raising
        cleanup_repo_dir(target)
        raise RuntimeError(
            f"Failed to clone remote repository '{url}': {cpe.stderr.strip() or cpe.stdout.strip()}"
        ) from cpe
    except subprocess.TimeoutExpired as te:
        cleanup_repo_dir(target)
        raise TimeoutError(f"Git clone operation timed out after 180s for '{url}'") from te
    except FileNotFoundError as fnf:
        cleanup_repo_dir(target)
        raise RuntimeError("git binary is not installed or not found on PATH.") from fnf

    return target

