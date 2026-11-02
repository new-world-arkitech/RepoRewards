from __future__ import annotations

from typing import Dict, List, Tuple
from repo_investigator.models.deliberation_models import (
    PerspectiveScoring,
    TradeoffScore,
    ConsensusVerdict,
)

class ConsensusScoringMatrix:
    """
    Evaluates competing perspectives across multidimensional architectural criteria
    and synthesizes an optimal architectural consensus verdict.
    """

    CRITERIA = [
        "ARCHITECTURAL_COHERENCE",
        "INVARIANT_SAFETY",
        "BLAST_RADIUS_CONTAINMENT",
        "COGNITIVE_ERGONOMICS",
        "IMPLEMENTATION_FEASIBILITY",
    ]

    @classmethod
    def evaluate_perspectives(
        cls,
        has_cycles: bool,
        has_churn: bool,
        has_layer_leaks: bool,
    ) -> Dict[str, PerspectiveScoring]:
        """
        Calculates balanced trade-off scores for the three deliberative perspectives.
        """
        # 1. Pragmatic Maintainer: High feasibility, high blast radius containment, lower long-term coherence
        pragmatist_scores = {
            "ARCHITECTURAL_COHERENCE": 6.8,
            "INVARIANT_SAFETY": 7.5,
            "BLAST_RADIUS_CONTAINMENT": 9.5,
            "COGNITIVE_ERGONOMICS": 7.0,
            "IMPLEMENTATION_FEASIBILITY": 9.2,
        }

        # 2. Radical Modernizer: High coherence, high ergonomics, but higher blast radius & lower feasibility
        modernizer_scores = {
            "ARCHITECTURAL_COHERENCE": 9.6,
            "INVARIANT_SAFETY": 8.0,
            "BLAST_RADIUS_CONTAINMENT": 4.5,
            "COGNITIVE_ERGONOMICS": 8.8,
            "IMPLEMENTATION_FEASIBILITY": 5.5,
        }

        # 3. Invariant & Resilience Sentinel: Maximum invariant safety, balanced blast radius
        sentinel_scores = {
            "ARCHITECTURAL_COHERENCE": 8.5,
            "INVARIANT_SAFETY": 9.8,
            "BLAST_RADIUS_CONTAINMENT": 8.0,
            "COGNITIVE_ERGONOMICS": 7.8,
            "IMPLEMENTATION_FEASIBILITY": 8.0,
        }

        # Adjust based on repo realities
        if has_layer_leaks:
            sentinel_scores["INVARIANT_SAFETY"] = 9.9
            pragmatist_scores["ARCHITECTURAL_COHERENCE"] -= 1.0

        if has_churn:
            pragmatist_scores["COGNITIVE_ERGONOMICS"] -= 1.0
            modernizer_scores["ARCHITECTURAL_COHERENCE"] += 0.2

        scoring_map: Dict[str, PerspectiveScoring] = {}

        for pid, name, scores, strengths, risks in [
            (
                "PRAGMATIST",
                "The Pragmatic Maintainer",
                pragmatist_scores,
                ["Guaranteed backward compatibility", "Zero disruption to existing callers", "Rapid deployment"],
                ["Leaves underlying structural debt intact", "Risk of repeating past churn workarounds"],
            ),
            (
                "MODERNIZER",
                "The Radical Modernizer",
                modernizer_scores,
                ["Elegant decoupling", "Future-proof modularity", "High conceptual clarity"],
                ["High blast radius", "Risk of introducing regressions in callers", "Longer refactor cycle"],
            ),
            (
                "SENTINEL",
                "The Invariants & Resilience Sentinel",
                sentinel_scores,
                ["Zero tolerance for invariant violation", "Defensive boundary isolation", "Deterministic behavior"],
                ["Requires strict interface adherence", "Slightly higher code ceremony"],
            ),
        ]:
            avg = round(sum(scores.values()) / len(scores), 2)
            scoring_map[pid] = PerspectiveScoring(
                perspective_id=pid,
                perspective_name=name,
                scores=scores,
                average_score=avg,
                key_strengths=strengths,
                key_risks=risks,
            )

        return scoring_map

    @classmethod
    def synthesize_consensus(
        cls,
        scoring: Dict[str, PerspectiveScoring],
        repo_name: str,
        hubs: List[str],
        friction_points: List[str],
    ) -> ConsensusVerdict:
        """
        Synthesizes the best combined interpretation into a unified architectural verdict.
        Merges the Pragmatist's low-risk containment with the Modernizer's decoupled structure
        and the Sentinel's strict invariant enforcement.
        """
        primary_hub = hubs[0] if hubs else "core execution module"

        rationale = (
            f"The council rejects both a complete disruptive rewrite (Modernizer) and superficial band-aids (Pragmatist). "
            f"Instead, the council synthesizes a 'Targeted Decoupled Invariant Facade' strategy. "
            f"This encapsulates the high-churn hub '{primary_hub}', enforces strict layer boundaries, "
            f"and provides a clean interface while maintaining existing call signatures."
        )

        hard_invariants = [
            "INV-01: Zero direct persistence imports within domain logic.",
            "INV-02: All state transformations must execute atomically without mutating external caller objects.",
            "INV-03: Backward-compatible public method signatures must be preserved or wrapped via deprecation adapter.",
            "INV-04: Concurrency-safe synchronization primitives must wrap any shared cached state.",
        ]

        required_mutations = [
            f"Introduce an abstract protocol/interface decoupling '{primary_hub}' from direct callers.",
            "Isolate database/external service interactions into dedicated adapter functions.",
            "Add defensive invariant validation guards at service ingress boundaries.",
            "Implement automated regression tests validating invariant integrity.",
        ]

        return ConsensusVerdict(
            verdict_id=f"VERDICT-{repo_name.upper()}-001",
            title="Targeted Invariant-Guarded Decoupling Strategy",
            strategic_rationale=rationale,
            developer_mindset_addressed=(
                "Validates original developer intent for simple ergonomics while lifting historical compromises "
                "into explicit, invariant-guarded contracts."
            ),
            chosen_path_description=(
                "Pragmatic refactoring with invariant enforcement: refactor the focal hub into clean decoupled "
                "interfaces while preserving public caller contracts."
            ),
            acknowledged_tradeoffs=[
                "Requires introducing one intermediate interface/adapter class.",
                "Slight increase in file count in exchange for zero cyclic coupling and strict invariant safety."
            ],
            rejected_alternatives=[
                "Total architectural rewrite: rejected due to excessive blast radius.",
                "In-place ad-hoc patching: rejected because it perpetuates historical cognitive churn."
            ],
            hard_invariants=hard_invariants,
            required_mutations=required_mutations,
        )
