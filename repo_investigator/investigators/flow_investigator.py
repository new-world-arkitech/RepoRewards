from __future__ import annotations

from typing import List
from repo_investigator.models.archaeology import RepoArchaeology
from repo_investigator.models.investigator_models import (
    InvestigationFinding,
    InvestigatorInsight,
    SpecialistRole,
)
from repo_investigator.investigators.base import BaseInvestigator

class FlowTopologyInvestigator(BaseInvestigator):
    def __init__(self, engine=None):
        super().__init__(
            role=SpecialistRole.FLOW_TOPOLOGY,
            name="Dr. Aris Vance (Topology & Dataflow Lead)",
            lens_description="Structural topology, component coupling, synchronous bottlenecks, and dataflow directionality.",
            engine=engine,
        )

    def investigate(self, archaeology: RepoArchaeology) -> InvestigationFinding:
        insights: List[InvestigatorInsight] = []
        friction_points: List[str] = []

        # 1. Inspect dependency cycles
        if archaeology.detected_cycles:
            cycles_str = ", ".join(" -> ".join(c) for c in archaeology.detected_cycles[:3])
            insights.append(
                InvestigatorInsight(
                    category="TOPOLOGY_CYCLIC_DEPENDENCY",
                    observation=f"Detected {len(archaeology.detected_cycles)} circular dependency loops.",
                    evidence=f"Cycle paths: {cycles_str}",
                    confidence=0.98,
                    implication="Circular dependencies tightly couple module lifecycles and impede independent testing and refactoring."
                )
            )
            friction_points.append(f"Cyclic coupling in: {cycles_str}")
        else:
            insights.append(
                InvestigatorInsight(
                    category="TOPOLOGY_ACYCLIC",
                    observation="Module graph is strictly acyclic.",
                    evidence="No cyclic loops detected across internal imports.",
                    confidence=0.95,
                    implication="Acyclic flow allows layered dependency injection and modular refactoring."
                )
            )

        # 2. Inspect central hubs & Robert C. Martin Stability Metrics
        hubs = archaeology.architectural_signals.get("architectural_hubs", [])
        if hubs:
            insights.append(
                InvestigatorInsight(
                    category="HIGH_CENTRALITY_HUB",
                    observation=f"Identified high-degree architectural hubs: {', '.join(hubs)}",
                    evidence=f"Hub modules act as convergence points for multiple ingress pathways.",
                    confidence=0.92,
                    implication="Mutating hub modules carries a large blast radius across dependent subsystems."
                )
            )
            friction_points.append(f"High-fan-in hub modules: {', '.join(hubs)}")

        # 3. Zone of Pain (Rigid Concrete Modules) & Package Metrics
        zop_modules = archaeology.architectural_signals.get("zone_of_pain_modules", [])
        if zop_modules:
            insights.append(
                InvestigatorInsight(
                    category="ZONE_OF_PAIN_RIGIDITY",
                    observation=f"Identified {len(zop_modules)} module(s) in Robert C. Martin's 'Zone of Pain': {', '.join(zop_modules[:3])}",
                    evidence="Modules exhibit low instability (I < 0.35) and low abstraction (A < 0.25) under heavy afferent load.",
                    confidence=0.96,
                    implication="These concrete classes are rigid and heavily depended on; modifying them causes cascading regressions."
                )
            )
            for zm in zop_modules:
                friction_points.append(f"Zone of Pain module: {zm} (concrete, rigid, high afferent coupling)")

        # 4. Inverted Architectural Layer Boundary Leaks
        layer_leaks = archaeology.architectural_signals.get("layer_boundary_inversions", [])
        if layer_leaks:
            sample_leak = layer_leaks[0]
            insights.append(
                InvestigatorInsight(
                    category="INVARIANT_LAYER_BOUNDARY_BREACH",
                    observation=f"Detected {len(layer_leaks)} inverted architectural layer boundary violation(s).",
                    evidence=f"Violation: {sample_leak.get('violation')}",
                    confidence=0.97,
                    implication="Lower-layer domain logic directly couples to concrete infrastructure adapters or ingress entrypoints."
                )
            )
            for lk in layer_leaks[:3]:
                friction_points.append(f"Layer Boundary Leak: {lk.get('violation')}")

        # 3. Analyze Call Graph Flow
        total_calls = len(archaeology.call_graph_edges)
        async_present = archaeology.architectural_signals.get("has_concurrency_markers", False)

        flow_summary = "synchronous and direct" if not async_present else "hybrid sync/async"
        insights.append(
            InvestigatorInsight(
                category="FLOW_EXECUTION_MODE",
                observation=f"Execution pipeline is predominantly {flow_summary}.",
                evidence=f"{total_calls} identified function call boundaries across {len(archaeology.modules)} modules.",
                confidence=0.90,
                implication="Direct call chains create implicit temporal coupling between producers and consumers."
            )
        )

        core_hyp = (
            f"The codebase routes data primarily through {hubs[0] if hubs else 'central modules'} using direct "
            f"call invocations. State transitions lack decoupling barriers, concentrating architectural pressure on shared hubs."
        )

        dev_thought = (
            "Developers initially structured the project for rapid end-to-end prototyping by calling downstream services "
            "directly, but as features scaled, downstream dependencies were pulled backward, threatening layered boundaries."
        )

        recommended = (
            "Decouple central hub dependencies via an event/pipeline boundary or explicit protocol interfaces to isolate "
            "upstream business logic from downstream storage and side-effects."
        )

        return InvestigationFinding(
            investigator_role=self.role,
            investigator_name=self.name,
            specialization_lens=self.lens_description,
            core_hypothesis=core_hyp,
            insights=insights,
            friction_points=friction_points,
            developer_thought_model=dev_thought,
            recommended_action=recommended,
            metadata={"hubs": hubs, "cycles_count": len(archaeology.detected_cycles)},
        )
