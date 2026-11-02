from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.coach.developer_aid import DeveloperAid

def test_explain_file_valid():
    aid = DeveloperAid()
    sample_file = REPO_ROOT / "sample_repo" / "rewards_processor.py"
    exp = aid.explain_file(sample_file, repo_root=REPO_ROOT / "sample_repo")

    assert exp.file_path is not None
    assert "rewards_processor" in exp.title or "rewards_processor" in exp.file_path
    assert len(exp.plain_english_summary) > 10
    assert len(exp.key_responsibilities) > 0
    assert "RewardsProcessor" in exp.beginner_usage_example or "import" in exp.beginner_usage_example

def test_explain_file_not_found():
    aid = DeveloperAid()
    with pytest.raises(FileNotFoundError):
        aid.explain_file("nonexistent_module.py")

def test_explain_file_detects_gotchas(tmp_path: Path):
    bad_code = (
        "def risky_function(items=[]):\n"
        "    try:\n"
        "        pass\n"
        "    except:\n"
        "        pass\n"
    )
    bad_file = tmp_path / "risky.py"
    bad_file.write_text(bad_code, encoding="utf-8")

    aid = DeveloperAid()
    exp = aid.explain_file(bad_file, repo_root=tmp_path)
    assert any("mutable default argument" in g for g in exp.potential_gotchas)
    assert any("bare 'except:'" in g for g in exp.potential_gotchas)

def test_diagnose_error_attribute_error():
    aid = DeveloperAid()
    error_str = "AttributeError: 'NoneType' object has no attribute 'execute'"
    diag = aid.diagnose_error(error_str)

    assert diag.error_type == "AttributeError"
    assert "property or method that does not exist" in diag.plain_english_explanation
    assert len(diag.step_by_step_fix) >= 2
    assert "defensive pattern" in diag.code_diff_suggestion

def test_diagnose_error_key_error():
    aid = DeveloperAid()
    error_str = "KeyError: 'user_id'"
    diag = aid.diagnose_error(error_str)

    assert diag.error_type == "KeyError"
    assert "dictionary" in diag.plain_english_explanation
    assert any("get('key'" in fix for fix in diag.step_by_step_fix)

def test_diagnose_error_traceback(tmp_path: Path):
    target = tmp_path / "app.py"
    target.write_text("def run():\n    return 1 / 0\nrun()\n", encoding="utf-8")

    tb = (
        'Traceback (most recent call last):\n'
        f'  File "{target}", line 2, in run\n'
        '    return 1 / 0\n'
        'ZeroDivisionError: division by zero\n'
    )
    aid = DeveloperAid()
    diag = aid.diagnose_error(tb, repo_root=tmp_path)

    assert diag.error_type == "ZeroDivisionError"
    assert diag.implicated_line == 2
    assert diag.implicated_file == str(target)
    assert "return 1 / 0" in diag.root_cause_analysis

def test_guide_feature():
    aid = DeveloperAid()
    guide = aid.guide_feature("Add multi-tier loyalty points bonus calculation", repo_root=REPO_ROOT / "sample_repo")

    assert "loyalty points bonus" in guide.goal
    assert len(guide.step_by_step_checklist) >= 4
    assert len(guide.architectural_rules_to_respect) >= 2
    assert "NewFeatureService" in guide.starter_code_snippet

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
