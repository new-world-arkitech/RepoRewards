import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from repo_investigator.bench_rotation.models import (
    CanonicalStateBus,
    VerifiedMilestone,
    DeadEndRecord,
)
from repo_investigator.bench_rotation.prompt_cache import (
    PromptPrefixManager,
    CACHE_BREAKPOINT_MARKER,
)

def test_prompt_prefix_hierarchy_and_cache_breakpoint():
    state_bus = CanonicalStateBus(
        workflow_id="wf-100",
        fencing_token=42,
        active_player="bench_agent_1",
        stint_number=2,
        goal="Enforce boundary isolation",
        verified_milestones=[
            VerifiedMilestone(step=1, summary="Extracted interface", commit_or_snapshot_id="snap-1")
        ],
        active_blockers=["Fix failing test in auth"],
        dead_ends_log=[
            DeadEndRecord(
                stint=1,
                attempted_play="Bypass check",
                failure_reason="Security breach",
                rule_out="Never bypass check",
            )
        ],
    )

    full_prompt = PromptPrefixManager.assemble_full_roster_prompt(
        fencing_token=42,
        stint_number=2,
        state_bus=state_bus,
        call_graph_edges=[("core", "db"), ("api", "core")],
        modules={"core": None, "db": None, "api": None},
        private_scratchpad="Initial observation for step 2",
    )

    # Validate ordering of all 4 layers and the cache breakpoint
    assert PromptPrefixManager.validate_prefix_ordering(full_prompt) is True

    # Check exact cache breakpoint marker placement
    idx_layer1 = full_prompt.find("1. SYSTEM INSTRUCTIONS & TOOL SCHEMAS")
    idx_layer2 = full_prompt.find("2. AST REPOMAP / GAME FILM")
    idx_layer3 = full_prompt.find("3. SHARED STATE BUS LEDGER")
    idx_marker = full_prompt.find(CACHE_BREAKPOINT_MARKER)
    idx_layer4 = full_prompt.find("4. PRIVATE AGENT SCRATCHPAD")

    assert idx_layer1 < idx_layer2 < idx_layer3 < idx_marker < idx_layer4

    # Verify content inside layers
    assert "Fencing Token is 42" in full_prompt
    assert "Stint #2" in full_prompt
    assert "Extracted interface" in full_prompt
    assert "Never bypass check" in full_prompt
    assert "Initial observation for step 2" in full_prompt

def test_repomap_token_budget_boundary():
    # Build large module set
    large_modules = {f"module_{i}": None for i in range(500)}
    edges = [(f"module_{i}", f"module_{i+1}") for i in range(499)]

    repomap = PromptPrefixManager.build_ast_repomap_layer(
        call_graph_edges=edges,
        modules=large_modules,
        max_tokens=2048,
    )

    # 1 token ~= 4 chars, 2048 tokens * 4 chars = 8192 chars max
    assert len(repomap) <= 2048 * 4

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-vv"]))

