from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from fastapi.testclient import TestClient
from repo_investigator.server import app, store, _execute_pipeline_task, InvestigateRequest

client = TestClient(app)

def test_server_root_and_health():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "1.0.0"
    assert "service" in data
    assert "dashboard_url" in data

    # Test Client-Facing SPA Dashboard endpoint
    resp_dash = client.get("/dashboard")
    assert resp_dash.status_code == 200
    assert "FLOWMIND" in resp_dash.text
    assert "CLIENT DASHBOARD" in resp_dash.text

    # Test root text/html content negotiation
    resp_html = client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert resp_html.status_code == 200
    assert "FLOWMIND" in resp_html.text

    resp_health = client.get("/v1/health")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "HEALTHY"

def test_workflow_lifecycle_api():
    sample_repo = str(REPO_ROOT / "sample_repo")
    payload = {
        "repo_path": sample_repo,
        "execute_code": True,
        "dry_run": True,
        "tier": "1",
    }

    # 1. Start investigation
    resp = client.post("/v1/investigate", json=payload)
    assert resp.status_code == 200
    w_data = resp.json()
    w_id = w_data["workflow_id"]
    assert w_id is not None
    assert w_data["status"] in ("PENDING", "RUNNING", "COMPLETED")

    # 2. Check workflow status
    status_resp = client.get(f"/v1/workflows/{w_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["workflow_id"] == w_id

    # 3. Synchronously execute pipeline task for deterministic completion verification
    req = InvestigateRequest(
        repo_path=sample_repo,
        execute_code=True,
        dry_run=True,
        tier="1",
    )
    _execute_pipeline_task(w_id, req)

    # 4. Check completed status
    completed_resp = client.get(f"/v1/workflows/{w_id}/status")
    assert completed_resp.status_code == 200
    assert completed_resp.json()["status"] == "COMPLETED"

    # 5. Check state-bus endpoint
    sb_resp = client.get(f"/v1/workflows/{w_id}/state-bus")
    assert sb_resp.status_code == 200
    assert "fencing_token" in sb_resp.json()

    # 6. Check JSON report endpoint
    report_resp = client.get(f"/v1/workflows/{w_id}/report")
    assert report_resp.status_code == 200
    assert "archaeology" in report_resp.json()

    # 7. Check HTML report endpoint
    html_resp = client.get(f"/v1/workflows/{w_id}/report/html")
    assert html_resp.status_code == 200
    assert "<!DOCTYPE html>" in html_resp.text
    assert "FlowMind Executive Architecture Audit" in html_resp.text

    # 8. Check Retrospective endpoint
    retro_resp = client.get(f"/v1/workflows/{w_id}/retrospective")
    assert retro_resp.status_code == 200
    assert "executive_summary" in retro_resp.json()

    # 9. Check Retrospective Markdown endpoint
    retro_md_resp = client.get(f"/v1/workflows/{w_id}/retrospective/markdown")
    assert retro_md_resp.status_code == 200
    assert "What We Learned" in retro_md_resp.text

def test_coach_endpoints():
    sample_file = str(REPO_ROOT / "sample_repo" / "rewards_processor.py")

    # Explain
    exp_resp = client.post("/v1/coach/explain", json={"file_path": sample_file})
    assert exp_resp.status_code == 200
    assert "rewards_processor" in exp_resp.json()["file_path"]

    # Debug
    dbg_resp = client.post("/v1/coach/debug", json={"error_text": "KeyError: 'user_id'"})
    assert dbg_resp.status_code == 200
    assert dbg_resp.json()["error_type"] == "KeyError"

    # Guide
    guide_resp = client.post("/v1/coach/guide", json={"feature_description": "Add caching layer"})
    assert guide_resp.status_code == 200
    assert "Add caching layer" in guide_resp.json()["goal"]

def test_workflow_not_found():
    resp = client.get("/v1/workflows/nonexistent_id/status")
    assert resp.status_code == 404

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

