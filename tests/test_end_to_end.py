from pathlib import Path
from repo_investigator.orchestrator import FlowMindOrchestrator

def test_full_pipeline_end_to_end():
    sample_dir = Path("sample_repo").resolve()
    orchestrator = FlowMindOrchestrator()

    # Run full pipeline in dry-run mode
    result = orchestrator.run(sample_dir, execute_code=True, dry_run=True)

    # 1. Archaeology
    assert result.archaeology.total_commits >= 4
    assert len(result.archaeology.churn_hotspots) > 0

    # 2. Findings from 4 investigators
    assert len(result.findings) == 4

    # 3. Deliberation Session
    assert len(result.deliberation.rounds) == 3
    assert result.deliberation.consensus_verdict is not None

    # 4. Machine-Readable Command Spec
    assert result.task_spec.task_id.startswith("TASK-")
    assert len(result.task_spec.execution_directives) > 0

    # 5. Reasoning Coding Agent Execution
    assert result.execution_report is not None
    assert result.execution_report.status == "COMPLETED_SUCCESSFULLY"
    assert len(result.execution_report.step_traces) > 0
