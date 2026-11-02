from __future__ import annotations

import html

def render_dashboard_html() -> str:
    """
    Renders a standalone, high-performance, client-facing single-page application (SPA)
    dashboard for FlowMind's REST API and autonomous cognitive engine.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FlowMind Autonomous Architecture Cockpit</title>
    <style>
        :root {
            --bg: #090d16;
            --surface: #111827;
            --surface-hover: #1f2937;
            --border: #1f2937;
            --border-highlight: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.2);
            --gold: #f59e0b;
            --green: #10b981;
            --red: #ef4444;
            --purple: #a855f7;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 0;
            background-color: var(--bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
        }
        header {
            background: linear-gradient(180deg, #1e293b 0%, #090d16 100%);
            border-bottom: 1px solid var(--border);
            padding: 24px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .brand-logo {
            font-size: 1.6rem;
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            letter-spacing: -0.5px;
        }
        .brand-badge {
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid #38bdf8;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 700;
        }
        .header-links a {
            color: var(--text-muted);
            text-decoration: none;
            margin-left: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            transition: color 0.2s;
        }
        .header-links a:hover { color: var(--accent); }
        .container {
            max-width: 1300px;
            margin: 0 auto;
            padding: 28px 24px 60px;
        }
        .nav-tabs {
            display: flex;
            gap: 8px;
            border-bottom: 2px solid var(--border);
            margin-bottom: 28px;
            overflow-x: auto;
        }
        .nav-tab {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 12px 20px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            border-radius: 6px 6px 0 0;
            transition: all 0.2s;
            white-space: nowrap;
        }
        .nav-tab:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.04);
        }
        .nav-tab.active {
            color: var(--accent);
            background: var(--surface);
            border-bottom: 3px solid var(--accent);
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; animation: fadeIn 0.2s ease; }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(4px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 18px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }
        .card-title {
            margin: 0;
            font-size: 1.25rem;
            font-weight: 700;
            color: #f8fafc;
        }
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 18px;
            margin-bottom: 18px;
        }
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        label {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-muted);
        }
        input, select, textarea {
            background: #0f172a;
            border: 1px solid var(--border-highlight);
            color: var(--text-main);
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 0.92rem;
            outline: none;
            transition: border 0.2s;
        }
        input:focus, select:focus, textarea:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 2px var(--accent-glow);
        }
        .btn {
            background: var(--accent);
            color: #000;
            font-weight: 700;
            border: none;
            padding: 10px 22px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.95rem;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .btn:hover {
            filter: brightness(1.1);
            transform: translateY(-1px);
        }
        .btn-secondary {
            background: #1e293b;
            color: #f8fafc;
            border: 1px solid #475569;
        }
        .btn-secondary:hover {
            background: #334155;
        }
        .table-responsive {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }
        th {
            background: #1e293b;
            color: var(--text-muted);
            padding: 12px 16px;
            font-weight: 600;
            border-bottom: 1px solid var(--border);
        }
        td {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            color: #e2e8f0;
        }
        tr:hover td { background: rgba(255, 255, 255, 0.02); }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 700;
        }
        .badge-COMPLETED { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }
        .badge-RUNNING { background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #38bdf8; }
        .badge-PENDING { background: rgba(245, 158, 11, 0.2); color: #fde68a; border: 1px solid #f59e0b; }
        .badge-FAILED { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444; }
        .log-box {
            background: #0b1120;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 14px;
            font-family: 'Consolas', 'Fira Code', monospace;
            font-size: 0.85rem;
            color: #38bdf8;
            max-height: 280px;
            overflow-y: auto;
            margin-top: 14px;
            white-space: pre-wrap;
        }
        .result-box {
            margin-top: 18px;
            padding: 18px;
            border-radius: 8px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid var(--border);
        }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <span class="brand-logo">FLOWMIND</span>
            <span class="brand-badge">CLIENT DASHBOARD</span>
        </div>
        <div class="header-links">
            <a href="/docs" target="_blank">📖 Swagger API Docs</a>
            <a href="/v1/health" target="_blank">💚 Healthcheck</a>
            <a href="/v1/brain" target="_blank">🧠 Central Brain</a>
        </div>
    </header>

    <div class="container">
        <!-- Dashboard Navigation Tabs -->
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchNav('tab-launch', this)">🚀 Launch Investigation</button>
            <button class="nav-tab" onclick="switchNav('tab-workflows', this)">📋 Active Workflows</button>
            <button class="nav-tab" onclick="switchNav('tab-coach', this)">🧑‍💻 New Developer Aid</button>
            <button class="nav-tab" onclick="switchNav('tab-brain', this)">🏛️ Cognitive Brain & Lineage</button>
        </div>

        <!-- TAB 1: LAUNCH INVESTIGATION -->
        <div id="tab-launch" class="tab-content active">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Launch Autonomous Repository Investigation</h2>
                    <span style="color: var(--text-muted); font-size: 0.85rem;">Archaeology &bull; Deliberation Council &bull; A2A Bench Rotation</span>
                </div>
                <form id="investigate-form" onsubmit="handleStartInvestigation(event)">
                    <div class="form-grid">
                        <div class="form-group">
                            <label for="repo-path">Repository Target (Local Path or Git Remote URL)</label>
                            <input type="text" id="repo-path" value="sample_repo" placeholder="sample_repo or https://github.com/owner/repo" required>
                        </div>
                        <div class="form-group">
                            <label for="tier-select">Execution Tier</label>
                            <select id="tier-select">
                                <option value="auto">Auto (Completion Effort Node Classifier)</option>
                                <option value="1">Tier 1 (Direct Execution)</option>
                                <option value="2">Tier 2 (Managed Single Agent)</option>
                                <option value="3" selected>Tier 3 (A2A Warm Bench Rotation)</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="model-provider">Reasoning LLM Carrier</label>
                            <select id="model-provider">
                                <option value="simulated">Simulated Cognitive Engine (Default / Free)</option>
                                <option value="gemma">Google Gemma 3B (Local / Ollama)</option>
                                <option value="anthropic">Anthropic Claude 3.5 Sonnet</option>
                                <option value="openai">OpenAI GPT-4o</option>
                                <option value="gemini">Google Gemini 1.5 Pro</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="repo-owner">Accredited Repository Owner (Optional)</label>
                            <input type="text" id="repo-owner" placeholder="Defaults to Git remote or author history">
                        </div>
                    </div>
                    <div style="display: flex; gap: 14px; align-items: center;">
                        <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; color: #cbd5e1;">
                            <input type="checkbox" id="dry-run" checked> Dry Run (Execute reasoning loops safely without file mutations)
                        </label>
                        <button type="submit" class="btn" id="start-btn">⚡ Start Investigation Pipeline</button>
                    </div>
                </form>

                <div id="live-console" style="display: none;">
                    <div class="card-header" style="margin-top: 20px;">
                        <h3 class="card-title" style="font-size: 1.05rem;" id="live-status-title">Pipeline Running...</h3>
                        <div id="live-actions" style="display: none; gap: 10px;">
                            <button class="btn btn-secondary" onclick="openReportHtml()">📊 View Full HTML Audit Report</button>
                            <button class="btn btn-secondary" onclick="openRetrospectiveMd()">🎓 View 'What We Learned'</button>
                        </div>
                    </div>
                    <div class="log-box" id="log-output">Connecting to workflow event stream...</div>
                </div>
            </div>
        </div>

        <!-- TAB 2: ACTIVE WORKFLOWS -->
        <div id="tab-workflows" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Autonomous Execution Workflows</h2>
                    <button class="btn btn-secondary" onclick="refreshWorkflows()">🔄 Refresh</button>
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
                            <tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Loading workflows...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 3: NEW DEVELOPER AID -->
        <div id="tab-coach" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">New Developer's Aid: Codebase Coach & Debugger</h2>
                    <span style="color: var(--text-muted); font-size: 0.85rem;">Plain-English Explanations &bull; Error Diagnoses &bull; Feature Guides</span>
                </div>

                <div style="display: flex; gap: 8px; margin-bottom: 20px;">
                    <button class="btn btn-secondary" onclick="switchCoach('coach-explain', this)">📖 Explain File</button>
                    <button class="btn btn-secondary" onclick="switchCoach('coach-debug', this)">🩺 Diagnose Error</button>
                    <button class="btn btn-secondary" onclick="switchCoach('coach-guide', this)">🗺️ Feature Implementation Guide</button>
                </div>

                <!-- Coach: Explain -->
                <div id="coach-explain" class="coach-pane">
                    <div class="form-group" style="margin-bottom: 14px;">
                        <label for="explain-file-input">Target File Path</label>
                        <input type="text" id="explain-file-input" value="sample_repo/rewards_processor.py" placeholder="sample_repo/rewards_processor.py">
                    </div>
                    <button class="btn" onclick="handleExplainFile()">Explain in Plain English</button>
                    <div id="explain-result" class="result-box" style="display: none;"></div>
                </div>

                <!-- Coach: Debug -->
                <div id="coach-debug" class="coach-pane" style="display: none;">
                    <div class="form-group" style="margin-bottom: 14px;">
                        <label for="debug-error-input">Python Error Text or Traceback</label>
                        <textarea id="debug-error-input" rows="4" placeholder="AttributeError: 'NoneType' object has no attribute 'execute'"></textarea>
                    </div>
                    <button class="btn" onclick="handleDebugError()">Diagnose Error & Get Fix</button>
                    <div id="debug-result" class="result-box" style="display: none;"></div>
                </div>

                <!-- Coach: Guide -->
                <div id="coach-guide" class="coach-pane" style="display: none;">
                    <div class="form-group" style="margin-bottom: 14px;">
                        <label for="guide-feature-input">Feature Description</label>
                        <input type="text" id="guide-feature-input" value="Add Redis caching to rewards calculation" placeholder="Describe the feature you want to build">
                    </div>
                    <button class="btn" onclick="handleGuideFeature()">Generate Architectural Implementation Guide</button>
                    <div id="guide-result" class="result-box" style="display: none;"></div>
                </div>
            </div>
        </div>

        <!-- TAB 4: COGNITIVE BRAIN & LINEAGE -->
        <div id="tab-brain" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Cognitive Brain: Contributor Attribution & Model Evolution</h2>
                    <button class="btn btn-secondary" onclick="loadBrainData()">🔄 Refresh Brain</button>
                </div>
                <div id="brain-stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 22px;"></div>
                
                <h3 style="color: #fde68a; font-size: 1.1rem; margin-bottom: 12px;">🚀 Model Evolution Stages (Attributed Capability Leaps)</h3>
                <div class="table-responsive" style="margin-bottom: 28px;">
                    <table>
                        <thead>
                            <tr>
                                <th>Stage #</th>
                                <th>Model Version</th>
                                <th>Accredited Developer</th>
                                <th>Source Repo</th>
                                <th>Capability Leap Unlocked</th>
                            </tr>
                        </thead>
                        <tbody id="evolution-tbody">
                            <tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Loading evolution stages...</td></tr>
                        </tbody>
                    </table>
                </div>

                <h3 style="color: #38bdf8; font-size: 1.1rem; margin-bottom: 12px;">⚡ Learned Architectural Skills</h3>
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
                            <tr><td colspan="3" style="text-align: center; color: var(--text-muted);">Loading learned skills...</td></tr>
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
                btn.textContent = '⚡ Start Investigation Pipeline';
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

                    titleEl.textContent = `Pipeline Status: ${data.status} (Tier: ${data.tier || 'Pending'})`;
                    logBox.textContent += `[Telemetry] Player: ${data.active_player || 'starter_agent'} | Stint #${data.stint_number || 1} | Fencing Token: ${data.fencing_token || 1}\\n`;
                    logBox.scrollTop = logBox.scrollHeight;

                    if (data.status === 'COMPLETED' || data.status === 'FAILED') {
                        clearInterval(interval);
                        btn.disabled = false;
                        btn.textContent = '⚡ Start Investigation Pipeline';
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
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Refreshing...</td></tr>';
            try {
                const res = await fetch('/v1/workflows');
                const workflows = await res.json();
                if (!workflows || workflows.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No workflows executed yet.</td></tr>';
                    return;
                }
                tbody.innerHTML = workflows.map(w => `
                    <tr>
                        <td style="font-family: monospace; color: var(--accent);">${w.workflow_id}</td>
                        <td>${w.repo_path}</td>
                        <td><span class="badge badge-${w.status}">${w.status}</span></td>
                        <td>${w.tier || 'auto'}</td>
                        <td>${w.active_player || 'starter_agent'}</td>
                        <td style="font-family: monospace;">${w.fencing_token || 1}</td>
                        <td>
                            <a href="/v1/workflows/${w.workflow_id}/report/html" target="_blank" style="color: var(--accent); text-decoration: none; margin-right: 12px; font-weight: 600;">HTML Report</a>
                            <a href="/v1/workflows/${w.workflow_id}/retrospective/markdown" target="_blank" style="color: var(--gold); text-decoration: none; font-weight: 600;">Retrospective</a>
                        </td>
                    </tr>
                `).join('');
            } catch (e) {
                tbody.innerHTML = `<tr><td colspan="7" style="color: var(--red);">Error loading workflows: ${e}</td></tr>`;
            }
        }

        async function handleExplainFile() {
            const path = document.getElementById('explain-file-input').value;
            const resBox = document.getElementById('explain-result');
            resBox.style.display = 'block';
            resBox.innerHTML = '<span style="color: var(--accent);">Analyzing AST gotchas and structure...</span>';
            try {
                const res = await fetch('/v1/coach/explain', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ file_path: path })
                });
                const data = await res.json();
                resBox.innerHTML = `
                    <h3 style="color: #38bdf8; margin: 0 0 8px 0;">${data.title}</h3>
                    <p style="color: #e2e8f0; font-size: 0.95rem; margin-bottom: 12px;">${data.plain_english_summary}</p>
                    <h4 style="color: #facc15; margin: 12px 0 6px 0;">Key Responsibilities:</h4>
                    <ul>${data.key_responsibilities.map(r => `<li>${r}</li>`).join('')}</ul>
                    ${data.potential_gotchas && data.potential_gotchas.length ? `
                        <h4 style="color: #f87171; margin: 12px 0 6px 0;">⚠️ Gotchas & Antipatterns Detected:</h4>
                        <ul>${data.potential_gotchas.map(g => `<li style="color: #fca5a5;">${g}</li>`).join('')}</ul>
                    ` : ''}
                    <h4 style="color: #34d399; margin: 12px 0 6px 0;">Beginner Usage Example:</h4>
                    <pre style="background: #0b1120; padding: 10px; border-radius: 6px; color: #a7f3d0; overflow-x: auto;"><code>${data.beginner_usage_example}</code></pre>
                `;
            } catch (e) {
                resBox.innerHTML = `<span style="color: var(--red);">Error explaining file: ${e}</span>`;
            }
        }

        async function handleDebugError() {
            const err = document.getElementById('debug-error-input').value;
            const resBox = document.getElementById('debug-result');
            resBox.style.display = 'block';
            resBox.innerHTML = '<span style="color: var(--accent);">Diagnosing root cause...</span>';
            try {
                const res = await fetch('/v1/coach/debug', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ error_text: err })
                });
                const data = await res.json();
                resBox.innerHTML = `
                    <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
                        <span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; font-size: 0.85rem;">${data.error_type}</span>
                        <strong style="color: #f8fafc;">${data.plain_english_explanation}</strong>
                    </div>
                    <div style="background: rgba(245, 158, 11, 0.1); border-left: 3px solid #f59e0b; padding: 10px 14px; margin-bottom: 12px;">
                        <strong style="color: #fde68a;">Probable Root Cause:</strong>
                        <div style="color: #e2e8f0; font-size: 0.9rem; margin-top: 4px;">${data.probable_root_cause}</div>
                    </div>
                    <h4 style="color: #34d399; margin: 10px 0 6px 0;">Step-by-Step Fix:</h4>
                    <ol>${data.step_by_step_fix.map(s => `<li style="margin-bottom: 4px;">${s}</li>`).join('')}</ol>
                `;
            } catch (e) {
                resBox.innerHTML = `<span style="color: var(--red);">Error diagnosing error: ${e}</span>`;
            }
        }

        async function handleGuideFeature() {
            const feat = document.getElementById('guide-feature-input').value;
            const resBox = document.getElementById('guide-result');
            resBox.style.display = 'block';
            resBox.innerHTML = '<span style="color: var(--accent);">Synthesizing architectural implementation guide...</span>';
            try {
                const res = await fetch('/v1/coach/guide', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ feature_description: feat })
                });
                const data = await res.json();
                resBox.innerHTML = `
                    <h3 style="color: #38bdf8; margin: 0 0 8px 0;">Implementation Strategy</h3>
                    <p style="color: #e2e8f0; margin-bottom: 12px;">${data.suggested_architecture_pattern}</p>
                    <h4 style="color: #facc15; margin: 10px 0 6px 0;">Recommended Implementation Steps:</h4>
                    <ol>${data.implementation_steps.map(s => `<li style="margin-bottom: 4px;">${s}</li>`).join('')}</ol>
                `;
            } catch (e) {
                resBox.innerHTML = `<span style="color: var(--red);">Error generating guide: ${e}</span>`;
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
                    <div class="card" style="margin: 0; padding: 14px; text-align: center;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Model Generation</div>
                        <div style="font-size: 1.6rem; font-weight: bold; color: var(--gold);">Gen-${brain.current_generation || 0}</div>
                    </div>
                    <div class="card" style="margin: 0; padding: 14px; text-align: center;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Repos Ingested</div>
                        <div style="font-size: 1.6rem; font-weight: bold; color: var(--green);">${brain.total_repos_ingested || 0}</div>
                    </div>
                    <div class="card" style="margin: 0; padding: 14px; text-align: center;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Learned Skills</div>
                        <div style="font-size: 1.6rem; font-weight: bold; color: var(--accent);">${(brain.learned_skills || []).length}</div>
                    </div>
                    <div class="card" style="margin: 0; padding: 14px; text-align: center;">
                        <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted);">Codified Rules</div>
                        <div style="font-size: 1.6rem; font-weight: bold; color: var(--purple);">${(brain.learned_rules || []).length}</div>
                    </div>
                `;

                if (evolution && evolution.length) {
                    evoTbody.innerHTML = evolution.map(e => `
                        <tr>
                            <td style="font-weight: bold; color: var(--gold);">Stage #${e.stage_number}</td>
                            <td style="font-family: monospace; color: var(--accent);">${e.model_version}</td>
                            <td style="font-weight: bold; color: var(--green);">${e.credited_owner}</td>
                            <td>${e.credited_repo}</td>
                            <td>${e.capability_unlocked}</td>
                        </tr>
                    `).join('');
                } else {
                    evoTbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No model evolution stages logged yet.</td></tr>';
                }

                if (brain.learned_skills && brain.learned_skills.length) {
                    skillsTbody.innerHTML = brain.learned_skills.slice(-10).map(s => `
                        <tr>
                            <td style="font-family: monospace; color: var(--accent);">${s.skill_id}</td>
                            <td>${s.skill_name}</td>
                            <td style="color: var(--green); font-weight: bold;">${s.source_attribution ? s.source_attribution.owner : 'Unknown'}</td>
                        </tr>
                    `).join('');
                } else {
                    skillsTbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No skills learned yet.</td></tr>';
                }
            } catch (err) {
                statsEl.innerHTML = `<span style="color: var(--red);">Error loading brain data: ${err}</span>`;
            }
        }
    </script>
</body>
</html>
"""

