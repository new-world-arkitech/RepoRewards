from __future__ import annotations

import html

def render_dashboard_html() -> str:
    """
    Renders a standalone, high-performance, client-facing single-page application (SPA)
    dashboard for FlowMind's REST API and autonomous cognitive engine.
    Matches the exact aesthetic, typography, and color tokens of the official GitHub Pages site.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>FlowMind Autonomous Architecture Cockpit | Local Engine</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🧠</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #101620;
            --surface: #171F2B;
            --surface-hover: #1E2838;
            --ink: #E6EBF2;
            --muted: #9AA6B6;
            --line: #2A3443;
            --accent: #8FA3FF;
            --accent-glow: rgba(143, 163, 255, 0.15);
            --on-accent: #101620;
            --ok: #4FC3A1;
            --bad: #FF8A80;
            --gold: #F59E0B;
            --code: #0C121A;
            --purple: #C084FC;
            --radius: 8px;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            background-color: var(--bg);
            color: var(--ink);
            font-family: "Instrument Sans", system-ui, -apple-system, sans-serif;
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }
        h1, h2, h3, h4 {
            font-family: "Bricolage Grotesque", "Instrument Sans", sans-serif;
            line-height: 1.15;
            letter-spacing: -0.02em;
            margin: 0 0 0.5rem 0;
            color: var(--ink);
        }
        code, pre, .mono {
            font-family: "JetBrains Mono", ui-monospace, monospace;
        }
        a { color: var(--accent); text-decoration: none; transition: opacity 0.15s; }
        a:hover { opacity: 0.85; text-decoration: underline; }
        :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

        /* HEADER */
        header {
            position: sticky;
            top: 0;
            z-index: 50;
            background: rgba(16, 22, 32, 0.92);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--line);
            padding: 0 1.5rem;
        }
        .header-wrap {
            max-width: 1200px;
            margin: 0 auto;
            height: 4rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1.5rem;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            text-decoration: none;
            color: var(--ink);
        }
        .brand:hover { text-decoration: none; opacity: 1; }
        .brand-logo {
            font: 800 1.35rem "Bricolage Grotesque", sans-serif;
            letter-spacing: -0.03em;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .brand-badge {
            background: var(--accent);
            color: var(--on-accent);
            font-family: "JetBrains Mono", monospace;
            padding: 0.18rem 0.5rem;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0;
        }
        .model-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            background: var(--surface);
            border: 1px solid var(--line);
            padding: 0.35rem 0.75rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--ink);
        }
        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--ok);
            box-shadow: 0 0 0 rgba(79, 195, 161, 0.4);
            animation: pulse-green 1.8s infinite;
        }
        @keyframes pulse-green {
            0% { box-shadow: 0 0 0 0 rgba(79, 195, 161, 0.7); }
            70% { box-shadow: 0 0 0 8px rgba(79, 195, 161, 0); }
            100% { box-shadow: 0 0 0 0 rgba(79, 195, 161, 0); }
        }
        .header-links {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        .header-links a {
            color: var(--muted);
            font-size: 0.85rem;
            font-weight: 500;
        }
        .header-links a:hover { color: var(--ink); text-decoration: none; }

        /* BUTTONS */
        .btn {
            font-family: "Instrument Sans", sans-serif;
            font-weight: 600;
            font-size: 0.875rem;
            padding: 0.55rem 1.1rem;
            border-radius: 6px;
            border: 1px solid var(--line);
            background: var(--surface);
            color: var(--ink);
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            transition: all 0.15s ease;
        }
        .btn:hover {
            border-color: var(--ink);
            background: var(--surface-hover);
            text-decoration: none;
        }
        .btn.primary {
            background: var(--accent);
            border-color: var(--accent);
            color: var(--on-accent);
        }
        .btn.primary:hover {
            background: #a3b4ff;
            border-color: #a3b4ff;
        }
        .btn.sm {
            padding: 0.35rem 0.75rem;
            font-size: 0.8rem;
        }
        .btn.danger {
            border-color: var(--bad);
            color: var(--bad);
        }
        .btn.danger:hover {
            background: var(--bad);
            color: #fff;
        }

        /* CONTAINER & TABS */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem 1.5rem 5rem;
        }
        .nav-tabs {
            display: flex;
            gap: 0.5rem;
            border-bottom: 1px solid var(--line);
            margin-bottom: 2rem;
            overflow-x: auto;
            padding-bottom: 0.25rem;
        }
        .nav-tab {
            background: transparent;
            border: 1px solid transparent;
            color: var(--muted);
            padding: 0.65rem 1.25rem;
            font-size: 0.92rem;
            font-weight: 600;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.15s;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .nav-tab:hover {
            color: var(--ink);
            background: rgba(255, 255, 255, 0.03);
        }
        .nav-tab.active {
            color: var(--on-accent);
            background: var(--accent);
            border-color: var(--accent);
        }

        /* CARDS */
        .card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            padding: 1.75rem;
            margin-bottom: 1.5rem;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
            flex-wrap: wrap;
            gap: 0.75rem;
        }
        .card-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin: 0;
        }

        /* FORMS & INPUTS */
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.25rem;
            margin-bottom: 1.25rem;
        }
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }
        .form-group label {
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        input[type="text"], select, textarea {
            background: var(--code);
            border: 1px solid var(--line);
            border-radius: 6px;
            color: var(--ink);
            font-family: "JetBrains Mono", monospace;
            font-size: 0.88rem;
            padding: 0.65rem 0.85rem;
            transition: border-color 0.15s;
            width: 100%;
        }
        input[type="text"]:focus, select:focus, textarea:focus {
            border-color: var(--accent);
            outline: none;
        }

        /* HUD METRICS */
        .hud-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 1rem;
            margin-bottom: 1.75rem;
        }
        .hud-card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            padding: 1.25rem;
        }
        .hud-label {
            font-size: 0.78rem;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.35rem;
        }
        .hud-val {
            font: 800 2.2rem/1 "Bricolage Grotesque", sans-serif;
            color: var(--ink);
            margin-bottom: 0.35rem;
        }
        .hud-val.accent { color: var(--accent); }
        .hud-val.ok { color: var(--ok); }
        .hud-val.gold { color: var(--gold); }
        .hud-val.purple { color: var(--purple); }

        /* LOG TERMINAL */
        .terminal-box {
            background: var(--code);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            padding: 1.25rem;
            margin-top: 1.25rem;
        }
        .terminal-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.82rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid var(--line);
            margin-bottom: 0.75rem;
        }
        .log-box {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.82rem;
            line-height: 1.6;
            color: #d1d5db;
            height: 280px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-all;
        }

        /* TABLES */
        .table-responsive {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }
        th {
            text-align: left;
            padding: 0.75rem 1rem;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--muted);
            border-bottom: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.02);
        }
        td {
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--line);
            color: var(--ink);
            vertical-align: middle;
        }
        tr:hover td {
            background: rgba(255, 255, 255, 0.015);
        }

        /* STATUS BADGES */
        .badge {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.72rem;
            font-weight: 600;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            display: inline-block;
        }
        .badge-COMPLETED { background: rgba(79, 195, 161, 0.15); color: var(--ok); border: 1px solid var(--ok); }
        .badge-RUNNING { background: rgba(143, 163, 255, 0.15); color: var(--accent); border: 1px solid var(--accent); }
        .badge-FAILED { background: rgba(255, 138, 128, 0.15); color: var(--bad); border: 1px solid var(--bad); }
        .badge-PENDING { background: rgba(154, 166, 182, 0.15); color: var(--muted); border: 1px solid var(--line); }

        .result-box {
            background: var(--code);
            border: 1px solid var(--line);
            border-radius: var(--radius);
            padding: 1.25rem;
            margin-top: 1rem;
        }

        .tab-content { display: none; }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <header>
        <div class="header-wrap">
            <a href="/" class="brand">
                <span class="brand-logo">🧠 FLOWMIND</span>
                <span class="brand-badge">CLIENT DASHBOARD</span>
            </a>
            <div style="display: flex; align-items: center; gap: 1rem;">
                <div class="model-pill">
                    <div class="pulse-dot"></div>
                    <span>_beautifulDATA (Ollama 8000)</span>
                </div>
                <div class="header-links">
                    <a href="http://127.0.0.1:8000/docs" target="_blank">Swagger API</a>
                    <a href="https://new-world-arkitech.github.io/RepoRewards/" target="_blank" class="btn sm">🌐 Wall of Evolution</a>
                </div>
            </div>
        </div>
    </header>

    <div class="container">
        <!-- NAVIGATION TABS -->
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchNav('tab-investigate', this)">⚡ Run Investigation</button>
            <button class="nav-tab" onclick="switchNav('tab-workflows', this)">📋 Active Workflows</button>
            <button class="nav-tab" onclick="switchNav('tab-coach', this)">🎓 Developer Coach</button>
            <button class="nav-tab" onclick="switchNav('tab-brain', this)">🧠 Cognitive Brain & Ledger</button>
        </div>

        <!-- TAB 1: RUN INVESTIGATION -->
        <div id="tab-investigate" class="tab-content active">
            <div class="card">
                <div class="card-header">
                    <div>
                        <h2 class="card-title">Autonomous Archaeology & Deliberation Pipeline</h2>
                        <span style="font-size: 0.85rem; color: var(--muted);">Dispatches multi-agent deliberation, AST flow analysis, Conway author entropy, and A2A bench rotation</span>
                    </div>
                </div>

                <form id="investigate-form" onsubmit="handleStartInvestigation(event)">
                    <div class="form-grid">
                        <div class="form-group" style="grid-column: 1 / -1;">
                            <label for="repo-path">Repository Target (Path or Remote URL)</label>
                            <input type="text" id="repo-path" value="sample_repo" placeholder="e.g. . or https://github.com/The-Arkitech/OMNI-3 or sample_repo" required>
                        </div>
                        <div class="form-group">
                            <label for="tier-select">Execution Tier</label>
                            <select id="tier-select">
                                <option value="auto">Auto (Completion Effort Node Classifier)</option>
                                <option value="1">Tier 1: Direct Single Agent (Fastest)</option>
                                <option value="2">Tier 2: Managed Verification Single Agent</option>
                                <option value="3">Tier 3: Multi-Agent A2A Bench Rotation</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="model-select">Reasoning Carrier Engine</label>
                            <select id="model-select">
                                <option value="gemma">_beautifulDATA:latest (Local Ollama)</option>
                                <option value="anthropic">Anthropic Claude 3.5 Sonnet</option>
                                <option value="openai">OpenAI GPT-4o</option>
                                <option value="gemini">Google Gemini 1.5 Pro</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="repo-owner">Accredited Contributor / Maintainer (Optional)</label>
                            <input type="text" id="repo-owner" placeholder="Auto-inferred from Git remote or author history">
                        </div>
                    </div>
                    <div style="display: flex; gap: 1rem; align-items: center; margin-top: 1.25rem; flex-wrap: wrap;">
                        <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer; color: var(--muted); font-size: 0.9rem;">
                            <input type="checkbox" id="dry-run" checked> Dry Run (Safe AST analysis without modifying files on disk)
                        </label>
                        <button type="submit" class="btn primary" id="start-btn">⚡ Dispatch Investigation Pipeline</button>
                    </div>
                </form>

                <div id="live-console" style="display: none;">
                    <div class="terminal-box">
                        <div class="terminal-head">
                            <span class="mono"><b id="live-status-title">PIPELINE RUNNING...</b></span>
                            <div id="live-actions" style="display: none; gap: 0.5rem;">
                                <button class="btn sm" onclick="openReportHtml()">📊 View Full HTML Audit Report</button>
                                <button class="btn sm" onclick="openRetrospectiveMd()">🎓 View Retrospective Brief</button>
                            </div>
                        </div>
                        <div class="log-box" id="log-output">Connecting to workflow stream...</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 2: ACTIVE WORKFLOWS -->
        <div id="tab-workflows" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Autonomous Execution Workflows</h2>
                    <button class="btn sm" onclick="refreshWorkflows()">🔄 Refresh</button>
                </div>
                <div class="table-responsive">
                    <table id="workflows-table">
                        <thead>
                            <tr>
                                <th>Workflow ID</th>
                                <th>Target Repository</th>
                                <th>Status</th>
                                <th>Tier</th>
                                <th>Active Player</th>
                                <th>Fencing Token</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="workflows-tbody">
                            <tr><td colspan="7" style="text-align: center; color: var(--muted);">Loading workflows...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 3: DEVELOPER AID COACH -->
        <div id="tab-coach" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div>
                        <h2 class="card-title">Developer AI Coach & Invariant Debugger</h2>
                        <span style="font-size: 0.85rem; color: var(--muted);">Powered by _beautifulDATA: AST Explanations &bull; Traceback Diagnosis &bull; Clean Architecture Guides</span>
                    </div>
                </div>

                <div style="display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap;">
                    <button class="btn sm active" onclick="switchCoach('coach-explain', this)">📖 Explain File</button>
                    <button class="btn sm" onclick="switchCoach('coach-debug', this)">🩺 Diagnose Error</button>
                    <button class="btn sm" onclick="switchCoach('coach-guide', this)">🗺️ Implementation Guide</button>
                </div>

                <!-- Coach: Explain -->
                <div id="coach-explain" class="coach-pane">
                    <div class="form-group" style="margin-bottom: 1rem;">
                        <label for="explain-file-input">Target File Path</label>
                        <input type="text" id="explain-file-input" value="sample_repo/rewards_processor.py" placeholder="e.g. sample_repo/rewards_processor.py">
                    </div>
                    <button class="btn primary" onclick="handleExplainFile()">Explain in Plain English</button>
                    <div id="explain-result" class="result-box" style="display: none;"></div>
                </div>

                <!-- Coach: Debug -->
                <div id="coach-debug" class="coach-pane" style="display: none;">
                    <div class="form-group" style="margin-bottom: 1rem;">
                        <label for="debug-error-input">Python Error Text or Traceback</label>
                        <textarea id="debug-error-input" rows="4" placeholder="AttributeError: 'NoneType' object has no attribute 'split'"></textarea>
                    </div>
                    <button class="btn primary" onclick="handleDebugError()">Diagnose Error & Get Fix</button>
                    <div id="debug-result" class="result-box" style="display: none;"></div>
                </div>

                <!-- Coach: Guide -->
                <div id="coach-guide" class="coach-pane" style="display: none;">
                    <div class="form-group" style="margin-bottom: 1rem;">
                        <label for="guide-feature-input">Feature Description</label>
                        <input type="text" id="guide-feature-input" value="Add Redis caching to rewards calculation" placeholder="Describe the feature you want to build">
                    </div>
                    <button class="btn primary" onclick="handleGuideFeature()">Generate Architectural Implementation Guide</button>
                    <div id="guide-result" class="result-box" style="display: none;"></div>
                </div>
            </div>
        </div>

        <!-- TAB 4: COGNITIVE BRAIN & LINEAGE -->
        <div id="tab-brain" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <div>
                        <h2 class="card-title">Cognitive Brain: Contributor Attribution & Model Evolution</h2>
                        <span style="font-size: 0.85rem; color: var(--muted);">Live episodic memory accredited to open-source repository maintainers</span>
                    </div>
                    <button class="btn sm" onclick="loadBrainData()">🔄 Refresh Brain</button>
                </div>

                <div class="hud-grid" id="brain-stats"></div>
                
                <h3 style="font-size: 1.15rem; margin: 1.5rem 0 0.75rem 0; color: var(--ink);">🚀 Model Evolution Stages (Attributed Capability Leaps)</h3>
                <div class="table-responsive" style="margin-bottom: 2rem;">
                    <table>
                        <thead>
                            <tr>
                                <th>Stage #</th>
                                <th>Model Version</th>
                                <th>Accredited Maintainer</th>
                                <th>Source Repo</th>
                                <th>Capability Leap Unlocked</th>
                            </tr>
                        </thead>
                        <tbody id="evolution-tbody">
                            <tr><td colspan="5" style="text-align: center; color: var(--muted);">Loading evolution stages...</td></tr>
                        </tbody>
                    </table>
                </div>

                <h3 style="font-size: 1.15rem; margin: 1.5rem 0 0.75rem 0; color: var(--ink);">⚡ Learned Architectural Skills</h3>
                <div class="table-responsive">
                    <table>
                        <thead>
                            <tr>
                                <th>Skill ID</th>
                                <th>Directive Action</th>
                                <th>Source Attribution</th>
                            </tr>
                        </thead>
                        <tbody id="skills-tbody">
                            <tr><td colspan="3" style="text-align: center; color: var(--muted);">Loading learned skills...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentWorkflowId = null;

        function switchNav(tabId, btn) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            btn.classList.add('active');

            if (tabId === 'tab-workflows') refreshWorkflows();
            if (tabId === 'tab-brain') loadBrainData();
        }

        function switchCoach(paneId, btn) {
            document.querySelectorAll('.coach-pane').forEach(el => el.style.display = 'none');
            document.getElementById(paneId).style.display = 'block';
            document.querySelectorAll('#tab-coach .btn').forEach(b => b.classList.remove('active', 'primary'));
            btn.classList.add('active', 'primary');
        }

        async function handleStartInvestigation(e) {
            e.preventDefault();
            const btn = document.getElementById('start-btn');
            btn.disabled = true;
            btn.textContent = 'Initiating...';

            const payload = {
                repo_path: document.getElementById('repo-path').value,
                tier: document.getElementById('tier-select').value,
                dry_run: document.getElementById('dry-run').checked,
                execute_code: true,
                repo_owner: document.getElementById('repo-owner').value || null
            };

            const consoleBox = document.getElementById('live-console');
            const logBox = document.getElementById('log-output');
            const titleEl = document.getElementById('live-status-title');
            const actionsEl = document.getElementById('live-actions');

            consoleBox.style.display = 'block';
            actionsEl.style.display = 'none';
            logBox.textContent = `Dispatching investigation for ${payload.repo_path}...\\n`;

            try {
                const res = await fetch('/v1/investigate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                currentWorkflowId = data.workflow_id;
                logBox.textContent += `Workflow initialized: [ID: ${currentWorkflowId}]\\nConnecting to live telemetry stream...\\n`;
                pollWorkflow(currentWorkflowId);
            } catch (err) {
                logBox.textContent += `Error starting workflow: ${err}\\n`;
                btn.disabled = false;
                btn.textContent = '⚡ Dispatch Investigation Pipeline';
            }
        }

        function pollWorkflow(wId) {
            const logBox = document.getElementById('log-output');
            const titleEl = document.getElementById('live-status-title');
            const actionsEl = document.getElementById('live-actions');
            const btn = document.getElementById('start-btn');

            const interval = setInterval(async () => {
                try {
                    const res = await fetch(`/v1/workflows/${wId}/status`);
                    const data = await res.json();

                    titleEl.textContent = `PIPELINE STATUS: ${data.status} (TIER: ${data.tier || 'PENDING'})`;
                    logBox.textContent += `[Telemetry] Player: ${data.active_player || 'starter_agent'} | Stint #${data.stint_number || 1} | Fencing Token: ${data.fencing_token || 1}\\n`;
                    logBox.scrollTop = logBox.scrollHeight;

                    if (data.status === 'COMPLETED' || data.status === 'FAILED') {
                        clearInterval(interval);
                        btn.disabled = false;
                        btn.textContent = '⚡ Dispatch Investigation Pipeline';
                        actionsEl.style.display = 'flex';
                        logBox.textContent += `\\n[SUCCESS] Pipeline finished with status: ${data.status}\\n`;
                    }
                } catch (e) {
                    clearInterval(interval);
                }
            }, 1200);
        }

        function openReportHtml() {
            if (currentWorkflowId) {
                window.open(`/v1/workflows/${currentWorkflowId}/report/html`, '_blank');
            }
        }

        function openRetrospectiveMd() {
            if (currentWorkflowId) {
                window.open(`/v1/workflows/${currentWorkflowId}/retrospective/markdown`, '_blank');
            }
        }

        async function refreshWorkflows() {
            const tbody = document.getElementById('workflows-tbody');
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--muted);">Refreshing...</td></tr>';
            try {
                const res = await fetch('/v1/workflows');
                const workflows = await res.json();
                if (!workflows || workflows.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--muted);">No workflows executed yet.</td></tr>';
                    return;
                }
                tbody.innerHTML = workflows.map(w => `
                    <tr>
                        <td class="mono" style="color: var(--accent); font-weight: 600;">${w.workflow_id}</td>
                        <td>${w.repo_path}</td>
                        <td><span class="badge badge-${w.status}">${w.status}</span></td>
                        <td>${w.tier || 'auto'}</td>
                        <td>${w.active_player || 'starter_agent'}</td>
                        <td class="mono">${w.fencing_token || 1}</td>
                        <td>
                            <a href="/v1/workflows/${w.workflow_id}/report/html" target="_blank" style="margin-right: 12px; font-weight: 600;">HTML Report</a>
                            <a href="/v1/workflows/${w.workflow_id}/retrospective/markdown" target="_blank" style="color: var(--gold); font-weight: 600;">Retrospective</a>
                        </td>
                    </tr>
                `).join('');
            } catch (e) {
                tbody.innerHTML = `<tr><td colspan="7" style="color: var(--bad);">Error loading workflows: ${e}</td></tr>`;
            }
        }

        async function handleExplainFile() {
            const path = document.getElementById('explain-file-input').value;
            const resBox = document.getElementById('explain-result');
            resBox.style.display = 'block';
            resBox.innerHTML = '<span style="color: var(--accent);">Analyzing AST gotchas and structure with _beautifulDATA...</span>';
            try {
                const res = await fetch('/v1/coach/explain', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ file_path: path })
                });
                const data = await res.json();
                resBox.innerHTML = `
                    <h3 style="color: var(--accent); margin: 0 0 8px 0;">${data.title}</h3>
                    <p style="color: var(--ink); font-size: 0.95rem; margin-bottom: 12px;">${data.plain_english_summary}</p>
                    <h4 style="color: var(--gold); margin: 12px 0 6px 0;">Key Responsibilities:</h4>
                    <ul style="padding-left: 20px; margin: 0 0 12px 0;">${data.key_responsibilities.map(r => `<li>${r}</li>`).join('')}</ul>
                    ${data.potential_gotchas && data.potential_gotchas.length ? `
                        <h4 style="color: var(--bad); margin: 12px 0 6px 0;">⚠️ Gotchas & Antipatterns Detected:</h4>
                        <ul style="padding-left: 20px; margin: 0 0 12px 0;">${data.potential_gotchas.map(g => `<li style="color: var(--bad);">${g}</li>`).join('')}</ul>
                    ` : ''}
                    <h4 style="color: var(--ok); margin: 12px 0 6px 0;">Beginner Usage Example:</h4>
                    <pre style="background: var(--bg); padding: 12px; border-radius: 6px; border: 1px solid var(--line); color: var(--ok); overflow-x: auto;"><code class="mono">${data.beginner_usage_example}</code></pre>
                `;
            } catch (e) {
                resBox.innerHTML = `<span style="color: var(--bad);">Error explaining file: ${e}</span>`;
            }
        }

        async function handleDebugError() {
            const err = document.getElementById('debug-error-input').value;
            const resBox = document.getElementById('debug-result');
            resBox.style.display = 'block';
            resBox.innerHTML = '<span style="color: var(--accent);">Diagnosing root cause with _beautifulDATA...</span>';
            try {
                const res = await fetch('/v1/coach/debug', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ error_text: err })
                });
                const data = await res.json();
                resBox.innerHTML = `
                    <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
                        <span class="badge badge-FAILED">${data.error_type}</span>
                        <strong style="color: var(--ink); font-size: 1.05rem;">${data.plain_english_explanation}</strong>
                    </div>
                    <div style="background: rgba(245, 158, 11, 0.08); border-left: 3px solid var(--gold); padding: 10px 14px; margin-bottom: 12px; border-radius: 0 6px 6px 0;">
                        <strong style="color: var(--gold);">Probable Root Cause:</strong>
                        <div style="color: var(--ink); font-size: 0.9rem; margin-top: 4px;">${data.probable_root_cause}</div>
                    </div>
                    <h4 style="color: var(--ok); margin: 10px 0 6px 0;">Step-by-Step Fix:</h4>
                    <ol style="padding-left: 20px;">${data.step_by_step_fix.map(s => `<li style="margin-bottom: 4px;">${s}</li>`).join('')}</ol>
                `;
            } catch (e) {
                resBox.innerHTML = `<span style="color: var(--bad);">Error diagnosing error: ${e}</span>`;
            }
        }

        async function handleGuideFeature() {
            const feat = document.getElementById('guide-feature-input').value;
            const resBox = document.getElementById('guide-result');
            resBox.style.display = 'block';
            resBox.innerHTML = '<span style="color: var(--accent);">Synthesizing architectural implementation guide with _beautifulDATA...</span>';
            try {
                const res = await fetch('/v1/coach/guide', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ feature_description: feat })
                });
                const data = await res.json();
                resBox.innerHTML = `
                    <h3 style="color: var(--accent); margin: 0 0 8px 0;">Implementation Strategy</h3>
                    <p style="color: var(--ink); margin-bottom: 12px;">${data.suggested_architecture_pattern}</p>
                    <h4 style="color: var(--gold); margin: 10px 0 6px 0;">Recommended Implementation Steps:</h4>
                    <ol style="padding-left: 20px;">${data.implementation_steps.map(s => `<li style="margin-bottom: 4px;">${s}</li>`).join('')}</ol>
                `;
            } catch (e) {
                resBox.innerHTML = `<span style="color: var(--bad);">Error generating guide: ${e}</span>`;
            }
        }

        async function loadBrainData() {
            const statsEl = document.getElementById('brain-stats');
            const evoTbody = document.getElementById('evolution-tbody');
            const skillsTbody = document.getElementById('skills-tbody');
            try {
                const [brainRes, evoRes] = await Promise.all([
                    fetch('/v1/brain'),
                    fetch('/v1/brain/evolution')
                ]);
                const brain = await brainRes.json();
                const evolution = await evoRes.json();

                statsEl.innerHTML = `
                    <div class="hud-card">
                        <div class="hud-label">Cognitive Generation</div>
                        <div class="hud-val gold">Gen-${brain.current_generation || 0}</div>
                    </div>
                    <div class="hud-card">
                        <div class="hud-label">Repos Ingested</div>
                        <div class="hud-val ok">${brain.total_repos_ingested || 0}</div>
                    </div>
                    <div class="hud-card">
                        <div class="hud-label">Learned Skills</div>
                        <div class="hud-val accent">${(brain.learned_skills || []).length}</div>
                    </div>
                    <div class="hud-card">
                        <div class="hud-label">Codified Rules</div>
                        <div class="hud-val purple">${(brain.learned_rules || []).length}</div>
                    </div>
                `;

                if (evolution && evolution.length) {
                    evoTbody.innerHTML = evolution.map(e => `
                        <tr>
                            <td class="mono" style="font-weight: 700; color: var(--gold);">Stage #${e.stage_number}</td>
                            <td class="mono" style="color: var(--accent);">${e.model_version}</td>
                            <td style="font-weight: 600; color: var(--ok);">${e.credited_owner}</td>
                            <td>${e.credited_repo}</td>
                            <td>${e.capability_unlocked}</td>
                        </tr>
                    `).join('');
                } else {
                    evoTbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--muted);">No model evolution stages logged yet.</td></tr>';
                }

                if (brain.learned_skills && brain.learned_skills.length) {
                    skillsTbody.innerHTML = brain.learned_skills.slice(-10).map(s => `
                        <tr>
                            <td class="mono" style="color: var(--accent);">${s.skill_id}</td>
                            <td>${s.skill_name}</td>
                            <td style="color: var(--ok); font-weight: 600;">${s.source_attribution ? s.source_attribution.owner : 'Unknown'}</td>
                        </tr>
                    `).join('');
                } else {
                    skillsTbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--muted);">No skills learned yet.</td></tr>';
                }
            } catch (err) {
                statsEl.innerHTML = `<span style="color: var(--bad);">Error loading brain data: ${err}</span>`;
            }
        }

        // Auto load initial brain data on page load
        document.addEventListener('DOMContentLoaded', () => {
            loadBrainData();
        });
    </script>
</body>
</html>
"""
