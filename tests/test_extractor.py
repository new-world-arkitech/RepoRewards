from pathlib import Path
from repo_investigator.extractor.git_archaeology import GitArchaeologyExtractor
from repo_investigator.extractor.flow_analyzer import FlowTopologyAnalyzer

def test_git_archaeology_extraction():
    sample_dir = Path("sample_repo").resolve()
    extractor = GitArchaeologyExtractor(sample_dir)
    assert extractor.is_git_repo() is True

    commits = extractor.extract_commits()
    assert len(commits) >= 4

    # Check intent tags
    tags = {tag for c in commits for tag in c.intent_tags}
    assert "HACK_OR_WORKAROUND" in tags or "BUG_FIX" in tags or "REFACTORING" in tags

    hotspots = extractor.calculate_churn_hotspots(commits)
    assert len(hotspots) > 0
    # rewards_processor.py was modified the most
    top_file = hotspots[0].file_path
    assert "rewards_processor.py" in top_file

def test_flow_topology_analysis():
    sample_dir = Path("sample_repo").resolve()
    analyzer = FlowTopologyAnalyzer(sample_dir)
    archaeology = analyzer.analyze()

    assert archaeology.total_commits >= 4
    assert len(archaeology.modules) >= 3
    assert any("rewards_processor" in k for k in archaeology.modules.keys())
    assert len(archaeology.call_graph_edges) > 0
