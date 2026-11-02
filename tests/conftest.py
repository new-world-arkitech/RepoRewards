import os
import stat
import shutil
import sys
import subprocess
from pathlib import Path
import pytest

# Ensure the repository root is on sys.path for pytest and direct execution
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

def _remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def _cleanup_git_dir(git_dir: Path):
    if git_dir.is_dir():
        shutil.rmtree(git_dir, onerror=_remove_readonly)

@pytest.fixture(scope="session", autouse=True)
def isolate_test_brain(tmp_path_factory):
    """
    Isolates the persistent Cognitive Brain path during test sessions
    to prevent mutating the user's local ~/.flowmind/brain.json.
    """
    temp_dir = tmp_path_factory.mktemp("flowmind_brain_session")
    isolated_brain_file = temp_dir / "isolated_brain.json"
    old_env = os.environ.get("FLOWMIND_BRAIN_PATH")
    os.environ["FLOWMIND_BRAIN_PATH"] = str(isolated_brain_file)
    yield isolated_brain_file
    if old_env is not None:
        os.environ["FLOWMIND_BRAIN_PATH"] = old_env
    else:
        os.environ.pop("FLOWMIND_BRAIN_PATH", None)

@pytest.fixture(scope="session", autouse=True)
def ensure_sample_repo_git():
    """
    Ensures that sample_repo has a valid git repository with commit history
    for archaeology and topology extraction tests, even when freshly cloned without .git.
    Cleans up the transient test repository upon session completion to prevent
    git embedded repository warnings during commits.
    """
    sample_dir = repo_root / "sample_repo"
    git_dir = sample_dir / ".git"
    created = False
    if not git_dir.is_dir():
        _init_sample_git_repo(sample_dir)
        created = True
    yield
    if created:
        _cleanup_git_dir(git_dir)

def _init_sample_git_repo(sample_dir: Path):
    try:
        # Trust directory boundary in CI environments
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], capture_output=True)
        subprocess.run(["git", "init"], cwd=sample_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Dev Alice"], cwd=sample_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "alice@example.com"], cwd=sample_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=sample_dir, capture_output=True)

        rewards_file = sample_dir / "rewards_processor.py"
        full_content = rewards_file.read_text(encoding="utf-8") if rewards_file.exists() else ""
        base_content = full_content.split("# TODO: temporary hack")[0].rstrip() + "\n"

        # Commit 1: base files
        rewards_file.write_text(base_content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=sample_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "feat: initial rewards processor implementation"], cwd=sample_dir, capture_output=True, check=True)

        # Commit 2: hack
        rewards_file.write_text(base_content + "\n# TODO: temporary hack to speed up processing\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "hack: temporary workaround for database connection latency"], cwd=sample_dir, capture_output=True, check=True)

        # Commit 3: fix race
        rewards_file.write_text(base_content + "\n# TODO: temporary hack to speed up processing\n\n# Hotfix for race condition\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "fix: race condition in rewards calculation during concurrent events"], cwd=sample_dir, capture_output=True, check=True)

        # Commit 4: refactor / decoupling (restoring full file)
        rewards_file.write_text(full_content, encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "refactor: explore decoupling storage adapter from core calculation"], cwd=sample_dir, capture_output=True, check=True)
    except Exception as e:
        print(f"Warning: Failed to initialize sample_repo git fixture: {e}")
