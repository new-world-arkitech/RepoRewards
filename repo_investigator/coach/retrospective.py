from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from repo_investigator.orchestrator import PipelineResult
from repo_investigator.models.explanations import get_plain_english_insight
from repo_investigator.brain.models import ModelEvolutionStage

console = Console(highlight=False)

class WhatWeLearnedReport(BaseModel):
    session_id: str
    repo_name: str
    executive_summary: str
    architectural_discoveries: List[Dict[str, str]] = Field(default_factory=list)
    developer_intent_uncovered: str
    invariants_established: List[str] = Field(default_factory=list)
    approaches_ruled_out: List[str] = Field(default_factory=list)
    verified_milestones_achieved: List[str] = Field(default_factory=list)
    key_takeaways_for_developers: List[str] = Field(default_factory=list)
    recommended_next_steps: List[str] = Field(default_factory=list)
    model_evolution_credit: Optional[ModelEvolutionStage] = Field(None, description="Attributed capability evolution credited to repo author")

class SessionRetrospectiveBuilder:
    """
    Builds the 'What We Learned' session retrospective report summarizing
    architectural discoveries, developer mental models, hard-won invariants,
    and lessons learned for the entire engineering team.
    """

    @classmethod
    def build(cls, result: PipelineResult, repo_name: str = "Repository") -> WhatWeLearnedReport:
        arch = result.archaeology
        verdict = result.deliberation.consensus_verdict
        task_spec = result.task_spec
        state_bus = result.state_bus

        # 1. Discoveries & Insights
        discoveries: List[Dict[str, str]] = []
        for finding in result.findings:
            for ins in finding.insights[:2]:
                plain = get_plain_english_insight(ins.category)
                discoveries.append({
                    "topic": plain["title"],
                    "observation": ins.observation,
                    "why_it_matters": plain["why_it_matters"],
                    "lesson": plain["how_to_fix"],
                })

        # 2. Developer Intent Uncovered
        intent_summary = verdict.developer_mindset_addressed or (
            "Developers initially prioritized delivery speed and direct execution paths. Over time, "
            "as dependencies grew, shared modules absorbed increasing cognitive churn without decoupling layers."
        )

        # 3. Invariants Established
        invariants = [
            f"[{inv.id}] {inv.rule} (Scope: {inv.enforcement_scope})"
            for inv in task_spec.architectural_invariants
        ]

        # 4. Approaches Ruled Out (Dead Ends)
        ruled_out = list(verdict.rejected_alternatives)
        if state_bus and state_bus.dead_ends_log:
            for de in state_bus.dead_ends_log:
                ruled_out.append(f"Stint #{de.stint}: Attempted '{de.attempted_play}' -> Ruled out: {de.rule_out}")
        if not ruled_out:
            ruled_out.append("Uncoordinated monolithic rewrites without backward-compatible adapter interfaces.")

        # 5. Verified Milestones Achieved
        milestones = []
        if state_bus and state_bus.verified_milestones:
            for ms in state_bus.verified_milestones:
                milestones.append(f"Step {ms.step}: {ms.summary}")
        else:
            milestones.append("Completed full architectural archaeology scan, council deliberation, and invariant compilation.")

        # 6. Key Takeaways for Developers
        takeaways = [
            "Decouple domain business logic from database, network, and storage dependencies.",
            "Keep the component import graph acyclic—circular dependencies multiply bug surface areas.",
            "Always wrap shared hot-churn modules behind stable, backward-compatible protocols.",
            "Preserve verified invariants with automated regression gates before merging code.",
        ]

        # 7. Recommended Next Steps
        next_steps = [
            "Review the generated client-facing HTML report for full visual flow topologies.",
            "Run automated invariant verification test suites in CI on every incoming pull request.",
            "Refactor high-centrality hub modules into focused single-responsibility services.",
        ]

        summary = (
            f"During this session on '{repo_name}', FlowMind identified {len(arch.modules)} modules, "
            f"{len(arch.detected_cycles)} circular loops, and {len(arch.architectural_signals.get('architectural_hubs', []))} architectural hubs. "
            f"The Multi-Agent Council reached unanimous consensus on: '{verdict.title}'."
        )

        # 8. Model Evolution & Contributor Capability Credit
        evo_credit = None
        if result.brain and result.brain.evolution_stages:
            evo_credit = result.brain.evolution_stages[-1]

        return WhatWeLearnedReport(
            session_id=task_spec.task_id,
            repo_name=repo_name,
            executive_summary=summary,
            architectural_discoveries=discoveries,
            developer_intent_uncovered=intent_summary,
            invariants_established=invariants,
            approaches_ruled_out=ruled_out,
            verified_milestones_achieved=milestones,
            key_takeaways_for_developers=takeaways,
            recommended_next_steps=next_steps,
            model_evolution_credit=evo_credit,
        )

    @classmethod
    def format_markdown(cls, report: WhatWeLearnedReport) -> str:
        discoveries_md = []
        for d in report.architectural_discoveries:
            discoveries_md.append(f"""### 🔍 {d['topic']}
- **What We Saw:** {d['observation']}
- **Why It Matters:** {d['why_it_matters']}
- **The Core Lesson:** {d['lesson']}
""")

        invariants_md = "\n".join(f"- `{inv}`" for inv in report.invariants_established)
        ruled_out_md = "\n".join(f"- ❌ {ro}" for ro in report.approaches_ruled_out)
        milestones_md = "\n".join(f"- ✅ {ms}" for ms in report.verified_milestones_achieved)
        takeaways_md = "\n".join(f"{i+1}. **{t}**" for i, t in enumerate(report.key_takeaways_for_developers))
        next_steps_md = "\n".join(f"- [ ] {ns}" for ns in report.recommended_next_steps)

        evolution_md = ""
        if report.model_evolution_credit:
            evo = report.model_evolution_credit
            evolution_md = f"""---

## 🏆 Model Capability Evolution & Contributor Credit
> **Model Evolution Stage:** Stage {evo.stage_number} (`{evo.stage_id}`)
> **Model Generation:** `{evo.model_version}`
> **Credited Developer / Author:** **{evo.credited_owner}**
> **Repository Source:** `{evo.credited_repo}` ({evo.license_type})
> **Capability Leap Unlocked:** {evo.capability_unlocked}

### How Studying This Codebase Evolved FlowMind's Capabilities:
{evo.stage_description}

**Official Credit Citation:**
_{evo.attribution_statement}_
"""

        md = f"""# 🎓 What We Learned: Architectural Retrospective
**Repository:** `{report.repo_name}` | **Session ID:** `{report.session_id}`

## 📌 Executive Summary
{report.executive_summary}

---

## 🧠 Developer Intent & Mental Model Uncovered
{report.developer_intent_uncovered}

---

## 🏛️ Key Architectural Discoveries
{''.join(discoveries_md)}

---

## 🛡️ Non-Negotiable Architectural Invariants Established
{invariants_md or "_No invariant constraints registered._"}

---

## 🚫 Approaches Ruled Out (Dead Ends)
{ruled_out_md}

---

## 🎯 Verified Milestones Achieved
{milestones_md}

---

## 💡 Top Lessons for the Engineering Team
{takeaways_md}

---

## 🚀 Recommended Next Actions
{next_steps_md}
{evolution_md}
---
*Generated automatically by FlowMind Autonomous Multi-Agent Retrospective Engine.*
"""
        return md

    @classmethod
    def save_markdown(cls, report: WhatWeLearnedReport, output_path: str | Path) -> Path:
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        md_text = cls.format_markdown(report)
        out_p.write_text(md_text, encoding="utf-8")
        return out_p

    @classmethod
    def print_terminal(cls, report: WhatWeLearnedReport):
        console.print(
            Panel.fit(
                f"[bold cyan]🎓 WHAT WE LEARNED: SESSION RETROSPECTIVE[/bold cyan]\n"
                f"Repository: [yellow]{report.repo_name}[/yellow] | Session: [dim]{report.session_id}[/dim]",
                border_style="cyan",
            )
        )

        console.print(Panel(report.executive_summary, title="📌 Executive Summary", border_style="blue"))
        console.print(Panel(report.developer_intent_uncovered, title="🧠 Developer Intent & Mindset", border_style="magenta"))

        if report.architectural_discoveries:
            disc_table = Table(title="🔍 Key Discoveries & Core Lessons", border_style="yellow")
            disc_table.add_column("Pattern / Finding", style="cyan", width=25)
            disc_table.add_column("What It Means for You", style="white", width=40)
            disc_table.add_column("Actionable Lesson", style="green", width=35)
            for d in report.architectural_discoveries[:4]:
                disc_table.add_row(d["topic"], d["why_it_matters"], d["lesson"])
            console.print(disc_table)

        if report.invariants_established:
            inv_table = Table(title="🛡️ Invariants Codified for Future Stability", border_style="green")
            inv_table.add_column("Rule", style="white")
            for inv in report.invariants_established:
                inv_table.add_row(inv)
            console.print(inv_table)

        takeaways_text = "\n".join(f"{i+1}. [bold white]{t}[/bold white]" for i, t in enumerate(report.key_takeaways_for_developers))
        console.print(Panel(takeaways_text, title="💡 Top Engineering Takeaways", border_style="gold1"))

        next_text = "\n".join(f"• [cyan]{ns}[/cyan]" for ns in report.recommended_next_steps)
        console.print(Panel(next_text, title="🚀 Actionable Next Steps", border_style="cyan"))

        if report.model_evolution_credit:
            evo = report.model_evolution_credit
            evo_content = (
                f"[bold gold1]Model Evolution Stage:[/bold gold1] {evo.stage_id} ([cyan]{evo.model_version}[/cyan])\n"
                f"[bold gold1]Accredited Developer / Owner:[/bold gold1] [bold green]{evo.credited_owner}[/bold green] ([yellow]{evo.credited_repo}[/yellow])\n"
                f"[bold gold1]Capability Leap Unlocked:[/bold gold1] [white]{evo.capability_unlocked}[/white]\n\n"
                f"[dim]{evo.attribution_statement}[/dim]"
            )
            console.print(Panel(evo_content, title="🏆 MODEL CAPABILITY EVOLUTION & CONTRIBUTOR CREDIT", border_style="gold1"))

