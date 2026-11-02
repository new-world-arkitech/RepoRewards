from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from repo_investigator.orchestrator import PipelineResult

logger = logging.getLogger(__name__)

# Standard recommended GitHub API version (pinned per GitHub Docs REST Guides)
GITHUB_API_VERSION = "2022-11-28"
DEFAULT_USER_AGENT = "FlowMind-Architecture-Bot/1.0 (+https://github.com/new-world-arkitech/RepoRewards)"
GITHUB_API_BASE_URL = "https://api.github.com"


# ==============================================================================
# 1. SPECIALIZED GITHUB API EXCEPTIONS
# ==============================================================================

class GitHubAPIError(Exception):
    """Base exception for all GitHub REST API communication failures."""
    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response_data: Any = None,
        documentation_url: str = "",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data
        self.documentation_url = documentation_url


class GitHubAuthenticationError(GitHubAPIError):
    """Raised when GitHub returns 401 Unauthorized (invalid or expired token)."""


class GitHubPermissionDeniedError(GitHubAPIError):
    """Raised when GitHub returns 403 Forbidden (missing token scopes or fine-grained permissions)."""


class GitHubNotFoundError(GitHubAPIError):
    """Raised when GitHub returns 404 Not Found (repository or resource does not exist or is private)."""


class GitHubRateLimitExceededError(GitHubAPIError):
    """
    Raised when GitHub primary or secondary rate limits are exhausted.
    Captures reset epoch timestamp and Retry-After interval for automated backoff.
    """
    def __init__(
        self,
        message: str,
        reset_timestamp: Optional[int] = None,
        retry_after: Optional[int] = None,
        is_secondary: bool = False,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.reset_timestamp = reset_timestamp
        self.retry_after = retry_after
        self.is_secondary = is_secondary


class GitHubValidationError(GitHubAPIError):
    """Raised when GitHub returns 422 Unprocessable Entity with validation details."""
    def __init__(
        self,
        message: str,
        errors: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.errors = errors or []


# ==============================================================================
# 2. RATE LIMIT & SECONDARY RATE LIMIT TRACKER
# ==============================================================================

@dataclass
class GitHubRateLimitStatus:
    """Snapshot of GitHub REST API rate limit status across resource domains."""
    limit: int = 5000
    remaining: int = 5000
    reset_epoch: int = 0
    used: int = 0
    resource: str = "core"

    @property
    def seconds_until_reset(self) -> float:
        return max(0.0, float(self.reset_epoch) - time.time())

    @property
    def is_exhausted(self) -> bool:
        return self.remaining <= 0 and self.seconds_until_reset > 0


class GitHubRateLimitTracker:
    """
    Thread-safe tracker for GitHub REST API primary and secondary rate limits.
    Inspects response headers:
      - x-ratelimit-limit
      - x-ratelimit-remaining
      - x-ratelimit-reset
      - x-ratelimit-used
      - x-ratelimit-resource
      - retry-after
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.status = GitHubRateLimitStatus()

    def update_from_headers(self, headers: Any):
        """Updates internal status from HTTP response headers."""
        with self._lock:
            # Case-insensitive lookup helper
            def get_h(key: str) -> Optional[str]:
                if hasattr(headers, "get"):
                    val = headers.get(key)
                    if val is None:
                        val = headers.get(key.lower())
                    return str(val) if val is not None else None
                return None

            limit = get_h("x-ratelimit-limit")
            remaining = get_h("x-ratelimit-remaining")
            reset = get_h("x-ratelimit-reset")
            used = get_h("x-ratelimit-used")
            resource = get_h("x-ratelimit-resource")

            if limit is not None and limit.isdigit():
                self.status.limit = int(limit)
            if remaining is not None and remaining.isdigit():
                self.status.remaining = int(remaining)
            if reset is not None and reset.isdigit():
                self.status.reset_epoch = int(reset)
            if used is not None and used.isdigit():
                self.status.used = int(used)
            if resource:
                self.status.resource = resource

    def wait_if_exhausted(self, safety_margin_seconds: float = 1.0) -> float:
        """
        Pauses thread execution if primary rate limit is exhausted until reset epoch.
        Returns the duration waited in seconds.
        """
        with self._lock:
            if self.status.is_exhausted:
                wait_sec = self.status.seconds_until_reset + safety_margin_seconds
                logger.warning(
                    "GitHub rate limit reached (0 remaining). Pausing %.1fs until reset at %s",
                    wait_sec,
                    self.status.reset_epoch,
                )
            else:
                return 0.0

        if wait_sec > 0:
            time.sleep(wait_sec)
        return wait_sec


# ==============================================================================
# 3. CONDITIONAL REQUEST ETAG CACHE (304 NOT MODIFIED)
# ==============================================================================

@dataclass
class CachedResponse:
    etag: Optional[str]
    last_modified: Optional[str]
    status_code: int
    data: Any
    headers: Dict[str, str]
    cached_at: float = field(default_factory=time.time)


class GitHubETagCache:
    """
    In-memory ETag & Last-Modified cache for GitHub REST API requests.
    Enables conditional GET requests (`If-None-Match`, `If-Modified-Since`).
    When GitHub responds with 304 Not Modified, cached data is returned with ZERO
    impact on primary rate limits, adhering to GitHub Best Practices.
    """
    def __init__(self, max_entries: int = 1000):
        self._cache: Dict[str, CachedResponse] = {}
        self._lock = threading.Lock()
        self.max_entries = max_entries

    def get(self, url: str) -> Optional[CachedResponse]:
        with self._lock:
            return self._cache.get(url)

    def set(
        self,
        url: str,
        etag: Optional[str],
        last_modified: Optional[str],
        status_code: int,
        data: Any,
        headers: Dict[str, str],
    ):
        with self._lock:
            if len(self._cache) >= self.max_entries:
                # Evict oldest entry
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].cached_at)
                del self._cache[oldest_key]

            self._cache[url] = CachedResponse(
                etag=etag,
                last_modified=last_modified,
                status_code=status_code,
                data=data,
                headers=headers,
            )

    def clear(self):
        with self._lock:
            self._cache.clear()


# ==============================================================================
# 4. RFC 5988 LINK HEADER PAGINATION HELPER
# ==============================================================================

class GitHubPaginationHelper:
    """
    Parses RFC 5988 hypermedia Link headers according to GitHub Docs Guides:
      Link: <https://api.github.com/resource?page=2>; rel="next",
            <https://api.github.com/resource?page=5>; rel="last"
    Ensures URL links are consumed dynamically rather than manually constructing pages.
    """
    LINK_REGEX = re.compile(r'<([^>]+)>;\s*rel="([^"]+)"')

    @classmethod
    def parse_link_header(cls, link_header: Optional[str]) -> Dict[str, str]:
        """Parses a Link header string into a dictionary of rel -> url."""
        if not link_header:
            return {}
        links: Dict[str, str] = {}
        for match in cls.LINK_REGEX.finditer(link_header):
            url, rel = match.groups()
            links[rel] = url
        return links


# ==============================================================================
# 5. WEBHOOK HMAC-SHA256 SIGNATURE VERIFICATION
# ==============================================================================

class GitHubWebhookVerifier:
    """
    Verifies GitHub Webhook payload authenticity using HMAC-SHA256 (X-Hub-Signature-256).
    Enforces constant-time comparison to guard against timing attacks per GitHub Security Guides.
    """
    @classmethod
    def verify_signature(
        cls,
        payload_bytes: bytes,
        signature_header: Optional[str],
        secret: str,
    ) -> bool:
        """
        Validates that the provided X-Hub-Signature-256 matches the HMAC-SHA256
        hexdigest of the payload bytes computed using the shared secret.
        """
        if not signature_header or not secret:
            return False

        # Header format must be 'sha256=<64-char-hex>'
        prefix = "sha256="
        if not signature_header.startswith(prefix):
            return False

        provided_digest = signature_header[len(prefix):].strip()
        expected_digest = hmac.new(
            key=secret.encode("utf-8"),
            msg=payload_bytes,
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison
        return hmac.compare_digest(expected_digest, provided_digest)


# ==============================================================================
# 6. PRODUCTION-GRADE GITHUB REST API CLIENT
# ==============================================================================

class GitHubRestClient:
    """
    Enterprise-grade GitHub REST API client implementing all requirements from GitHub Docs Guides:
      1. Explicit version pinning (`X-GitHub-Api-Version: 2022-11-28`)
      2. Strict JSON media type (`Accept: application/vnd.github+json`)
      3. Custom User-Agent header (mandatory for all API traffic)
      4. ETag / 304 conditional request caching to preserve rate limits
      5. Primary & secondary rate limit monitoring with automatic backoff
      6. Mutative request pacing (pausing >= 1.0s between POST/PATCH/DELETE per Best Practices)
      7. RFC 5988 hypermedia Link header pagination
      8. Automatic redirect handling and structured error diagnostics
    """
    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = GITHUB_API_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        api_version: str = GITHUB_API_VERSION,
        mutative_delay: float = 1.0,
        enable_cache: bool = True,
        max_retries: int = 3,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.api_version = api_version
        self.mutative_delay = mutative_delay
        self.enable_cache = enable_cache
        self.max_retries = max_retries

        self.rate_limiter = GitHubRateLimitTracker()
        self.cache = GitHubETagCache()
        self._mutative_lock = threading.Lock()
        self._last_mutative_time: float = 0.0

    def _build_headers(
        self,
        extra_headers: Optional[Dict[str, str]] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.api_version,
            "User-Agent": self.user_agent,
        }
        if self.token:
            # Handles classic tokens (ghp_...) or fine-grained tokens (github_pat_...)
            headers["Authorization"] = f"Bearer {self.token}"

        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def request(
        self,
        method: str,
        endpoint_or_url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
    ) -> Tuple[int, Any, Dict[str, str]]:
        """
        Executes an HTTP request against GitHub REST API with full resilience:
          - ETag conditional requests (304 Not Modified)
          - Mutative request rate throttling
          - Primary rate limit reset backoff
          - Secondary rate limit exponential backoff
        Returns (status_code, response_data, response_headers).
        """
        # Determine full URL
        if endpoint_or_url.startswith("http://") or endpoint_or_url.startswith("https://"):
            full_url = endpoint_or_url
        else:
            full_url = f"{self.base_url}/{endpoint_or_url.lstrip('/')}"

        # Append query params if present
        if params:
            query_str = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            sep = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{sep}{query_str}"

        # Mutative pacing check (POST, PATCH, PUT, DELETE)
        is_mutative = method.upper() in ("POST", "PATCH", "PUT", "DELETE")
        if is_mutative:
            with self._mutative_lock:
                elapsed = time.time() - self._last_mutative_time
                if elapsed < self.mutative_delay:
                    sleep_time = self.mutative_delay - elapsed
                    logger.debug("Pacing mutative request (%s): sleeping %.2fs", method, sleep_time)
                    time.sleep(sleep_time)

        # Primary rate limit check
        self.rate_limiter.wait_if_exhausted()

        # Check ETag cache for GET requests
        cached_entry = None
        if method.upper() == "GET" and use_cache and self.enable_cache:
            cached_entry = self.cache.get(full_url)

        req_headers = self._build_headers(
            extra_headers=headers,
            etag=cached_entry.etag if cached_entry else None,
            last_modified=cached_entry.last_modified if cached_entry else None,
        )

        payload_bytes: Optional[bytes] = None
        if json_data is not None:
            payload_bytes = json.dumps(json_data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        # Retry loop for secondary rate limits and transient network glitches
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                full_url,
                data=payload_bytes,
                headers=req_headers,
                method=method.upper(),
            )

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_headers = dict(resp.headers.items())
                    self.rate_limiter.update_from_headers(resp_headers)
                    if is_mutative:
                        self._last_mutative_time = time.time()

                    status_code = resp.status
                    body = resp.read()
                    data = None
                    if body:
                        try:
                            data = json.loads(body.decode("utf-8"))
                        except Exception:
                            data = body.decode("utf-8", errors="replace")

                    # Cache successful GET responses with an ETag
                    if method.upper() == "GET" and self.enable_cache and ("etag" in resp_headers or "last-modified" in resp_headers):
                        self.cache.set(
                            url=full_url,
                            etag=resp_headers.get("etag"),
                            last_modified=resp_headers.get("last-modified"),
                            status_code=status_code,
                            data=data,
                            headers=resp_headers,
                        )

                    return status_code, data, resp_headers

            except urllib.error.HTTPError as he:
                resp_headers = dict(he.headers.items()) if he.headers else {}
                self.rate_limiter.update_from_headers(resp_headers)
                if is_mutative:
                    self._last_mutative_time = time.time()

                # Handle 304 Not Modified
                if he.code == 304 and cached_entry is not None:
                    logger.debug("Conditional request 304 Not Modified for %s (0 rate-limit cost)", full_url)
                    return 200, cached_entry.data, {**cached_entry.headers, **resp_headers}

                # Parse error response body
                error_body = he.read().decode("utf-8", errors="replace") if he.fp else ""
                error_json: Dict[str, Any] = {}
                try:
                    error_json = json.loads(error_body)
                except Exception:
                    pass

                message = error_json.get("message", error_body) or str(he)
                doc_url = error_json.get("documentation_url", "")

                # Handle 429 or 403 Secondary Rate Limits / Abuse Limits
                is_secondary = (
                    he.code == 429 or
                    (he.code == 403 and "secondary rate limit" in message.lower()) or
                    (he.code == 403 and "abuse detection" in message.lower())
                )

                retry_after_str = resp_headers.get("retry-after")
                retry_after = int(retry_after_str) if (retry_after_str and retry_after_str.isdigit()) else None

                if is_secondary and attempt < self.max_retries:
                    backoff = retry_after if retry_after else (2 ** attempt * 2.0)
                    logger.warning("GitHub secondary rate limit encountered. Backing off %.1fs (attempt %d/%d)", backoff, attempt + 1, self.max_retries)
                    time.sleep(backoff)
                    continue

                # Raise specialized errors
                if he.code == 401:
                    raise GitHubAuthenticationError(f"GitHub authentication failed (401): {message}", status_code=401, response_data=error_json, documentation_url=doc_url)
                if he.code == 403:
                    if is_secondary or "rate limit" in message.lower():
                        raise GitHubRateLimitExceededError(
                            f"GitHub rate limit exceeded (403): {message}",
                            status_code=403,
                            response_data=error_json,
                            documentation_url=doc_url,
                            reset_timestamp=self.rate_limiter.status.reset_epoch,
                            retry_after=retry_after,
                            is_secondary=is_secondary,
                        )
                    raise GitHubPermissionDeniedError(f"GitHub permission denied (403): {message}", status_code=403, response_data=error_json, documentation_url=doc_url)
                if he.code == 404:
                    raise GitHubNotFoundError(f"GitHub resource not found (404): {message}", status_code=404, response_data=error_json, documentation_url=doc_url)
                if he.code == 422:
                    errors_list = error_json.get("errors", [])
                    raise GitHubValidationError(f"GitHub validation failed (422): {message}", status_code=422, response_data=error_json, documentation_url=doc_url, errors=errors_list)

                raise GitHubAPIError(f"GitHub API error ({he.code}): {message}", status_code=he.code, response_data=error_json, documentation_url=doc_url)

            except (urllib.error.URLError, TimeoutError) as ue:
                if attempt < self.max_retries:
                    wait_sec = 1.5 * (attempt + 1)
                    logger.warning("Network connection glitch (%s). Retrying in %.1fs...", ue, wait_sec)
                    time.sleep(wait_sec)
                    continue
                raise GitHubAPIError(f"Network error connecting to GitHub: {ue}")

        raise GitHubAPIError("Maximum request retries exceeded")

    # --------------------------------------------------------------------------
    # PAGINATION (Iterating with Link Headers per GitHub Best Practices)
    # --------------------------------------------------------------------------
    def paginate(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        per_page: int = 30,
        max_pages: Optional[int] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Paginates through GitHub collection endpoints utilizing hypermedia Link headers.
        Yields individual collection items seamlessly.
        """
        current_url: Optional[str] = endpoint
        request_params = dict(params or {})
        request_params["per_page"] = min(per_page, 100)
        pages_retrieved = 0

        while current_url:
            status, data, headers = self.request(
                method="GET",
                endpoint_or_url=current_url,
                params=request_params if pages_retrieved == 0 else None,
            )
            pages_retrieved += 1

            if isinstance(data, list):
                for item in data:
                    yield item
            elif isinstance(data, dict):
                # Some endpoints return {"items": [...]} (e.g. search)
                items = data.get("items", [])
                for item in items:
                    yield item
            else:
                break

            if max_pages and pages_retrieved >= max_pages:
                break

            # Extract rel="next" from Link header
            link_header = headers.get("link")
            parsed_links = GitHubPaginationHelper.parse_link_header(link_header)
            current_url = parsed_links.get("next")

    # --------------------------------------------------------------------------
    # API OPERATIONS: AUTHENTICATION & RATE LIMIT
    # --------------------------------------------------------------------------
    def get_rate_limit(self) -> Dict[str, Any]:
        """Fetches the official rate limit breakdown from GET /rate_limit."""
        _, data, _ = self.request("GET", "rate_limit", use_cache=False)
        return data if isinstance(data, dict) else {}

    def get_authenticated_user(self) -> Dict[str, Any]:
        """Fetches the authenticated user profile from GET /user."""
        _, data, _ = self.request("GET", "user")
        return data if isinstance(data, dict) else {}

    # --------------------------------------------------------------------------
    # API OPERATIONS: REPOSITORIES
    # --------------------------------------------------------------------------
    def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = False,
        org: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new GitHub repository for the authenticated user or an organization.
        Endpoint: POST /user/repos or POST /orgs/{org}/repos
        """
        endpoint = f"orgs/{org}/repos" if org else "user/repos"
        payload = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        }
        _, data, _ = self.request("POST", endpoint, json_data=payload)
        logger.info("Created GitHub repository '%s' (private=%s)", name, private)
        return data if isinstance(data, dict) else {}

    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetches repository metadata from GET /repos/{owner}/{repo}."""
        _, data, _ = self.request("GET", f"repos/{owner}/{repo}")
        return data if isinstance(data, dict) else {}

    def list_user_repositories(
        self,
        visibility: str = "all",
        sort: str = "updated",
        per_page: int = 30,
        max_pages: Optional[int] = 3,
    ) -> List[Dict[str, Any]]:
        """Lists repositories for the authenticated user."""
        params = {"visibility": visibility, "sort": sort}
        return list(self.paginate("user/repos", params=params, per_page=per_page, max_pages=max_pages))

    # --------------------------------------------------------------------------
    # API OPERATIONS: PULL REQUESTS & COMMENTS
    # --------------------------------------------------------------------------
    def get_pull_request(self, owner: str, repo: str, pull_number: int) -> Dict[str, Any]:
        """Fetches pull request details from GET /repos/{owner}/{repo}/pulls/{pull_number}."""
        _, data, _ = self.request("GET", f"repos/{owner}/{repo}/pulls/{pull_number}")
        return data if isinstance(data, dict) else {}

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> Iterator[Dict[str, Any]]:
        """Lists pull requests for a repository."""
        return self.paginate(f"repos/{owner}/{repo}/pulls", params={"state": state}, per_page=per_page)

    def list_issue_comments(
        self,
        owner: str,
        repo: str,
        issue_number: int,
    ) -> Iterator[Dict[str, Any]]:
        """Lists comments on an issue or PR."""
        return self.paginate(f"repos/{owner}/{repo}/issues/{issue_number}/comments")

    def create_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> Dict[str, Any]:
        """Posts a new comment on an issue or PR."""
        endpoint = f"repos/{owner}/{repo}/issues/{issue_number}/comments"
        _, data, _ = self.request("POST", endpoint, json_data={"body": body})
        return data if isinstance(data, dict) else {}

    def update_issue_comment(
        self,
        owner: str,
        repo: str,
        comment_id: int,
        body: str,
    ) -> Dict[str, Any]:
        """Updates an existing issue/PR comment."""
        endpoint = f"repos/{owner}/{repo}/issues/comments/{comment_id}"
        _, data, _ = self.request("PATCH", endpoint, json_data={"body": body})
        return data if isinstance(data, dict) else {}

    def post_or_update_pr_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
        identifier_marker: str = "<!-- flowmind-pr-audit-scorecard -->",
    ) -> Dict[str, Any]:
        """
        Posts or updates an existing FlowMind audit comment on a PR.
        Avoids comment spam by searching for the identifier_marker in existing comments
        and updating the comment in place if found.
        """
        full_body = f"{identifier_marker}\n{body}"

        # Search for existing comment with identifier_marker
        try:
            for comment in self.list_issue_comments(owner, repo, issue_number):
                comment_text = comment.get("body", "")
                if identifier_marker in comment_text:
                    comment_id = comment["id"]
                    logger.info("Found existing FlowMind comment #%d on %s#%d. Updating in place.", comment_id, f"{owner}/{repo}", issue_number)
                    return self.update_issue_comment(owner, repo, comment_id, full_body)
        except Exception as e:
            logger.warning("Could not list comments to check for updates: %s. Proceeding to post new.", e)

        # No existing comment found; create new
        return self.create_issue_comment(owner, repo, issue_number, full_body)

    # --------------------------------------------------------------------------
    # API OPERATIONS: COMMIT STATUSES & CHECK RUNS (CI Integration Guide)
    # --------------------------------------------------------------------------
    def create_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str,
        state: str,
        target_url: str = "",
        description: str = "",
        context: str = "flowmind/invariants",
    ) -> Dict[str, Any]:
        """
        Posts a Commit Status for CI/CD gating:
          Endpoint: POST /repos/{owner}/{repo}/statuses/{sha}
          States: 'pending', 'success', 'failure', 'error'
        """
        endpoint = f"repos/{owner}/{repo}/statuses/{sha}"
        payload = {
            "state": state,
            "target_url": target_url,
            "description": description[:140],  # GitHub status description cap
            "context": context,
        }
        _, data, _ = self.request("POST", endpoint, json_data=payload)
        logger.info("Posted Commit Status '%s' on %s@%s (%s)", state, f"{owner}/{repo}", sha[:7], context)
        return data if isinstance(data, dict) else {}

    def create_check_run(
        self,
        owner: str,
        repo: str,
        name: str,
        head_sha: str,
        status: str = "completed",
        conclusion: str = "success",
        title: str = "FlowMind Invariant Evaluation",
        summary: str = "",
        text: str = "",
    ) -> Dict[str, Any]:
        """
        Creates a GitHub Check Run with structured output:
          Endpoint: POST /repos/{owner}/{repo}/check-runs
        """
        endpoint = f"repos/{owner}/{repo}/check-runs"
        payload = {
            "name": name,
            "head_sha": head_sha,
            "status": status,
            "conclusion": conclusion if status == "completed" else None,
            "output": {
                "title": title,
                "summary": summary,
                "text": text,
            },
        }
        _, data, _ = self.request("POST", endpoint, json_data=payload)
        logger.info("Created Check Run '%s' on %s@%s (conclusion=%s)", name, f"{owner}/{repo}", head_sha[:7], conclusion)
        return data if isinstance(data, dict) else {}

    # --------------------------------------------------------------------------
    # API OPERATIONS: WORKFLOW DISPATCH (Actions Guide)
    # --------------------------------------------------------------------------
    def dispatch_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Triggers a GitHub Actions workflow dispatch event:
          Endpoint: POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches
        """
        endpoint = f"repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"
        payload: Dict[str, Any] = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs

        status, _, _ = self.request("POST", endpoint, json_data=payload)
        return status in (204, 201, 200)


# ==============================================================================
# 7. BACKWARDS-COMPATIBLE PR COMMENTER & CONVENIENCE FUNCTIONS
# ==============================================================================

class GitHubPRCommenter:
    """
    Formats and posts FlowMind Architectural Invariant Audit scorecards
    directly to GitHub Pull Requests via the GitHub REST API.
    Maintains 100% backward compatibility with existing tests and scripts.
    """

    @classmethod
    def detect_github_context(cls) -> Tuple[Optional[str], Optional[int]]:
        """
        Extracts repository ('owner/repo') and PR number from GitHub Actions environment.
        """
        repo = os.getenv("GITHUB_REPOSITORY")
        pr_number: Optional[int] = None

        ref = os.getenv("GITHUB_REF", "")
        if ref.startswith("refs/pull/"):
            parts = ref.split("/")
            if len(parts) >= 3 and parts[2].isdigit():
                pr_number = int(parts[2])

        event_path = os.getenv("GITHUB_EVENT_PATH")
        if event_path and Path(event_path).exists():
            try:
                event_data = json.loads(Path(event_path).read_text(encoding="utf-8"))
                if "pull_request" in event_data:
                    pr_number = event_data["pull_request"].get("number")
                elif "issue" in event_data:
                    pr_number = event_data["issue"].get("number")
            except Exception as e:
                logger.warning("Failed to parse GITHUB_EVENT_PATH: %s", e)

        return repo, pr_number

    @classmethod
    def build_pr_markdown_comment(
        cls,
        result: PipelineResult,
        repo_name: str = "Repository",
    ) -> str:
        """
        Constructs a GitHub-flavored Markdown comment with verification gate results,
        system health scorecard, and an embedded Mermaid architecture flow diagram.
        """
        verdict = result.deliberation.consensus_verdict
        arch = result.archaeology
        hubs = arch.architectural_signals.get("architectural_hubs", [])
        cycles = arch.detected_cycles
        task_spec = result.task_spec
        exec_report = result.execution_report
        state_bus = result.state_bus

        gates_total = len(task_spec.verification_gates)
        gates_passed = sum(1 for g in (exec_report.gate_results if exec_report else []) if g.passed)
        all_passed = (gates_passed == gates_total) if gates_total > 0 else True

        status_banner = (
            "> 🟢 **FLOWMIND STATUS: INVARIANTS PRESERVED**\n"
            "> All architectural invariant gates passed. No layer boundary breaches or cyclic regressions detected."
            if all_passed
            else
            "> 🔴 **FLOWMIND ALERT: INVARIANT VIOLATION DETECTED**\n"
            "> One or more architectural verification gates failed. Manual review required."
        )

        gate_rows = []
        if exec_report and exec_report.gate_results:
            for g in exec_report.gate_results:
                badge = "✅ PASS" if g.passed else "❌ FAIL"
                gate_rows.append(f"| `{g.gate_id}` | **{g.gate_name}** | {badge} | {g.details} |")
        else:
            gate_rows.append("| - | *Baseline Invariant Check* | ℹ️ NOT RUN | Execution skipped |")
        gates_table_md = "\n".join(gate_rows)

        inv_rows = []
        for inv in task_spec.architectural_invariants:
            inv_rows.append(f"| `{inv.id}` | `{inv.invariant_type.value}` | `{inv.enforcement_scope}` | {inv.rule} |")
        inv_table_md = "\n".join(inv_rows)

        mermaid_lines = ["```mermaid", "graph TD"]
        modules = list(arch.modules.keys())[:15]
        for m in modules:
            safe_id = m.replace(".", "_").replace("-", "_")
            if m in hubs:
                mermaid_lines.append(f"    {safe_id}[\"⚡ {m} (Hub)\"]")
            elif any(m in c for c in cycles):
                mermaid_lines.append(f"    {safe_id}[\"⚠️ {m} (Cycle)\"]")
            else:
                mermaid_lines.append(f"    {safe_id}[\"{m}\"]")

        for edge in arch.call_graph_edges[:20]:
            src_id = edge.source.replace(".", "_").replace("-", "_").replace(":", "_")
            tgt_id = edge.target.replace(".", "_").replace("-", "_").replace(":", "_")
            mermaid_lines.append(f"    {src_id} --> {tgt_id}")
        mermaid_lines.append("```")
        mermaid_md = "\n".join(mermaid_lines)

        milestone_items = []
        if state_bus and state_bus.verified_milestones:
            for ms in state_bus.verified_milestones:
                milestone_items.append(f"- **Step {ms.step}**: {ms.summary} (`{ms.commit_or_snapshot_id[:8]}`)")
        milestones_md = "\n".join(milestone_items) if milestone_items else "_No state mutations applied (audit mode)._"

        comment = f"""## 🧠 FlowMind Architectural Audit & Invariant Scorecard

{status_banner}

### 📊 Executive Architecture Metrics
| Metric | Value | Status |
| :--- | :--- | :--- |
| **Consensus Verdict** | `{verdict.title.split(':')[0]}` | 🏛️ Unanimous Specialist Council |
| **Execution Tier** | `{result.execution_tier or "TIER_3"}` | ⚙️ Adaptive A2A Bench Rotation |
| **Verification Gates** | `{gates_passed}/{gates_total} Passed` | {"🟢 100% Compliant" if all_passed else "🔴 Action Required"} |
| **Architectural Hubs** | `{len(hubs)} identified` | {"⚡ " + ", ".join(hubs) if hubs else "Decoupled"} |
| **Dependency Cycles** | `{len(cycles)} loops` | {"🟢 Strict Acyclic Graph" if not cycles else "⚠️ Cycles Detected"} |
| **Kleppmann Fencing Token** | `{state_bus.fencing_token if state_bus else 1}` | 🔒 Monotonic Lock Enforced |

---

### 🛡️ Verification Gate Evaluations
| Gate ID | Gate Name | Result | Details |
| :--- | :--- | :---: | :--- |
{gates_table_md}

---

### 📜 Protected Architectural Invariants
| ID | Invariant Type | Scope | Rule |
| :--- | :--- | :--- | :--- |
{inv_table_md}

---

### 🗺️ Component Flow & Topology Map
{mermaid_md}

---

### ⏱️ Verified Milestones & State Bus
{milestones_md}

{f'''---

### 🏆 Model Evolution & Contributor Credit
> **Credited Developer / Owner:** **{result.brain.evolution_stages[-1].credited_owner}** (`{result.brain.evolution_stages[-1].credited_repo}`)  
> **Capability Leap Unlocked:** {result.brain.evolution_stages[-1].capability_unlocked}  
> _{result.brain.evolution_stages[-1].attribution_statement}_
''' if result.brain and result.brain.evolution_stages else ''}

---

> 💡 **Full Interactive Report:** View the comprehensive HTML dashboard in the **Artifacts** tab of this GitHub Actions run (`flowmind-report.html`).
> *Automated review generated by [FlowMind Multi-Agent Architecture Engine](https://github.com/)*.
"""
        return comment

    @classmethod
    def post_comment(
        cls,
        comment_body: str,
        repo: str,
        pr_number: int,
        token: str,
    ) -> bool:
        """
        Posts the markdown comment to GitHub Pull Request / Issue.
        Uses GitHubRestClient with automated retry, error translation, and rate limit handling.
        """
        client = GitHubRestClient(token=token, mutative_delay=0.0)
        parts = repo.split("/", 1)
        if len(parts) != 2:
            logger.error("Invalid repo format: '%s'. Expected 'owner/repo'.", repo)
            return False

        owner, repo_name = parts
        try:
            client.create_issue_comment(
                owner=owner,
                repo=repo_name,
                issue_number=pr_number,
                body=comment_body,
            )
            return True
        except Exception as e:
            logger.error("Failed to post PR comment to %s#%d: %s", repo, pr_number, e)
            return False


def post_pr_comment(
    result: PipelineResult,
    token: Optional[str] = None,
    repo: Optional[str] = None,
    pr_number: Optional[int] = None,
    repo_name: str = "Repository",
) -> bool:
    """Convenience helper to format and post PR comment."""
    auth_token = token or os.getenv("GITHUB_TOKEN")
    detected_repo, detected_pr = GitHubPRCommenter.detect_github_context()

    target_repo = repo or detected_repo
    target_pr = pr_number or detected_pr

    if not auth_token:
        logger.warning("No GITHUB_TOKEN available; skipping PR comment posting.")
        return False
    if not target_repo or not target_pr:
        logger.warning("GitHub repository or PR number could not be determined; skipping PR comment posting.")
        return False

    markdown_comment = GitHubPRCommenter.build_pr_markdown_comment(result, repo_name=repo_name)
    return GitHubPRCommenter.post_comment(
        comment_body=markdown_comment,
        repo=target_repo,
        pr_number=target_pr,
        token=auth_token,
    )
