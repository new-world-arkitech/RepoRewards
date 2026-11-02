A2A Bench Rotation: Agent Implementation Spec
Use this blueprint to configure an adaptive Agent-to-Agent (A2A) runtime with a Completion Effort Node, Asymmetric State Bus, Zero-LLM Coach Telemetry, and Warm Bench Substitutions.
1. Adaptive Execution Tiers (Completion Effort Node)
Route every incoming task through a lightweight classifier (e.g., RouteLLM mf or a small fast model) and monitor live execution to promote tasks dynamically:
Tier
Mode
Trigger Thresholds
Runtime & Memory Configuration
Tier 1
Direct Execution
Est. steps 5, static state, minimal tool output
Stateless LLM call; implicit cache; max_turns = 5 circuit breaker.
Tier 2
Managed Single Agent
Est. steps 6--15, bounded file edits, moderate stdout
Single LangGraph loop; 5m cache TTL; local stdout truncation; max_retries = 2.
Tier 3
Full A2A Bench Rotation
Est. steps >15, high state mutability, heavy compiler/log noise
Isolated LangGraph subgraphs + Temporal (Continue-As-New at 15 steps); NATS KV State Bus; 1h cache TTL / RadixAttention; Firecracker CoW sandbox.

Mid-Game Promotion Rule (Tier 2  Tier 3)
Automatically pause a Tier 2 agent and promote it to Tier 3 if any of the following occur:
Step count reaches step >= 8 without task completion.
Cumulative raw tool stdout exceeds 12,000 tokens.
The agent logs 2 consecutive test/build failures or tool errors.
2. Prompt Prefix Ordering (Zero-Latency KV-Cache Handoff)
To ensure incoming Bench Players reuse $100\%$ of the pre-computed GPU KV-cache (via SGLang RadixAttention, vLLM + LMCache, or Cloud API ttl: "1h" cache breakpoints), enforce this strict prompt ordering across all roster agents:
+-----------------------------------------------------------------------+
| 1. SYSTEM INSTRUCTIONS & TOOL SCHEMAS (Static across all stints)      |
+-----------------------------------------------------------------------+
| 2. AST REPOMAP / "GAME FILM" (2,048-token Tree-Sitter PageRank map)   |
+-----------------------------------------------------------------------+
| 3. SHARED STATE BUS LEDGER (Milestones, Active Blockers, Dead-Ends)   |
|    <-- [INSERT 1-HOUR CACHE BREAKPOINT HERE]                          |
+-----------------------------------------------------------------------+
| 4. PRIVATE AGENT SCRATCHPAD (Cleared to zero on every substitution)   |
+-----------------------------------------------------------------------+


3. State Bus Ledger & Diff Schema (NATS KV + RFC 6902)
Store the canonical state in NATS KV (or Redis) and broadcast updates at 5-step "Timeouts" or substitutions using RFC 6902 JSON Patch. Every write to the State Bus or sandbox vsock daemon must validate the monotonic Kleppmann Fencing Token (fencing_token >= max_accepted_token).
Canonical State Bus Object (state_bus.json)
{
  "workflow_id": "task-9482",
  "fencing_token": 82,
  "active_player": "bench_agent_2",
  "stint_number": 2,
  "goal": "Refactor auth middleware to support rotating JWT keys without breaking session tests.",
  "verified_milestones": [
    {
      "step": 5,
      "summary": "Extracted key parser into src/auth/keys.py; unit tests passing.",
      "commit_or_snapshot_id": "cow-snap-001"
    }
  ],
  "active_blockers": [
    "Integration test test_token_refresh fails with 401 when legacy token format is passed."
  ],
  "dead_ends_log": [
    {
      "stint": 1,
      "attempted_play": "Modified jwt.decode() options to disable signature verification on fallback.",
      "failure_reason": "Triggered security linter failure and broke 4 downstream permission tests.",
      "rule_out": "Do not bypass signature verification in decode(); handle legacy key lookup in KeyProvider."
    }
  ]
}


Example Timeout Update (RFC 6902 JSON Patch)
[
  { "op": "test", "path": "/fencing_token", "value": 82 },
  { "op": "replace", "path": "/active_blockers/0", "value": "Resolved 401; now debugging race condition in Redis key cache." },
  { "op": "add", "path": "/dead_ends_log/-", "value": {
      "stint": 2,
      "attempted_play": "Added threading.Lock() around async Redis client call.",
      "failure_reason": "Blocked event loop and caused test timeout.",
      "rule_out": "Use asyncio.Lock() or Redis atomic Lua script instead of synchronous threading primitives."
    }
  }
]


4. Zero-LLM Coach Telemetry & Substitution Protocol
Run the Fast Deterministic Reflex Loop after every tool turn (0 LLM tokens). Trigger an immediate substitution when the composite health score drops below 0.50 or when stint_steps == 15:

Shealth=0.40(Srep)+0.35(Sstag)+0.25(Scycle)

Tool Repetition (Srep): Hash (tool_name, canonical_args).
<3 identical calls =1.0 | 3 calls =0.5 | 6 calls (or identical 400 error retry) =0.0.
Reasoning Stagnation (Sstag): Compute (BigramJaccard,SequenceMatcher) between consecutive assistant thoughts.
Similarity <0.85=1.0 | Similarity 0.85=0.0.
Call Graph Cycle (Scycle): Run DFS on trace spans and check if domain state (modified files or failing test count) changed.
State progressed =1.0 | Cycle detected with zero state change =0.0.
Atomic Substitution Checklist (Coach Node)
Increment Fencing Token: Atomically increment fencing_token (nn+1) and write max_accepted_token = n+1 to the NATS KV bucket and Firecracker vsock daemon before revoking the Starter.
Sandbox Handoff: If the Starter left the workspace dirty/broken, restore the last verified Firecracker CoW snapshot (~28ms); otherwise, transfer the live vsock session to the incoming Bench Player.
Distill Scratchpad: Run a fast model (e.g., Haiku / small local model) over the outgoing Starter's last 5 steps to append an RFC 6902 patch to verified_milestones and dead_ends_log.
Dispatch Bench Player: Invoke the isolated Bench Agent subgraph with the shared cached prefix and a clean private scratchpad.
5. Drop-In System Prompts
A. Starter / Bench Player System Prompt
You are an autonomous execution agent operating in a Tier 3 A2A Bench Rotation runtime.
Your current Fencing Token is {{fencing_token}} (Stint #{{stint_number}}).

### RULES OF ENGAGEMENT
1. TRUST THE STATE BUS: The `SHARED STATE BUS LEDGER` contains verified milestones and the `dead_ends_log` from prior stints. Treat all verified milestones as ground truth. Do NOT re-verify completed work unless a test explicitly fails.
2. NEVER REPEAT DEAD ENDS: Review `dead_ends_log` before selecting a tool. Any attempt to repeat a ruled-out approach will trigger an automatic Coach substitution.
3. STAY FOCUSED ON ACTIVE BLOCKERS: Execute clean, incremental tool calls to resolve the first item in `active_blockers`.
4. RESPECT FENCING: Include `fencing_token: {{fencing_token}}` in all tool calls. If a tool returns `FENCING_TOKEN_REJECTED`, halt execution immediately.


B. Coach Distiller Prompt (Run Only at 5-Step Timeouts or Substitutions)
You are the State Coach Distiller for an A2A Bench Rotation runtime.
Compress the outgoing agent's raw scratchpad from the last {{step_count}} steps into an RFC 6902 JSON Patch updating the State Bus Ledger.

### DISTILLATION RULES
1. NO RAW LOGS: Strip all terminal stdout, stack traces, and file dumps. Keep only exact symbol names, file paths, and root causes.
2. VERIFIED MILESTONES ONLY: Only add a milestone if a test passed, a build succeeded, or a file change was verified.
3. CAPTURE NEGATIVE PATHS: If the agent tried an approach that failed or looped, append a concise entry to `/dead_ends_log/-` specifying `attempted_play`, `failure_reason`, and a clear `rule_out` directive for the next Bench Player.
4. OUTPUT FORMAT: Return strictly a valid RFC 6902 JSON Patch array.


