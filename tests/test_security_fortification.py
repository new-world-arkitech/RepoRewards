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
from repo_investigator.extractor.repo_loader import clone_remote_repo

def test_executor_safe_path_resolution(tmp_path: Path):
    safe_path = ReasoningCodingAgent._resolve_safe_path(tmp_path, "core/service.py")
    assert safe_path == (tmp_path / "core" / "service.py").resolve()

    with pytest.raises(PermissionError) as exc_info:
        ReasoningCodingAgent._resolve_safe_path(tmp_path, "../../etc/shadow")
    assert "path traversal outside repository" in str(exc_info.value).lower()

def test_executor_blocks_directory_traversal_directive(tmp_path: Path):
    agent = ReasoningCodingAgent(dry_run=False)

    spec = CodingAgentTaskSpec(
        task_id="ATTACK-001",
        title="Malicious Traversal Test",
        target_repo=str(tmp_path),
        consensus_verdict_ref="VERDICT-TEST",
        high_level_intent="Test security isolation",
        developer_cognitive_context="Simulated attack vector",
        execution_directives=[
            ExecutionDirective(
                step_number=1,
                action_type=ActionType.CREATE_FILE,
                target_file="../../escaped_attack.py",
                instruction="Attempt to write outside repository root",
            )
        ],
    )

    report = agent.execute_spec(spec, target_dir=tmp_path)
    assert report.status == "FAILED"
    assert len(report.files_mutated) == 0
    assert not (tmp_path.parent / "escaped_attack.py").exists()
    trace = report.step_traces[0]
    assert trace.ast_validation_passed is False
    assert any("SECURITY ALERT" in msg for msg in trace.reasoning_chain_of_thought)

def test_repo_loader_blocks_flag_injection(tmp_path: Path):
    with pytest.raises(ValueError) as exc:
        clone_remote_repo(url="--upload-pack=test", dest_dir=tmp_path / "danger")
    assert "cannot start with a dash" in str(exc.value)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
