from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from repo_investigator.orchestrator import PipelineResult

logger = logging.getLogger(__name__)

class GitHubPRCommenter:
    """
    Formats and posts FlowMind Architectural Invariant Audit scorecards
    directly to GitHub Pull Requests via the GitHub REST API.
    """

    @classmethod
    def detect_github_context(cls) -> Tuple[Optional[str], Optional[int]]:
        """
        Extracts the repository name ('owner/repo') and PR number from GitHub Actions environment.
        """
        repo = os.getenv("GITHUB_REPOSITORY")
        pr_number: Optional[int] = None

        # Check PR ref if available, e.g., refs/pull/123/merge
        ref = os.getenv("GITHUB_REF", "")
        if ref.startswith("refs/pull/"):
            parts = ref.split("/")
            if len(parts) >= 3 and parts[2].isdigit():
                pr_number = int(parts[2])

        # Check GitHub event JSON payload if available
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

        # Evaluate overall pass/fail status
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

        # Build Gate Table
        gate_rows = []
        if exec_report and exec_report.gate_results:
            for g in exec_report.gate_results:
                badge = "✅ PASS" if g.passed else "❌ FAIL"
                gate_rows.append(f"| `{g.gate_id}` | **{g.gate_name}** | {badge} | {g.details} |")
        else:
            gate_rows.append("| - | *Baseline Invariant Check* | ℹ️ NOT RUN | Execution skipped |")
        gates_table_md = "\n".join(gate_rows)

        # Build Invariants Table
        inv_rows = []
        for inv in task_spec.architectural_invariants:
            inv_rows.append(f"| `{inv.id}` | `{inv.invariant_type.value}` | `{inv.enforcement_scope}` | {inv.rule} |")
        inv_table_md = "\n".join(inv_rows)

        # Build Mermaid graph
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

        # Milestone list
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
        """
        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "FlowMind-Audit-Bot",
            "Content-Type": "application/json",
        }
        payload = json.dumps({"body": comment_body}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status in (200, 201):
                    logger.info("Successfully posted FlowMind audit comment to %s#%s", repo, pr_number)
                    return True
                logger.warning("GitHub API returned non-201 status: %s", resp.status)
                return False
        except urllib.error.HTTPError as he:
            logger.error("Failed to post PR comment (HTTP %s): %s", he.code, he.read().decode("utf-8", errors="replace"))
            return False
        except Exception as e:
            logger.error("Failed to post PR comment: %s", e)
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

