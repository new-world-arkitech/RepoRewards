from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Dict, Any, List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(highlight=False)

def check_python_version() -> Tuple[bool, str, str]:
    ver = sys.version_info
    ver_str = f"{ver.major}.{ver.minor}.{ver.micro}"
    if ver.major == 3 and ver.minor >= 10:
        return True, f"Python {ver_str}", "Compatible runtime environment."
    return False, f"Python {ver_str}", "FlowMind requires Python 3.10 or newer."

def check_git_installed() -> Tuple[bool, str, str]:
    git_path = shutil.which("git")
    if not git_path:
        return False, "Not Found", "Git is not installed or not found on system PATH. Install from https://git-scm.com/"
    try:
        res = subprocess.run(["git", "--version"], capture_output=True, text=True, check=True)
        version_str = res.stdout.strip()
        return True, version_str, f"Found at {git_path}"
    except Exception as e:
        return False, "Error running git", str(e)

def check_model_providers() -> Tuple[bool, str, str]:
    keys_found = []
    if os.getenv("ANTHROPIC_API_KEY"):
        keys_found.append("Anthropic (Claude)")
    if os.getenv("OPENAI_API_KEY"):
        keys_found.append("OpenAI (GPT-4o)")
    if os.getenv("GEMINI_API_KEY"):
        keys_found.append("Google (Gemini)")
    if os.getenv("GEMMA_ENDPOINT") or os.getenv("GEMMA_MODEL") or os.getenv("GEMMA_API_KEY"):
        keys_found.append("Gemma 3B (Local/Ollama/Cloud)")
    if os.getenv("SGLANG_ENDPOINT"):
        keys_found.append("SGLang/vLLM Cluster")

    if keys_found:
        return True, ", ".join(keys_found), "Live cloud LLM carrier(s) detected and ready."
    return True, "Simulated Cognitive Engine (Default)", "No API key configured. Offline high-fidelity simulated engine active (100% free)."

def check_optional_dependencies() -> List[Tuple[str, bool, str]]:
    deps = [
        ("FastAPI & Uvicorn (REST API Server)", "fastapi", "flowmind --serve"),
        ("Redis (Distributed State Bus)", "redis", "FLOWMIND_STATE_BUS_BACKEND=redis"),
        ("NATS (Distributed Message Bus)", "nats", "FLOWMIND_STATE_BUS_BACKEND=nats"),
        ("OpenTelemetry (Distributed Tracing)", "opentelemetry", "FLOWMIND_TELEMETRY_BACKEND=otel"),
    ]
    results = []
    for name, module, usage in deps:
        try:
            __import__(module)
            results.append((name, True, f"Installed & available for {usage}"))
        except ImportError:
            results.append((name, False, f"Not installed. (Optional for {usage})"))
    return results

def run_doctor() -> bool:
    """
    Executes a friendly system diagnostic and prints actionable setup advice.
    """
    console.print(
        Panel.fit(
            "[bold cyan]FLOWMIND SYSTEM DOCTOR[/bold cyan]\n"
            "[dim]Environment Diagnostics, Dependency Verification & Setup Healthcheck[/dim]",
            border_style="cyan",
        )
    )

    all_healthy = True

    # 1. Core Requirements Table
    table = Table(title="Core Prerequisites", border_style="blue")
    table.add_column("Component", style="cyan", width=25)
    table.add_column("Status", width=12)
    table.add_column("Detected Version / Value", style="white", width=35)
    table.add_column("Details & Guidance", style="dim", width=40)

    # Python
    py_ok, py_ver, py_msg = check_python_version()
    if not py_ok:
        all_healthy = False
    table.add_row(
        "Python Runtime",
        "[bold green]OK[/bold green]" if py_ok else "[bold red]ACTION[/bold red]",
        py_ver,
        py_msg,
    )

    # Git
    git_ok, git_ver, git_msg = check_git_installed()
    if not git_ok:
        all_healthy = False
    table.add_row(
        "Git Version Control",
        "[bold green]OK[/bold green]" if git_ok else "[bold red]ACTION[/bold red]",
        git_ver,
        git_msg,
    )

    # AI Models
    ai_ok, ai_prov, ai_msg = check_model_providers()
    table.add_row(
        "AI Reasoning Carrier",
        "[bold green]READY[/bold green]",
        ai_prov,
        ai_msg,
    )

    console.print(table)

    # 2. Optional Capabilities Table
    opt_table = Table(title="Optional Enterprise Features", border_style="magenta")
    opt_table.add_column("Feature", style="cyan", width=35)
    opt_table.add_column("Status", width=12)
    opt_table.add_column("Feature Guidance", style="dim", width=65)

    for name, ok, details in check_optional_dependencies():
        opt_table.add_row(
            name,
            "[bold green]ENABLED[/bold green]" if ok else "[dim yellow]OPTIONAL[/dim yellow]",
            details,
        )

    console.print(opt_table)

    # 3. Friendly Next Steps
    if all_healthy:
        console.print(
            Panel(
                "[bold green]✓ Your system is 100% ready to use FlowMind![/bold green]\n\n"
                "[bold white]Try running your first architectural scan:[/bold white]\n"
                "  [cyan]flowmind sample_repo --dry-run[/cyan]                 (Safe preview on demo repo)\n"
                "  [cyan]flowmind . --report-html report.html[/cyan]           (Generate interactive visual report)\n"
                "  [cyan]flowmind serve[/cyan]                                  (Launch web REST & streaming server)\n",
                title="Next Steps for Beginners",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]! A required component needs attention before running FlowMind.[/bold red]\n"
                "Please address the flagged items above (such as installing Git or updating Python).",
                title="Action Required",
                border_style="red",
            )
        )

    return all_healthy

if __name__ == "__main__":
    run_doctor()

