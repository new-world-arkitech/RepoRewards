from __future__ import annotations

import datetime
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from repo_investigator.brain.models import (
    CognitiveBrain,
    RepositoryAttribution,
    LearnedSkill,
    LearnedRule,
    LearnedDeadEnd,
    ModelEvolutionStage,
)
from repo_investigator.models.archaeology import RepoArchaeology

if TYPE_CHECKING:
    from repo_investigator.orchestrator import PipelineResult

logger = logging.getLogger(__name__)
console = Console(highlight=False)

DEFAULT_BRAIN_DIR = Path.home() / ".flowmind"
DEFAULT_BRAIN_FILE = DEFAULT_BRAIN_DIR / "brain.json"

class BrainManager:
    """
    Manages FlowMind's persistent Cognitive Brain.
    Ingests learned architectural wisdom, workflows, and coding abilities
    from scanned repositories, attributing every skill and rule to the repository owner.
    """

    @classmethod
    def get_default_brain_path(cls) -> Path:
        return Path(os.getenv("FLOWMIND_BRAIN_PATH", str(DEFAULT_BRAIN_FILE)))

    @classmethod
    def load_brain(cls, brain_path: Optional[Path] = None) -> CognitiveBrain:
        path = brain_path or cls.get_default_brain_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return CognitiveBrain.model_validate(data)
            except Exception as e:
                logger.warning("Could not parse brain at %s: %s. Initializing fresh brain.", path, e)
        brain = CognitiveBrain()
        brain.evolution_stages = cls.get_foundational_stages()
        brain.current_generation = len(brain.evolution_stages)
        return brain

    @classmethod
    def save_brain(cls, brain: CognitiveBrain, brain_path: Optional[Path] = None) -> Path:
        path = brain_path or cls.get_default_brain_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        brain.last_updated = datetime.datetime.now(datetime.timezone.utc).isoformat()
        path.write_text(json.dumps(brain.model_dump(), indent=2), encoding="utf-8")
        logger.info("Saved Cognitive Brain with %d skills to %s", len(brain.learned_skills), path)
        return path

    @classmethod
    def extract_attribution(
        cls,
        repo_path: Path,
        archaeology: Optional[RepoArchaeology] = None,
        owner_override: Optional[str] = None,
    ) -> RepositoryAttribution:
        """
        Determines the true owner, primary author, and license of the scanned repository.
        """
        repo_dir = repo_path.resolve()
        repo_name = repo_dir.name or "Repository"
        owner = owner_override
        remote_url = None
        top_contributors: List[str] = []
        license_type = "Proprietary / Unspecified"

        # 1. Try Git remote origin URL (only if repo_dir itself contains a .git boundary)
        if (repo_dir / ".git").exists():
            try:
                res = subprocess.run(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                raw_url = res.stdout.strip()
                if raw_url:
                    remote_url = raw_url
                    # Match github.com/owner/repo or git@github.com:owner/repo
                    m = re.search(r"github\.com[:/]([a-zA-Z0-9._-]+)/([a-zA-Z0-9._-]+)", raw_url)
                    if m and not owner:
                        owner = m.group(1)
                        repo_name = m.group(2).removesuffix(".git")
            except Exception:
                pass

        # 2. Extract commit authors from archaeology
        if archaeology and archaeology.commits:
            author_counts: Dict[str, int] = {}
            for c in archaeology.commits:
                if c.author:
                    author_counts[c.author] = author_counts.get(c.author, 0) + 1
            sorted_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
            top_contributors = [a[0] for a in sorted_authors[:5]]
            if not owner and top_contributors:
                owner = top_contributors[0]

        # 3. Check pyproject.toml / package.json / LICENSE
        license_file = next((repo_dir / f for f in ["LICENSE", "LICENSE.txt", "LICENSE.md"] if (repo_dir / f).exists()), None)
        if license_file:
            content = license_file.read_text(encoding="utf-8", errors="replace")[:200].lower()
            if "mit" in content:
                license_type = "MIT"
            elif "apache" in content:
                license_type = "Apache-2.0"
            elif "bsd" in content:
                license_type = "BSD"
            elif "gpl" in content:
                license_type = "GPL"
            else:
                license_type = "Custom Open Source"

        if not owner:
            owner = os.getenv("USER") or os.getenv("USERNAME") or "Unknown Maintainer"

        statement = (
            f"Coding intelligence, patterns, and workflows synthesized from repository '{repo_name}', "
            f"owned/authored by {owner} under {license_type}."
        )

        return RepositoryAttribution(
            owner=owner,
            repo_name=repo_name,
            remote_url=remote_url,
            top_contributors=top_contributors,
            license_type=license_type,
            attribution_statement=statement,
            ingested_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    @classmethod
    def ingest_session(
        cls,
        result: PipelineResult,
        repo_path: Path,
        owner_override: Optional[str] = None,
        brain_path: Optional[Path] = None,
    ) -> CognitiveBrain:
        """
        Synthesizes the entire session's discoveries into the Cognitive Brain,
        accrediting all learned skills, rules, and dead-ends to the repository owner.
        """
        brain = cls.load_brain(brain_path)
        attribution = cls.extract_attribution(
            repo_path=repo_path,
            archaeology=result.archaeology,
            owner_override=owner_override,
        )

        repo_key = f"{attribution.owner}/{attribution.repo_name}"
        brain.attributions[repo_key] = attribution
        brain.total_repos_ingested = len(brain.attributions)

        new_skills: List[LearnedSkill] = []
        new_rules: List[LearnedRule] = []
        new_heuristics: List[str] = []

        # 1. Ingest Learned Architectural Rules
        for inv in result.task_spec.architectural_invariants:
            rule_id = f"{attribution.repo_name}-{inv.id}"
            if not any(r.rule_id == rule_id for r in brain.learned_rules):
                r_obj = LearnedRule(
                    rule_id=rule_id,
                    rule_statement=inv.rule,
                    enforcement_scope=inv.enforcement_scope,
                    rationale=f"Invariant established to protect {attribution.repo_name}'s domain boundaries.",
                    source_attribution=attribution,
                )
                brain.learned_rules.append(r_obj)
                new_rules.append(r_obj)

        # 2. Ingest Coding Abilities / Skills
        for d in result.task_spec.execution_directives:
            skill_id = f"{attribution.repo_name}-SKILL-{d.action_type.value}-{d.step_number}"
            if not any(s.skill_id == skill_id for s in brain.learned_skills):
                s_obj = LearnedSkill(
                    skill_id=skill_id,
                    skill_name=f"{d.action_type.value}: {d.target_file}",
                    description=d.instruction,
                    architectural_category=d.diff_strategy,
                    code_pattern_template=d.code_snippet_template or "# Invariant-compliant pattern",
                    source_attribution=attribution,
                )
                brain.learned_skills.append(s_obj)
                new_skills.append(s_obj)

        # 3. Ingest Ruled-Out Dead Ends
        for ro in result.deliberation.consensus_verdict.rejected_alternatives:
            brain.learned_dead_ends.append(
                LearnedDeadEnd(
                    attempted_approach=ro,
                    failure_mode="Excessive blast radius or cognitive debt",
                    rule_out_reason=f"Rejected by Council during {attribution.repo_name} deliberation.",
                    source_attribution=attribution,
                )
            )

        # 4. Formulate General Coding Heuristics
        hubs = result.archaeology.architectural_signals.get("architectural_hubs", [])
        if hubs:
            h1 = (
                f"[Source: {repo_key}] When converging on shared modules ({', '.join(hubs)}), "
                "always place callers behind an abstract protocol to contain blast radius."
            )
            if h1 not in brain.coding_heuristics:
                brain.coding_heuristics.append(h1)
                new_heuristics.append(h1)
        if result.archaeology.detected_cycles:
            h2 = f"[Source: {repo_key}] Never introduce direct mutual imports; decouple via dependency inversion."
            if h2 not in brain.coding_heuristics:
                brain.coding_heuristics.append(h2)
                new_heuristics.append(h2)

        # Deduplicate heuristics
        brain.coding_heuristics = list(dict.fromkeys(brain.coding_heuristics))[-20:]

        # 5. Formulate Model Evolution Stage & Contributor Capability Credit
        stage_num = len(brain.evolution_stages) + 1
        safe_owner_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", attribution.owner)
        stage_id = f"EVO-STAGE-{stage_num:03d}-{safe_owner_slug}"
        verdict_title = result.deliberation.consensus_verdict.title

        capability_unlocked = (
            f"Invariant Defense & Pattern Synthesis via {attribution.repo_name} ({verdict_title})"
        )
        stage_desc = (
            f"Model capabilities advanced through deep architectural and dialectic synthesis of "
            f"{attribution.owner}'s codebase ('{attribution.repo_name}'). Acquired {len(new_skills)} specialized "
            f"execution skills and {len(new_rules)} hard architectural invariants, elevating reasoning fidelity "
            f"for domain decoupling and safe AST transformation."
        )
        credit_statement = (
            f"FlowMind Model Evolution Stage {stage_num} is officially credited to {attribution.owner} "
            f"for structural innovations and engineering patterns derived from '{attribution.repo_name}' ({attribution.license_type})."
        )

        evolution_stage = ModelEvolutionStage(
            stage_id=stage_id,
            stage_number=stage_num,
            model_version=f"FlowMind-v1.{stage_num}.0-cognitive",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            credited_owner=attribution.owner,
            credited_repo=repo_key,
            license_type=attribution.license_type or "Unknown",
            capability_unlocked=capability_unlocked,
            stage_description=stage_desc,
            skills_gained=[s.skill_name for s in new_skills],
            rules_codified=[r.rule_statement for r in new_rules],
            heuristics_learned=new_heuristics,
            attribution_statement=credit_statement,
        )
        brain.evolution_stages.append(evolution_stage)
        brain.current_generation = len(brain.evolution_stages)

        cls.save_brain(brain, brain_path)
        return brain

    @classmethod
    def format_brain_prompt_prefix(cls, brain: CognitiveBrain, limit: int = 5) -> str:
        """
        Injects the brain's model evolution stages, accredited contributors,
        and learned heuristics into LLM reasoning prompts.
        """
        if not brain.learned_rules and not brain.coding_heuristics and not brain.evolution_stages:
            return ""

        lines = [
            "### FLOWMIND MODEL EVOLUTION & CONTRIBUTOR CREDIT LINEAGE:",
            "FlowMind's coding and reasoning capabilities have evolved across the following stages thanks to repository creators:",
        ]

        for stage in brain.evolution_stages[-limit:]:
            lines.append(
                f"- [Stage {stage.stage_number} | {stage.stage_id}] Credited Author: {stage.credited_owner} ({stage.credited_repo})\n"
                f"  * Capability Leap: {stage.capability_unlocked}\n"
                f"  * Official Credit: {stage.attribution_statement}"
            )

        lines.append("\n### CODIFIED ARCHITECTURAL RULES TO ENFORCE (LEARNED FROM AUTHORS):")
        for r in brain.learned_rules[-limit:]:
            lines.append(f"- [{r.rule_id}] {r.rule_statement} (Capability credited to {r.source_attribution.owner})")

        lines.append("\n### PROVEN CODING HEURISTICS (ATTRIBUTED TO REPOSITORY OWNERS):")
        for h in brain.coding_heuristics[-limit:]:
            lines.append(f"- {h}")

        lines.append(
            "\n### ATTRIBUTION DIRECTIVE FOR CODE SYNTHESIS:\n"
            "When generating or modifying code using these capabilities, include a concise attribution comment in the "
            "code docstring or header honoring the contributing repository author (e.g., '# Architectural pattern credited to {owner}')."
        )

        return "\n".join(lines)

    @classmethod
    def print_brain_inspect(cls, brain_path: Optional[Path] = None):
        """
        Renders a rich inspection table of the brain's knowledge, accredited owners, and learned skills.
        """
        brain = cls.load_brain(brain_path)

        console.print(
            Panel.fit(
                f"[bold cyan]FLOWMIND COGNITIVE BRAIN INSPECTION[/bold cyan]\n"
                f"Brain ID: [yellow]{brain.brain_id}[/yellow] | Current Generation: [bold magenta]Gen-{brain.current_generation}[/bold magenta]\n"
                f"Source Repos Ingested: [bold green]{brain.total_repos_ingested}[/bold green] | Evolution Stages: [bold gold1]{len(brain.evolution_stages)}[/bold gold1]\n"
                f"Learned Skills: [magenta]{len(brain.learned_skills)}[/magenta] | Codified Rules: [cyan]{len(brain.learned_rules)}[/cyan]",
                border_style="cyan",
            )
        )

        # 1. Model Evolution Stages & Contributor Capability Credits Table
        if brain.evolution_stages:
            evo_table = Table(title="🚀 Model Evolution Stages & Contributor Capability Credits", border_style="gold1")
            evo_table.add_column("Stage #", style="bold gold1", width=8)
            evo_table.add_column("Model Version", style="cyan", width=22)
            evo_table.add_column("Credited Author", style="bold green", width=20)
            evo_table.add_column("Source Repo", style="yellow", width=22)
            evo_table.add_column("Capability Leap Unlocked", style="white", width=42)
            evo_table.add_column("Official Credit Citation", style="dim", width=50)

            for stage in brain.evolution_stages:
                evo_table.add_row(
                    str(stage.stage_number),
                    stage.model_version,
                    stage.credited_owner,
                    stage.credited_repo,
                    stage.capability_unlocked,
                    stage.attribution_statement,
                )
            console.print(evo_table)

        # Accredited Owners Table
        if brain.attributions:
            attr_table = Table(title="🏛️ Accredited Repository Owners & Authors", border_style="green")
            attr_table.add_column("Repository Key", style="cyan", width=25)
            attr_table.add_column("Accredited Owner / Author", style="yellow", width=25)
            attr_table.add_column("License", style="white", width=12)
            attr_table.add_column("Official Attribution Statement", style="dim", width=55)

            for key, attr in brain.attributions.items():
                attr_table.add_row(key, attr.owner, attr.license_type, attr.attribution_statement)
            console.print(attr_table)

        # Learned Skills Table
        if brain.learned_skills:
            skill_table = Table(title="⚡ Learned Coding Skills & Abilities", border_style="blue")
            skill_table.add_column("Skill ID", style="cyan", width=30)
            skill_table.add_column("Skill Directive", style="white", width=40)
            skill_table.add_column("Attributed Source", style="yellow", width=25)

            for s in brain.learned_skills[-10:]:
                skill_table.add_row(s.skill_id, s.description[:60], s.source_attribution.owner)
            console.print(skill_table)

        # Learned Invariants Table
        if brain.learned_rules:
            rule_table = Table(title="🛡️ Codified Invariants & Architectural Rules", border_style="purple")
            rule_table.add_column("Rule ID", style="cyan", width=25)
            rule_table.add_column("Rule Statement", style="white", width=55)
            rule_table.add_column("Accredited Creator", style="yellow", width=20)

            for r in brain.learned_rules[-10:]:
                rule_table.add_row(r.rule_id, r.rule_statement, r.source_attribution.owner)
            console.print(rule_table)

    @classmethod
    def get_foundational_stages(cls) -> List[ModelEvolutionStage]:
        """
        Returns the foundational genesis evolution stages established by
        Cosmic Souls Of Sovereignty Inc., @new-world-arkitech, and collaborative AI research.
        """
        return [
            ModelEvolutionStage(
                stage_id="EVO-STAGE-001-cosmicsouls",
                stage_number=1,
                model_version="FlowMind-v1.0.0-cognitive",
                timestamp="2026-01-15T00:00:00Z",
                credited_owner="Cosmic Souls Of Sovereignty Inc. & @new-world-arkitech",
                credited_repo="new-world-arkitech/RepoRewards",
                license_type="MIT",
                capability_unlocked="Genesis Invariant Reasoning Engine & AST Verification Gate",
                stage_description=(
                    "Synthesized foundational AST pre-flight checks, AST mutation guardrails, "
                    "and deterministic verification gates preventing regression and cognitive drift across complex codebases."
                ),
                skills_gained=[
                    "AST Boundary Guardrail: Enforce semantic tree validity prior to file mutation",
                    "Static Invariant Enforcement: Codify and gate execution against architectural invariants",
                    "Deterministic Code Verification Gate: Verify diffs with pytest/unittest subprocesses",
                ],
                rules_codified=[
                    "Never mutate AST nodes without pre-flight invariant check",
                    "Maintain zero side-effects across module boundaries",
                ],
                heuristics_learned=[
                    "Always verify AST syntax integrity before committing diffs",
                    "Decouple callers via clean interface boundaries",
                ],
                attribution_statement=(
                    "FlowMind Model Evolution Stage 1 is officially credited to Cosmic Souls Of Sovereignty Inc. "
                    "& @new-world-arkitech for genesis engineering patterns and architectural invariant enforcement."
                ),
            ),
            ModelEvolutionStage(
                stage_id="EVO-STAGE-002-cosmicsouls",
                stage_number=2,
                model_version="FlowMind-v1.1.0-cognitive",
                timestamp="2026-02-01T00:00:00Z",
                credited_owner="Cosmic Souls Of Sovereignty Inc. & @new-world-arkitech",
                credited_repo="new-world-arkitech/RepoRewards",
                license_type="MIT",
                capability_unlocked="Dialectic Multi-Agent Council & Kleppmann Fencing Protocol",
                stage_description=(
                    "Engineered dialectic triad (Principal Architect, Chaos Engineer, Domain SRE) "
                    "with thesis-antithesis-synthesis deliberative consensus and Kleppmann fencing token state management."
                ),
                skills_gained=[
                    "Multi-Agent Dialectic Deliberation: Three distinct cognitive lenses analyzing architectural changes",
                    "Kleppmann Fencing State Synchronization: RFC 6902 JSON-patch asymmetric state bus with fencing tokens",
                    "Asymmetric Consensus Synthesis: Reconciling opposing hypotheses into an invariant-guarded directive",
                ],
                rules_codified=[
                    "All architecture transformations require triadic consensus",
                    "Active execution player must hold monotonic fencing token",
                ],
                heuristics_learned=[
                    "Never allow single-agent unilateral refactoring in critical shared paths",
                    "Evaluate adversarial chaos hypotheses before code generation",
                ],
                attribution_statement=(
                    "FlowMind Model Evolution Stage 2 is officially credited to Cosmic Souls Of Sovereignty Inc. "
                    "& @new-world-arkitech for multi-agent dialectic consensus protocols."
                ),
            ),
            ModelEvolutionStage(
                stage_id="EVO-STAGE-003-google-deepmind",
                stage_number=3,
                model_version="FlowMind-v1.2.0-cognitive",
                timestamp="2026-02-15T00:00:00Z",
                credited_owner="Google DeepMind / Gemma Team",
                credited_repo="google-deepmind/gemma",
                license_type="Apache-2.0 / Gemma Terms of Use",
                capability_unlocked="Gemma 3B Local Edge-Native Carrier Inference Engine",
                stage_description=(
                    "Synthesized carrier inference engine using lightweight, ultra-high-efficiency Gemma 3B weights "
                    "via OpenAI-compatible endpoints with structured XML deliberation parsing and deterministic fallback."
                ),
                skills_gained=[
                    "Gemma Carrier Engine Inference: High-throughput local reasoning on edge devices",
                    "Structured Deliberation XML Parsing: Extracting hypotheses and invariants from LLM streams",
                    "Zero-Cloud Privacy Execution: Offline architectural reviews without data leakage",
                ],
                rules_codified=[
                    "Ensure carrier models support structured XML tags for dialectic consensus",
                    "Gracefully fall back to local simulated carrier if remote endpoint is offline",
                ],
                heuristics_learned=[
                    "Lightweight 3B parameter models provide sufficient fidelity for invariant auditing when prompted with structured reasoning scaffolds",
                    "Enforce strict temperature control (<= 0.2) on architectural decisions",
                ],
                attribution_statement=(
                    "FlowMind Model Evolution Stage 3 is officially credited to Google DeepMind for open Gemma 3B "
                    "reasoning weights and edge-native model capabilities."
                ),
            ),
            ModelEvolutionStage(
                stage_id="EVO-STAGE-004-cosmicsouls",
                stage_number=4,
                model_version="FlowMind-v1.3.0-cognitive",
                timestamp="2026-03-01T00:00:00Z",
                credited_owner="Cosmic Souls Of Sovereignty Inc. & @new-world-arkitech",
                credited_repo="new-world-arkitech/RepoRewards",
                license_type="MIT",
                capability_unlocked="Autonomous GitHub REST API Ecosystem & Actions CI/CD Integration",
                stage_description=(
                    "Built native GitHub REST integration per official GitHub Docs REST Guides: "
                    "PR Scorecards, Commit Statuses, Check Runs, Webhook HMAC-SHA256 signature verification, "
                    "and marketplace-ready action containerization."
                ),
                skills_gained=[
                    "GitHub REST PR Review Automation: Automated inline review comments and markdown scorecards",
                    "HMAC-SHA256 Webhook Verification: Cryptographic request signing and validation",
                    "GitHub Check Run Lifecycle Management: Granular conclusion reporting on PR branches",
                    "Marketplace Action Packaging: Zero-dependency, pinned composite action execution",
                ],
                rules_codified=[
                    "Sign and verify all incoming webhooks using HMAC-SHA256 timing-safe comparison",
                    "All CI actions must execute deterministically without external undeclared dependencies",
                ],
                heuristics_learned=[
                    "Post structured PR scorecards with collapsible diffs to minimize developer cognitive load",
                    "Use Commit Status states (pending, success, failure) to prevent merge of unverified invariant violations",
                ],
                attribution_statement=(
                    "FlowMind Model Evolution Stage 4 is officially credited to Cosmic Souls Of Sovereignty Inc. "
                    "& @new-world-arkitech for GitHub Ecosystem orchestration."
                ),
            ),
        ]

    @classmethod
    def format_evolution_markdown(cls, brain: Optional[CognitiveBrain] = None) -> str:
        """
        Formats the public Model Evolution Ledger as GitHub Flavored Markdown.
        Deduplicates repeated test runs while preserving chronological integrity
        and full contributor accreditation.
        """
        b = brain or cls.load_brain()

        # Combine foundational stages with any recorded brain stages
        foundational = cls.get_foundational_stages()
        foundational_ids = {f.stage_id for f in foundational}

        existing_stages = list(b.evolution_stages)
        custom_stages = [s for s in existing_stages if s.stage_id not in foundational_ids]
        combined_stages = foundational + custom_stages

        # Deduplicate repeated identical stage snapshots (e.g. from repeated test runs)
        seen_keys = set()
        deduped_stages: List[ModelEvolutionStage] = []
        for s in combined_stages:
            key = (s.credited_owner, s.credited_repo, s.capability_unlocked)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_stages.append(s)

        # Re-number stages sequentially for continuous presentation
        normalized_stages: List[ModelEvolutionStage] = []
        for idx, s in enumerate(deduped_stages, start=1):
            s_copy = s.model_copy()
            s_copy.stage_number = idx
            normalized_stages.append(s_copy)

        lines = [
            "# 🧠 FlowMind Cognitive Model Evolution Ledger",
            "",
            "> **A permanent, publicly auditable record of cognitive model evolution stages, capability leaps, and accredited repository maintainers.**",
            ">",
            "> Maintained & Published by **Cosmic Souls Of Sovereignty Inc.** & `@new-world-arkitech`  ",
            "> Governed under the [MIT License](LICENSE)",
            "",
            "---",
            "",
            "## 🏛️ Philosophy & Architecture Attribution Charter",
            "",
            "FlowMind operates strictly on an **Attribution-First AI** doctrine:",
            "- **No Anonymous Mining**: Codebases and engineering architectures are not anonymous commodities. Structural patterns, design idioms, and domain invariants synthesized by FlowMind are formally accredited to the originating repository owners and contributors.",
            "- **Permanent Evolutionary Lineage**: When FlowMind ingests a codebase's topology, call graphs, churn hotspots, and dialectic resolutions, the model records a permanent, sequentially numbered **Evolution Stage**.",
            "- **Open & Auditable**: This ledger is publicly tracked and versioned in source control alongside releases and marketplace actions, ensuring total transparency into the model's capabilities and provenance.",
            "",
            "---",
            "",
            "## 📊 Model Evolution Stages Matrix",
            "",
            "| Stage | Model Version | Credited Maintainer / Entity | Source Repository | License | Capability Leap Unlocked | Recorded Date |",
            "|:---:|:---|:---|:---|:---:|:---|:---:|",
        ]

        for s in normalized_stages:
            date_str = s.timestamp.split("T")[0] if "T" in s.timestamp else s.timestamp[:10]
            repo_link = f"[{s.credited_repo}](https://github.com/{s.credited_repo})" if "/" in s.credited_repo else s.credited_repo
            lines.append(
                f"| `{s.stage_id}` | `{s.model_version}` | **{s.credited_owner}** | {repo_link} | `{s.license_type}` | {s.capability_unlocked} | {date_str} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 📜 Detailed Evolution Stage Dossiers",
            "",
        ])

        for s in normalized_stages:
            lines.append(f"### 🚀 Stage {s.stage_number:03d}: {s.capability_unlocked}")
            lines.append(f"- **Stage Identifier**: `{s.stage_id}`")
            lines.append(f"- **Model Version Tag**: `{s.model_version}`")
            lines.append(f"- **Accredited Maintainer**: **{s.credited_owner}**")
            lines.append(f"- **Source Repository**: `{s.credited_repo}` *(License: `{s.license_type}`)*")
            lines.append(f"- **Recorded Timestamp**: `{s.timestamp}`")
            lines.append(f"- **Official Attribution Citation**:")
            lines.append(f"  > 📜 *\"{s.attribution_statement}\"*")
            lines.append("")
            lines.append("#### 💡 Capability Leap & Structural Impact")
            lines.append(f"{s.stage_description}")
            lines.append("")

            if s.skills_gained:
                lines.append("#### ⚡ Acquired Execution Skills & Directives")
                for sk in s.skills_gained:
                    lines.append(f"- `{sk}`")
                lines.append("")

            if s.rules_codified:
                lines.append("#### 🛡️ Codified Architectural Invariants")
                for r in s.rules_codified:
                    lines.append(f"- `{r}`")
                lines.append("")

            if s.heuristics_learned:
                lines.append("#### 🧠 Synthesized Cognitive Heuristics")
                for h in s.heuristics_learned:
                    lines.append(f"- {h}")
                lines.append("")

            lines.append("---")
            lines.append("")

        lines.extend([
            "## 🛠️ How to Evolve FlowMind With Your Repository",
            "",
            "When you run FlowMind against your codebase or invoke the FlowMind GitHub Action in your CI/CD pipeline, your repository can contribute to the shared cognitive intelligence:",
            "",
            "```bash",
            "# Run FlowMind and accredit your engineering organization",
            "flowmind . --repo-owner \"Your Name or Org\" --export-evolution MODEL_EVOLUTION.md",
            "```",
            "",
            "To inspect the local cognitive brain state in your terminal:",
            "```bash",
            "flowmind brain",
            "```",
            "",
            "To export the public evolution stages ledger via CLI:",
            "```bash",
            "flowmind brain --export-evolution MODEL_EVOLUTION.md",
            "```",
            "",
            "---",
            "",
            "## 📜 Corporate Governance & Legal Notices",
            "",
            "FlowMind is sponsored, architected, and maintained by **Cosmic Souls Of Sovereignty Inc.** in collaboration with `@new-world-arkitech`.",
            "",
            "- **GitHub Organization / Profile**: [@new-world-arkitech](https://github.com/new-world-arkitech)",
            "- **Official Websites**: [cosmicsoul.org](https://cosmicsoul.org) | [new-world-arkitech.dev](https://new-world-arkitech.dev)",
            "- **Toll-Free Phone**: [833-3-COSMIC](tel:+18333267642) (`833-326-7642`)",
            "- **Legal & Licensing Inquiries**: [legal@cosmicsoul.org](mailto:legal@cosmicsoul.org)",
            "- **Lead Systems Architecture**: [arkitech@new-world-arkitech.dev](mailto:arkitech@new-world-arkitech.dev)",
            "- **Corporate Mailing Address**:  ",
            "  `3723 Greenville Ave PMB 78450`  ",
            "  `Dallas, TX 75206`  ",
            "  `United States of America`  ",
            "",
            "*Copyright © 2026 Cosmic Souls Of Sovereignty Inc. & new-world-arkitech. All rights reserved under the [MIT License](LICENSE).*",
            "",
        ])

        return "\n".join(lines)

    @classmethod
    def export_evolution_markdown(
        cls,
        output_path: Path,
        brain: Optional[CognitiveBrain] = None,
    ) -> Path:
        """
        Renders and writes the public Model Evolution Ledger to the specified markdown path.
        """
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        content = cls.format_evolution_markdown(brain)
        out_p.write_text(content, encoding="utf-8")
        logger.info("Successfully exported Model Evolution Ledger to %s", out_p)
        return out_p
