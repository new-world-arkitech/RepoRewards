from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from repo_investigator.orchestrator import PipelineResult
from repo_investigator.models.explanations import get_plain_english_insight
from repo_investigator.coach.retrospective import SessionRetrospectiveBuilder

class HTMLReportGenerator:
    """
    Generates a standalone, zero-dependency, interactive HTML executive report
    for client presentation, stakeholder review, and architectural sign-off.
    """

    @classmethod
    def generate_html(cls, result: PipelineResult, repo_name: str = "Repository") -> str:
        verdict = result.deliberation.consensus_verdict
        arch = result.archaeology
        hubs = arch.architectural_signals.get("architectural_hubs", [])
        cycles = arch.detected_cycles
        task_spec = result.task_spec
        exec_report = result.execution_report
        state_bus = result.state_bus
        brain = result.brain

        # Build retrospective summary for executive and engineering review
        retrospective = SessionRetrospectiveBuilder.build(result, repo_name=repo_name)

        # Gate stats
        gates_total = len(task_spec.verification_gates)
        gates_passed = sum(1 for g in (exec_report.gate_results if exec_report else []) if g.passed)
        gate_rate = f"{(gates_passed / gates_total * 100):.0f}%" if gates_total > 0 else "100%"

        # Generate Mermaid diagram definition
        mermaid_lines = [
            "graph TD",
            "    classDef hub fill:#f97316,stroke:#ea580c,stroke-width:2px,color:#fff;",
            "    classDef cycle fill:#ef4444,stroke:#b91c1c,stroke-width:2px,color:#fff;",
            "    classDef normal fill:#1e293b,stroke:#475569,stroke-width:1px,color:#f8fafc;",
        ]

        # Add nodes
        modules = list(arch.modules.keys())[:25]
        for m in modules:
            safe_id = m.replace(".", "_").replace("-", "_")
            node_label = f'"{m}"'
            if m in hubs:
                mermaid_lines.append(f'    {safe_id}[{node_label}]:::hub')
            elif any(m in c for c in cycles):
                mermaid_lines.append(f'    {safe_id}[{node_label}]:::cycle')
            else:
                mermaid_lines.append(f'    {safe_id}[{node_label}]:::normal')

        # Add edges from call graph or internal imports
        added_edges = set()
        for edge in arch.call_graph_edges[:30]:
            src_id = edge.source.replace(".", "_").replace("-", "_").replace(":", "_")
            tgt_id = edge.target.replace(".", "_").replace("-", "_").replace(":", "_")
            edge_key = (src_id, tgt_id)
            if edge_key not in added_edges:
                added_edges.add(edge_key)
                mermaid_lines.append(f"    {src_id} --> {tgt_id}")

        for mod_name, mod_obj in list(arch.modules.items())[:20]:
            src_id = mod_name.replace(".", "_").replace("-", "_")
            for imp in getattr(mod_obj, "internal_imports", [])[:5]:
                tgt_id = imp.replace(".", "_").replace("-", "_")
                edge_key = (src_id, tgt_id)
                if edge_key not in added_edges:
                    added_edges.add(edge_key)
                    mermaid_lines.append(f"    {src_id} --> {tgt_id}")

        mermaid_graph = "\n".join(mermaid_lines)

        # Deliberation rounds HTML
        rounds_html = []
        for r in result.deliberation.rounds:
            args_html = []
            for arg in r.arguments:
                badge_color = "#3b82f6" if "PRAGMATIST" in arg.speaker_id else "#10b981" if "MODERNIZER" in arg.speaker_id else "#8b5cf6"
                args_html.append(f"""
                <div style="background: rgba(30, 41, 59, 0.7); border-left: 4px solid {badge_color}; padding: 12px; margin-bottom: 10px; border-radius: 4px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                        <strong style="color: {badge_color}; font-size: 0.95rem;">{html.escape(arg.speaker_name)}</strong>
                        <span style="font-size: 0.75rem; background: #334155; padding: 2px 6px; border-radius: 4px; color: #cbd5e1;">Severity: {html.escape(arg.severity)}</span>
                    </div>
                    <div style="font-size: 0.9rem; color: #e2e8f0; line-height: 1.4;">{html.escape(arg.point)}</div>
                    {f'<div style="font-size: 0.8rem; color: #94a3b8; margin-top: 6px;"><em>Evidence: {html.escape(arg.counter_evidence)}</em></div>' if arg.counter_evidence else ''}
                </div>
                """)
            rounds_html.append(f"""
            <div style="margin-bottom: 24px; background: rgba(15, 23, 42, 0.6); padding: 16px; border-radius: 8px; border: 1px solid #334155;">
                <h4 style="margin: 0 0 8px 0; color: #38bdf8; font-size: 1.05rem;">{html.escape(r.round_name)}</h4>
                <p style="margin: 0 0 12px 0; font-size: 0.85rem; color: #94a3b8;">{html.escape(r.round_summary)}</p>
                {''.join(args_html)}
            </div>
            """)

        # Trade-off Matrix HTML
        matrix_rows = []
        criteria = [
            ("Architectural Coherence", "ARCHITECTURAL_COHERENCE"),
            ("Invariant Safety", "INVARIANT_SAFETY"),
            ("Blast Radius Containment", "BLAST_RADIUS_CONTAINMENT"),
            ("Cognitive Ergonomics", "COGNITIVE_ERGONOMICS"),
            ("Implementation Feasibility", "IMPLEMENTATION_FEASIBILITY"),
        ]
        scoring = result.deliberation.perspectives_scoring
        for label, key in criteria:
            cells = [f"<td style='padding: 10px; font-weight: 600; color: #e2e8f0;'>{label}</td>"]
            for pid, pdata in scoring.items():
                val = pdata.scores.get(key, 0.0)
                color = "#10b981" if val >= 8.5 else "#38bdf8" if val >= 7.0 else "#f59e0b"
                cells.append(f"<td style='padding: 10px; text-align: center; color: {color}; font-weight: bold;'>{val:.1f}/10</td>")
            matrix_rows.append(f"<tr style='border-bottom: 1px solid #334155;'>{''.join(cells)}</tr>")

        matrix_headers = ["<th style='padding: 10px; text-align: left; color: #94a3b8;'>Evaluation Dimension</th>"]
        for pid, pdata in scoring.items():
            matrix_headers.append(f"<th style='padding: 10px; text-align: center; color: #38bdf8;'>{html.escape(pdata.perspective_name)}<br><span style='font-size: 0.75rem; color: #64748b;'>Avg: {pdata.average_score}</span></th>")
        tradeoff_matrix_html = f"""
        <table style="width: 100%; border-collapse: collapse; background: #0f172a; border-radius: 8px; overflow: hidden; margin-top: 14px;">
            <thead><tr style="background: #1e293b; border-bottom: 2px solid #334155;">{''.join(matrix_headers)}</tr></thead>
            <tbody>{''.join(matrix_rows)}</tbody>
        </table>
        """

        # Milestones HTML
        milestones_html = []
        if state_bus and state_bus.verified_milestones:
            for ms in state_bus.verified_milestones:
                milestones_html.append(f"""
                <li style="margin-bottom: 8px; font-size: 0.88rem; color: #e2e8f0;">
                    <span style="background: #047857; color: #ecfdf5; padding: 2px 6px; border-radius: 3px; font-weight: bold; margin-right: 6px;">Step {ms.step}</span>
                    {html.escape(ms.summary)}
                    <span style="font-size: 0.75rem; color: #64748b; margin-left: 6px;">[Snapshot: {html.escape(ms.commit_or_snapshot_id[:8])}]</span>
                </li>
                """)
        else:
            milestones_html.append("<li style='color: #94a3b8;'>Completed initial repository archaeological scan and invariant compilation.</li>")

        # Invariants HTML
        invariants_html = []
        for inv in task_spec.architectural_invariants:
            invariants_html.append(f"""
            <div style="background: #1e293b; padding: 12px 16px; margin-bottom: 10px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #334155;">
                <div>
                    <span style="font-weight: bold; color: #f59e0b; margin-right: 8px;">[{html.escape(inv.id)}]</span>
                    <span style="color: #cbd5e1; font-size: 0.95rem;">{html.escape(inv.rule)}</span>
                </div>
                <span style="font-size: 0.75rem; background: #0f172a; border: 1px solid #475569; padding: 3px 10px; border-radius: 4px; color: #38bdf8;">Scope: {html.escape(inv.enforcement_scope)}</span>
            </div>
            """)

        # Verification gates HTML
        gates_html = []
        if exec_report:
            for g in exec_report.gate_results:
                status_color = "#10b981" if g.passed else "#ef4444"
                status_icon = "PASSED" if g.passed else "FAILED"
                gates_html.append(f"""
                <div style="background: #1e293b; padding: 12px 16px; margin-bottom: 10px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid {status_color}; border-right: 1px solid #334155; border-top: 1px solid #334155; border-bottom: 1px solid #334155;">
                    <div>
                        <strong style="color: #f8fafc; font-size: 0.95rem;">{html.escape(g.gate_name)}</strong>
                        <div style="font-size: 0.85rem; color: #94a3b8; margin-top: 3px;">{html.escape(g.details)}</div>
                    </div>
                    <span style="background: {status_color}22; color: {status_color}; border: 1px solid {status_color}; font-size: 0.8rem; font-weight: bold; padding: 4px 10px; border-radius: 4px;">{status_icon}</span>
                </div>
                """)

        # Unified Diffs HTML (Client-facing code mutations)
        diffs_html = []
        if exec_report and exec_report.unified_diffs:
            for fpath, diff_content in exec_report.unified_diffs.items():
                diff_lines_html = []
                for line in diff_content.splitlines():
                    escaped_line = html.escape(line)
                    if line.startswith("+") and not line.startswith("+++"):
                        diff_lines_html.append(f"<div style='background: rgba(16, 185, 129, 0.18); color: #6ee7b7; padding: 1px 6px;'>{escaped_line}</div>")
                    elif line.startswith("-") and not line.startswith("---"):
                        diff_lines_html.append(f"<div style='background: rgba(239, 68, 68, 0.18); color: #fca5a5; padding: 1px 6px;'>{escaped_line}</div>")
                    elif line.startswith("@@"):
                        diff_lines_html.append(f"<div style='background: rgba(168, 85, 247, 0.18); color: #d8b4fe; padding: 2px 6px; font-weight: bold;'>{escaped_line}</div>")
                    else:
                        diff_lines_html.append(f"<div style='color: #94a3b8; padding: 1px 6px;'>{escaped_line}</div>")
                diffs_html.append(f"""
                <div style="background: #0f172a; border: 1px solid #334155; border-radius: 6px; margin-bottom: 16px; overflow: hidden;">
                    <div style="background: #1e293b; padding: 8px 14px; font-family: monospace; font-size: 0.85rem; color: #38bdf8; border-bottom: 1px solid #334155; display: flex; justify-content: space-between;">
                        <span>Target: <strong>{html.escape(fpath)}</strong></span>
                        <span style="color: #10b981;">Synthesized by Reasoning Agent</span>
                    </div>
                    <pre style="margin: 0; padding: 8px; font-family: 'Consolas', 'Fira Code', monospace; font-size: 0.82rem; overflow-x: auto; line-height: 1.4;">{''.join(diff_lines_html)}</pre>
                </div>
                """)

        # Retrospective: Lessons & Next Steps HTML
        lessons_html = []
        for i, t in enumerate(retrospective.key_takeaways_for_developers):
            lessons_html.append(f"""
            <li style="margin-bottom: 10px; color: #e2e8f0; font-size: 0.95rem;">
                <strong style="color: #facc15;">Lesson {i+1}:</strong> {html.escape(t)}
            </li>
            """)

        next_steps_html = []
        for s in retrospective.recommended_next_steps:
            next_steps_html.append(f"""
            <li style="margin-bottom: 8px; color: #38bdf8; font-size: 0.9rem;">
                <span style="color: #64748b; margin-right: 6px;">[ ]</span> {html.escape(s)}
            </li>
            """)

        dead_ends_html = []
        for de in retrospective.approaches_ruled_out:
            dead_ends_html.append(f"""
            <li style="margin-bottom: 8px; color: #f87171; font-size: 0.88rem;">
                <span style="margin-right: 6px;">❌</span> {html.escape(de)}
            </li>
            """)

        # Model Evolution & Contributor Credit Card HTML
        evolution_credit_html = ""
        if retrospective.model_evolution_credit:
            evo = retrospective.model_evolution_credit
            evolution_credit_html = f"""
            <div style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(15, 23, 42, 0.8) 100%); border: 2px solid #f59e0b; border-radius: 10px; padding: 22px; margin-bottom: 24px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 1.8rem;">🏆</span>
                        <div>
                            <h3 style="margin: 0; color: #fde68a; font-size: 1.25rem;">Model Evolution & Contributor Capability Credit</h3>
                            <div style="font-size: 0.82rem; color: #cbd5e1;">Attributed to repository author for advancing FlowMind's reasoning abilities</div>
                        </div>
                    </div>
                    <span style="background: #f59e0b; color: #000; font-weight: 800; padding: 4px 12px; border-radius: 14px; font-size: 0.8rem;">Stage #{evo.stage_number} | {html.escape(evo.model_version)}</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 16px;">
                    <div style="background: rgba(15, 23, 42, 0.7); padding: 12px; border-radius: 6px; border: 1px solid rgba(245, 158, 11, 0.3);">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8;">Accredited Developer / Owner</div>
                        <div style="font-size: 1.05rem; font-weight: bold; color: #34d399;">{html.escape(evo.credited_owner)}</div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.7); padding: 12px; border-radius: 6px; border: 1px solid rgba(245, 158, 11, 0.3);">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8;">Source Repository & License</div>
                        <div style="font-size: 1.05rem; font-weight: bold; color: #38bdf8;">{html.escape(evo.credited_repo)} <span style="font-size: 0.75rem; color: #94a3b8;">({html.escape(evo.license_type)})</span></div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.7); padding: 12px; border-radius: 6px; border: 1px solid rgba(245, 158, 11, 0.3);">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8;">Capability Leap Unlocked</div>
                        <div style="font-size: 0.95rem; font-weight: bold; color: #fde68a;">{html.escape(evo.capability_unlocked)}</div>
                    </div>
                </div>
                <p style="margin: 0 0 10px 0; font-size: 0.92rem; color: #e2e8f0; line-height: 1.5;">{html.escape(evo.stage_description)}</p>
                <div style="padding-top: 10px; border-top: 1px dashed rgba(245, 158, 11, 0.4); font-size: 0.85rem; color: #cbd5e1; font-style: italic;">
                    "{html.escape(evo.attribution_statement)}"
                </div>
            </div>
            """

        # Plain-English Beginner-Friendly Guide
        plain_cards_html = []
        if cycles:
            exp = get_plain_english_insight("TOPOLOGY_CYCLIC_DEPENDENCY")
            plain_cards_html.append(f"""
            <div style="background: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; padding: 14px; margin-bottom: 12px; border-radius: 6px;">
                <h5 style="margin: 0 0 4px 0; color: #fca5a5; font-size: 1rem;">⚠️ {exp['title']}</h5>
                <p style="margin: 0 0 6px 0; font-size: 0.9rem; color: #f1f5f9;">{exp['plain_english']}</p>
                <div style="font-size: 0.8rem; color: #cbd5e1;"><strong>Why it matters:</strong> {exp['why_it_matters']}</div>
                <div style="font-size: 0.8rem; color: #38bdf8; margin-top: 4px;"><strong>Recommended Fix:</strong> {exp['how_to_fix']}</div>
            </div>
            """)
        else:
            exp = get_plain_english_insight("TOPOLOGY_ACYCLIC")
            plain_cards_html.append(f"""
            <div style="background: rgba(16, 185, 129, 0.1); border-left: 4px solid #10b981; padding: 14px; margin-bottom: 12px; border-radius: 6px;">
                <h5 style="margin: 0 0 4px 0; color: #6ee7b7; font-size: 1rem;">✓ {exp['title']}</h5>
                <p style="margin: 0 0 6px 0; font-size: 0.9rem; color: #f1f5f9;">{exp['plain_english']}</p>
                <div style="font-size: 0.8rem; color: #cbd5e1;"><strong>Why it matters:</strong> {exp['why_it_matters']}</div>
            </div>
            """)

        if hubs:
            exp = get_plain_english_insight("HIGH_CENTRALITY_HUB")
            plain_cards_html.append(f"""
            <div style="background: rgba(249, 115, 22, 0.1); border-left: 4px solid #f97316; padding: 14px; margin-bottom: 12px; border-radius: 6px;">
                <h5 style="margin: 0 0 4px 0; color: #fdba74; font-size: 1rem;">⚡ {exp['title']}</h5>
                <p style="margin: 0 0 6px 0; font-size: 0.9rem; color: #f1f5f9;">{exp['plain_english']}</p>
                <div style="font-size: 0.8rem; color: #cbd5e1;"><strong>Why it matters:</strong> {exp['why_it_matters']}</div>
                <div style="font-size: 0.8rem; color: #38bdf8; margin-top: 4px;"><strong>Recommended Fix:</strong> {exp['how_to_fix']}</div>
            </div>
            """)

        if arch.churn_hotspots:
            exp = get_plain_english_insight("COGNITIVE_CHURN")
            plain_cards_html.append(f"""
            <div style="background: rgba(147, 51, 234, 0.1); border-left: 4px solid #9333ea; padding: 14px; margin-bottom: 12px; border-radius: 6px;">
                <h5 style="margin: 0 0 4px 0; color: #d8b4fe; font-size: 1rem;">🔥 {exp['title']}</h5>
                <p style="margin: 0 0 6px 0; font-size: 0.9rem; color: #f1f5f9;">{exp['plain_english']}</p>
                <div style="font-size: 0.8rem; color: #cbd5e1;"><strong>Why it matters:</strong> {exp['why_it_matters']}</div>
                <div style="font-size: 0.8rem; color: #38bdf8; margin-top: 4px;"><strong>Recommended Fix:</strong> {exp['how_to_fix']}</div>
            </div>
            """)

        # Full Document Template
        doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FlowMind Executive Architecture Audit - {html.escape(repo_name)}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});</script>
    <style>
        :root {{
            --bg: #090d16;
            --card-bg: #111827;
            --border: #1f2937;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.15);
            --gold: #f59e0b;
            --green: #10b981;
        }}
        body {{
            margin: 0;
            padding: 0;
            background-color: var(--bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
        }}
        .header {{
            background: linear-gradient(180deg, #1e293b 0%, #090d16 100%);
            padding: 40px 24px 26px;
            border-bottom: 1px solid var(--border);
            text-align: center;
        }}
        .header h1 {{
            margin: 0 0 8px 0;
            font-size: 2.2rem;
            color: #f8fafc;
            letter-spacing: -0.5px;
        }}
        .header .subtitle {{
            color: var(--accent);
            font-size: 1.05rem;
            font-weight: 500;
        }}
        .client-badge {{
            display: inline-block;
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid #38bdf8;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-top: 10px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px 20px 60px;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .kpi-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }}
        .kpi-val {{
            font-size: 1.9rem;
            font-weight: 700;
            color: var(--accent);
            margin: 6px 0;
        }}
        .kpi-label {{
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
        }}
        .tabs-nav {{
            display: flex;
            gap: 8px;
            border-bottom: 2px solid var(--border);
            margin-bottom: 24px;
            overflow-x: auto;
            padding-bottom: 2px;
        }}
        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 10px 18px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            border-radius: 6px 6px 0 0;
            transition: all 0.2s ease;
            white-space: nowrap;
        }}
        .tab-btn:hover {{
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.04);
        }}
        .tab-btn.active {{
            color: var(--accent);
            background: var(--card-bg);
            border-bottom: 3px solid var(--accent);
        }}
        .tab-pane {{
            display: none;
        }}
        .tab-pane.active {{
            display: block;
            animation: fadeIn 0.2s ease;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(4px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .section-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .section-title {{
            font-size: 1.25rem;
            font-weight: 600;
            color: #f8fafc;
            margin: 0 0 16px 0;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-green {{ background: #065f46; color: #a7f3d0; }}
        .badge-amber {{ background: #78350f; color: #fde68a; }}
        .badge-blue {{ background: #1e3a8a; color: #93c5fd; }}
        .mermaid {{
            display: flex;
            justify-content: center;
            padding: 20px;
            background: #0b1120;
            border-radius: 6px;
            overflow-x: auto;
        }}
        .action-bar {{
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            margin-bottom: 20px;
        }}
        .print-btn {{
            background: #1e293b;
            color: #f8fafc;
            border: 1px solid #475569;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.88rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .print-btn:hover {{
            background: #334155;
            border-color: #64748b;
        }}
        footer {{
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 0.85rem;
            border-top: 1px solid var(--border);
        }}
        @media print {{
            body {{ background: #ffffff !important; color: #000000 !important; }}
            .header {{ background: #ffffff !important; color: #000000 !important; border-bottom: 2px solid #000 !important; }}
            .tabs-nav, .action-bar, .print-btn {{ display: none !important; }}
            .tab-pane {{ display: block !important; margin-bottom: 30px !important; }}
            .section-card, .kpi-card {{ background: #ffffff !important; border: 1px solid #ccc !important; box-shadow: none !important; color: #000 !important; }}
            .section-title {{ color: #000000 !important; border-bottom: 1px solid #000 !important; }}
            pre, code {{ background: #f8f8f8 !important; color: #000 !important; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>FlowMind Executive Architecture Audit</h1>
        <div class="subtitle">Autonomous Archaeology, Specialist Deliberation, A2A Bench Rotation & State Bus</div>
        <div style="margin-top: 10px;">
            <span class="client-badge">CLIENT AUDIT REPORT</span>
            <span style="color: #94a3b8; font-size: 0.9rem; margin-left: 10px;">Target: <strong>{html.escape(repo_name)}</strong> &bull; Tier: <strong>{html.escape(result.execution_tier or "TIER_3")}</strong></span>
        </div>
    </div>

    <div class="container">
        <!-- Top Action Bar -->
        <div class="action-bar">
            <button class="print-btn" onclick="window.print()">🖨️ Export PDF / Print Audit</button>
        </div>

        <!-- KPI Executive Scorecard -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Consensus Verdict</div>
                <div class="kpi-val" style="font-size: 1.25rem; padding-top: 6px;">{html.escape(verdict.title.split(':')[0])}</div>
                <span class="badge badge-green">Specialist Consensus</span>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Invariant Gates</div>
                <div class="kpi-val">{gate_rate}</div>
                <span class="badge badge-green">{gates_passed}/{gates_total} Passed</span>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Architectural Hubs</div>
                <div class="kpi-val">{len(hubs)}</div>
                <span class="badge badge-amber">{len(cycles)} Cycles Detected</span>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Fencing Token</div>
                <div class="kpi-val">{state_bus.fencing_token if state_bus else 1}</div>
                <span class="badge badge-green">Monotonic CAS Lock</span>
            </div>
        </div>

        {evolution_credit_html}

        <!-- Interactive Tabs Navigation -->
        <div class="tabs-nav">
            <button class="tab-btn active" onclick="switchTab('tab-overview', this)">📊 Executive Overview</button>
            <button class="tab-btn" onclick="switchTab('tab-topology', this)">🗺️ Component Flow Map</button>
            <button class="tab-btn" onclick="switchTab('tab-deliberation', this)">⚖️ Council Deliberation</button>
            <button class="tab-btn" onclick="switchTab('tab-invariants', this)">🛡️ Invariants & Gates</button>
            <button class="tab-btn" onclick="switchTab('tab-retrospective', this)">🎓 What We Learned</button>
            <button class="tab-btn" onclick="switchTab('tab-diffs', this)">⚡ Synthesized Diffs</button>
        </div>

        <!-- TAB 1: EXECUTIVE OVERVIEW -->
        <div id="tab-overview" class="tab-pane active">
            <div class="section-card">
                <div class="section-title">Consensus Strategy & Strategic Rationale</div>
                <p style="font-size: 1.1rem; color: #f8fafc; font-weight: 600;">{html.escape(verdict.title)}</p>
                <p style="color: #cbd5e1; font-size: 0.98rem; line-height: 1.6;">{html.escape(verdict.strategic_rationale)}</p>
                <div style="margin-top: 14px; background: rgba(56, 189, 248, 0.08); padding: 12px 16px; border-radius: 6px; border-left: 4px solid #38bdf8;">
                    <strong style="color: #38bdf8;">Developer Thought Model Addressed:</strong>
                    <div style="color: #e2e8f0; font-size: 0.92rem; margin-top: 4px;">{html.escape(verdict.developer_mindset_addressed)}</div>
                </div>
            </div>

            <div class="section-card">
                <div class="section-title">
                    Plain-English Architectural Insights
                    <span style="font-size: 0.8rem; color: #38bdf8; font-weight: normal;">ELI5 guidance for engineering leads</span>
                </div>
                {''.join(plain_cards_html)}
            </div>

            <div class="section-card">
                <div class="section-title">Canonical State Bus & Verified Milestones</div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
                    <div style="background: #1e293b; padding: 14px; border-radius: 6px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8;">Active Stint Player</div>
                        <div style="font-size: 1.15rem; font-weight: bold; color: #38bdf8;">{html.escape(state_bus.active_player if state_bus else 'starter_agent')}</div>
                    </div>
                    <div style="background: #1e293b; padding: 14px; border-radius: 6px;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8;">Stint Number</div>
                        <div style="font-size: 1.15rem; font-weight: bold; color: #10b981;">{state_bus.stint_number if state_bus else 1}</div>
                    </div>
                </div>
                <h4 style="color: #38bdf8; margin: 12px 0 8px 0; font-size: 0.95rem;">Verified Milestones Ledger:</h4>
                <ul style="padding-left: 20px; margin: 0;">
                    {''.join(milestones_html)}
                </ul>
            </div>
        </div>

        <!-- TAB 2: COMPONENT FLOW MAP -->
        <div id="tab-topology" class="tab-pane">
            <div class="section-card">
                <div class="section-title">
                    Component Flow & Topology Map
                    <span style="font-size: 0.8rem; color: #94a3b8; font-weight: normal;">Orange: Hubs | Red: Cycles | Dark: Clean Modules</span>
                </div>
                <p style="color: #94a3b8; font-size: 0.88rem; margin-bottom: 14px;">
                    This topological DAG illustrates call-graph boundaries and import flow vectors extracted through deep AST archaeology.
                </p>
                <div class="mermaid">
{mermaid_graph}
                </div>
            </div>
        </div>

        <!-- TAB 3: DELIBERATION COUNCIL -->
        <div id="tab-deliberation" class="tab-pane">
            <div class="section-card">
                <div class="section-title">Multi-Perspective Deliberation Council</div>
                <p style="color: #94a3b8; font-size: 0.88rem; margin-bottom: 16px;">
                    Three autonomous specialists—the Pragmatist, Modernizer, and Boundary Sentinel—deliberated across 3 rounds to achieve dialectic consensus.
                </p>
                {''.join(rounds_html)}
            </div>

            <div class="section-card">
                <div class="section-title">Multi-Criteria Trade-Off Scoring Matrix</div>
                <p style="color: #94a3b8; font-size: 0.88rem; margin-bottom: 12px;">
                    Specialist perspective scores across core non-negotiable architectural dimensions.
                </p>
                {tradeoff_matrix_html}
            </div>
        </div>

        <!-- TAB 4: INVARIANTS & GATES -->
        <div id="tab-invariants" class="tab-pane">
            <div class="section-card">
                <div class="section-title">Architectural Invariant Integrity & Verification Gates</div>
                <h4 style="color: #38bdf8; margin: 0 0 10px 0; font-size: 1rem;">Protected Hard Invariants:</h4>
                {''.join(invariants_html)}
                <h4 style="color: #38bdf8; margin: 24px 0 10px 0; font-size: 1rem;">Verification Gate Evaluations:</h4>
                {''.join(gates_html)}
            </div>
        </div>

        <!-- TAB 5: WHAT WE LEARNED (RETROSPECTIVE) -->
        <div id="tab-retrospective" class="tab-pane">
            <div class="section-card">
                <div class="section-title">🎓 What We Learned: Session Retrospective</div>
                <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 6px; padding: 18px; margin-bottom: 20px;">
                    <h4 style="margin: 0 0 8px 0; color: #38bdf8; font-size: 1.05rem;">📌 Executive Retrospective Summary</h4>
                    <p style="color: #e2e8f0; font-size: 0.95rem; line-height: 1.6; margin: 0;">{html.escape(retrospective.executive_summary)}</p>
                </div>

                <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 6px; padding: 18px; margin-bottom: 20px;">
                    <h4 style="margin: 0 0 8px 0; color: #f472b6; font-size: 1.05rem;">🧠 Developer Mental Model & Intent Uncovered</h4>
                    <p style="color: #e2e8f0; font-size: 0.95rem; line-height: 1.6; margin: 0;">{html.escape(retrospective.developer_intent_uncovered)}</p>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 6px; padding: 18px;">
                        <h4 style="margin: 0 0 12px 0; color: #facc15; font-size: 1.05rem;">💡 Key Takeaways for the Team</h4>
                        <ol style="padding-left: 20px; margin: 0;">
                            {''.join(lessons_html)}
                        </ol>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 6px; padding: 18px;">
                        <h4 style="margin: 0 0 12px 0; color: #f87171; font-size: 1.05rem;">🚫 Ruled-Out Dead Ends (Failed Plays)</h4>
                        <ul style="padding-left: 20px; margin: 0; list-style-type: none;">
                            {''.join(dead_ends_html)}
                        </ul>
                    </div>
                </div>

                <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid #334155; border-radius: 6px; padding: 18px;">
                    <h4 style="margin: 0 0 10px 0; color: #34d399; font-size: 1.05rem;">🚀 Recommended Next Actions</h4>
                    <ul style="padding-left: 20px; margin: 0; list-style-type: none;">
                        {''.join(next_steps_html)}
                    </ul>
                </div>
            </div>
        </div>

        <!-- TAB 6: SYNTHESIZED DIFFS -->
        <div id="tab-diffs" class="tab-pane">
            <div class="section-card">
                <div class="section-title">Synthesized Architectural Diffs & Safe Mutations</div>
                <p style="color: #94a3b8; font-size: 0.88rem; margin-bottom: 16px;">
                    Verified code refactorings generated by the Reasoning Coding Agent to enforce invariants while maintaining 100% backward compatibility.
                </p>
                {''.join(diffs_html) if diffs_html else '<p style="color: #94a3b8;">No direct code mutations executed during this pass (Audit mode).</p>'}
            </div>
        </div>
    </div>

    <footer>
        Generated by <strong>FlowMind Autonomous Architecture Engine</strong> &bull; Client-Facing Production Audit
    </footer>

    <script>
        function switchTab(tabId, btn) {{
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');
        }}
    </script>
</body>
</html>
"""
        return doc

    @classmethod
    def save_report(cls, result: PipelineResult, output_path: str | Path, repo_name: str = "Repository") -> Path:
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        html_content = cls.generate_html(result, repo_name=repo_name)
        out_file.write_text(html_content, encoding="utf-8")
        return out_file
