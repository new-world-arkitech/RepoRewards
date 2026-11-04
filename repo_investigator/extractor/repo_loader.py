from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Common remote Git URL patterns: https://, http://, git@, ssh://, git://
GIT_URL_PATTERNS = [
    re.compile(r"^(https?|git|ssh)://[^\s/$.?#].[^\s]*$", re.IGNORECASE),
    re.compile(r"^git@[a-zA-Z0-9._-]+:[a-zA-Z0-9._/-]+(\.git)?$", re.IGNORECASE),
    re.compile(r"^[a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+:[a-zA-Z0-9._/-]+(\.git)?$", re.IGNORECASE),
]

GITHUB_USER_PATTERN = re.compile(
    r"^https?://github\.com/([a-zA-Z0-9._-]+)/?$",
    re.IGNORECASE,
)
GITHUB_REPO_HTTP_PATTERN = re.compile(
    r"^https?://github\.com/([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+?)(\.git)?/?$",
    re.IGNORECASE,
)
GITHUB_REPO_SSH_PATTERN = re.compile(
    r"^git@github\.com:([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+?)(\.git)?$",
    re.IGNORECASE,
)

GITHUB_RESERVED_USERS = {
    "about", "pricing", "features", "explore", "topics", "collections",
    "trending", "events", "readme", "security", "customer-stories",
    "enterprise", "login", "join", "settings", "orgs", "organizations",
}

def resolve_repo_target(target: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Resolves a target string (which could be a local directory, a Git clone URL,
    or a GitHub user/organization profile URL like https://github.com/The-arkitech) into:
    (clone_url_or_local_path, derived_repo_name, derived_owner)
    """
    if not isinstance(target, str):
        p = Path(target).resolve()
        return str(p), p.name, None

    cleaned = target.strip()
    if not cleaned:
        p = Path(".").resolve()
        return str(p), p.name, None

    # 1. Local filesystem path check
    try:
        p = Path(cleaned)
        if p.exists():
            resolved = p.resolve()
            return str(resolved), resolved.name, None
    except Exception:
        pass

    # 2. Check for GitHub User / Organization Profile URL
    user_match = GITHUB_USER_PATTERN.match(cleaned)
    if user_match:
        username = user_match.group(1)
        if username.lower() not in GITHUB_RESERVED_USERS:
            try:
                api_url = f"https://api.github.com/users/{username}/repos?per_page=100"
                headers = {"User-Agent": "FlowMind-Auditor", "Accept": "application/vnd.github.v3+json"}
                token = os.getenv("GITHUB_TOKEN")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                req = urllib.request.Request(api_url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    repos = json.loads(resp.read().decode("utf-8"))
                    if isinstance(repos, list) and repos:
                        non_forks = [r for r in repos if isinstance(r, dict) and not r.get("fork", False)]
                        candidates = non_forks if non_forks else repos
                        candidates.sort(
                            key=lambda r: (
                                r.get("stargazers_count", 0),
                                r.get("pushed_at") or r.get("updated_at") or "",
                            ),
                            reverse=True,
                        )
                        primary = candidates[0]
                        primary_clone = primary.get("clone_url") or f"https://github.com/{username}/{primary['name']}.git"
                        logger.info("Resolved GitHub user profile '%s' to primary repository '%s'", username, primary["name"])
                        return primary_clone, primary.get("name"), username
            except Exception as e:
                logger.warning("Failed to auto-resolve GitHub user repos for '%s': %s", username, e)
                return cleaned, username, username

    # 3. Check for GitHub Repository HTTP/HTTPS URL
    repo_http_match = GITHUB_REPO_HTTP_PATTERN.match(cleaned)
    if repo_http_match:
        owner = repo_http_match.group(1)
        repo_name = repo_http_match.group(2)
        return cleaned, repo_name, owner

    # 4. Check for GitHub Repository SSH URL
    repo_ssh_match = GITHUB_REPO_SSH_PATTERN.match(cleaned)
    if repo_ssh_match:
        owner = repo_ssh_match.group(1)
        repo_name = repo_ssh_match.group(2)
        return cleaned, repo_name, owner

    # 5. Generic Remote Git URL (GitLab, Bitbucket, etc.)
    if is_git_remote_url(cleaned):
        clean_url = cleaned.rstrip("/").removesuffix(".git")
        derived_name = clean_url.split("/")[-1] or "repository"
        return cleaned, derived_name, None

    # Fallback: treat as local path
    p = Path(cleaned).resolve()
    return str(p), p.name, None

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

    cmd = ["git", "-c", "core.longpaths=true", "clone"]
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
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
            timeout=300,
        )
    except subprocess.CalledProcessError as cpe:
        # If the repository cloned successfully but had checkout warnings (e.g. Windows long paths on non-critical assets)
        if (target / ".git").exists():
            logger.warning("Git clone exited with non-zero status (%s) but .git repository exists: %s", cpe.returncode, cpe.stderr)
            return target
        cleanup_repo_dir(target)
        raise RuntimeError(
            f"Failed to clone remote repository '{url}': {cpe.stderr.strip() or cpe.stdout.strip()}"
        ) from cpe
    except subprocess.TimeoutExpired as te:
        cleanup_repo_dir(target)
        raise TimeoutError(f"Git clone operation timed out after 300s for '{url}'") from te
    except FileNotFoundError as fnf:
        cleanup_repo_dir(target)
        raise RuntimeError("git binary is not installed or not found on PATH.") from fnf

    return target

