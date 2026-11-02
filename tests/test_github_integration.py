from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.orchestrator import FlowMindOrchestrator
from repo_investigator.integrations.github import GitHubPRCommenter, post_pr_comment

def test_detect_github_context(tmp_path: Path):
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps({"pull_request": {"number": 42}}), encoding="utf-8")

    with patch.dict(os.environ, {
        "GITHUB_REPOSITORY": "octocat/Hello-World",
        "GITHUB_EVENT_PATH": str(event_file),
    }):
        repo, pr_num = GitHubPRCommenter.detect_github_context()
        assert repo == "octocat/Hello-World"
        assert pr_num == 42

def test_detect_github_context_fallback_ref():
    with patch.dict(os.environ, {
        "GITHUB_REPOSITORY": "octocat/Hello-World",
        "GITHUB_REF": "refs/pull/99/merge",
        "GITHUB_EVENT_PATH": "",
    }):
        repo, pr_num = GitHubPRCommenter.detect_github_context()
        assert repo == "octocat/Hello-World"
        assert pr_num == 99

def test_build_pr_markdown_comment():
    sample_repo = REPO_ROOT / "sample_repo"
    orchestrator = FlowMindOrchestrator()
    result = orchestrator.run(
        repo_path=sample_repo,
        execute_code=True,
        dry_run=True,
        tier="1",
    )

    comment = GitHubPRCommenter.build_pr_markdown_comment(result, repo_name="sample_repo")
    assert "## 🧠 FlowMind Architectural Audit & Invariant Scorecard" in comment
    assert "FLOWMIND STATUS: INVARIANTS PRESERVED" in comment
    assert "Executive Architecture Metrics" in comment
    assert "Verification Gate Evaluations" in comment
    assert "Protected Architectural Invariants" in comment
    assert "```mermaid" in comment
    assert "Verified Milestones & State Bus" in comment

def test_post_comment_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        success = GitHubPRCommenter.post_comment(
            comment_body="Test comment",
            repo="octocat/Hello-World",
            pr_number=42,
            token="ghp_fake_token",
        )
        assert success is True
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert "api.github.com/repos/octocat/Hello-World/issues/42/comments" in req.full_url
        assert req.headers["Authorization"] == "Bearer ghp_fake_token"

def test_post_comment_http_error():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://test", code=403, msg="Forbidden", hdrs={}, fp=MagicMock(read=lambda: b"Permission Denied")
        )

        success = GitHubPRCommenter.post_comment(
            comment_body="Test comment",
            repo="octocat/Hello-World",
            pr_number=42,
            token="ghp_fake_token",
        )
        assert success is False

def test_post_pr_comment_convenience_function():
    sample_repo = REPO_ROOT / "sample_repo"
    orchestrator = FlowMindOrchestrator()
    result = orchestrator.run(
        repo_path=sample_repo,
        execute_code=True,
        dry_run=True,
        tier="1",
    )

    with patch.object(GitHubPRCommenter, "post_comment", return_value=True) as mock_post:
        success = post_pr_comment(
            result=result,
            token="fake_token",
            repo="octocat/Hello-World",
            pr_number=101,
        )
        assert success is True
        mock_post.assert_called_once()
        assert mock_post.call_args[1]["pr_number"] == 101

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

