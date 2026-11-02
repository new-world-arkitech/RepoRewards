from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.brain.models import (
    CognitiveBrain,
    RepositoryAttribution,
    LearnedSkill,
    LearnedRule,
    LearnedDeadEnd,
    ModelEvolutionStage,
)
from repo_investigator.brain.brain_manager import BrainManager
from repo_investigator.models.archaeology import RepoArchaeology, CommitRecord
from repo_investigator.orchestrator import FlowMindOrchestrator

def test_extract_attribution_with_override(tmp_path: Path):
    attr = BrainManager.extract_attribution(
        repo_path=tmp_path,
        owner_override="AcmeCorp",
    )
    assert attr.owner == "AcmeCorp"
    assert attr.repo_name == tmp_path.name
    assert "AcmeCorp" in attr.attribution_statement
    assert "Proprietary / Unspecified" in attr.license_type

def test_extract_attribution_from_commits(tmp_path: Path):
    commits = [
        CommitRecord(
            commit_hash="abc1234",
            author="Ada Lovelace",
            date="2026-01-01T00:00:00",
            message="Initial commit",
            files_changed=["engine.py"],
        ),
        CommitRecord(
            commit_hash="def5678",
            author="Ada Lovelace",
            date="2026-01-02T00:00:00",
            message="Add calculation routine",
            files_changed=["calc.py"],
        ),
        CommitRecord(
            commit_hash="9998887",
            author="Charles Babbage",
            date="2026-01-03T00:00:00",
            message="Hardware specifications",
            files_changed=["spec.py"],
        ),
    ]
    arch = RepoArchaeology(
        repo_path=str(tmp_path),
        commits=commits,
        total_commits=len(commits),
    )

    attr = BrainManager.extract_attribution(repo_path=tmp_path, archaeology=arch)
    assert attr.owner == "Ada Lovelace"
    assert "Ada Lovelace" in attr.top_contributors
    assert "Charles Babbage" in attr.top_contributors
    assert "Ada Lovelace" in attr.attribution_statement

def test_extract_attribution_license_detection(tmp_path: Path):
    mit_file = tmp_path / "LICENSE"
    mit_file.write_text("The MIT License (MIT)\nCopyright (c) 2026", encoding="utf-8")

    attr = BrainManager.extract_attribution(repo_path=tmp_path, owner_override="OpenSourceDev")
    assert attr.license_type == "MIT"
    assert "under MIT" in attr.attribution_statement

def test_brain_persistence_save_load(tmp_path: Path):
    brain_file = tmp_path / "test_brain.json"
    brain = CognitiveBrain(brain_id="TEST_BRAIN", current_generation=1)
    attribution = RepositoryAttribution(
        owner="Guido van Rossum",
        repo_name="cpython",
        remote_url="https://github.com/python/cpython",
        top_contributors=["Guido van Rossum"],
        license_type="Python Software Foundation",
        attribution_statement="Python core runtime patterns.",
        ingested_at="2026-01-01T00:00:00Z",
    )
    brain.attributions["Guido van Rossum/cpython"] = attribution
    brain.learned_skills.append(
        LearnedSkill(
            skill_id="cpython-001",
            skill_name="Bytecode Execution Loop",
            description="High-velocity opcode dispatch with ceval",
            architectural_category="CORE_RUNTIME",
            code_pattern_template="TARGET(NOP) { DISPATCH(); }",
            source_attribution=attribution,
        )
    )
    brain.learned_rules.append(
        LearnedRule(
            rule_id="RULE-GIL",
            rule_statement="Always hold the Global Interpreter Lock when mutating PyObject reference counts",
            enforcement_scope="GLOBAL",
            rationale="Thread safety for refcounts",
            source_attribution=attribution,
        )
    )
    brain.evolution_stages.append(
        ModelEvolutionStage(
            stage_id="EVO-STAGE-001-Guido",
            stage_number=1,
            model_version="FlowMind-v1.1.0-cognitive",
            timestamp="2026-01-01T00:00:00Z",
            credited_owner="Guido van Rossum",
            credited_repo="Guido van Rossum/cpython",
            license_type="Python Software Foundation",
            capability_unlocked="Global Interpreter Lock Protocol",
            stage_description="Studied CPython runtime",
            skills_gained=["Bytecode Execution Loop"],
            rules_codified=["Always hold GIL"],
            heuristics_learned=["Avoid reference leaks"],
            attribution_statement="Credited to Guido van Rossum",
        )
    )

    saved_path = BrainManager.save_brain(brain, brain_file)
    assert saved_path.exists()

    loaded_brain = BrainManager.load_brain(brain_file)
    assert loaded_brain.brain_id == "TEST_BRAIN"
    assert loaded_brain.current_generation == 1
    assert len(loaded_brain.evolution_stages) == 1
    assert loaded_brain.evolution_stages[0].credited_owner == "Guido van Rossum"
    assert len(loaded_brain.learned_skills) == 1
    assert loaded_brain.learned_skills[0].skill_name == "Bytecode Execution Loop"
    assert loaded_brain.learned_rules[0].rule_statement.startswith("Always hold the Global Interpreter Lock")
    assert loaded_brain.attributions["Guido van Rossum/cpython"].owner == "Guido van Rossum"

def test_brain_session_ingestion_and_attribution(tmp_path: Path):
    sample_repo = REPO_ROOT / "sample_repo"
    brain_path = tmp_path / "session_brain.json"

    orchestrator = FlowMindOrchestrator()
    result = orchestrator.run(
        repo_path=sample_repo,
        execute_code=True,
        dry_run=True,
        tier="1",
        repo_owner="TestArchitect",
        brain_path=brain_path,
    )

    assert result.brain is not None
    assert result.brain.total_repos_ingested >= 1
    assert result.brain.current_generation >= 1
    key = "TestArchitect/sample_repo"
    assert key in result.brain.attributions
    assert result.brain.attributions[key].owner == "TestArchitect"

    # Verify evolution stages record contributor credit
    assert len(result.brain.evolution_stages) >= 1
    stage = result.brain.evolution_stages[-1]
    assert stage.credited_owner == "TestArchitect"
    assert "TestArchitect/sample_repo" in stage.credited_repo
    assert len(stage.skills_gained) > 0
    assert len(stage.rules_codified) > 0
    assert "officially credited to TestArchitect" in stage.attribution_statement

    # Verify skills and rules were ingested and accredited
    assert len(result.brain.learned_skills) > 0
    for skill in result.brain.learned_skills:
        assert skill.source_attribution.owner == "TestArchitect"

    assert len(result.brain.learned_rules) > 0
    for rule in result.brain.learned_rules:
        assert rule.source_attribution.owner == "TestArchitect"

    # Verify prompt prefix formatting with model evolution & credit
    prefix = BrainManager.format_brain_prompt_prefix(result.brain)
    assert "FLOWMIND MODEL EVOLUTION & CONTRIBUTOR CREDIT LINEAGE" in prefix
    assert "Credited Author: TestArchitect" in prefix
    assert "CODIFIED ARCHITECTURAL RULES TO ENFORCE" in prefix

def test_server_brain_endpoint(tmp_path: Path):
    from fastapi.testclient import TestClient
    from repo_investigator.server import app

    brain_file = tmp_path / "api_brain.json"
    brain = CognitiveBrain(brain_id="API_TEST_BRAIN", current_generation=2)
    brain.evolution_stages.append(
        ModelEvolutionStage(
            stage_id="EVO-STAGE-001-Tester",
            stage_number=1,
            model_version="FlowMind-v1.1.0-cognitive",
            timestamp="2026-01-01T00:00:00Z",
            credited_owner="Tester",
            credited_repo="Tester/test-repo",
            license_type="MIT",
            capability_unlocked="Test Capability",
            stage_description="Test evolution",
            attribution_statement="Credited to Tester",
        )
    )
    BrainManager.save_brain(brain, brain_file)

    client = TestClient(app)
    resp = client.get(f"/v1/brain?brain_path={brain_file}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["brain_id"] == "API_TEST_BRAIN"
    assert data["current_generation"] == 2

    # Test evolution stages endpoint
    resp_evo = client.get(f"/v1/brain/evolution?brain_path={brain_file}")
    assert resp_evo.status_code == 200
    evo_data = resp_evo.json()
    assert len(evo_data) == 1
    assert evo_data[0]["credited_owner"] == "Tester"
