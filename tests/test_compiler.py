import json
from pathlib import Path
from repo_investigator.extractor.flow_analyzer import FlowTopologyAnalyzer
from repo_investigator.investigators import (
    FlowTopologyInvestigator,
    DeveloperIntentInvestigator,
    IdiomsPatternInvestigator,
    InvariantsHazardsInvestigator,
)
from repo_investigator.deliberation.council import DeliberationCouncil
from repo_investigator.translator.command_compiler import CommandCompiler
from repo_investigator.models.command_spec import CodingAgentTaskSpec

def test_command_compiler_schema_and_json():
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
        hubs=["rewards_processor"],
    )

    compiler = CommandCompiler()
    spec = compiler.compile(archaeology, findings, session)

    assert isinstance(spec, CodingAgentTaskSpec)
    assert len(spec.architectural_invariants) >= 3
    assert len(spec.execution_directives) >= 3
    assert len(spec.verification_gates) >= 2

    # Verify JSON serialization and validity
    json_str = compiler.to_json(spec)
    parsed = json.loads(json_str)
    assert parsed["task_id"] == spec.task_id
    assert "execution_directives" in parsed
    assert "architectural_invariants" in parsed
