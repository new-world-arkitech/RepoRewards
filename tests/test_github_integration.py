from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from repo_investigator.orchestrator import FlowMindOrchestrator
from repo_investigator.integrations.github import (
    GITHUB_API_VERSION,
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubETagCache,
    GitHubNotFoundError,
    GitHubPaginationHelper,
    GitHubPermissionDeniedError,
    GitHubPRCommenter,
    GitHubRateLimitExceededError,
    GitHubRateLimitStatus,
    GitHubRateLimitTracker,
    GitHubRestClient,
    GitHubValidationError,
    GitHubWebhookVerifier,
    post_pr_comment,
)


# ==============================================================================
# 1. CONTEXT & PR COMMENT FORMATTING TESTS (BACKWARD COMPATIBILITY)
# ==============================================================================

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
        mock_resp.read.return_value = b'{"id": 12345, "body": "Test comment"}'
        mock_resp.headers = {"x-ratelimit-remaining": "4999"}
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
        assert req.headers["X-github-api-version"] == GITHUB_API_VERSION
        assert req.headers["Accept"] == "application/vnd.github+json"


def test_post_comment_http_error():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://test",
            code=403,
            msg="Forbidden",
            hdrs={"content-type": "application/json"},
            fp=MagicMock(read=lambda: b'{"message": "Resource not accessible by integration"}'),
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


# ==============================================================================
# 2. GITHUB REST GUIDES: RATE LIMIT TRACKER TESTS
# ==============================================================================

def test_rate_limit_tracker_header_parsing():
    tracker = GitHubRateLimitTracker()
    now_epoch = int(time.time()) + 120

    headers = {
        "x-ratelimit-limit": "5000",
        "x-ratelimit-remaining": "4850",
        "x-ratelimit-reset": str(now_epoch),
        "x-ratelimit-used": "150",
        "x-ratelimit-resource": "core",
    }
    tracker.update_from_headers(headers)

    assert tracker.status.limit == 5000
    assert tracker.status.remaining == 4850
    assert tracker.status.reset_epoch == now_epoch
    assert tracker.status.used == 150
    assert tracker.status.resource == "core"
    assert tracker.status.is_exhausted is False
    assert tracker.status.seconds_until_reset > 0


def test_rate_limit_tracker_exhausted():
    tracker = GitHubRateLimitTracker()
    now_epoch = int(time.time()) + 10

    tracker.update_from_headers({
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": str(now_epoch),
    })
    assert tracker.status.is_exhausted is True

    # If reset is in the past, is_exhausted should be False
    past_epoch = int(time.time()) - 10
    tracker.update_from_headers({
        "x-ratelimit-remaining": "0",
        "x-ratelimit-reset": str(past_epoch),
    })
    assert tracker.status.is_exhausted is False


# ==============================================================================
# 3. GITHUB REST GUIDES: CONDITIONAL REQUESTS & ETAG CACHING (304 NOT MODIFIED)
# ==============================================================================

def test_etag_cache_lifecycle():
    cache = GitHubETagCache(max_entries=3)
    url = "https://api.github.com/repos/octocat/Hello-World"

    cache.set(
        url=url,
        etag='"644b5b01"',
        last_modified="Mon, 02 Nov 2026 04:00:00 GMT",
        status_code=200,
        data={"name": "Hello-World"},
        headers={"content-type": "application/json"},
    )

    entry = cache.get(url)
    assert entry is not None
    assert entry.etag == '"644b5b01"'
    assert entry.data["name"] == "Hello-World"

    # Test eviction
    cache.set("https://api.github.com/1", "e1", None, 200, {}, {})
    cache.set("https://api.github.com/2", "e2", None, 200, {}, {})
    cache.set("https://api.github.com/3", "e3", None, 200, {}, {})
    # Max size 3 should have evicted the oldest entry
    assert cache.get(url) is None

    cache.clear()
    assert cache.get("https://api.github.com/3") is None


def test_client_conditional_request_304_handling():
    client = GitHubRestClient(token="test_token", mutative_delay=0.0)
    url = "https://api.github.com/repos/octocat/Hello-World"

    # Pre-populate cache
    client.cache.set(
        url=url,
        etag='"mock_etag_123"',
        last_modified="Mon, 02 Nov 2026 04:00:00 GMT",
        status_code=200,
        data={"id": 1, "name": "Hello-World"},
        headers={"etag": '"mock_etag_123"'},
    )

    # Simulate GitHub returning HTTP 304 Not Modified
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url=url,
            code=304,
            msg="Not Modified",
            hdrs={"x-ratelimit-remaining": "5000"},
            fp=None,
        )

        status, data, headers = client.request("GET", url)
        assert status == 200
        assert data["name"] == "Hello-World"
        assert headers["etag"] == '"mock_etag_123"'

        # Ensure If-None-Match header was sent
        req = mock_urlopen.call_args[0][0]
        assert req.headers["If-none-match"] == '"mock_etag_123"'


# ==============================================================================
# 4. GITHUB REST GUIDES: RFC 5988 LINK HEADER PAGINATION
# ==============================================================================

def test_pagination_helper_parse_links():
    header = (
        '<https://api.github.com/user/repos?page=2&per_page=30>; rel="next", '
        '<https://api.github.com/user/repos?page=5&per_page=30>; rel="last", '
        '<https://api.github.com/user/repos?page=1&per_page=30>; rel="prev", '
        '<https://api.github.com/user/repos?page=1&per_page=30>; rel="first"'
    )
    links = GitHubPaginationHelper.parse_link_header(header)
    assert links["next"] == "https://api.github.com/user/repos?page=2&per_page=30"
    assert links["last"] == "https://api.github.com/user/repos?page=5&per_page=30"
    assert links["prev"] == "https://api.github.com/user/repos?page=1&per_page=30"
    assert links["first"] == "https://api.github.com/user/repos?page=1&per_page=30"

    assert GitHubPaginationHelper.parse_link_header(None) == {}
    assert GitHubPaginationHelper.parse_link_header("") == {}


def test_client_paginate_generator():
    client = GitHubRestClient(token="test_token", mutative_delay=0.0)

    # Page 1 response
    resp_page1 = MagicMock()
    resp_page1.status = 200
    resp_page1.read.return_value = json.dumps([{"id": 1, "name": "repo1"}]).encode("utf-8")
    resp_page1.headers = {
        "link": '<https://api.github.com/user/repos?page=2>; rel="next"',
        "x-ratelimit-remaining": "4998",
    }

    # Page 2 response
    resp_page2 = MagicMock()
    resp_page2.status = 200
    resp_page2.read.return_value = json.dumps([{"id": 2, "name": "repo2"}]).encode("utf-8")
    resp_page2.headers = {"x-ratelimit-remaining": "4997"}

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=resp_page1)),
            MagicMock(__enter__=MagicMock(return_value=resp_page2)),
        ]

        items = list(client.paginate("user/repos", per_page=1))
        assert len(items) == 2
        assert items[0]["name"] == "repo1"
        assert items[1]["name"] == "repo2"


# ==============================================================================
# 5. GITHUB REST GUIDES: WEBHOOK HMAC-SHA256 SIGNATURE VERIFICATION
# ==============================================================================

def test_webhook_verifier_valid_signature():
    secret = "super_secret_webhook_key_2026"
    payload = b'{"action": "opened", "repository": {"full_name": "owner/repo"}}'

    # Compute valid signature
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert GitHubWebhookVerifier.verify_signature(payload, sig, secret) is True


def test_webhook_verifier_invalid_signature():
    secret = "super_secret_webhook_key_2026"
    payload = b'{"action": "opened"}'

    # Wrong digest
    wrong_sig = "sha256=" + "0" * 64
    assert GitHubWebhookVerifier.verify_signature(payload, wrong_sig, secret) is False

    # Missing prefix
    no_prefix_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    assert GitHubWebhookVerifier.verify_signature(payload, no_prefix_sig, secret) is False

    # Missing parameters
    assert GitHubWebhookVerifier.verify_signature(payload, None, secret) is False
    assert GitHubWebhookVerifier.verify_signature(payload, wrong_sig, "") is False


# ==============================================================================
# 6. GITHUB REST GUIDES: SPECIALIZED ERROR TAXONOMY
# ==============================================================================

def test_client_error_taxonomy_401():
    client = GitHubRestClient(token="bad_token", mutative_delay=0.0)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://test",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"message": "Bad credentials", "documentation_url": "https://docs.github.com/rest"}'),
        )

        with pytest.raises(GitHubAuthenticationError) as exc_info:
            client.get_authenticated_user()
        assert exc_info.value.status_code == 401
        assert "Bad credentials" in str(exc_info.value)
        assert exc_info.value.documentation_url == "https://docs.github.com/rest"


def test_client_error_taxonomy_404():
    client = GitHubRestClient(token="token", mutative_delay=0.0)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://test",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"message": "Not Found"}'),
        )

        with pytest.raises(GitHubNotFoundError) as exc_info:
            client.get_repository("nonexistent", "repo")
        assert exc_info.value.status_code == 404


def test_client_error_taxonomy_422_validation():
    client = GitHubRestClient(token="token", mutative_delay=0.0)

    error_payload = {
        "message": "Validation Failed",
        "errors": [{"resource": "Repository", "code": "custom", "field": "name", "message": "name already exists"}],
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://test",
            code=422,
            msg="Unprocessable Entity",
            hdrs={},
            fp=MagicMock(read=lambda: json.dumps(error_payload).encode("utf-8")),
        )

        with pytest.raises(GitHubValidationError) as exc_info:
            client.create_repository(name="duplicate_repo")
        assert exc_info.value.status_code == 422
        assert len(exc_info.value.errors) == 1
        assert exc_info.value.errors[0]["field"] == "name"


# ==============================================================================
# 7. GITHUB REST GUIDES: REPOSITORY, STATUS & CHECK RUN OPERATIONS
# ==============================================================================

def test_client_create_repository_call():
    client = GitHubRestClient(token="test_token", mutative_delay=0.0)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_resp.read.return_value = json.dumps({
            "name": "RepoRewards",
            "html_url": "https://github.com/owner/RepoRewards",
            "clone_url": "https://github.com/owner/RepoRewards.git",
        }).encode("utf-8")
        mock_resp.headers = {"x-ratelimit-remaining": "4995"}
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        repo = client.create_repository(
            name="RepoRewards",
            description="FlowMind Engine",
            private=False,
        )
        assert repo["name"] == "RepoRewards"
        assert repo["clone_url"] == "https://github.com/owner/RepoRewards.git"

        # Check request body
        req = mock_urlopen.call_args[0][0]
        sent_body = json.loads(req.data.decode("utf-8"))
        assert sent_body["name"] == "RepoRewards"
        assert sent_body["description"] == "FlowMind Engine"
        assert sent_body["private"] is False


def test_client_commit_status_and_check_runs():
    client = GitHubRestClient(token="test_token", mutative_delay=0.0)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_resp.read.return_value = json.dumps({"state": "success"}).encode("utf-8")
        mock_resp.headers = {}
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        # 1. Commit Status
        status_res = client.create_commit_status(
            owner="octocat",
            repo="Hello-World",
            sha="6dcb09b5b57875f334f61aebed695e2e4193db5e",
            state="success",
            description="All 100 invariants passed",
        )
        assert status_res["state"] == "success"

        # 2. Check Run
        mock_resp.read.return_value = json.dumps({"id": 999, "conclusion": "success"}).encode("utf-8")
        check_res = client.create_check_run(
            owner="octocat",
            repo="Hello-World",
            name="FlowMind Invariants",
            head_sha="6dcb09b5b57875f334f61aebed695e2e4193db5e",
            conclusion="success",
        )
        assert check_res["conclusion"] == "success"


def test_client_in_place_comment_updating():
    """Verifies that post_or_update_pr_comment edits existing comment if present to avoid spam."""
    client = GitHubRestClient(token="test_token", mutative_delay=0.0)

    existing_comments = [
        {"id": 101, "body": "Normal user comment"},
        {"id": 102, "body": "<!-- flowmind-pr-audit-scorecard -->\nOld Scorecard Content"},
    ]

    resp_list = MagicMock()
    resp_list.status = 200
    resp_list.read.return_value = json.dumps(existing_comments).encode("utf-8")
    resp_list.headers = {}

    resp_patch = MagicMock()
    resp_patch.status = 200
    resp_patch.read.return_value = json.dumps({"id": 102, "body": "Updated content"}).encode("utf-8")
    resp_patch.headers = {}

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=resp_list)),
            MagicMock(__enter__=MagicMock(return_value=resp_patch)),
        ]

        res = client.post_or_update_pr_comment(
            owner="octocat",
            repo="Hello-World",
            issue_number=42,
            body="New Audit Scorecard Content",
        )
        assert res["id"] == 102

        # Check that PATCH was called on comments/102
        req = mock_urlopen.call_args[0][0]
        assert req.method == "PATCH"
        assert "comments/102" in req.full_url


# ==============================================================================
# 8. SERVER GITHUB WEBHOOK & RATE LIMIT ENDPOINTS
# ==============================================================================

def test_server_github_webhook_and_rate_limit(tmp_path: Path):
    from fastapi.testclient import TestClient
    from repo_investigator.server import app

    client = TestClient(app)

    # 1. Ping Event
    resp = client.post(
        "/v1/webhooks/github",
        json={"zen": "Non-blocking is better than blocking."},
        headers={"X-GitHub-Event": "ping", "X-GitHub-Delivery": "test-delivery-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "Pong!" in resp.json()["message"]

    # 2. Secret Verification Failure
    with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "test_secret"}):
        resp_fail = client.post(
            "/v1/webhooks/github",
            json={"action": "opened"},
            headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=invalid"},
        )
        assert resp_fail.status_code == 401
        assert "Invalid X-Hub-Signature-256" in resp_fail.json()["detail"]

    # 3. Valid Signature PR Event
    secret = "test_secret"
    payload_dict = {
        "action": "opened",
        "pull_request": {"number": 12, "head": {"sha": "abc1234"}},
        "repository": {"full_name": "owner/repo", "clone_url": "https://github.com/owner/repo.git"},
    }
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
        resp_pr = client.post(
            "/v1/webhooks/github",
            content=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": sig,
            },
        )
        assert resp_pr.status_code == 200
        data = resp_pr.json()
        assert data["status"] == "accepted"
        assert data["pull_request"] == 12
        assert "workflow_id" in data

    # 4. GET /v1/github/rate-limit endpoint
    with patch.object(GitHubRestClient, "get_rate_limit", return_value={"resources": {"core": {"limit": 5000, "remaining": 4900}}}):
        resp_rl = client.get("/v1/github/rate-limit")
        assert resp_rl.status_code == 200
        rl_data = resp_rl.json()
        assert rl_data["api_version"] == GITHUB_API_VERSION
        assert "core" in rl_data["rate_limits"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
