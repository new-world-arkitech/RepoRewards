import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.extractor.repomap import MultiLanguageRepomapGenerator

def test_multilanguage_repomap_polyglot(tmp_path: Path):
    # Create sample polyglot files
    py_file = tmp_path / "service.py"
    py_file.write_text("class OrderProcessor:\n    def process(self): pass\n", encoding="utf-8")

    ts_file = tmp_path / "api.ts"
    ts_file.write_text("class ApiClient {\n    function fetchOrders() {}\n}\n", encoding="utf-8")

    go_file = tmp_path / "main.go"
    go_file.write_text("type Server struct {}\nfunc StartServer() {}\n", encoding="utf-8")

    gen = MultiLanguageRepomapGenerator(root_dir=tmp_path, max_tokens=2048)
    repomap = gen.analyze()

    assert "AST REPOMAP / GAME FILM" in repomap
    assert "service.py" in repomap
    assert "api.ts" in repomap
    assert "main.go" in repomap
    assert len(repomap) <= 2048 * 4

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

