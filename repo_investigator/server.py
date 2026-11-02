from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from repo_investigator.orchestrator import FlowMindOrchestrator, PipelineResult
from repo_investigator.bench_rotation.models import CanonicalStateBus
from repo_investigator.reports.html_reporter import HTMLReportGenerator
from repo_investigator.reports.dashboard import render_dashboard_html
from repo_investigator.config import get_settings
from repo_investigator.coach import (
    DeveloperAid,
    SessionRetrospectiveBuilder,
    CodeExplanation,
    DebugDiagnosis,
    ImplementationGuide,
    WhatWeLearnedReport,
)
from repo_investigator.brain import CognitiveBrain, BrainManager, ModelEvolutionStage
from repo_investigator.integrations.github import GitHubWebhookVerifier, GitHubRestClient

logger = logging.getLogger(__name__)

class CoachExplainRequest(BaseModel):
    file_path: str
    symbol: Optional[str] = None

class CoachDebugRequest(BaseModel):
    error_text: str

class CoachGuideRequest(BaseModel):
    feature_description: str

class InvestigateRequest(BaseModel):
    repo_path: str = Field(..., description="Local path or remote Git URL (https://..., git@...)")
    execute_code: bool = Field(True, description="Whether to execute the reasoning coding agent")
    dry_run: bool = Field(False, description="Whether to perform dry run without writing files")
    tier: str = Field("auto", description="Execution tier: auto, 1, 2, or 3")
    enable_bench_rotation: bool = Field(True, description="Enable adaptive A2A bench rotation")
    remote_depth: int = Field(50, description="Clone depth for remote git repos")
    remote_branch: Optional[str] = Field(None, description="Branch to checkout for remote git repos")
    repo_owner: Optional[str] = Field(None, description="Repository author/owner to accredit for learned brain wisdom")
    brain_path: Optional[str] = Field(None, description="Custom path to brain.json")

class WorkflowRecord(BaseModel):
    workflow_id: str
    status: str  # PENDING, RUNNING, COMPLETED, FAILED
    repo_path: str
    tier: Optional[str] = None
    error: Optional[str] = None
    active_player: Optional[str] = "starter_agent"
    stint_number: Optional[int] = 1
    fencing_token: Optional[int] = 1
    milestones_count: int = 0
    result: Optional[Dict[str, Any]] = None

class WorkflowStore:
    def __init__(self, max_history: int = 500):
        self._lock = threading.Lock()
        self._max_history = max_history
        self._workflows: Dict[str, WorkflowRecord] = {}
        self._results: Dict[str, PipelineResult] = {}
        self._event_queues: Dict[str, List[asyncio.Queue]] = {}

    def create(self, repo_path: str) -> str:
        w_id = str(uuid.uuid4())[:8]
        with self._lock:
            # Memory safety: Evict oldest workflow record if capacity exceeded
            if len(self._workflows) >= self._max_history:
                oldest_key = next(iter(self._workflows))
                self._workflows.pop(oldest_key, None)
                self._results.pop(oldest_key, None)
                self._event_queues.pop(oldest_key, None)

            self._workflows[w_id] = WorkflowRecord(
                workflow_id=w_id,
                status="PENDING",
                repo_path=repo_path,
            )
        return w_id

    def update_status(self, w_id: str, status: str, tier: Optional[str] = None, error: Optional[str] = None):
        with self._lock:
            if w_id in self._workflows:
                rec = self._workflows[w_id]
                rec.status = status
                if tier:
                    rec.tier = tier
                if error:
                    rec.error = error

    def store_result(self, w_id: str, result: PipelineResult):
        with self._lock:
            self._results[w_id] = result
            if w_id in self._workflows:
                rec = self._workflows[w_id]
                rec.status = "COMPLETED"
                rec.tier = result.execution_tier
                if result.state_bus:
                    rec.active_player = result.state_bus.active_player
                    rec.stint_number = result.state_bus.stint_number
                    rec.fencing_token = result.state_bus.fencing_token
                    rec.milestones_count = len(result.state_bus.verified_milestones)

    def get(self, w_id: str) -> Optional[WorkflowRecord]:
        with self._lock:
            return self._workflows.get(w_id)

    def get_result(self, w_id: str) -> Optional[PipelineResult]:
        with self._lock:
            return self._results.get(w_id)

    def list_all(self) -> List[WorkflowRecord]:
        with self._lock:
            return list(self._workflows.values())

store = WorkflowStore()

app = FastAPI(
    title="FlowMind Autonomous Multi-Agent API",
    version="1.0.0",
    description="HTTP & Event Streaming REST API for Repository Flow Archaeology, Deliberation Council, and A2A Bench Rotation",
)

cors_env = os.getenv("FLOWMIND_CORS_ORIGINS", "")
allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()] if cors_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _execute_pipeline_task(workflow_id: str, req: InvestigateRequest):
    store.update_status(workflow_id, "RUNNING")
    try:
        orchestrator = FlowMindOrchestrator()
        result = orchestrator.run(
            repo_path=req.repo_path,
            execute_code=req.execute_code,
            dry_run=req.dry_run,
            tier=None if req.tier == "auto" else req.tier,
            enable_bench_rotation=req.enable_bench_rotation,
            remote_depth=req.remote_depth,
            remote_branch=req.remote_branch,
            repo_owner=req.repo_owner,
            brain_path=Path(req.brain_path) if req.brain_path else None,
        )
        store.store_result(workflow_id, result)
    except Exception as e:
        logger.exception("Pipeline failed for %s", workflow_id)
        store.update_status(workflow_id, "FAILED", error=str(e))

@app.get("/")
def get_root(request: Request):
    accept_header = request.headers.get("accept", "")
    if accept_header.startswith("text/html"):
        return HTMLResponse(content=render_dashboard_html(), media_type="text/html")

    settings = get_settings()
    return {
        "service": "FlowMind Autonomous Engine API",
        "version": "1.0.0",
        "model_provider": settings.default_model_provider.value,
        "state_bus_backend": settings.state_bus_backend.value,
        "docs_url": "/docs",
        "dashboard_url": "/dashboard",
    }

@app.get("/dashboard", response_class=HTMLResponse)
def get_client_dashboard():
    return HTMLResponse(content=render_dashboard_html(), media_type="text/html")

@app.get("/v1/health")
def healthcheck():
    return {"status": "HEALTHY", "active_workflows": len(store.list_all())}

@app.post("/v1/investigate", response_model=WorkflowRecord)
def start_investigation(req: InvestigateRequest, background_tasks: BackgroundTasks):
    w_id = store.create(req.repo_path)
    background_tasks.add_task(_execute_pipeline_task, w_id, req)
    rec = store.get(w_id)
    if not rec:
        raise HTTPException(status_code=500, detail="Failed to initialize workflow")
    return rec

@app.get("/v1/workflows", response_model=List[WorkflowRecord])
def list_workflows():
    return store.list_all()

@app.get("/v1/workflows/{workflow_id}/status", response_model=WorkflowRecord)
def get_workflow_status(workflow_id: str):
    rec = store.get(workflow_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Workflow ID not found")
    return rec

@app.get("/v1/workflows/{workflow_id}/state-bus")
def get_workflow_state_bus(workflow_id: str):
    res = store.get_result(workflow_id)
    if not res:
        rec = store.get(workflow_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Workflow ID not found")
        return {"status": rec.status, "message": "State bus pending completion"}
    if not res.state_bus:
        return {"status": "NO_STATE_BUS"}
    return res.state_bus.model_dump()

@app.get("/v1/workflows/{workflow_id}/report")
def get_workflow_report(workflow_id: str):
    res = store.get_result(workflow_id)
    if not res:
        raise HTTPException(status_code=404, detail="Report not ready or workflow not found")
    return res.model_dump()

@app.get("/v1/workflows/{workflow_id}/report/html", response_class=HTMLResponse)
def get_workflow_html_report(workflow_id: str):
    res = store.get_result(workflow_id)
    if not res:
        raise HTTPException(status_code=404, detail="Report not ready or workflow not found")
    rec = store.get(workflow_id)
    repo_name = Path(rec.repo_path).name if rec else "Repository"
    return HTMLReportGenerator.generate_html(res, repo_name=repo_name)

@app.get("/v1/workflows/{workflow_id}/stream")
async def stream_workflow_events(workflow_id: str):
    rec = store.get(workflow_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Workflow not found")

    async def event_generator():
        while True:
            cur = store.get(workflow_id)
            if not cur:
                break
            payload = {
                "workflow_id": cur.workflow_id,
                "status": cur.status,
                "tier": cur.tier,
                "active_player": cur.active_player,
                "fencing_token": cur.fencing_token,
                "milestones_count": cur.milestones_count,
            }
            yield f"data: {json.dumps(payload)}\n\n"
            if cur.status in ("COMPLETED", "FAILED"):
                break
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/v1/coach/explain", response_model=CodeExplanation)
def coach_explain_code(req: CoachExplainRequest):
    aid = DeveloperAid()
    try:
        return aid.explain_file(req.file_path, symbol=req.symbol)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))

@app.post("/v1/coach/debug", response_model=DebugDiagnosis)
def coach_debug_error(req: CoachDebugRequest):
    aid = DeveloperAid()
    return aid.diagnose_error(req.error_text)

@app.post("/v1/coach/guide", response_model=ImplementationGuide)
def coach_guide_feature(req: CoachGuideRequest):
    aid = DeveloperAid()
    return aid.guide_feature(req.feature_description)

@app.get("/v1/workflows/{workflow_id}/retrospective", response_model=WhatWeLearnedReport)
def get_workflow_retrospective(workflow_id: str):
    res = store.get_result(workflow_id)
    if not res:
        raise HTTPException(status_code=404, detail="Workflow retrospective not ready or workflow not found")
    rec = store.get(workflow_id)
    repo_name = Path(rec.repo_path).name if rec else "Repository"
    return SessionRetrospectiveBuilder.build(res, repo_name=repo_name)

@app.get("/v1/workflows/{workflow_id}/retrospective/markdown")
def get_workflow_retrospective_markdown(workflow_id: str):
    res = store.get_result(workflow_id)
    if not res:
        raise HTTPException(status_code=404, detail="Workflow retrospective not ready or workflow not found")
    rec = store.get(workflow_id)
    repo_name = Path(rec.repo_path).name if rec else "Repository"
    report = SessionRetrospectiveBuilder.build(res, repo_name=repo_name)
    md = SessionRetrospectiveBuilder.format_markdown(report)
    return HTMLResponse(content=f"<pre style='font-family: monospace; white-space: pre-wrap;'>{md}</pre>", media_type="text/html")

@app.get("/v1/brain", response_model=CognitiveBrain)
def get_cognitive_brain(brain_path: Optional[str] = Query(None, description="Custom path to brain.json")):
    bp = Path(brain_path) if brain_path else None
    return BrainManager.load_brain(bp)

@app.get("/v1/brain/evolution", response_model=List[ModelEvolutionStage])
def get_cognitive_brain_evolution(brain_path: Optional[str] = Query(None, description="Custom path to brain.json")):
    bp = Path(brain_path) if brain_path else None
    brain = BrainManager.load_brain(bp)
    return brain.evolution_stages

@app.post("/v1/webhooks/github")
async def github_webhook_endpoint(request: Request, background_tasks: BackgroundTasks):
    """
    Receives and processes GitHub webhook events (e.g. pull_request, push, ping).
    Enforces HMAC-SHA256 signature verification (X-Hub-Signature-256) per GitHub Docs Guides.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    event_type = request.headers.get("X-GitHub-Event", "ping")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    payload_bytes = await request.body()

    if secret:
        if not signature or not GitHubWebhookVerifier.verify_signature(payload_bytes, signature, secret):
            logger.warning("GitHub webhook signature verification failed for delivery %s", delivery_id)
            raise HTTPException(status_code=401, detail="Invalid X-Hub-Signature-256")

    try:
        payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON payload")

    action = payload.get("action")
    logger.info("Received GitHub webhook event='%s' action='%s' delivery='%s'", event_type, action, delivery_id)

    if event_type == "ping":
        return {"status": "ok", "message": "Pong! FlowMind webhook is configured correctly."}

    # If it's a pull request opened/synchronized event, trigger background audit
    if event_type == "pull_request" and action in ("opened", "synchronize", "reopened"):
        pr_info = payload.get("pull_request", {})
        repo_info = payload.get("repository", {})
        clone_url = repo_info.get("clone_url")
        full_name = repo_info.get("full_name")
        pr_number = pr_info.get("number")
        head_sha = pr_info.get("head", {}).get("sha")

        if clone_url:
            req = InvestigateRequest(
                repo_path=clone_url,
                execute_code=True,
                dry_run=True,
                tier="auto",
                enable_bench_rotation=True,
                remote_depth=50,
            )
            w_id = store.create(req.repo_path)
            background_tasks.add_task(_execute_pipeline_task, w_id, req)
            return {
                "status": "accepted",
                "workflow_id": w_id,
                "event": event_type,
                "action": action,
                "repository": full_name,
                "pull_request": pr_number,
                "head_sha": head_sha,
            }

    return {"status": "received", "event": event_type, "action": action}

@app.get("/v1/github/rate-limit")
def get_github_rate_limits():
    """Returns the authenticated GitHub user's current rate limit quotas per GitHub REST Guides."""
    client = GitHubRestClient()
    try:
        limits = client.get_rate_limit()
        user = client.get_authenticated_user() if client.token else None
        return {
            "api_version": client.api_version,
            "authenticated_user": user.get("login") if user else None,
            "rate_limits": limits.get("resources", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch GitHub rate limits: {e}")

def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    import uvicorn
    uvicorn.run("repo_investigator.server:app", host=host, port=port, reload=reload)

if __name__ == "__main__":
    run_server()

