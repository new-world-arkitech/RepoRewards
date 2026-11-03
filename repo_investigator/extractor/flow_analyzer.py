from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set
import networkx as nx

from repo_investigator.models.archaeology import (
    ASTModule,
    ASTClass,
    ASTFunction,
    CallGraphEdge,
    RepoArchaeology,
    InCodeCognitiveMarker,
    MartinPackageMetrics,
)
from repo_investigator.extractor.git_archaeology import GitArchaeologyExtractor

class FlowASTVisitor(ast.NodeVisitor):
    COGNITIVE_MARKER_REGEX = re.compile(
        r"#\s*(TODO|FIXME|HACK|XXX|WORKAROUND|BUG|TEMP|CAUTION|DEPRECATED)\b[:\s]*(.*)",
        re.IGNORECASE,
    )

    def __init__(self, file_path: str, module_name: str, raw_content: str = ""):
        self.file_path = file_path
        self.module_name = module_name
        self.raw_content = raw_content
        self.imports: List[str] = []
        self.classes: List[ASTClass] = []
        self.functions: List[ASTFunction] = []
        self.cognitive_markers: List[InCodeCognitiveMarker] = []
        self.abstract_classes_count: int = 0
        self.current_class: str | None = None
        self.current_function: str | None = None
        self.function_calls: Dict[str, List[str]] = {}

        # Scan in-code cognitive debt & compromise markers
        if raw_content:
            for line_idx, line in enumerate(raw_content.splitlines(), start=1):
                match = self.COGNITIVE_MARKER_REGEX.search(line)
                if match:
                    cat = match.group(1).upper()
                    text = match.group(2).strip() or line.strip()
                    self.cognitive_markers.append(
                        InCodeCognitiveMarker(
                            category=cat,
                            text=text,
                            line_number=line_idx,
                            file_path=file_path,
                        )
                    )

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
        
        is_abstract = any(b in ("ABC", "Protocol") or "Protocol" in b or "ABC" in b for b in bases)
        methods: List[ASTFunction] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in getattr(item, "decorator_list", []):
                    dec_name = getattr(dec, "id", getattr(dec, "attr", ""))
                    if "abstractmethod" in dec_name:
                        is_abstract = True
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

        if is_abstract:
            self.abstract_classes_count += 1

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


def classify_architectural_layer(path: str, module_name: str) -> str:
    """Classifies a Python module into its semantic architectural tier."""
    tokens = set(re.split(r"[/._\s\\]+", f"{path.lower()} {module_name.lower()}"))
    if tokens & {"api", "cli", "route", "routes", "endpoint", "endpoints", "controller", "controllers", "gateway", "gateways", "server", "main", "web", "ui"}:
        return "INGRESS"
    if tokens & {"service", "services", "use_case", "use_cases", "workflow", "workflows", "orchestrator", "handler", "pipeline", "coach"}:
        return "APPLICATION"
    if tokens & {"entity", "entities", "model", "models", "domain", "core", "rule", "rules", "spec", "schema", "schemas"}:
        return "DOMAIN"
    if tokens & {"db", "database", "storage", "redis", "repo", "repository", "client", "http", "network", "adapter", "adapters", "nats", "llm", "integration"}:
        return "INFRASTRUCTURE"
    return "APPLICATION"


class FlowTopologyAnalyzer:
    """
    Constructs dependency graphs, call flows, and topological metrics from code ASTs.
    """

    LAYER_RANK = {
        "INGRESS": 4,
        "APPLICATION": 3,
        "DOMAIN": 2,
        "INFRASTRUCTURE": 1,
        "UNCLASSIFIED": 2,
    }

    def __init__(self, repo_dir: str | Path):
        self.repo_dir = Path(repo_dir).resolve()
        self.git_extractor = GitArchaeologyExtractor(self.repo_dir)

    def analyze(self) -> RepoArchaeology:
        commits = self.git_extractor.extract_commits()
        hotspots = self.git_extractor.calculate_churn_hotspots(commits)

        modules: Dict[str, ASTModule] = {}
        abstract_counts: Dict[str, int] = {}
        dep_graph = nx.DiGraph()
        call_edges: List[CallGraphEdge] = []

        # Find all python files, filtering out internal dot-directories and virtualenvs
        all_py_files = []
        for p in self.repo_dir.glob("**/*.py"):
            rel_parts = p.relative_to(self.repo_dir).parts
            if not any(part.startswith(".") or part in ("venv", "__pycache__", "site-packages", "node_modules") for part in rel_parts):
                all_py_files.append(p)

        # First pass: parse modules
        for py_path in all_py_files:
            rel_path = str(py_path.relative_to(self.repo_dir)).replace("\\", "/")
            mod_name = rel_path.replace("/", ".").removesuffix(".py")

            try:
                content = py_path.read_text(encoding="utf-8", errors="replace")
                parsed = ast.parse(content, filename=str(py_path))
                visitor = FlowASTVisitor(rel_path, mod_name, raw_content=content)
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
                layer = classify_architectural_layer(rel_path, mod_name)
                friction_density = round(len(visitor.cognitive_markers) / max(lines, 1), 4)

                modules[rel_path] = ASTModule(
                    file_path=rel_path,
                    module_name=mod_name,
                    imports=visitor.imports,
                    internal_imports=internal_imports,
                    external_imports=external_imports,
                    classes=visitor.classes,
                    functions=visitor.functions,
                    total_lines=lines,
                    architectural_layer=layer,
                    cognitive_markers=visitor.cognitive_markers,
                    cognitive_friction_density=friction_density,
                )
                abstract_counts[rel_path] = visitor.abstract_classes_count

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

        # Compute Robert C. Martin package metrics (Ca, Ce, I, A, D)
        zone_of_pain: List[str] = []
        zone_of_uselessness: List[str] = []
        for rel_path, mod in modules.items():
            m_name = mod.module_name
            ca = dep_graph.in_degree(m_name) if dep_graph.has_node(m_name) else 0
            ce = dep_graph.out_degree(m_name) if dep_graph.has_node(m_name) else 0
            total_c = ca + ce

            instability = round(ce / total_c, 3) if total_c > 0 else 0.5
            total_classes = len(mod.classes)
            abstractness = round(abstract_counts.get(rel_path, 0) / total_classes, 3) if total_classes > 0 else 0.0
            distance = round(abs(abstractness + instability - 1.0), 3)

            is_zop = (instability < 0.35 and abstractness < 0.25 and ca >= 2)
            is_zou = (instability > 0.70 and abstractness > 0.75 and ca == 0)

            if is_zop:
                zone_of_pain.append(mod.file_path)
            if is_zou:
                zone_of_uselessness.append(mod.file_path)

            mod.package_metrics = MartinPackageMetrics(
                afferent_coupling=ca,
                efferent_coupling=ce,
                instability=instability,
                abstractness=abstractness,
                distance_from_main_sequence=distance,
                in_zone_of_pain=is_zop,
                in_zone_of_uselessness=is_zou,
            )

        # Detect Inverted Architectural Layer Boundary Leaks
        layer_inversions: List[Dict[str, str]] = []
        for u, v in dep_graph.edges():
            u_mod = next((m for m in modules.values() if m.module_name == u), None)
            v_mod = next((m for m in modules.values() if m.module_name == v), None)
            if u_mod and v_mod:
                if u_mod.architectural_layer == "DOMAIN" and v_mod.architectural_layer in ("INFRASTRUCTURE", "INGRESS"):
                    layer_inversions.append({
                        "source_module": u_mod.file_path,
                        "target_module": v_mod.file_path,
                        "violation": f"Domain Layer ({u_mod.file_path}) imports {v_mod.architectural_layer} ({v_mod.file_path})",
                    })
                elif u_mod.architectural_layer == "APPLICATION" and v_mod.architectural_layer == "INGRESS":
                    layer_inversions.append({
                        "source_module": u_mod.file_path,
                        "target_module": v_mod.file_path,
                        "violation": f"Application Layer ({u_mod.file_path}) imports Ingress Layer ({v_mod.file_path})",
                    })

        arch_signals = {
            "total_modules": len(modules),
            "dependency_cycles_count": len(detected_cycles),
            "architectural_hubs": hubs,
            "has_concurrency_markers": any("async" in m.file_path or any(f.is_async for f in m.functions) for m in modules.values()),
            "zone_of_pain_modules": zone_of_pain,
            "zone_of_uselessness_modules": zone_of_uselessness,
            "layer_boundary_inversions": layer_inversions,
            "total_in_code_cognitive_markers": sum(len(m.cognitive_markers) for m in modules.values()),
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
