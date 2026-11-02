from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.coding_agent.executor import ReasoningCodingAgent
from repo_investigator.models.command_spec import (
    CodingAgentTaskSpec,
    ExecutionDirective,
    ActionType,
)
from repo_investigator.models.explanations import get_plain_english_insight

def test_unified_diff_generation_in_executor(tmp_path: Path):
    agent = ReasoningCodingAgent(dry_run=False)

    spec = CodingAgentTaskSpec(
        task_id="ERG-001",
        title="Ergonomics Test Spec",
        target_repo=str(tmp_path),
        consensus_verdict_ref="VERDICT-TEST",
        high_level_intent="Test unified diffs",
        developer_cognitive_context="Developer ergonomics verification",
        execution_directives=[
            ExecutionDirective(
                step_number=1,
                action_type=ActionType.CREATE_FILE,
                target_file="test_module.py",
                target_symbol="TestModule",
                instruction="Create new test module",
            )
        ],
    )

    report = agent.execute_spec(spec, target_dir=tmp_path)
    assert "test_module.py" in report.unified_diffs
    diff_text = report.unified_diffs["test_module.py"]
    assert "--- a/test_module.py" in diff_text
    assert "+++ b/test_module.py" in diff_text
    assert "+class TestModule" in diff_text or "+Auto-generated decoupled module" in diff_text

def test_plain_english_glossary_lookup():
    insight = get_plain_english_insight("TOPOLOGY_CYCLIC_DEPENDENCY")
    assert "Chicken-and-Egg" in insight["title"]
    assert len(insight["why_it_matters"]) > 10
    assert len(insight["how_to_fix"]) > 10

    default_insight = get_plain_english_insight("CUSTOM_UNKNOWN_PATTERN")
    assert default_insight["title"] == "Custom Unknown Pattern"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
