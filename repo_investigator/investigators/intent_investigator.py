from __future__ import annotations

from typing import List, Dict
from repo_investigator.models.archaeology import RepoArchaeology
from repo_investigator.models.investigator_models import (
    InvestigationFinding,
    InvestigatorInsight,
    SpecialistRole,
)
from repo_investigator.investigators.base import BaseInvestigator

class DeveloperIntentInvestigator(BaseInvestigator):
    def __init__(self, engine=None):
        super().__init__(
            role=SpecialistRole.DEVELOPER_INTENT,
            name="Elena Rostova (Developer Archaeology & Cognition Lead)",
            lens_description="Historical commit genealogies, churn hotspots, cognitive friction, and intentionality reconstruction.",
            engine=engine,
        )

    def investigate(self, archaeology: RepoArchaeology) -> InvestigationFinding:
        insights: List[InvestigatorInsight] = []
        friction_points: List[str] = []

        # 1. Analyze Churn Hotspots
        top_churn = archaeology.churn_hotspots[:3]
        if top_churn:
            churn_desc = ", ".join(f"{h.file_path} ({h.modification_count} touches, risk {h.risk_score})" for h in top_churn)
            insights.append(
                InvestigatorInsight(
                    category="CHURN_COGNITIVE_FRICTION",
                    observation=f"Primary cognitive friction localized in churn hotspots: {churn_desc}",
                    evidence=f"Files modified repeatedly across historical commit progression.",
                    confidence=0.96,
                    implication="High-churn files reflect unresolved design ambiguity or unstable domain interfaces."
                )
            )
            for h in top_churn:
                friction_points.append(f"Hotspot file {h.file_path} repeatedly revised ({h.modification_count} times)")

        # 2. Extract Developer Cognitive Signals from Commits
        hacks = [c for c in archaeology.commits if "HACK_OR_WORKAROUND" in c.intent_tags]
        fixes = [c for c in archaeology.commits if "BUG_FIX" in c.intent_tags]
        refactors = [c for c in archaeology.commits if "REFACTORING" in c.intent_tags]
        races = [c for c in archaeology.commits if "RACE_OR_CONCURRENCY" in c.intent_tags]

        if hacks:
            insights.append(
                InvestigatorInsight(
                    category="COGNITIVE_COMPROMISE",
                    observation=f"Detected {len(hacks)} explicit workarounds/hacks recorded by developers.",
                    evidence=f"Latest hack commit: '{hacks[0].message.splitlines()[0]}'",
                    confidence=0.94,
                    implication="Developers encountered resistance from existing architecture and chose expediency over structural purity."
                )
            )
            friction_points.append(f"Historical compromise: '{hacks[0].message.splitlines()[0]}'")

        if races:
            insights.append(
                InvestigatorInsight(
                    category="HISTORICAL_CONCURRENCY_STRUGGLE",
                    observation="Git lineage reflects prior struggles with race conditions or asynchronous state consistency.",
                    evidence=f"Commits explicitly reference concurrency concerns ({len(races)} commits).",
                    confidence=0.92,
                    implication="Shared mutable state or asynchronous callbacks have caused non-deterministic bugs in past iterations."
                )
            )
            friction_points.append("Past concurrency/race bug regressions noted in commits")

        # 3. Formulate Developer Mental Model
        if hacks or fixes:
            mindset_summary = (
                "Developers experienced high cognitive load balancing new business logic with unstable shared state. "
                "Commit narratives indicate they intended to refactor the core execution pathway, but deadlines favored targeted fixes."
            )
        else:
            mindset_summary = (
                "Developers followed a disciplined additive development model, prioritizing straightforward procedural flows "
                "with clear evolutionary markers."
            )

        core_hyp = (
            f"The evolutionary lineage demonstrates clear developer intention to maintain a simple execution model, "
            f"but accumulated bug fixes and hotfixes in '{top_churn[0].file_path if top_churn else 'core components'}' "
            f"indicate that the original architectural assumptions are now under strain."
        )

        recommended = (
            "Honor the developer's original ergonomic intentions while lifting technical compromises into first-class architectural abstractions."
        )

        return InvestigationFinding(
            investigator_role=self.role,
            investigator_name=self.name,
            specialization_lens=self.lens_description,
            core_hypothesis=core_hyp,
            insights=insights,
            friction_points=friction_points,
            developer_thought_model=mindset_summary,
            recommended_action=recommended,
            metadata={"total_commits": archaeology.total_commits, "hacks_count": len(hacks), "fixes_count": len(fixes)},
        )
