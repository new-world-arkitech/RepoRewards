import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.sandbox import LocalSandbox
from repo_investigator.extractor.repomap import MultiLanguageRepomapGenerator
from repo_investigator.extractor.git_archaeology import GitArchaeologyExtractor

def test_attack_path_traversal_in_sandbox(tmp_path: Path):
    sandbox = LocalSandbox(workspace_dir=tmp_path, initial_fencing_token=1)

    # Attempting to escape sandbox directory via path traversal
    with pytest.raises((ValueError, PermissionError)):
        sandbox.write_file("../../escaped_file.txt", "malicious content", fencing_token=1)

def test_attack_absolute_path_escape_in_sandbox(tmp_path: Path):
    sandbox = LocalSandbox(workspace_dir=tmp_path, initial_fencing_token=1)

    # Attempting to write to an absolute path outside workspace
    escape_target = (tmp_path.parent / "outside.txt").resolve()
    with pytest.raises((ValueError, PermissionError)):
        sandbox.write_file(str(escape_target), "malicious content", fencing_token=1)

def test_attack_giant_file_dos_in_repomap(tmp_path: Path):
    # Create a 15MB minified JavaScript bundle in the target repo
    big_js = tmp_path / "huge_bundle.js"
    big_js.write_text("var a = 1;\n" * 1000000, encoding="utf-8")

    gen = MultiLanguageRepomapGenerator(root_dir=tmp_path, max_tokens=2048)
    repomap = gen.analyze()

    assert "AST REPOMAP / GAME FILM" in repomap
    assert len(repomap) <= 2048 * 4

def test_attack_corrupted_git_repo_archaeology(tmp_path: Path):
    # Create invalid .git directory
    corrupt_git = tmp_path / ".git"
    corrupt_git.mkdir(parents=True)
    (corrupt_git / "HEAD").write_text("corrupted reference garbage", encoding="utf-8")

    extractor = GitArchaeologyExtractor(tmp_path)
    # Must not crash, should fall back safely to synthetic commits
    commits = extractor.extract_commits()
    assert isinstance(commits, list)

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

