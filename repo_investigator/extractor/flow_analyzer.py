from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set
import networkx as nx

from repo_investigator.models.archaeology import (
    ASTModule,
    ASTClass,
    ASTFunction,
    CallGraphEdge,
    RepoArchaeology,
)
from repo_investigator.extractor.git_archaeology import GitArchaeologyExtractor

class FlowASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, module_name: str):
        self.file_path = file_path
        self.module_name = module_name
        self.imports: List[str] = []
        self.classes: List[ASTClass] = []
        self.functions: List[ASTFunction] = []
        self.current_class: str | None = None
        self.current_function: str | None = None
        self.function_calls: Dict[str, List[str]] = {}

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            self.imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(f"{getattr(b.value, 'id', '')}.{b.attr}")

        old_class = self.current_class
        self.current_class = node.name
        
        methods: List[ASTFunction] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m_calls: List[str] = []
                for sub in ast.walk(item):
                    if isinstance(sub, ast.Call):
                        if isinstance(sub.func, ast.Name):
                            m_calls.append(sub.func.id)
                        elif isinstance(sub.func, ast.Attribute):
                            m_calls.append(sub.func.attr)

                args = [a.arg for a in item.args.args]
                methods.append(
                    ASTFunction(
                        name=f"{node.name}.{item.name}",
                        args=args,
                        docstring=ast.get_docstring(item),
                        line_start=item.lineno,
                        line_end=getattr(item, "end_lineno", item.lineno),
                        calls=m_calls,
                        is_async=isinstance(item, ast.AsyncFunctionDef),
                    )
                )

        doc = ast.get_docstring(node)
        self.classes.append(
            ASTClass(
                name=node.name,
                bases=bases,
                methods=methods,
                docstring=doc,
                line_start=node.lineno,
                line_end=getattr(node, "end_lineno", node.lineno),
            )
        )

        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self.current_class is None:
            calls: List[str] = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    if isinstance(sub.func, ast.Name):
                        calls.append(sub.func.id)
                    elif isinstance(sub.func, ast.Attribute):
                        calls.append(sub.func.attr)

            args = [a.arg for a in node.args.args]
            self.functions.append(
                ASTFunction(
                    name=node.name,
                    args=args,
                    docstring=ast.get_docstring(node),
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    calls=calls,
                    is_async=False,
                )
            )
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if self.current_class is None:
            calls: List[str] = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    if isinstance(sub.func, ast.Name):
                        calls.append(sub.func.id)
                    elif isinstance(sub.func, ast.Attribute):
                        calls.append(sub.func.attr)

            args = [a.arg for a in node.args.args]
            self.functions.append(
                ASTFunction(
                    name=node.name,
                    args=args,
                    docstring=ast.get_docstring(node),
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    calls=calls,
                    is_async=True,
                )
            )
        self.generic_visit(node)


class FlowTopologyAnalyzer:
    """
    Constructs dependency graphs, call flows, and topological metrics from code ASTs.
    """

    def __init__(self, repo_dir: str | Path):
        self.repo_dir = Path(repo_dir).resolve()
        self.git_extractor = GitArchaeologyExtractor(self.repo_dir)

    def analyze(self) -> RepoArchaeology:
        commits = self.git_extractor.extract_commits()
        hotspots = self.git_extractor.calculate_churn_hotspots(commits)

        modules: Dict[str, ASTModule] = {}
        dep_graph = nx.DiGraph()
        call_edges: List[CallGraphEdge] = []

        # Find all python files
        all_py_files = [
            p for p in self.repo_dir.glob("**/*.py")
            if not any(part.startswith(".") or part in ("venv", "__pycache__", "site-packages") for part in p.parts)
        ]

        # First pass: parse modules
        for py_path in all_py_files:
            rel_path = str(py_path.relative_to(self.repo_dir)).replace("\\", "/")
            mod_name = rel_path.replace("/", ".").removesuffix(".py")

            try:
                content = py_path.read_text(encoding="utf-8", errors="replace")
                parsed = ast.parse(content, filename=str(py_path))
                visitor = FlowASTVisitor(rel_path, mod_name)
                visitor.visit(parsed)

                internal_imports = []
                external_imports = []
                for imp in visitor.imports:
                    # Heuristic for internal vs external imports
                    first_segment = imp.split(".")[0]
                    if any((self.repo_dir / first_segment).exists() or (self.repo_dir / f"{first_segment}.py").exists() for _ in [0]):
                        internal_imports.append(imp)
                        dep_graph.add_edge(mod_name, imp)
                    else:
                        external_imports.append(imp)

                lines = content.count("\n") + 1
                modules[rel_path] = ASTModule(
                    file_path=rel_path,
                    module_name=mod_name,
                    imports=visitor.imports,
                    internal_imports=internal_imports,
                    external_imports=external_imports,
                    classes=visitor.classes,
                    functions=visitor.functions,
                    total_lines=lines,
                )

                # Collect calls
                for cls in visitor.classes:
                    for meth in cls.methods:
                        for target in meth.calls:
                            call_edges.append(CallGraphEdge(source=meth.name, target=target))
                for fn in visitor.functions:
                    for target in fn.calls:
                        call_edges.append(CallGraphEdge(source=fn.name, target=target))

            except Exception:
                continue

        # Detect dependency cycles
        detected_cycles: List[List[str]] = []
        try:
            cycles = list(nx.simple_cycles(dep_graph))
            detected_cycles = [list(c) for c in cycles]
        except Exception:
            pass

        # Identify central architectural hubs
        hubs = []
        if len(dep_graph) > 0:
            degrees = dict(dep_graph.degree())
            sorted_deg = sorted(degrees.items(), key=lambda x: x[1], reverse=True)
            hubs = [node for node, deg in sorted_deg[:5] if deg > 1]

        arch_signals = {
            "total_modules": len(modules),
            "dependency_cycles_count": len(detected_cycles),
            "architectural_hubs": hubs,
            "has_concurrency_markers": any("async" in m.file_path or any(f.is_async for f in m.functions) for m in modules.values()),
        }

        return RepoArchaeology(
            repo_path=str(self.repo_dir),
            branch="main",
            total_commits=len(commits),
            commits=commits,
            churn_hotspots=hotspots,
            modules=modules,
            call_graph_edges=call_edges,
            detected_cycles=detected_cycles,
            architectural_signals=arch_signals,
        )
