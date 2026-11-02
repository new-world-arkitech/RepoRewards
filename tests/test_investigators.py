from pathlib import Path
from repo_investigator.extractor.flow_analyzer import FlowTopologyAnalyzer
from repo_investigator.investigators import (
    FlowTopologyInvestigator,
    DeveloperIntentInvestigator,
    IdiomsPatternInvestigator,
    InvariantsHazardsInvestigator,
)
from repo_investigator.models.investigator_models import SpecialistRole

def test_investigative_council():
    sample_dir = Path("sample_repo").resolve()
    analyzer = FlowTopologyAnalyzer(sample_dir)
    archaeology = analyzer.analyze()

    flow_inv = FlowTopologyInvestigator()
    f_finding = flow_inv.investigate(archaeology)
    assert f_finding.investigator_role == SpecialistRole.FLOW_TOPOLOGY
    assert len(f_finding.insights) > 0
    assert f_finding.core_hypothesis != ""

    intent_inv = DeveloperIntentInvestigator()
    i_finding = intent_inv.investigate(archaeology)
    assert i_finding.investigator_role == SpecialistRole.DEVELOPER_INTENT
    assert any("CHURN" in ins.category or "COMPROMISE" in ins.category for ins in i_finding.insights)
    assert len(i_finding.developer_thought_model) > 10

    pattern_inv = IdiomsPatternInvestigator()
    p_finding = pattern_inv.investigate(archaeology)
    assert p_finding.investigator_role == SpecialistRole.IDIOMS_PATTERNS
    assert len(p_finding.insights) > 0

    inv_haz = InvariantsHazardsInvestigator()
    h_finding = inv_haz.investigate(archaeology)
    assert h_finding.investigator_role == SpecialistRole.INVARIANTS_HAZARDS
    assert len(h_finding.insights) > 0
