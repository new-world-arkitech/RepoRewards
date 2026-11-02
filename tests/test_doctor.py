from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.doctor import (
    check_python_version,
    check_git_installed,
    check_model_providers,
    check_optional_dependencies,
    run_doctor,
)

def test_check_python_version():
    ok, ver_str, msg = check_python_version()
    assert ok is True
    assert "Python" in ver_str

def test_check_git_installed():
    ok, ver_str, msg = check_git_installed()
    # In test environment, git is available
    assert ok is True
    assert "git version" in ver_str

def test_check_model_providers():
    ok, prov_str, msg = check_model_providers()
    assert ok is True
    assert len(prov_str) > 0

def test_check_optional_dependencies():
    results = check_optional_dependencies()
    assert len(results) >= 4
    # FastAPI was installed in prior step
    fastapi_check = next(r for r in results if "FastAPI" in r[0])
    assert fastapi_check[1] is True

def test_run_doctor():
    success = run_doctor()
    assert success is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

