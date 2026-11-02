from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.orchestrator import FlowMindOrchestrator
from repo_investigator.reports.html_reporter import HTMLReportGenerator

def test_html_report_generation(tmp_path: Path):
    sample_repo = REPO_ROOT / "sample_repo"
    orchestrator = FlowMindOrchestrator()
    result = orchestrator.run(
        repo_path=sample_repo,
        execute_code=True,
        dry_run=True,
        tier="1",
    )

    html_content = HTMLReportGenerator.generate_html(result, repo_name="sample_repo")
    assert "<!DOCTYPE html>" in html_content
    assert "FlowMind Executive Architecture Audit" in html_content
    assert "mermaid" in html_content
    assert "Consensus Strategy & Strategic Rationale" in html_content
    assert "Architectural Invariant Integrity & Verification Gates" in html_content
    assert "Canonical State Bus & Verified Milestones" in html_content
    assert "What We Learned: Session Retrospective" in html_content
    assert "Multi-Criteria Trade-Off Scoring Matrix" in html_content
    assert "CLIENT AUDIT REPORT" in html_content
    assert "tab-overview" in html_content

    # Test saving report to file
    out_file = tmp_path / "report.html"
    saved = HTMLReportGenerator.save_report(result, out_file, repo_name="sample_repo")
    assert saved.exists()
    assert saved.stat().st_size > 500
    assert saved.read_text(encoding="utf-8") == html_content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

