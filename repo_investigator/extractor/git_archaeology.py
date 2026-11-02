from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from repo_investigator.models.archaeology import CommitRecord, ChurnHotspot

class GitArchaeologyExtractor:
    """
    Mines Git version history to extract developer intent, churn hotspots,
    and historical decision paths.
    """

    INTENT_PATTERNS = {
        "HACK_OR_WORKAROUND": re.compile(r"\b(hack|workaround|temp|temporary|quickfix|bandaid|kludge|todo: fix)\b", re.IGNORECASE),
        "REFACTORING": re.compile(r"\b(refactor|decouple|cleanup|reorganize|abstract|modularize|split)\b", re.IGNORECASE),
        "BUG_FIX": re.compile(r"\b(fix|bug|patch|issue|error|resolve|crash|flaky|failure)\b", re.IGNORECASE),
        "RACE_OR_CONCURRENCY": re.compile(r"\b(race condition|deadlock|mutex|lock|thread|concurrency|async|invalidation)\b", re.IGNORECASE),
        "PERFORMANCE": re.compile(r"\b(perf|performance|optimize|speed|latency|slow|cache|bottleneck)\b", re.IGNORECASE),
        "ARCHITECTURAL_PIVOT": re.compile(r"\b(migrate|redesign|deprecate|rewrite|pivot|transition)\b", re.IGNORECASE),
    }

    def __init__(self, repo_dir: str | Path):
        self.repo_dir = Path(repo_dir).resolve()

    def is_git_repo(self) -> bool:
        return (self.repo_dir / ".git").is_dir()

    def extract_commits(self, max_count: int = 50) -> List[CommitRecord]:
        """
        Parses commit history, extracting author thoughts, file diffs, and intent markers.
        """
        if not self.is_git_repo():
            return self._fallback_synthetic_commits()

        cmd = [
            "git", "log",
            f"-n{max_count}",
            "--pretty=format:COMMIT_START%n%H%n%an%n%ad%n%s%n%b%nCOMMIT_FILES",
            "--name-only",
            "--date=iso-strict"
        ]

        try:
            res = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, check=True)
            output = res.stdout
        except Exception:
            return self._fallback_synthetic_commits()

        commits: List[CommitRecord] = []
        raw_chunks = output.split("COMMIT_START\n")

        for chunk in raw_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            parts = chunk.split("COMMIT_FILES\n")
            meta_and_msg = parts[0].strip().split("\n")
            if len(meta_and_msg) < 4:
                continue

            commit_hash = meta_and_msg[0].strip()
            author = meta_and_msg[1].strip()
            date = meta_and_msg[2].strip()
            subject = meta_and_msg[3].strip()
            body = "\n".join(meta_and_msg[4:]).strip()
            full_msg = f"{subject}\n{body}".strip()

            files: List[str] = []
            if len(parts) > 1 and parts[1].strip():
                files = [f.strip() for f in parts[1].strip().split("\n") if f.strip()]

            # Classify intent & cognitive signals
            tags = []
            signals = []
            for tag_name, pattern in self.INTENT_PATTERNS.items():
                if pattern.search(full_msg):
                    tags.append(tag_name)
                    signals.append(f"Detected {tag_name} in commit: '{subject}'")

            commits.append(
                CommitRecord(
                    commit_hash=commit_hash,
                    author=author,
                    date=date,
                    message=full_msg,
                    files_changed=files,
                    intent_tags=tags,
                    cognitive_signals=signals,
                )
            )

        return commits

    def calculate_churn_hotspots(self, commits: List[CommitRecord]) -> List[ChurnHotspot]:
        """
        Identifies files that undergo disproportionate modification,
        indicating cognitive friction or architectural instability.
        """
        churn_counts: Dict[str, int] = {}
        for c in commits:
            for f in c.files_changed:
                churn_counts[f] = churn_counts.get(f, 0) + 1

        hotspots: List[ChurnHotspot] = []
        total_commits = max(len(commits), 1)

        for file_path, count in churn_counts.items():
            # Higher churn ratio indicates architectural hotspot
            risk_score = round(min(count / total_commits * 10.0, 10.0), 2)
            hotspots.append(
                ChurnHotspot(
                    file_path=file_path,
                    modification_count=count,
                    risk_score=risk_score
                )
            )

        hotspots.sort(key=lambda h: h.modification_count, reverse=True)
        return hotspots

    def _fallback_synthetic_commits(self) -> List[CommitRecord]:
        """
        Fallback when running in a directory without an active git repository.
        Inspects existing code files and creates baseline archaeological markers.
        """
        commits: List[CommitRecord] = []
        py_files = list(self.repo_dir.glob("**/*.py"))
        if py_files:
            commits.append(
                CommitRecord(
                    commit_hash="INIT_LOCAL_STATE",
                    author="Current Workspace Developer",
                    date="2026-10-30T00:00:00Z",
                    message="Initial repository baseline scan (local unversioned state)",
                    files_changed=[str(p.relative_to(self.repo_dir)) for p in py_files[:15]],
                    intent_tags=["BASELINE_INGESTION"],
                    cognitive_signals=["Directory analyzed directly without git history metadata"],
                )
            )
        return commits
