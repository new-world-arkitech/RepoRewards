from __future__ import annotations

import difflib
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple

from repo_investigator.bench_rotation.models import (
    HealthScoreResult,
    DeadEndRecord,
    VerifiedMilestone,
)

class ZeroLLMCoach:
    """
    Zero-LLM Coach Telemetry & Reflex Loop Engine.
    Executes a fast deterministic reflex loop after every tool turn using 0 LLM tokens.
    Evaluates health score:
        Shealth = 0.40(Srep) + 0.35(Sstag) + 0.25(Scycle)
    Triggers an immediate Warm Bench Substitution if Shealth < 0.50 or stint_steps >= 15.
    """

    @staticmethod
    def compute_tool_repetition_score(
        call_history: List[Tuple[str, Any, Optional[int]]],
    ) -> float:
        """
        Tool Repetition (Srep):
        Hash (tool_name, canonical_args).
        <3 identical calls = 1.0 | 3 calls = 0.5 | >=6 calls (or identical 400 error retry) = 0.0
        """
        if not call_history:
            return 1.0

        hashes: List[str] = []
        consecutive_error_hashes: List[str] = []

        for item in call_history:
            tool_name = str(item[0]) if len(item) > 0 else "unknown"
            args = item[1] if len(item) > 1 else {}
            status_code = item[2] if len(item) > 2 else None

            try:
                canonical_args = json.dumps(args, sort_keys=True, default=str)
            except Exception:
                canonical_args = repr(args)[:1024]

            h = hashlib.sha256(f"{tool_name}:{canonical_args}".encode("utf-8")).hexdigest()
            hashes.append(h)

            if status_code in (400, 500, "ERROR", "FAILED"):
                consecutive_error_hashes.append(h)
            else:
                consecutive_error_hashes.clear()

            # Immediate failure on identical error retry
            if len(consecutive_error_hashes) >= 2 and consecutive_error_hashes[-1] == consecutive_error_hashes[-2]:
                return 0.0

        # Frequency analysis of calls in recent window (last 10 turns)
        window = hashes[-10:] if len(hashes) > 10 else hashes
        counts: Dict[str, int] = {}
        for h in window:
            counts[h] = counts.get(h, 0) + 1

        max_reps = max(counts.values()) if counts else 0

        if max_reps < 3:
            return 1.0
        elif max_reps == 3:
            return 0.5
        elif max_reps == 4:
            return 0.33
        elif max_reps == 5:
            return 0.17
        else:
            return 0.0

    @staticmethod
    def compute_reasoning_stagnation_score(thought_history: List[str]) -> float:
        """
        Reasoning Stagnation (Sstag):
        Compute max(BigramJaccard, SequenceMatcher) between consecutive assistant thoughts.
        Similarity < 0.85 = 1.0 | Similarity >= 0.85 = 0.0
        """
        if len(thought_history) < 2:
            return 1.0

        t1 = thought_history[-2].strip().lower()
        t2 = thought_history[-1].strip().lower()

        if not t1 or not t2:
            return 1.0

        # Defensive ceiling on sequence comparison to guarantee sub-millisecond reflex latency
        MAX_COMPARE_CHARS = 4000
        t1_cmp = t1[:MAX_COMPARE_CHARS]
        t2_cmp = t2[:MAX_COMPARE_CHARS]

        # 1. Bigram Jaccard Similarity
        words1 = t1_cmp.split()
        words2 = t2_cmp.split()

        bigrams1 = set(zip(words1[:-1], words1[1:])) if len(words1) > 1 else {t1_cmp}
        bigrams2 = set(zip(words2[:-1], words2[1:])) if len(words2) > 1 else {t2_cmp}

        union = bigrams1 | bigrams2
        intersection = bigrams1 & bigrams2
        jaccard = len(intersection) / len(union) if union else 0.0

        # 2. SequenceMatcher Similarity
        seq_matcher_ratio = difflib.SequenceMatcher(None, t1_cmp, t2_cmp).ratio()

        max_similarity = max(jaccard, seq_matcher_ratio)

        if max_similarity < 0.85:
            return 1.0
        return 0.0

    @staticmethod
    def compute_call_graph_cycle_score(
        action_history: List[str],
        domain_progress_history: List[int],
    ) -> float:
        """
        Call Graph Cycle (Scycle):
        Run cycle detection on trace spans and check if domain state
        (modified files count or progress score) changed.
        State progressed = 1.0 | Cycle detected with zero state change = 0.0
        """
        if len(action_history) < 3:
            return 1.0

        # Check for cycles in recent action spans (e.g. A -> B -> A)
        last_action = action_history[-1]
        prior_indices = [i for i, a in enumerate(action_history[:-1]) if a == last_action]

        if not prior_indices:
            return 1.0

        most_recent_prev_idx = prior_indices[-1]
        cycle_length = len(action_history) - 1 - most_recent_prev_idx

        # If cycle detected, check whether domain state progressed during the cycle
        if cycle_length >= 1:
            initial_domain_state = (
                domain_progress_history[most_recent_prev_idx]
                if most_recent_prev_idx < len(domain_progress_history)
                else 0
            )
            current_domain_state = domain_progress_history[-1] if domain_progress_history else 0

            if current_domain_state <= initial_domain_state:
                # Cycle with zero state change detected
                return 0.0

        return 1.0

    def evaluate_health(
        self,
        stint_steps: int,
        step_number: int,
        call_history: List[Tuple[str, Any, Optional[int]]],
        thought_history: List[str],
        action_history: List[str],
        domain_progress_history: List[int],
    ) -> HealthScoreResult:
        """
        Evaluates Shealth = 0.40(Srep) + 0.35(Sstag) + 0.25(Scycle).
        Triggers substitution if Shealth < 0.50 or stint_steps >= 15.
        """
        s_rep = self.compute_tool_repetition_score(call_history)
        s_stag = self.compute_reasoning_stagnation_score(thought_history)
        s_cycle = self.compute_call_graph_cycle_score(action_history, domain_progress_history)

        s_health = round(0.40 * s_rep + 0.35 * s_stag + 0.25 * s_cycle, 4)

        substitution_triggered = False
        trigger_reason: Optional[str] = None

        if stint_steps >= 15:
            substitution_triggered = True
            trigger_reason = f"Stint step limit reached (15 steps Continue-As-New). Shealth={s_health:.2f}."
        elif s_health < 0.50:
            substitution_triggered = True
            reasons = []
            if s_rep < 0.5:
                reasons.append("Tool repetition detected")
            if s_stag < 0.85:
                reasons.append("Reasoning thought stagnation detected")
            if s_cycle < 1.0:
                reasons.append("Cyclic call pattern with zero state change detected")
            reason_str = ", ".join(reasons) if reasons else "Composite health degraded"
            trigger_reason = f"Composite health score dropped below 0.50 ({s_health:.2f} < 0.50): {reason_str}."

        return HealthScoreResult(
            s_rep=round(s_rep, 3),
            s_stag=round(s_stag, 3),
            s_cycle=round(s_cycle, 3),
            s_health=s_health,
            substitution_triggered=substitution_triggered,
            trigger_reason=trigger_reason,
            step_number=step_number,
            stint_steps=stint_steps,
        )

    @staticmethod
    def distill_scratchpad(
        stint_number: int,
        traces: List[Any],
        current_fencing_token: int,
        current_blockers: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        State Coach Distiller:
        Compresses the outgoing agent's raw scratchpad from the last 5 steps into
        an RFC 6902 JSON Patch updating the State Bus Ledger.
        Rules:
        1. NO RAW LOGS: Strip terminal stdout, stack traces, and dumps.
        2. VERIFIED MILESTONES ONLY: Only add milestone if test passed or verified.
        3. CAPTURE NEGATIVE PATHS: Append dead ends to /dead_ends_log/-.
        """
        patches: List[Dict[str, Any]] = [
            {"op": "test", "path": "/fencing_token", "value": current_fencing_token}
        ]

        # Scan traces for verified milestones and negative dead ends
        for t in traces:
            step_num = getattr(t, "step_number", 1)
            target = getattr(t, "target_file", "unknown")
            action = getattr(t, "action_type", "ACTION")
            ast_ok = getattr(t, "ast_validation_passed", True)
            err = getattr(t, "error_message", None)

            if ast_ok and not err:
                summary = f"Verified clean {action} on {target}; AST validation passed."
                patches.append({
                    "op": "add",
                    "path": "/verified_milestones/-",
                    "value": {
                        "step": step_num,
                        "summary": summary,
                        "commit_or_snapshot_id": f"cow-snap-{step_num:03d}",
                    },
                })
            elif err or not ast_ok:
                failure = err or "AST syntax self-audit failure"
                patches.append({
                    "op": "add",
                    "path": "/dead_ends_log/-",
                    "value": {
                        "stint": stint_number,
                        "attempted_play": f"Attempted {action} on {target}",
                        "failure_reason": failure[:120],
                        "rule_out": f"Do not repeat {action} on {target} without pre-validating syntax and interfaces.",
                    },
                })

        # Update blockers if provided
        if current_blockers:
            patches.append({
                "op": "replace",
                "path": "/active_blockers",
                "value": current_blockers,
            })

        return patches

