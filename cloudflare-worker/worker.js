/**
 * FlowMind Autonomous Architecture Engine — Cloudflare Edge Webhook Worker
 * Domain: new-world-arkitech.dev
 *
 * Capabilities:
 *  1. Cryptographic HMAC-SHA256 signature verification (X-Hub-Signature-256) via Web Crypto API.
 *  2. Edge routing for GitHub Events (pull_request, check_run, issue_comment, ping).
 *  3. Automated dispatch to FlowMind GitHub Actions CI/CD runner.
 *  4. Optional reverse-proxy to local Cloudflare Tunnel (if running backend server).
 *  5. Edge telemetry & health status UI for new-world-arkitech.dev.
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Health & Status Dashboard for GET requests
    if (request.method === "GET") {
      return handleStatusPage(request, env);
    }

    // 2. Only accept POST for webhooks
    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method not allowed. Send POST webhook." }), {
        status: 405,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 3. Extract GitHub Webhook Headers
    const eventType = request.headers.get("X-GitHub-Event") || "ping";
    const deliveryId = request.headers.get("X-GitHub-Delivery") || "unknown";
    const signature = request.headers.get("X-Hub-Signature-256");

    const payloadBuffer = await request.arrayBuffer();

    // 4. Verify HMAC-SHA256 Signature at Edge
    const webhookSecret = env.GITHUB_WEBHOOK_SECRET;
    if (webhookSecret) {
      if (!signature) {
        return new Response(JSON.stringify({ error: "Missing X-Hub-Signature-256 header" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }

      const isValid = await verifyGitHubSignature(payloadBuffer, signature, webhookSecret);
      if (!isValid) {
        return new Response(JSON.stringify({ error: "Invalid HMAC-SHA256 signature" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    // 5. Parse Payload
    let payload;
    try {
      const decoder = new TextDecoder("utf-8");
      payload = JSON.parse(decoder.decode(payloadBuffer));
    } catch (e) {
      return new Response(JSON.stringify({ error: "Malformed JSON payload", details: e.message }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 6. Handle Ping Event
    if (eventType === "ping") {
      return new Response(
        JSON.stringify({
          status: "ok",
          message: "Pong! FlowMind Edge Worker is active and verified on new-world-arkitech.dev.",
          delivery_id: deliveryId,
          zen: payload.zen || "Keep it logically awesome.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    // 7. Optional Forward to FlowMind Backend Tunnel (if configured)
    if (env.FLOWMIND_BACKEND_URL) {
      try {
        const backendResp = await fetch(`${env.FLOWMIND_BACKEND_URL}/v1/webhooks/github`, {
          method: "POST",
          headers: request.headers,
          body: payloadBuffer,
        });
        const backendJson = await backendResp.json();
        return new Response(JSON.stringify({ forwarded_to_backend: true, backend_response: backendJson }), {
          status: backendResp.status,
          headers: { "Content-Type": "application/json" },
        });
      } catch (err) {
        console.warn("Backend forwarding failed, falling back to GitHub Actions dispatch:", err);
      }
    }

    // 8. Event Routing: Pull Request Opened, Synchronized, Reopened
    const action = payload.action;
    const repoFullName = payload.repository?.full_name || "new-world-arkitech/RepoRewards";

    if (eventType === "pull_request" && ["opened", "synchronize", "reopened"].includes(action)) {
      const prNumber = payload.pull_request?.number;
      const headSha = payload.pull_request?.head?.sha;
      const headRef = payload.pull_request?.head?.ref;

      // Dispatch FlowMind GitHub Actions Audit Workflow
      const dispatchResult = await dispatchGitHubAction(env, repoFullName, {
        pr_number: String(prNumber),
        head_sha: headSha,
        event_type: "pull_request",
        ref: headRef || "main",
      });

      return new Response(
        JSON.stringify({
          status: "accepted",
          flowmind_edge: "dispatched",
          event: eventType,
          action: action,
          repository: repoFullName,
          pr_number: prNumber,
          head_sha: headSha,
          dispatch: dispatchResult,
        }),
        { status: 202, headers: { "Content-Type": "application/json" } }
      );
    }

    // 9. Event Routing: Slash Commands in PR Comments (e.g. `/flowmind audit`, `/flowmind review`)
    if (eventType === "issue_comment" && action === "created") {
      const commentBody = payload.comment?.body || "";
      const isPR = !!payload.issue?.pull_request;

      if (isPR && (commentBody.includes("/flowmind audit") || commentBody.includes("/flowmind review"))) {
        const issueNumber = payload.issue?.number;
        const dispatchResult = await dispatchGitHubAction(env, repoFullName, {
          pr_number: String(issueNumber),
          event_type: "comment_slash_command",
          ref: "main",
        });

        return new Response(
          JSON.stringify({
            status: "accepted",
            command: "slash_audit_dispatched",
            repository: repoFullName,
            issue_number: issueNumber,
            dispatch: dispatchResult,
          }),
          { status: 202, headers: { "Content-Type": "application/json" } }
        );
      }
    }

    // Default response for unhandled actions
    return new Response(
      JSON.stringify({
        status: "received",
        edge_host: "new-world-arkitech.dev",
        event: eventType,
        action: action,
        message: "Event received and acknowledged by FlowMind Edge.",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  },
};

/**
 * Validates HMAC-SHA256 signature using standard Web Crypto API.
 */
async function verifyGitHubSignature(payloadBuffer, signatureHeader, secret) {
  try {
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign", "verify"]
    );

    const cleanHex = signatureHeader.replace(/^sha256=/, "").trim();
    if (cleanHex.length !== 64) return false;

    // Convert hex string to byte array
    const signatureBytes = new Uint8Array(32);
    for (let i = 0; i < 32; i++) {
      signatureBytes[i] = parseInt(cleanHex.substr(i * 2, 2), 16);
    }

    return await crypto.subtle.verify("HMAC", key, signatureBytes, payloadBuffer);
  } catch (err) {
    console.error("Signature verification error:", err);
    return false;
  }
}

/**
 * Dispatches the FlowMind Audit workflow via GitHub Actions REST API.
 */
async function dispatchGitHubAction(env, repoFullName, inputs) {
  const token = env.GITHUB_TOKEN;
  if (!token) {
    return { ok: false, error: "Missing GITHUB_TOKEN environment variable in Cloudflare Worker" };
  }

  const workflowId = env.WORKFLOW_ID || "flowmind-audit.yml";
  const url = `https://api.github.com/repos/${repoFullName}/actions/workflows/${workflowId}/dispatches`;

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "FlowMind-Cloudflare-Worker/1.0 (+https://new-world-arkitech.dev)",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ref: inputs.ref || "main",
        inputs: {
          pr_number: inputs.pr_number || "",
          head_sha: inputs.head_sha || "",
        },
      }),
    });

    if (resp.status === 204 || resp.status === 200) {
      return { ok: true, status: resp.status, message: "Workflow dispatch queued successfully" };
    }

    const text = await resp.text();
    return { ok: false, status: resp.status, error_body: text };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

/**
 * Renders an interactive Edge Status Dashboard when visited via GET.
 */
function handleStatusPage(request, env) {
  const cfColo = request.cf?.colo || "EDGE";
  const cfCountry = request.cf?.country || "GLOBAL";

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FlowMind Edge Gateway — new-world-arkitech.dev</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card: #111827;
      --border: #1f2937;
      --accent: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.2);
      --ok: #10b981;
      --text: #f9fafb;
      --muted: #9ca3af;
      --mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
    }
    body {
      margin: 0;
      padding: 2rem;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    .box {
      max-width: 640px;
      width: 100%;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 2rem;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 0 40px var(--accent-glow);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.75rem;
      font-family: var(--mono);
      background: rgba(16, 185, 129, 0.15);
      color: var(--ok);
      border: 1px solid rgba(16, 185, 129, 0.3);
      padding: 4px 10px;
      border-radius: 9999px;
      margin-bottom: 1rem;
    }
    .dot {
      width: 8px;
      height: 8px;
      background: var(--ok);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--ok);
    }
    h1 {
      margin: 0 0 0.5rem 0;
      font-size: 1.6rem;
      letter-spacing: -0.02em;
    }
    p {
      color: var(--muted);
      line-height: 1.6;
      font-size: 0.95rem;
      margin: 0 0 1.5rem 0;
    }
    .meta {
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      font-family: var(--mono);
      font-size: 0.82rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .meta div {
      display: flex;
      justify-content: space-between;
    }
    .meta span:first-child {
      color: var(--muted);
    }
    .meta span:last-child {
      color: var(--accent);
      font-weight: 600;
    }
    .endpoint {
      margin-top: 1.5rem;
      padding: 0.85rem;
      background: rgba(99, 102, 241, 0.1);
      border: 1px solid var(--accent);
      border-radius: 8px;
      font-family: var(--mono);
      font-size: 0.85rem;
      word-break: break-all;
    }
  </style>
</head>
<body>
  <div class="box">
    <div class="badge"><div class="dot"></div> CLOUDFLARE EDGE ACTIVE</div>
    <h1>FlowMind Webhook Gateway</h1>
    <p>Serverless zero-latency GitHub Webhook gateway with Web Crypto HMAC-SHA256 verification and automated A2A deliberation dispatch.</p>
    
    <div class="meta">
      <div><span>Gateway Domain</span><span>new-world-arkitech.dev</span></div>
      <div><span>Edge Datacenter</span><span>${cfColo} (${cfCountry})</span></div>
      <div><span>Protocol Engine</span><span>FlowMind v1.179.0</span></div>
      <div><span>Signature Mode</span><span>HMAC-SHA256 (Constant-Time)</span></div>
      <div><span>Active Backend</span><span>${env.FLOWMIND_BACKEND_URL ? "Cloudflare Tunnel Proxy" : "GitHub Actions Runner"}</span></div>
    </div>

    <div class="endpoint">
      <strong>Webhook URL:</strong><br>
      ${request.url}
    </div>
  </div>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}
