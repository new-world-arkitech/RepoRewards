from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.orchestrator import FlowMindOrchestrator
from repo_investigator.coach.retrospective import SessionRetrospectiveBuilder, WhatWeLearnedReport

def test_what_we_learned_retrospective_lifecycle(tmp_path: Path):
    sample_repo = REPO_ROOT / "sample_repo"
    orchestrator = FlowMindOrchestrator()
    result = orchestrator.run(
        repo_path=sample_repo,
        execute_code=True,
        dry_run=True,
        tier="1",
    )

    report = SessionRetrospectiveBuilder.build(result, repo_name="sample_repo")
    assert isinstance(report, WhatWeLearnedReport)
    assert report.repo_name == "sample_repo"
    assert len(report.executive_summary) > 20
    assert len(report.developer_intent_uncovered) > 20
    assert len(report.invariants_established) > 0
    assert len(report.key_takeaways_for_developers) >= 3
    assert len(report.recommended_next_steps) >= 2
    assert report.model_evolution_credit is not None
    assert report.model_evolution_credit.credited_owner is not None

    # Verify Markdown formatting
    md = SessionRetrospectiveBuilder.format_markdown(report)
    assert "# 🎓 What We Learned: Architectural Retrospective" in md
    assert "Developer Intent & Mental Model" in md
    assert "Top Lessons for the Engineering Team" in md
    assert "Model Capability Evolution & Contributor Credit" in md
    assert report.model_evolution_credit.credited_owner in md

    # Verify file export
    out_file = tmp_path / "what_we_learned.md"
    saved = SessionRetrospectiveBuilder.save_markdown(report, out_file)
    assert saved.exists()
    assert saved.read_text(encoding="utf-8") == md

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

