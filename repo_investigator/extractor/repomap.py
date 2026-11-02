from __future__ import annotations

import ast
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
import networkx as nx

logger = logging.getLogger(__name__)

# Supported language extensions for polyglot repository analysis
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".js": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
}

class MultiLanguageRepomapGenerator:
    """
    Universal Tree-Sitter & AST Topological PageRank Repomap Generator ("Game Film").
    Extracts central architectural hubs across polyglot files and budgets output
    to 2,048 tokens for GPU prompt KV-cache pre-computation.
    """

    def __init__(self, root_dir: Path | str, max_tokens: int = 2048):
        self.root_dir = Path(root_dir).resolve()
        self.max_tokens = max_tokens
        self.graph = nx.DiGraph()
        self.symbols_by_file: Dict[str, List[str]] = {}

    def analyze(self) -> str:
        """Parses repository files, constructs dependency graph, and formats ranked Game Film."""
        if not self.root_dir.exists():
            return "### AST REPOMAP / GAME FILM (Empty or Uninitialized Repository)"

        for root, dirs, files in os.walk(self.root_dir):
            # Exclude unwanted child subdirectories during traversal
            dirs[:] = [d for d in dirs if not d.startswith((".", "node_modules", "venv", "dist", "build"))]
            for f in files:
                p = Path(root) / f
                ext = p.suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    rel_p = str(p.relative_to(self.root_dir)).replace("\\", "/")
                    self._extract_file_symbols(p, rel_p, ext)

        return self._format_ranked_repomap()

    def _extract_file_symbols(self, file_path: Path, rel_path: str, ext: str):
        self.graph.add_node(rel_path)
        symbols: List[str] = []

        try:
            # Skip giant files (>2MB) to prevent memory bloating on bundled/generated assets
            if file_path.stat().st_size > 2 * 1024 * 1024:
                self.symbols_by_file[rel_path] = ["[Large asset skipped >2MB]"]
                return
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return

        if ext == ".py":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        symbols.append(f"Class {node.name}")
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(f"Def {node.name}()")
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        mod_target = node.module.replace(".", "/") + ".py"
                        self.graph.add_edge(rel_path, mod_target)
            except SyntaxError:
                pass
        else:
            # Polyglot regex extraction for TypeScript, Go, Rust, Java
            class_matches = re.findall(r"(?:class|interface|struct|type)\s+([A-Z]\w+)", content)
            func_matches = re.findall(r"(?:function|def|func|fn)\s+([a-zA-Z_]\w+)\s*\(", content)
            for c in class_matches[:4]:
                symbols.append(f"Type {c}")
            for fn in func_matches[:5]:
                symbols.append(f"Fn {fn}()")

        self.symbols_by_file[rel_path] = symbols

    def _format_ranked_repomap(self) -> str:
        if len(self.graph) == 0:
            return "### AST REPOMAP / GAME FILM (0 source modules detected)"

        try:
            pagerank_scores = nx.pagerank(self.graph, alpha=0.85)
        except Exception:
            pagerank_scores = {n: 1.0 / len(self.graph) for n in self.graph.nodes()}

        sorted_files = sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True)

        lines: List[str] = [
            "### AST REPOMAP / GAME FILM (Topological PageRank Ranked)",
        ]

        for file_path, score in sorted_files:
            syms = self.symbols_by_file.get(file_path, [])
            lines.append(f"Module: {file_path} (PageRank: {score:.4f})")
            for s in syms[:4]:
                lines.append(f"  {s}")

        full_text = "\n".join(lines)
        max_chars = self.max_tokens * 4
        truncation_suffix = "\n... [TRUNCATED TO 2048 TOKENS]"
        if len(full_text) > max_chars:
            cut_idx = max(0, max_chars - len(truncation_suffix))
            full_text = full_text[:cut_idx] + truncation_suffix

        return full_text
