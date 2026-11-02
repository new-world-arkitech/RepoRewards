from pathlib import Path
from repo_investigator.extractor.flow_analyzer import FlowTopologyAnalyzer
from repo_investigator.investigators import (
    FlowTopologyInvestigator,
    DeveloperIntentInvestigator,
    IdiomsPatternInvestigator,
    InvariantsHazardsInvestigator,
)
from repo_investigator.deliberation.council import DeliberationCouncil
from repo_investigator.deliberation.consensus_matrix import ConsensusScoringMatrix

def test_deliberation_council_and_scoring():
    sample_dir = Path("sample_repo").resolve()
    analyzer = FlowTopologyAnalyzer(sample_dir)
    archaeology = analyzer.analyze()

    findings = [
        FlowTopologyInvestigator().investigate(archaeology),
        DeveloperIntentInvestigator().investigate(archaeology),
        IdiomsPatternInvestigator().investigate(archaeology),
        InvariantsHazardsInvestigator().investigate(archaeology),
    ]

    council = DeliberationCouncil()
    session = council.deliberate(
        repo_name="sample_repo",
        findings=findings,
        hubs=archaeology.architectural_signals.get("architectural_hubs", ["rewards_processor"]),
        has_cycles=len(archaeology.detected_cycles) > 0,
        has_churn=len(archaeology.churn_hotspots) > 0,
        has_layer_leaks=True,
    )

    assert len(session.rounds) == 3
    assert session.rounds[0].round_name.startswith("Round 1")
    assert session.rounds[1].round_name.startswith("Round 2")
    assert session.rounds[2].round_name.startswith("Round 3")

    # Verify scoring
    assert "PRAGMATIST" in session.perspectives_scoring
    assert "MODERNIZER" in session.perspectives_scoring
    assert "SENTINEL" in session.perspectives_scoring

    # Verify consensus verdict
    verdict = session.consensus_verdict
    assert verdict.verdict_id.startswith("VERDICT-")
    assert len(verdict.hard_invariants) >= 3
    assert len(verdict.required_mutations) >= 3
