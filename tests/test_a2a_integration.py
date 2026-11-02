import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.orchestrator import FlowMindOrchestrator
from repo_investigator.bench_rotation.models import ExecutionTier

def test_full_pipeline_with_a2a_bench_rotation_tier3(tmp_path: Path):
    sample_dir = Path("sample_repo").resolve()
    orchestrator = FlowMindOrchestrator()

    # Run full pipeline with explicit Tier 3 A2A Bench Rotation in dry-run
    result = orchestrator.run(
        sample_dir,
        execute_code=True,
        dry_run=True,
        tier=ExecutionTier.TIER_3_A2A_BENCH_ROTATION,
    )

    # 1. Pipeline basics
    assert result.archaeology.total_commits >= 4
    assert len(result.findings) == 4
    assert result.deliberation.consensus_verdict is not None
    assert result.task_spec.task_id.startswith("TASK-")

    # 2. Execution Tier & State Bus
    assert result.execution_tier == "TIER_3"
    assert result.state_bus is not None
    assert result.state_bus.workflow_id == result.task_spec.task_id
    assert result.state_bus.fencing_token >= 1

    # 3. Execution Report & Bench Rotation Telemetry
    assert result.execution_report is not None
    assert result.execution_report.status == "COMPLETED_SUCCESSFULLY"
    bench_rep = result.execution_report.bench_rotation_report
    assert bench_rep is not None
    assert bench_rep.final_tier == ExecutionTier.TIER_3_A2A_BENCH_ROTATION
    assert len(bench_rep.telemetry_history) > 0

    # Verify telemetry has S_health metrics
    first_tel = bench_rep.telemetry_history[0]
    assert hasattr(first_tel, "s_health")
    assert 0.0 <= first_tel.s_health <= 1.0

def test_full_pipeline_tier1_direct_execution():
    sample_dir = Path("sample_repo").resolve()
    orchestrator = FlowMindOrchestrator()

    # Run with Tier 1
    result = orchestrator.run(
        sample_dir,
        execute_code=True,
        dry_run=True,
        tier=ExecutionTier.TIER_1_DIRECT,
    )

    assert result.execution_tier == "TIER_1"
    assert result.execution_report is not None
    assert result.execution_report.status == "COMPLETED_SUCCESSFULLY"
    assert result.state_bus is not None

def test_state_bus_serialization(tmp_path: Path):
    sample_dir = Path("sample_repo").resolve()
    orchestrator = FlowMindOrchestrator()

    result = orchestrator.run(
        sample_dir,
        execute_code=True,
        dry_run=True,
    )

    # Write state bus to disk
    out_file = tmp_path / "state_bus.json"
    assert result.state_bus is not None
    out_file.write_text(json.dumps(result.state_bus.model_dump(), indent=2), encoding="utf-8")

    assert out_file.exists()
    loaded_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded_data["workflow_id"] == result.task_spec.task_id
    assert "fencing_token" in loaded_data
    assert "verified_milestones" in loaded_data

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

