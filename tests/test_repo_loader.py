from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.extractor.repo_loader import (
    is_git_remote_url,
    clone_remote_repo,
    cleanup_repo_dir,
)

def test_is_git_remote_url_detection():
    # Valid remote git URLs
    assert is_git_remote_url("https://github.com/facebook/react.git") is True
    assert is_git_remote_url("http://github.com/facebook/react.git") is True
    assert is_git_remote_url("git@github.com:facebook/react.git") is True
    assert is_git_remote_url("ssh://git@github.com/facebook/react.git") is True

    # Invalid / Local paths
    assert is_git_remote_url(".") is False
    assert is_git_remote_url("./sample_repo") is False
    assert is_git_remote_url("C:\\Users\\test") is False
    assert is_git_remote_url("") is False
    assert is_git_remote_url(None) is False

def test_clone_remote_repo_command_assembly(tmp_path: Path):
    dest = tmp_path / "cloned_repo"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        res_dir = clone_remote_repo(
            url="https://github.com/test/repo.git",
            dest_dir=dest,
            depth=25,
            branch="develop",
        )
        assert res_dir == dest
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "git"
        assert cmd[1] == "clone"
        assert "--depth" in cmd
        assert "25" in cmd
        assert "--branch" in cmd
        assert "develop" in cmd
        assert "https://github.com/test/repo.git" in cmd

def test_clone_remote_repo_failure_handling(tmp_path: Path):
    dest = tmp_path / "failed_clone"
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "clone"], stderr="Repository not found."
        )
        with pytest.raises(RuntimeError) as exc_info:
            clone_remote_repo(url="https://github.com/nonexistent/repo.git", dest_dir=dest)
        assert "Failed to clone remote repository" in str(exc_info.value)
        assert "Repository not found." in str(exc_info.value)
        # Verify failed target directory is cleaned up
        assert not dest.exists()

def test_cleanup_repo_dir_safe(tmp_path: Path):
    test_dir = tmp_path / "temp_to_delete"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("hello")
    assert test_dir.exists()

    cleanup_repo_dir(test_dir)
    assert not test_dir.exists()

def test_clone_remote_repo_blocks_flag_injection(tmp_path: Path):
    malicious_url = "--upload-pack=evil.exe"
    with pytest.raises(ValueError) as exc_info:
        clone_remote_repo(url=malicious_url, dest_dir=tmp_path / "danger")
    assert "cannot start with a dash" in str(exc_info.value)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

