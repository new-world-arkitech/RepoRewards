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

        # 1. Analyze Churn Hotspots, Author Entropy & Conway's Law Dissonance
        top_churn = archaeology.churn_hotspots[:3]
        if top_churn:
            churn_desc = ", ".join(f"{h.file_path} ({h.modification_count} touches, risk {h.risk_score}, H_author {h.author_entropy})" for h in top_churn)
            insights.append(
                InvestigatorInsight(
                    category="CHURN_COGNITIVE_FRICTION",
                    observation=f"Primary cognitive friction localized in churn hotspots: {churn_desc}",
                    evidence=f"Files modified repeatedly across historical commit progression.",
                    confidence=0.96,
                    implication="High-churn files reflect unresolved design ambiguity, Conway's law author divergence, or unstable domain interfaces."
                )
            )
            for h in top_churn:
                friction_points.append(f"Hotspot file {h.file_path} repeatedly revised ({h.modification_count} times, H_author={h.author_entropy})")
                if h.author_entropy > 1.2 or h.author_count >= 3:
                    insights.append(
                        InvestigatorInsight(
                            category="CONWAY_AUTHOR_DISSONANCE",
                            observation=f"Elevated author entropy (H={h.author_entropy}, {h.author_count} authors) on '{h.file_path}'.",
                            evidence=f"Commits originated from multiple distinct contributors without a single unified mental model.",
                            confidence=0.91,
                            implication="Fragmented code ownership induces stylistic drift and conflicting architectural conventions."
                        )
                    )
                if h.has_firefighting_burst:
                    insights.append(
                        InvestigatorInsight(
                            category="RAPID_FIREFIGHTING_SPIRAL",
                            observation=f"Temporal firefighting burst detected on '{h.file_path}'.",
                            evidence="Rapid cluster of consecutive bug fixes/patches committed within short chronological intervals.",
                            confidence=0.93,
                            implication="Emergency patches were deployed in reaction to regressions, signaling tight coupling and hidden side-effects."
                        )
                    )

        # 2. Extract In-Code Cognitive Debt & Compromise Markers (AST-Level)
        all_markers = [
            m for mod in archaeology.modules.values()
            for m in mod.cognitive_markers
        ]
        if all_markers:
            todo_count = sum(1 for m in all_markers if m.category in ("TODO", "FIXME"))
            hack_count = sum(1 for m in all_markers if m.category in ("HACK", "WORKAROUND", "BUG", "TEMP"))
            caution_count = sum(1 for m in all_markers if m.category in ("CAUTION", "DEPRECATED"))
            sample_marker = all_markers[0]
            insights.append(
                InvestigatorInsight(
                    category="IN_CODE_COGNITIVE_DEBT",
                    observation=f"Discovered {len(all_markers)} in-code cognitive debt markers ({todo_count} TODOs, {hack_count} Workarounds, {caution_count} Cautions).",
                    evidence=f"Direct developer annotation at {sample_marker.file_path}:{sample_marker.line_number}: '{sample_marker.text}'",
                    confidence=0.97,
                    implication="Developers embedded explicit cautionary notes where existing abstractions failed to accommodate requirements."
                )
            )
            friction_points.append(f"In-code compromise marker at {sample_marker.file_path}:{sample_marker.line_number} ('{sample_marker.text}')")

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
