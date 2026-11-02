from __future__ import annotations

import json
from typing import Dict, List, Any, Optional
import networkx as nx

from repo_investigator.bench_rotation.models import CanonicalStateBus
from repo_investigator.bench_rotation.prompts import render_starter_bench_prompt

CACHE_BREAKPOINT_MARKER = "<-- [INSERT 1-HOUR CACHE BREAKPOINT HERE]"

class PromptPrefixManager:
    """
    Zero-Latency KV-Cache Handoff Prompt Manager.
    Enforces the strict 4-layer prompt prefix hierarchy specified in memory.md Section 2:
    1. SYSTEM INSTRUCTIONS & TOOL SCHEMAS (Static across all stints)
    2. AST REPOMAP / "GAME FILM" (2,048-token Tree-Sitter PageRank map)
    3. SHARED STATE BUS LEDGER (Milestones, Active Blockers, Dead-Ends)
       <-- [INSERT 1-HOUR CACHE BREAKPOINT HERE]
    4. PRIVATE AGENT SCRATCHPAD (Cleared to zero on every substitution)
    """

    @staticmethod
    def build_system_layer(
        fencing_token: int,
        stint_number: int,
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        base_prompt = render_starter_bench_prompt(fencing_token=fencing_token, stint_number=stint_number)
        tools_str = ""
        if tool_schemas:
            tools_str = "\n\n### REGISTERED TOOL SCHEMAS\n" + json.dumps(tool_schemas, indent=2)
        else:
            tools_str = (
                "\n\n### REGISTERED TOOL SCHEMAS\n"
                "- file_read(path: str)\n"
                "- file_write(path: str, content: str)\n"
                "- ast_parse_check(path: str)\n"
                "- run_verification_tests(target: str)"
            )
        return f"{base_prompt}{tools_str}"

    @staticmethod
    def build_ast_repomap_layer(
        call_graph_edges: Optional[List[Any]] = None,
        modules: Optional[Dict[str, Any]] = None,
        max_tokens: int = 2048,
    ) -> str:
        """
        Builds the 2,048-token Tree-Sitter / AST PageRank repomap ("Game Film").
        Uses PageRank across call/dependency graph to highlight central architectural hubs.
        """
        lines: List[str] = [
            "### AST REPOMAP / GAME FILM (Topological PageRank Ranked)",
        ]

        # Build NetworkX graph if edges available
        g = nx.DiGraph()
        if modules:
            for mod_name in modules.keys():
                g.add_node(mod_name)

        if call_graph_edges:
            for edge in call_graph_edges:
                u = getattr(edge, "caller", None) or (edge[0] if isinstance(edge, (list, tuple)) else None)
                v = getattr(edge, "callee", None) or (edge[1] if isinstance(edge, (list, tuple)) else None)
                if u and v:
                    g.add_edge(u, v)

        pagerank_scores = {}
        if len(g) > 0:
            try:
                pagerank_scores = nx.pagerank(g, alpha=0.85)
            except Exception:
                pagerank_scores = {n: 1.0 / len(g) for n in g.nodes()}

        sorted_nodes = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)
        if not sorted_nodes and modules:
            sorted_nodes = [(m, 1.0) for m in modules.keys()]

        for node_name, score in sorted_nodes:
            mod_data = modules.get(node_name) if modules else None
            mod_classes = getattr(mod_data, "classes", []) if mod_data else []
            mod_functions = getattr(mod_data, "functions", []) if mod_data else []

            lines.append(f"Module: {node_name} (PageRank: {score:.4f})")
            for c in mod_classes[:3]:
                c_name = getattr(c, "name", str(c))
                lines.append(f"  Class {c_name}")
            for fn in mod_functions[:4]:
                fn_name = getattr(fn, "name", str(fn))
                lines.append(f"  Def {fn_name}()")

        if len(lines) == 1:
            lines.append("Topology: Decoupled / Standard Package Structure (0 circular dependencies).")

        full_text = "\n".join(lines)
        # 1 token ~= 4 chars rule of thumb
        max_chars = max_tokens * 4
        truncation_suffix = "\n... [TRUNCATED TO 2048 TOKENS]"
        if len(full_text) > max_chars:
            cut_idx = max(0, max_chars - len(truncation_suffix))
            full_text = full_text[:cut_idx] + truncation_suffix
        return full_text

    @staticmethod
    def build_state_bus_ledger_layer(state_bus: CanonicalStateBus) -> str:
        """
        Formats the canonical state bus ledger for GPU prompt caching.
        """
        lines = [
            "### SHARED STATE BUS LEDGER",
            f"Workflow ID: {state_bus.workflow_id} | Fencing Token: {state_bus.fencing_token} | Stint: {state_bus.stint_number}",
            f"Goal: {state_bus.goal}",
            f"Active Player: {state_bus.active_player}",
            "",
            "Active Blockers:",
        ]
        if state_bus.active_blockers:
            for b in state_bus.active_blockers:
                lines.append(f"- [BLOCKER] {b}")
        else:
            lines.append("- (No active blockers)")

        lines.append("\nVerified Milestones (Ground Truth):")
        if state_bus.verified_milestones:
            for m in state_bus.verified_milestones:
                lines.append(f"- Step {m.step} [{m.commit_or_snapshot_id}]: {m.summary}")
        else:
            lines.append("- (No verified milestones yet)")

        lines.append("\nDead Ends Log (Ruled Out Approaches - DO NOT REPEAT):")
        if state_bus.dead_ends_log:
            for d in state_bus.dead_ends_log:
                lines.append(
                    f"- Stint #{d.stint}: Attempted '{d.attempted_play}' -> "
                    f"Failed: {d.failure_reason} | RULE OUT: {d.rule_out}"
                )
        else:
            lines.append("- (No dead ends logged)")

        return "\n".join(lines)

    @classmethod
    def assemble_full_roster_prompt(
        cls,
        fencing_token: int,
        stint_number: int,
        state_bus: CanonicalStateBus,
        call_graph_edges: Optional[List[Any]] = None,
        modules: Optional[Dict[str, Any]] = None,
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        private_scratchpad: str = "",
    ) -> str:
        """
        Enforces strict 4-layer ordering with the cache breakpoint marker before the private scratchpad.
        """
        layer_1 = cls.build_system_layer(fencing_token, stint_number, tool_schemas)
        layer_2 = cls.build_ast_repomap_layer(call_graph_edges, modules)
        layer_3 = cls.build_state_bus_ledger_layer(state_bus)

        scratchpad_content = private_scratchpad.strip() or "(Private scratchpad initialized to zero for this stint)"

        sections = [
            "==================== 1. SYSTEM INSTRUCTIONS & TOOL SCHEMAS ====================",
            layer_1,
            "==================== 2. AST REPOMAP / GAME FILM ====================",
            layer_2,
            "==================== 3. SHARED STATE BUS LEDGER ====================",
            layer_3,
            CACHE_BREAKPOINT_MARKER,
            "==================== 4. PRIVATE AGENT SCRATCHPAD ====================",
            scratchpad_content,
        ]

        return "\n\n".join(sections)

    @staticmethod
    def validate_prefix_ordering(prompt_text: str) -> bool:
        """
        Verifies that all 4 layers and the cache breakpoint marker appear in strict order.
        """
        pos_layer_1 = prompt_text.find("1. SYSTEM INSTRUCTIONS & TOOL SCHEMAS")
        pos_layer_2 = prompt_text.find("2. AST REPOMAP / GAME FILM")
        pos_layer_3 = prompt_text.find("3. SHARED STATE BUS LEDGER")
        pos_marker = prompt_text.find(CACHE_BREAKPOINT_MARKER)
        pos_layer_4 = prompt_text.find("4. PRIVATE AGENT SCRATCHPAD")

        if -1 in (pos_layer_1, pos_layer_2, pos_layer_3, pos_marker, pos_layer_4):
            return False

        return pos_layer_1 < pos_layer_2 < pos_layer_3 < pos_marker < pos_layer_4
