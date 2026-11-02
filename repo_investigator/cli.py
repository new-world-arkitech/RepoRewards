from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Safe encoding configuration for Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.tree import Tree
from rich.text import Text

from repo_investigator.orchestrator import FlowMindOrchestrator
from repo_investigator.translator.command_compiler import CommandCompiler
from repo_investigator.bench_rotation.models import ExecutionTier
from repo_investigator.extractor.repo_loader import is_git_remote_url
from repo_investigator.reports.html_reporter import HTMLReportGenerator
from repo_investigator.integrations.github import post_pr_comment
from repo_investigator.coach import DeveloperAid, SessionRetrospectiveBuilder
from repo_investigator.brain import BrainManager

console = Console(highlight=False)

def run_cli():
    parser = argparse.ArgumentParser(
        description="FlowMind: Multi-Agent Software Architecture Research & Deliberation Engine with A2A Bench Rotation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to repository to scan and investigate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute reasoning loop without writing files to disk",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Stop after compiling machine-readable commands (skip Coding Agent)",
    )
    parser.add_argument(
        "--output-spec",
        type=str,
        default=None,
        help="Path to save the compiled machine-readable JSON command specification",
    )
    parser.add_argument(
        "--tier",
        type=str,
        choices=["auto", "1", "2", "3", "TIER_1", "TIER_2", "TIER_3"],
        default="auto",
        help="Select execution tier (auto uses Completion Effort Node classifier)",
    )
    parser.add_argument(
        "--disable-bench-rotation",
        action="store_true",
        help="Disable adaptive A2A bench rotation and run single-agent loop",
    )
    parser.add_argument(
        "--output-state-bus",
        type=str,
        default=None,
        help="Path to save the canonical State Bus JSON ledger",
    )
    parser.add_argument(
        "--report-html",
        type=str,
        default=None,
        help="Path to save the client-facing interactive HTML executive report",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch FlowMind HTTP & Event Streaming REST API server",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Server host bind address",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port number",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=50,
        help="Git clone depth for remote repositories",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Git branch to checkout for remote repositories",
    )
    parser.add_argument(
        "--keep-repo",
        action="store_true",
        help="Keep cloned repository directory on disk after pipeline completes",
    )
    parser.add_argument(
        "--post-pr-comment",
        action="store_true",
        help="Post architectural audit scorecard as a comment to GitHub Pull Request",
    )
    parser.add_argument(
        "--pr-number",
        type=int,
        default=None,
        help="Target GitHub Pull Request number (defaults to GITHUB_EVENT_PATH/GITHUB_REF)",
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default=None,
        help="GitHub Personal Access Token or workflow token (defaults to GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--fail-on-gates",
        action="store_true",
        help="Exit with non-zero exit code (1) if any architectural verification gate fails",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Display colored unified diffs of all synthesized and refactored code",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Interactive review mode: prompt before applying mutations to each file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose mode to display complete reasoning chains-of-thought",
    )
    parser.add_argument(
        "--explain",
        type=str,
        default=None,
        help="New Developer Aid: Explain a file's purpose, gotchas, and usage in plain English",
    )
    parser.add_argument(
        "--debug",
        type=str,
        default=None,
        help="New Developer Aid: Diagnose a Python error or traceback and get a step-by-step fix",
    )
    parser.add_argument(
        "--guide",
        type=str,
        default=None,
        help="New Developer Aid: Architectural guidance on where and how to implement a new feature",
    )
    parser.add_argument(
        "--save-learned",
        type=str,
        default=None,
        help="Path to export the 'What We Learned' session retrospective markdown report",
    )
    parser.add_argument(
        "--no-retrospective",
        action="store_true",
        help="Skip displaying the 'What We Learned' session retrospective at completion",
    )
    parser.add_argument(
        "--repo-owner",
        type=str,
        default=None,
        help="Repository owner/maintainer to accredit for learned architectural skills and brain knowledge",
    )
    parser.add_argument(
        "--brain-path",
        type=str,
        default=None,
        help="Custom file path for persistent Cognitive Brain knowledge base",
    )
    parser.add_argument(
        "--model-provider",
        type=str,
        choices=["simulated", "gemma", "anthropic", "openai", "gemini", "sglang", "vllm"],
        default=None,
        help="Explicit LLM carrier reasoning engine (e.g. gemma, anthropic, openai)",
    )
    parser.add_argument(
        "--gemma-endpoint",
        type=str,
        default=None,
        help="Local or remote inference endpoint for Gemma 3B (default: http://localhost:11434/v1)",
    )
    parser.add_argument(
        "--gemma-model",
        type=str,
        default=None,
        help="Gemma model tag/name (default: gemma:3b)",
    )

    args = parser.parse_args()

    # Optional explicit carrier instantiation
    custom_engine = None
    if args.model_provider == "gemma" or args.gemma_endpoint or args.gemma_model:
        import os
        from repo_investigator.llm import GemmaCarrierEngine
        custom_engine = GemmaCarrierEngine(
            model=args.gemma_model or os.getenv("GEMMA_MODEL", "gemma:3b"),
            endpoint=args.gemma_endpoint or os.getenv("GEMMA_ENDPOINT", "http://localhost:11434/v1"),
        )

    # Doctor mode handling (friendly environment healthcheck)
    if args.repo_path == "doctor":
        from repo_investigator.doctor import run_doctor
        ok = run_doctor()
        sys.exit(0 if ok else 1)

    # Brain Inspection mode
    if args.repo_path in ("brain", "brain-inspect", "brain:inspect"):
        bp = Path(args.brain_path) if args.brain_path else None
        BrainManager.print_brain_inspect(brain_path=bp)
        return

    # Developer's Aid standalone modes: Explain, Debug, Guide
    coach = DeveloperAid(engine=custom_engine)
    if args.explain:
        exp = coach.explain_file(args.explain)
        coach.print_explanation(exp)
        return

    if args.debug:
        diag = coach.diagnose_error(args.debug)
        coach.print_diagnosis(diag)
        return

    if args.guide:
        guide = coach.guide_feature(args.guide)
        coach.print_guide(guide)
        return

    # Server mode handling
    if args.serve or args.repo_path == "serve":
        from repo_investigator.server import run_server
        console.print(
            Panel.fit(
                f"[bold cyan]FLOWMIND REST API SERVER[/bold cyan]\n"
                f"Binding to [yellow]http://{args.host}:{args.port}[/yellow]\n"
                f"Swagger UI available at [link=http://{args.host}:{args.port}/docs]http://{args.host}:{args.port}/docs[/link]",
                border_style="cyan",
            )
        )
        run_server(host=args.host, port=args.port)
        return

    # Ingestion target resolution: Remote Git URL or Local Path
    is_remote = is_git_remote_url(args.repo_path)
    if is_remote:
        target_display = args.repo_path
        target_path = args.repo_path
    else:
        target_path = Path(args.repo_path).resolve()
        target_display = str(target_path)
        if not target_path.exists():
            console.print(f"[bold red]Error:[/bold red] Target path does not exist: [yellow]{target_path}[/yellow]")
            sys.exit(1)
        if not target_path.is_dir():
            console.print(f"[bold red]Error:[/bold red] Target path is not a directory: [yellow]{target_path}[/yellow]")
            sys.exit(1)

    console.print(
        Panel.fit(
            "[bold cyan]FLOWMIND: ARCHITECTURAL INVESTIGATION & DELIBERATION ENGINE[/bold cyan]\n"
            "[dim]Autonomous Repository Archaeology, Multi-Perspective Dialectics, A2A Bench Rotation & State Bus[/dim]",
            border_style="cyan",
        )
    )

    console.print(f"\n[bold green]>> Initiating archaeological scan on:[/bold green] [yellow]{target_display}[/yellow]" + (" [cyan](Remote Git Ingestion)[/cyan]" if is_remote else ""))

    # Parse tier parameter
    chosen_tier = None
    if args.tier != "auto":
        tier_map = {
            "1": ExecutionTier.TIER_1_DIRECT,
            "TIER_1": ExecutionTier.TIER_1_DIRECT,
            "2": ExecutionTier.TIER_2_MANAGED_SINGLE,
            "TIER_2": ExecutionTier.TIER_2_MANAGED_SINGLE,
            "3": ExecutionTier.TIER_3_A2A_BENCH_ROTATION,
            "TIER_3": ExecutionTier.TIER_3_A2A_BENCH_ROTATION,
        }
        chosen_tier = tier_map.get(args.tier)

    orchestrator = FlowMindOrchestrator(engine=custom_engine)
    result = orchestrator.run(
        repo_path=target_path,
        execute_code=not args.no_execute,
        dry_run=args.dry_run,
        tier=chosen_tier,
        enable_bench_rotation=not args.disable_bench_rotation,
        remote_depth=args.depth,
        remote_branch=args.branch,
        keep_cloned_repo=args.keep_repo,
        review_mode=args.review,
        repo_owner=args.repo_owner,
        brain_path=Path(args.brain_path) if args.brain_path else None,
    )

    # 1. Display Archaeology Scan
    arch = result.archaeology
    scan_table = Table(title="Repository Archaeological Summary", border_style="blue")
    scan_table.add_column("Metric", style="cyan")
    scan_table.add_column("Value", style="magenta")
    scan_table.add_row("Scanned Modules", str(len(arch.modules)))
    scan_table.add_row("Total Commits Mined", str(arch.total_commits))
    scan_table.add_row("Call Graph Boundaries", str(len(arch.call_graph_edges)))
    scan_table.add_row("Dependency Cycles", str(len(arch.detected_cycles)))
    hubs_str = ", ".join(arch.architectural_signals.get("architectural_hubs", [])) or "None (Decoupled)"
    scan_table.add_row("Central Architectural Hubs", hubs_str)
    console.print(scan_table)

    if arch.churn_hotspots:
        churn_table = Table(title="Cognitive Churn Hotspots (Historical Friction)", border_style="red")
        churn_table.add_column("File Path", style="yellow")
        churn_table.add_column("Modifications", style="white")
        churn_table.add_column("Risk Index", style="bold red")
        for h in arch.churn_hotspots[:5]:
            churn_table.add_row(h.file_path, str(h.modification_count), f"{h.risk_score}/10")
        console.print(churn_table)

    # 2. Display Investigator Findings
    console.print("\n[bold yellow]=========== PHASE 2: INVESTIGATIVE COUNCIL DISPATCHES ===========[/bold yellow]")
    for finding in result.findings:
        inv_tree = Tree(f"[bold green]{finding.investigator_name}[/bold green] ([dim]{finding.investigator_role.value}[/dim])")
        inv_tree.add(f"[bold cyan]Specialist Lens:[/bold cyan] {finding.specialization_lens}")
        inv_tree.add(f"[bold magenta]Core Hypothesis:[/bold magenta] {finding.core_hypothesis}")
        inv_tree.add(f"[bold yellow]Developer Mental Model:[/bold yellow] {finding.developer_thought_model}")

        insights_node = inv_tree.add("[bold white]Key Analytical Insights:[/bold white]")
        for ins in finding.insights:
            insights_node.add(f"[cyan]{ins.category}:[/cyan] {ins.observation} [dim]({ins.implication})[/dim]")

        console.print(Panel(inv_tree, border_style="green"))

    # 3. Display Deliberation Council (Group Reasoning)
    console.print("\n[bold yellow]=========== PHASE 3: DELIBERATION COUNCIL (GROUP REASONING) ===========[/bold yellow]")
    session = result.deliberation

    for r in session.rounds:
        r_table = Table(title=f"[bold blue]{r.round_name}[/bold blue]", border_style="bright_blue")
        r_table.add_column("Speaker / Perspective", style="bold cyan", width=22)
        r_table.add_column("Dialectic Argument / Stance", style="white")
        r_table.add_column("Severity / Priority", style="magenta", width=12)

        for arg in r.arguments:
            r_table.add_row(arg.speaker_name, arg.point, arg.severity)
        console.print(r_table)

    # Display Trade-off Matrix
    matrix_table = Table(title="Multi-Criteria Trade-Off Scoring Matrix", border_style="yellow")
    matrix_table.add_column("Criterion", style="cyan")
    for pid, pdata in session.perspectives_scoring.items():
        matrix_table.add_column(f"{pdata.perspective_name}\n[dim](Avg: {pdata.average_score})[/dim]", style="green")

    criteria = [
        "ARCHITECTURAL_COHERENCE",
        "INVARIANT_SAFETY",
        "BLAST_RADIUS_CONTAINMENT",
        "COGNITIVE_ERGONOMICS",
        "IMPLEMENTATION_FEASIBILITY",
    ]
    for c in criteria:
        row_vals = [c.replace("_", " ").title()]
        for pid in session.perspectives_scoring.keys():
            val = session.perspectives_scoring[pid].scores.get(c, 0.0)
            row_vals.append(f"{val:.1f}")
        matrix_table.add_row(*row_vals)
    console.print(matrix_table)

    # Verdict
    verdict = session.consensus_verdict
    console.print(
        Panel(
            f"[bold gold1]ARCHITECTURAL VERDICT: {verdict.title}[/bold gold1]\n\n"
            f"[bold cyan]Strategic Rationale:[/bold cyan]\n{verdict.strategic_rationale}\n\n"
            f"[bold green]Developer Mindset Addressed:[/bold green]\n{verdict.developer_mindset_addressed}\n\n"
            f"[bold red]Hard Invariants Enforced:[/bold red]\n" + "\n".join(f"  * {inv}" for inv in verdict.hard_invariants),
            title="Consensus Synthesis",
            border_style="gold1",
        )
    )

    # 4. Display Machine-Readable Commands
    console.print("\n[bold yellow]=========== PHASE 4: MACHINE-READABLE COMMAND SPECIFICATION ===========[/bold yellow]")
    json_spec = CommandCompiler.to_json(result.task_spec)
    syntax = Syntax(json_spec, "json", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=f"Compiled Machine Directive Spec ({result.task_spec.task_id})", border_style="cyan"))

    if args.output_spec:
        out_file = CommandCompiler.save_spec(result.task_spec, args.output_spec)
        console.print(f"[bold green][OK] Saved machine-readable spec to:[/bold green] {out_file}")

    # 5. Display Adaptive Execution Tier & Bench Rotation Execution
    if result.execution_report:
        console.print("\n[bold yellow]=========== PHASE 5: A2A BENCH ROTATION & CODING AGENT EXECUTION ===========[/bold yellow]")
        rep = result.execution_report
        bench = rep.bench_rotation_report

        tier_style = "bold magenta"
        console.print(
            Panel(
                f"[bold cyan]Assigned Execution Tier:[/bold cyan] [{tier_style}]{rep.execution_tier or 'STANDARD'}[/{tier_style}]\n"
                f"[bold cyan]Mid-Game Promotion:[/bold cyan] {bench.promoted_mid_game if bench else False}"
                + (f" [dim]({bench.promotion_reason})[/dim]" if bench and bench.promotion_reason else "") + "\n"
                f"[bold cyan]Roster Stints Executed:[/bold cyan] {bench.stints_count if bench else 1}",
                title="Adaptive Completion Effort Tier",
                border_style="magenta",
            )
        )

        status_style = "bold green" if rep.status == "COMPLETED_SUCCESSFULLY" else "bold red"
        console.print(f"Coding Agent Execution Status: [{status_style}]{rep.status}[/{status_style}]")

        for trace in rep.step_traces:
            step_panel_content = (
                f"[bold cyan]Target File:[/bold cyan] {trace.target_file} | [bold cyan]Action:[/bold cyan] {trace.action_type}\n\n"
                f"[bold magenta]Pre-Flight Invariant Checks:[/bold magenta]\n" +
                "\n".join(f"  [CHECK] {c}" for c in trace.pre_flight_invariant_checks) +
                "\n\n[bold yellow]Internal Chain-of-Thought (Reasoning Model):[/bold yellow]\n" +
                "\n".join(f"  [THINK] {cot}" for cot in trace.reasoning_chain_of_thought) +
                f"\n\n[bold green]AST Verification Passed:[/bold green] {trace.ast_validation_passed}"
            )
            console.print(Panel(step_panel_content, title=f"Step {trace.step_number} Reasoning Trace", border_style="magenta"))

        # Zero-LLM Coach Telemetry Table
        if bench and bench.telemetry_history:
            tel_table = Table(title="Zero-LLM Coach Telemetry Reflex Loop History", border_style="cyan")
            tel_table.add_column("Turn", style="cyan", width=6)
            tel_table.add_column("S_rep", style="yellow")
            tel_table.add_column("S_stag", style="yellow")
            tel_table.add_column("S_cycle", style="yellow")
            tel_table.add_column("S_health", style="bold magenta")
            tel_table.add_column("Reflex Decision", style="white")

            for t in bench.telemetry_history:
                reflex_desc = "[bold red]SUBSTITUTION TRIGGERED[/bold red]" if t.substitution_triggered else "[bold green]NOMINAL (HEALTHY)[/bold green]"
                tel_table.add_row(
                    str(t.step_number),
                    f"{t.s_rep:.2f}",
                    f"{t.s_stag:.2f}",
                    f"{t.s_cycle:.2f}",
                    f"{t.s_health:.2f}",
                    reflex_desc,
                )
            console.print(tel_table)

        # Roster Substitutions Table (if any)
        if bench and bench.substitutions:
            sub_table = Table(title="Warm Bench Player Substitutions (Coach Node Protocol)", border_style="gold1")
            sub_table.add_column("Stint #", style="bold gold1")
            sub_table.add_column("Outgoing Agent", style="cyan")
            sub_table.add_column("Incoming Agent", style="green")
            sub_table.add_column("Fencing Token", style="magenta")
            sub_table.add_column("Trigger Reason", style="white")

            for s in bench.substitutions:
                sub_table.add_row(
                    str(s.stint_number),
                    s.outgoing_player,
                    s.incoming_player,
                    f"{s.old_fencing_token} -> {s.new_fencing_token}",
                    s.reason,
                )
            console.print(sub_table)

        # Verification Gate Table
        gate_table = Table(title="Verification Gate Evaluations", border_style="green")
        gate_table.add_column("Gate ID", style="cyan")
        gate_table.add_column("Gate Name", style="white")
        gate_table.add_column("Status", style="bold green")
        gate_table.add_column("Details", style="dim white")

        for g in rep.gate_results:
            status_text = "[bold green]PASS[/bold green]" if g.passed else "[bold red]FAIL[/bold red]"
            gate_table.add_row(g.gate_id, g.gate_name, status_text, g.details)
        console.print(gate_table)

        # 5b. Display Unified Diffs if requested or in review mode
        if rep.unified_diffs and (args.diff or args.review):
            console.print("\n[bold cyan]=========== SYNTHESIZED ARCHITECTURAL DIFFS ===========[/bold cyan]")
            for fpath, diff_content in rep.unified_diffs.items():
                syntax_diff = Syntax(diff_content, "diff", theme="monokai", line_numbers=True)
                console.print(Panel(syntax_diff, title=f"Unified Diff: [yellow]{fpath}[/yellow]", border_style="cyan"))

        # 5c. Display Verbose Reasoning Chains if requested
        if args.verbose and rep.step_traces:
            console.print("\n[bold magenta]=========== VERBOSE REASONING CHAINS-OF-THOUGHT ===========[/bold magenta]")
            for tr in rep.step_traces:
                trace_tree = Tree(f"[bold cyan]Step {tr.step_number}: {tr.action_type} on '{tr.target_file}'[/bold cyan] -> {tr.postcondition_status}")
                for cot_item in tr.reasoning_chain_of_thought:
                    trace_tree.add(cot_item)
                console.print(trace_tree)

    # 6. Display Shared State Bus Ledger Summary
    if result.state_bus:
        console.print("\n[bold yellow]=========== ASYMMETRIC STATE BUS LEDGER ===========[/bold yellow]")
        sb = result.state_bus
        bus_panel = (
            f"[bold cyan]Workflow ID:[/bold cyan] {sb.workflow_id} | "
            f"[bold magenta]Kleppmann Fencing Token:[/bold magenta] {sb.fencing_token} | "
            f"[bold green]Active Player:[/bold green] {sb.active_player} (Stint #{sb.stint_number})\n\n"
            f"[bold gold1]Goal:[/bold gold1] {sb.goal}\n\n"
            f"[bold green]Verified Milestones ({len(sb.verified_milestones)}):[/bold green]\n" +
            ("\n".join(f"  * Step {m.step} [{m.commit_or_snapshot_id}]: {m.summary}" for m in sb.verified_milestones) if sb.verified_milestones else "  (None)") +
            f"\n\n[bold red]Active Blockers ({len(sb.active_blockers)}):[/bold red]\n" +
            ("\n".join(f"  * {b}" for b in sb.active_blockers) if sb.active_blockers else "  (None)") +
            f"\n\n[bold yellow]Dead Ends Log (Ruled Out Approaches) ({len(sb.dead_ends_log)}):[/bold yellow]\n" +
            ("\n".join(f"  * Stint #{d.stint}: Attempted '{d.attempted_play}' -> {d.failure_reason} (RULE OUT: {d.rule_out})" for d in sb.dead_ends_log) if sb.dead_ends_log else "  (None)")
        )
        console.print(Panel(bus_panel, title="Canonical State Bus (NATS KV / RFC 6902)", border_style="blue"))

        if args.output_state_bus:
            out_p = Path(args.output_state_bus).resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(sb.model_dump(), indent=2), encoding="utf-8")
            console.print(f"[bold green][OK] Saved State Bus JSON to:[/bold green] {out_p}")

    if args.report_html:
        repo_name = Path(args.repo_path).name or "Repository"
        html_file = HTMLReportGenerator.save_report(result, args.report_html, repo_name=repo_name)
        console.print(f"\n[bold green][OK] Saved Client-Facing Interactive HTML Report to:[/bold green] [cyan]{html_file}[/cyan]")

    # 7. Post PR Comment if requested
    if args.post_pr_comment:
        repo_name = Path(args.repo_path).name or "Repository"
        posted = post_pr_comment(
            result=result,
            token=args.github_token,
            pr_number=args.pr_number,
            repo_name=repo_name,
        )
        if posted:
            console.print("[bold green][OK] Successfully posted FlowMind architectural scorecard to GitHub PR.[/bold green]")
        else:
            console.print("[yellow][NOTICE] Could not post to GitHub PR (check GITHUB_TOKEN or PR context).[/yellow]")

    # 8. Check Verification Gates for CI Gating
    gates_failed = False
    if rep and rep.gate_results:
        for g in rep.gate_results:
            if not g.passed:
                gates_failed = True
                break

    if gates_failed and args.fail_on_gates:
        console.print("\n[bold red][GATE FAILURE] One or more architectural verification gates failed. Exiting with error code 1 for CI gate enforcement.[/bold red]\n")
        sys.exit(1)

    # 9. Session Retrospective: "What We Learned" Report
    if not args.no_retrospective:
        repo_name = Path(args.repo_path).name or "Repository"
        learned_report = SessionRetrospectiveBuilder.build(result, repo_name=repo_name)
        console.print("")
        SessionRetrospectiveBuilder.print_terminal(learned_report)

        if args.save_learned:
            saved_md = SessionRetrospectiveBuilder.save_markdown(learned_report, args.save_learned)
            console.print(f"\n[bold green][OK] Exported 'What We Learned' Retrospective to:[/bold green] [cyan]{saved_md}[/cyan]")

    # 10. Cognitive Brain Notification
    if result.brain:
        console.print(
            f"[bold cyan][BRAIN][/bold cyan] Ingested session wisdom into Cognitive Brain "
            f"({len(result.brain.learned_skills)} skills, {len(result.brain.learned_rules)} rules codified and accredited)."
        )

    console.print("\n[bold green][SUCCESS] Full Cognitive Pipeline Execution Finished Successfully.[/bold green]\n")

if __name__ == "__main__":
    run_cli()
