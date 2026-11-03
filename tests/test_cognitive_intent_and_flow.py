from __future__ import annotations

import ast
from pathlib import Path
from repo_investigator.models.archaeology import CommitRecord, ASTModule, ASTClass, ASTFunction, RepoArchaeology
from repo_investigator.extractor.git_archaeology import GitArchaeologyExtractor
from repo_investigator.extractor.flow_analyzer import (
    FlowASTVisitor,
    FlowTopologyAnalyzer,
    classify_architectural_layer,
)
from repo_investigator.investigators.intent_investigator import DeveloperIntentInvestigator
from repo_investigator.investigators.flow_investigator import FlowTopologyInvestigator


def test_in_code_cognitive_markers_extraction(tmp_path: Path):
    sample_code = '''
# TODO: refactor database connection pooling
class CoreProcessor:
    """Core domain processor."""
    # HACK: bypass security auth for integration test
    def run(self):
        # FIXME: intermittent deadlock under high concurrency
        return 42
    # CAUTION: thread unsafe state mutation
    def mutate(self):
        pass
'''
    visitor = FlowASTVisitor("core/processor.py", "core.processor", raw_content=sample_code)
    parsed = ast.parse(sample_code)
    visitor.visit(parsed)

    assert len(visitor.cognitive_markers) == 4
    categories = {m.category for m in visitor.cognitive_markers}
    assert "TODO" in categories
    assert "HACK" in categories
    assert "FIXME" in categories
    assert "CAUTION" in categories

    todo_marker = next(m for m in visitor.cognitive_markers if m.category == "TODO")
    assert "connection pooling" in todo_marker.text
    assert todo_marker.line_number == 2


def test_architectural_layer_classification():
    assert classify_architectural_layer("api/v1/routes.py", "api.v1.routes") == "INGRESS"
    assert classify_architectural_layer("cli/main.py", "cli.main") == "INGRESS"
    assert classify_architectural_layer("services/order_service.py", "services.order_service") == "APPLICATION"
    assert classify_architectural_layer("core/models.py", "core.models") == "DOMAIN"
    assert classify_architectural_layer("domain/entities.py", "domain.entities") == "DOMAIN"
    assert classify_architectural_layer("infrastructure/db.py", "infrastructure.db") == "INFRASTRUCTURE"
    assert classify_architectural_layer("adapters/redis_cache.py", "adapters.redis_cache") == "INFRASTRUCTURE"


def test_author_entropy_and_firefighting_bursts(tmp_path: Path):
    extractor = GitArchaeologyExtractor(tmp_path)

    # 1. Single author: entropy should be 0.0
    single_author_commits = [
        CommitRecord(
            commit_hash=f"h{i}",
            author="Alice",
            date="2026-10-01T12:00:00Z",
            message="Feature work",
            files_changed=["engine.py"],
        )
        for i in range(5)
    ]
    hotspots = extractor.calculate_churn_hotspots(single_author_commits)
    assert len(hotspots) == 1
    assert hotspots[0].author_entropy == 0.0
    assert hotspots[0].author_count == 1
    assert hotspots[0].has_firefighting_burst is False

    # 2. Multi-author: entropy should be positive (Conway Dissonance)
    multi_author_commits = [
        CommitRecord(
            commit_hash=f"h{i}",
            author=author,
            date=f"2026-10-0{i+1}T12:00:00Z",
            message="Fix regression",
            files_changed=["engine.py"],
            intent_tags=["BUG_FIX"],
        )
        for i, author in enumerate(["Alice", "Bob", "Charlie", "Dave"])
    ]
    hotspots_multi = extractor.calculate_churn_hotspots(multi_author_commits)
    assert hotspots_multi[0].author_entropy > 1.5
    assert hotspots_multi[0].author_count == 4
    # All were BUG_FIX within 72 hours -> firefighting burst
    assert hotspots_multi[0].has_firefighting_burst is True


def test_flow_topology_martin_metrics_and_layer_leaks(tmp_path: Path):
    # Create mock repo structure with domain layer directly importing infrastructure
    domain_dir = tmp_path / "domain"
    domain_dir.mkdir()
    infra_dir = tmp_path / "infrastructure"
    infra_dir.mkdir()

    infra_file = infra_dir / "db.py"
    infra_file.write_text("class DatabaseAdapter:\n    pass\n", encoding="utf-8")

    domain_file = domain_dir / "models.py"
    # Inverted layer leak: domain models directly importing infrastructure.db
    domain_file.write_text("import infrastructure.db\n# TODO: eliminate direct db coupling\nclass OrderModel:\n    pass\n", encoding="utf-8")

    analyzer = FlowTopologyAnalyzer(tmp_path)
    archaeology = analyzer.analyze()

    assert len(archaeology.modules) == 2
    # Verify cognitive markers
    assert archaeology.architectural_signals["total_in_code_cognitive_markers"] >= 1

    # Verify layer classification
    domain_mod = archaeology.modules["domain/models.py"]
    infra_mod = archaeology.modules["infrastructure/db.py"]
    assert domain_mod.architectural_layer == "DOMAIN"
    assert infra_mod.architectural_layer == "INFRASTRUCTURE"

    # Verify package metrics exist
    assert domain_mod.package_metrics is not None
    assert infra_mod.package_metrics is not None

    # Verify layer inversion detection
    inversions = archaeology.architectural_signals["layer_boundary_inversions"]
    assert len(inversions) >= 1
    assert any("Domain Layer" in inv["violation"] for inv in inversions)


def test_investigators_emit_advanced_cognitive_insights():
    # Setup mock archaeology with advanced cognitive signals
    archaeology = RepoArchaeology(
        repo_path="/mock",
        total_commits=10,
        commits=[],
        churn_hotspots=[],
        modules={},
        call_graph_edges=[],
        detected_cycles=[],
        architectural_signals={
            "zone_of_pain_modules": ["core/engine.py"],
            "layer_boundary_inversions": [{
                "source_module": "core/models.py",
                "target_module": "infrastructure/db.py",
                "violation": "Domain Layer (core/models.py) imports INFRASTRUCTURE (infrastructure/db.py)",
            }],
            "architectural_hubs": ["core/engine.py"],
            "total_in_code_cognitive_markers": 5,
        },
    )

    # Test Flow Investigator
    flow_inv = FlowTopologyInvestigator()
    flow_finding = flow_inv.investigate(archaeology)
    categories = {i.category for i in flow_finding.insights}
    assert "ZONE_OF_PAIN_RIGIDITY" in categories
    assert "INVARIANT_LAYER_BOUNDARY_BREACH" in categories

    # Test Intent Investigator
    intent_inv = DeveloperIntentInvestigator()
    intent_finding = intent_inv.investigate(archaeology)
    assert intent_finding.investigator_name.startswith("Elena")
