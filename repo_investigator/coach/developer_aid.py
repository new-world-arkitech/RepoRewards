from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from repo_investigator.coach.models import (
    CodeExplanation,
    DebugDiagnosis,
    ImplementationGuide,
)
from repo_investigator.llm.base import (
    BaseReasoningEngine,
    SimulatedCognitiveEngine,
    get_default_engine,
)

console = Console(highlight=False)

class DeveloperAid:
    """
    New Developer's AI Coach, Mentor, and Debugging Assistant.
    Provides plain-English code explanations, root-cause error debugging,
    architectural navigation, and step-by-step refactoring guides.
    """

    def __init__(self, engine: Optional[BaseReasoningEngine] = None):
        self.engine = engine or get_default_engine()

    def explain_file(
        self,
        file_path: str | Path,
        repo_root: Optional[Path] = None,
        symbol: Optional[str] = None,
    ) -> CodeExplanation:
        """
        Parses a file and explains its purpose, architectural role, gotchas,
        and usage in clear, beginner-friendly plain English.
        """
        root = Path(repo_root or ".").resolve()
        target = Path(file_path)
        full_path = target if target.is_absolute() else (root / target).resolve()

        if not full_path.exists():
            raise FileNotFoundError(f"Cannot explain file: '{full_path}' does not exist.")

        code_text = full_path.read_text(encoding="utf-8", errors="replace")
        rel_path = str(full_path.relative_to(root)) if full_path.is_relative_to(root) else str(full_path)

        # 1. Parse AST to extract structural facts
        try:
            tree = ast.parse(code_text)
            docstring = ast.get_docstring(tree) or ""
            classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
            functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
            imports = []
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        except SyntaxError as se:
            return CodeExplanation(
                file_path=rel_path,
                title=f"{full_path.name} (Syntax Error Detected)",
                plain_english_summary=f"This file currently contains a Python syntax error on line {se.lineno}: {se.msg}",
                key_responsibilities=["Needs syntax repair before code analysis can continue."],
                architectural_role="Unparsed Source Module",
                potential_gotchas=[f"Syntax error at line {se.lineno}: {se.text}"],
                beginner_usage_example="# Fix syntax error before importing",
                how_to_test="pytest will fail on this file until syntax is repaired.",
            )

        # 2. Check for common beginner gotchas via AST
        gotchas = []
        for node in ast.walk(tree):
            # Check mutable default args
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        gotchas.append(
                            f"Function '{node.name}' uses a mutable default argument ({type(default).__name__}). "
                            "This list/dict is shared across all function calls and can lead to strange bugs!"
                        )
            # Check bare except clauses
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    gotchas.append(
                        "Found a bare 'except:' clause. This catches everything, including KeyboardInterrupt (Ctrl+C), "
                        "making it hard to stop your program."
                    )
                elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    gotchas.append(
                        "Catching generic 'Exception'. Prefer catching specific errors (e.g. ValueError, KeyError) "
                        "so unexpected bugs aren't accidentally hidden."
                    )

        if any("db" in imp or "sql" in imp for imp in imports) and ("core" in rel_path or "domain" in rel_path):
            gotchas.append(
                "Direct database imports inside a core/domain folder! In clean architecture, core logic shouldn't "
                "depend directly on database tools."
            )

        # 3. If live LLM carrier available, enrich explanation
        if not isinstance(self.engine, SimulatedCognitiveEngine):
            prompt = (
                f"Explain the following Python file '{rel_path}' to a junior software engineer.\n"
                f"File content:\n```python\n{code_text[:4000]}\n```\n"
                "Return a JSON object with keys: title, plain_english_summary, key_responsibilities (list of strings), "
                "architectural_role, beginner_usage_example (string), how_to_test (string)."
            )
            system = "You are a friendly, expert software engineering mentor who explains code clearly with simple analogies."
            try:
                resp = self.engine.reason(prompt=prompt, system_prompt=system, response_format="json")
                data = json.loads(resp)
                return CodeExplanation(
                    file_path=rel_path,
                    symbol_name=symbol,
                    title=data.get("title", f"Module: {full_path.name}"),
                    plain_english_summary=data.get("plain_english_summary", docstring or "Utility module."),
                    key_responsibilities=data.get("key_responsibilities", classes + functions),
                    architectural_role=data.get("architectural_role", "Application Component"),
                    potential_gotchas=gotchas or ["No major anti-patterns detected in AST."],
                    beginner_usage_example=data.get("beginner_usage_example", f"from {full_path.stem} import {classes[0] if classes else '...' }"),
                    how_to_test=data.get("how_to_test", "Write unit tests using pytest."),
                )
            except Exception:
                pass

        # 4. Deterministic beginner-friendly explanation generator
        title = f"Module: {full_path.stem}"
        if classes:
            summary = (
                f"This file defines the core classes: {', '.join(classes)}. "
                f"It acts as a building block for handling application data and business rules."
            )
        elif functions:
            summary = (
                f"This file contains helper functions: {', '.join(functions)}. "
                "It performs specialized tasks without storing persistent internal state."
            )
        else:
            summary = "Configuration or data definitions module."

        responsibilities = []
        if docstring:
            responsibilities.append(f"Declared purpose: {docstring.splitlines()[0]}")
        for c in classes:
            responsibilities.append(f"Class '{c}': Manages data structure and behaviors.")
        for f in functions:
            responsibilities.append(f"Function '{f}()': Performs a specific operational step.")

        example_symbol = classes[0] if classes else (functions[0] if functions else "module")
        usage_example = (
            f"# Step 1: Import the component\n"
            f"from {full_path.stem} import {example_symbol}\n\n"
            f"# Step 2: Initialize or call it\n"
            f"instance = {example_symbol}()\n"
            f"# print(instance)\n"
        )

        how_to_test = (
            f"# In tests/test_{full_path.stem}.py:\n"
            f"import pytest\n"
            f"from {full_path.stem} import {example_symbol}\n\n"
            f"def test_{full_path.stem}_initialization():\n"
            f"    # Verify default state works without throwing exceptions\n"
            f"    obj = {example_symbol}()\n"
            f"    assert obj is not None\n"
        )

        return CodeExplanation(
            file_path=rel_path,
            symbol_name=symbol,
            title=title,
            plain_english_summary=summary,
            key_responsibilities=responsibilities,
            architectural_role="Domain / Utility Service",
            potential_gotchas=gotchas if gotchas else ["Clean AST: zero mutable default arguments or bare except blocks."],
            beginner_usage_example=usage_example,
            how_to_test=how_to_test,
        )

    def diagnose_error(
        self,
        error_text: str,
        repo_root: Optional[Path] = None,
    ) -> DebugDiagnosis:
        """
        Takes a raw Python error traceback or message, identifies the root cause,
        and generates a plain-English explanation with step-by-step fix instructions.
        """
        root = Path(repo_root or ".").resolve()

        # Parse exception type and message
        error_type = "Exception"
        error_msg = error_text.strip()
        implicated_file = None
        implicated_line = None

        # Regex for standard Python Traceback
        # File "...", line 42, in ...
        file_matches = re.findall(r'File\s+"([^"]+)",\s+line\s+(\d+)', error_text)
        if file_matches:
            last_file, last_line = file_matches[-1]
            implicated_file = last_file
            implicated_line = int(last_line)

        # Regex for exception name
        exc_match = re.search(r'([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception):\s*(.*)', error_text)
        if exc_match:
            error_type = exc_match.group(1)
            error_msg = exc_match.group(2).strip()

        # Educational explanations by error type
        explanations = {
            "AttributeError": (
                "You tried to access a property or method that does not exist on this object. "
                "Think of it like asking a Bicycle for a 'steering_wheel'—it simply doesn't have one!"
            ),
            "KeyError": (
                "You tried to look up a key in a dictionary that isn't there. "
                "Think of it like looking for a word in a dictionary that wasn't printed on the page."
            ),
            "TypeError": (
                "An operation or function was called with data of the wrong type. "
                "For example, trying to add a number and a string: 5 + 'apple'."
            ),
            "IndexError": (
                "You asked a list for an item at a position that doesn't exist. "
                "For example, asking a 3-item list for item #5."
            ),
            "NameError": (
                "Python encountered a variable or function name that has not been defined yet. "
                "Check for typos or make sure you defined the variable before this line."
            ),
            "SyntaxError": (
                "Python couldn't understand your code's grammar. "
                "Usually caused by a missing colon ':', unmatched parentheses '()', or wrong indentation."
            ),
            "ImportError": (
                "Python could not find the module or file you tried to import. "
                "Check if the file is spelled correctly or if you need to run 'pip install'."
            ),
            "ModuleNotFoundError": (
                "The requested Python package or file is not installed or not found on sys.path."
            ),
        }

        plain_explanation = explanations.get(
            error_type,
            f"An unexpected {error_type} occurred during execution. Python halted to protect state."
        )

        # Inspect implicated file context if accessible
        context_code = ""
        if implicated_file:
            imp_path = Path(implicated_file)
            if not imp_path.is_absolute():
                imp_path = (root / imp_path).resolve()
            if imp_path.exists():
                lines = imp_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if implicated_line and 1 <= implicated_line <= len(lines):
                    start_l = max(0, implicated_line - 3)
                    end_l = min(len(lines), implicated_line + 2)
                    context_code = "\n".join(
                        f"{i+1}: {'-> ' if i+1 == implicated_line else '   '}{lines[i]}"
                        for i in range(start_l, end_l)
                    )

        # Build step-by-step fix instructions
        fixes = []
        if error_type == "AttributeError":
            fixes.append(f"1. Check the exact spelling of the attribute you called: '{error_msg}'")
            fixes.append("2. Add a print(type(your_object), dir(your_object)) right before this line to see what methods it actually has.")
            fixes.append("3. If the object might sometimes be None, guard it: if obj is not None: obj.attribute")
        elif error_type == "KeyError":
            fixes.append("1. Use dict.get('key', default_value) instead of dict['key'] to avoid crashing when the key is missing.")
            fixes.append("2. Print dict.keys() right before this line to see what keys currently exist.")
        elif error_type == "TypeError":
            fixes.append("1. Verify the data types of your function arguments: print(type(arg)).")
            fixes.append("2. If expecting a number from user input or JSON, convert it: int(val) or float(val).")
        else:
            fixes.append("1. Inspect the stack trace lines above to see which of your functions called this line.")
            fixes.append("2. Place a breakpoint (breakpoint()) right before the failing line to inspect variables interactively.")

        prevention = (
            "Add a unit test in 'tests/' that specifically tests this scenario (especially edge cases like empty lists, "
            "None values, or missing dictionary keys) to make sure this error never happens again."
        )

        return DebugDiagnosis(
            error_type=error_type,
            error_message=error_msg,
            implicated_file=str(implicated_file) if implicated_file else None,
            implicated_line=implicated_line,
            plain_english_explanation=plain_explanation,
            root_cause_analysis=f"The program encountered {error_type} in {implicated_file or 'unknown file'}" + (f" at line {implicated_line}" if implicated_line else "") + f". Context:\n{context_code}" if context_code else f"{error_type}: {error_msg}",
            step_by_step_fix=fixes,
            code_diff_suggestion=f"# Recommended defensive pattern for {error_type}\ntry:\n    # execute statement\n    pass\nexcept {error_type} as err:\n    logger.warning('Safely caught %s: %s', type(err).__name__, err)\n",
            how_to_prevent_next_time=prevention,
        )

    def guide_feature(
        self,
        feature_description: str,
        repo_root: Optional[Path] = None,
    ) -> ImplementationGuide:
        """
        Guides a developer on how to add a new feature cleanly without breaking existing
        architectural boundaries, creating circular dependencies, or violating invariants.
        """
        root = Path(repo_root or ".").resolve()

        # Discover existing modules
        py_files = [str(p.relative_to(root)) for p in root.rglob("*.py") if not any(part.startswith(".") for part in p.parts)]

        # Determine best placement
        core_files = [f for f in py_files if "core" in f or "services" in f]
        adapter_files = [f for f in py_files if "api" in f or "gateway" in f or "db" in f]

        checklist = [
            f"1. Define the interface protocol first (in a decoupled module like 'interfaces.py').",
            f"2. Implement the pure business logic in a new or existing domain service.",
            f"3. Do NOT import database or external network libraries into core domain services.",
            f"4. Add an automated test in 'tests/' verifying that your new feature works.",
            f"5. Run 'flowmind . --dry-run' to ensure no new circular dependencies or invariant breaches were created.",
        ]

        starter_code = (
            f"\"\"\"New feature: {feature_description}\"\"\"\n\n"
            f"from typing import Any, Dict, Optional\n\n"
            f"class NewFeatureService:\n"
            f"    \"\"\"Encapsulates '{feature_description}' with decoupled invariants.\"\"\"\n\n"
            f"    def __init__(self, persistence_adapter: Optional[Any] = None):\n"
            f"        self._adapter = persistence_adapter\n\n"
            f"    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:\n"
            f"        if not isinstance(payload, dict):\n"
            f"            raise ValueError('Payload must be a dictionary')\n"
            f"        # Implement feature logic here\n"
            f"        return {{'status': 'SUCCESS', 'data': payload}}\n"
        )

        return ImplementationGuide(
            goal=feature_description,
            recommended_approach="Invariant-Guarded Adapter Pattern (Decoupled Domain Service)",
            files_to_modify=core_files[:2] if core_files else ["main.py"],
            files_to_create=["services/new_feature.py", "tests/test_new_feature.py"],
            architectural_rules_to_respect=[
                "INV-001: Domain logic must be free of direct database coupling.",
                "INV-002: Keep dependencies strictly acyclic (no circular import loops).",
                "INV-003: Maintain backward-compatible method signatures for existing callers.",
            ],
            step_by_step_checklist=checklist,
            starter_code_snippet=starter_code,
        )

    def print_explanation(self, explanation: CodeExplanation):
        """Renders the explanation in a gorgeous, clear, friendly Rich terminal format."""
        console.print(
            Panel.fit(
                f"[bold cyan]DEVELOPER'S AID: CODE EXPLANATION[/bold cyan]\n"
                f"[yellow]{explanation.title}[/yellow] ([dim]{explanation.file_path}[/dim])",
                border_style="cyan",
            )
        )

        console.print(Panel(explanation.plain_english_summary, title="💡 What Does This File Do?", border_style="green"))

        if explanation.key_responsibilities:
            resp_table = Table(title="Core Responsibilities & Components", border_style="blue")
            resp_table.add_column("Component / Task", style="white")
            for r in explanation.key_responsibilities:
                resp_table.add_row(r)
            console.print(resp_table)

        if explanation.potential_gotchas:
            gotcha_table = Table(title="⚠️ Watch Out For (Potential Gotchas & Anti-Patterns)", border_style="yellow")
            gotcha_table.add_column("Gotcha / Trap", style="yellow")
            for g in explanation.potential_gotchas:
                gotcha_table.add_row(g)
            console.print(gotcha_table)

        syntax_example = Syntax(explanation.beginner_usage_example, "python", theme="monokai", line_numbers=True)
        console.print(Panel(syntax_example, title="🚀 Beginner Usage Example", border_style="cyan"))

        syntax_test = Syntax(explanation.how_to_test, "python", theme="monokai", line_numbers=True)
        console.print(Panel(syntax_test, title="🧪 How to Test This File", border_style="magenta"))

    def print_diagnosis(self, diagnosis: DebugDiagnosis):
        """Renders an error diagnosis in an empathetic, clear Rich terminal format."""
        console.print(
            Panel.fit(
                f"[bold red]DEVELOPER'S AID: DEBUGGING ASSISTANT[/bold red]\n"
                f"Diagnosing: [bold white]{diagnosis.error_type}[/bold white]: [yellow]{diagnosis.error_message}[/yellow]",
                border_style="red",
            )
        )

        console.print(Panel(diagnosis.plain_english_explanation, title="📖 What Does This Error Mean?", border_style="blue"))

        console.print(Panel(diagnosis.root_cause_analysis, title="🔍 Root Cause Analysis", border_style="yellow"))

        fix_table = Table(title="🛠️ Step-by-Step Fix Instructions", border_style="green")
        fix_table.add_column("Step", style="white")
        for f in diagnosis.step_by_step_fix:
            fix_table.add_row(f)
        console.print(fix_table)

        if diagnosis.code_diff_suggestion:
            syntax_fix = Syntax(diagnosis.code_diff_suggestion, "python", theme="monokai", line_numbers=True)
            console.print(Panel(syntax_fix, title="💡 Suggested Defensive Code Pattern", border_style="cyan"))

        console.print(Panel(diagnosis.how_to_prevent_next_time, title="🛡️ How to Prevent This in the Future", border_style="purple"))

    def print_guide(self, guide: ImplementationGuide):
        """Renders an architectural implementation guide in the terminal."""
        console.print(
            Panel.fit(
                f"[bold green]DEVELOPER'S AID: FEATURE IMPLEMENTATION COACH[/bold green]\n"
                f"Goal: [bold white]{guide.goal}[/bold white]",
                border_style="green",
            )
        )

        console.print(Panel(f"Recommended Strategy: [bold cyan]{guide.recommended_approach}[/bold cyan]", title="📐 Architectural Strategy", border_style="cyan"))

        checklist_table = Table(title="📋 Step-by-Step Implementation Checklist", border_style="blue")
        checklist_table.add_column("Task", style="white")
        for step in guide.step_by_step_checklist:
            checklist_table.add_row(step)
        console.print(checklist_table)

        rules_table = Table(title="🛡️ Non-Negotiable Invariants to Preserve", border_style="yellow")
        rules_table.add_column("Invariant Rule", style="yellow")
        for rule in guide.architectural_rules_to_respect:
            rules_table.add_row(rule)
        console.print(rules_table)

        if guide.starter_code_snippet:
            syntax_starter = Syntax(guide.starter_code_snippet, "python", theme="monokai", line_numbers=True)
            console.print(Panel(syntax_starter, title="🚀 Starter Code Template", border_style="green"))

