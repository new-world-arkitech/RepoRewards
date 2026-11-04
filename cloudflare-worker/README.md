# ⚡ FlowMind Cloudflare Worker: Serverless GitHub App Gateway

> **Deploy an edge-native, zero-server webhook gateway on `new-world-arkitech.dev` in under 2 minutes.**
> 
> Handles incoming GitHub webhooks with **Web Crypto HMAC-SHA256 signature verification**, routes PR events, and triggers FlowMind's architectural invariant audits on GitHub Actions.

---

## 🏗️ Architecture

```
[ GitHub Pull Request / Push / Comment ]
                  │
                  ▼  (HTTPS POST)
[ Cloudflare Global Edge: webhook.new-world-arkitech.dev ]
                  │
                  ├──► 1. Constant-Time Web Crypto HMAC-SHA256 Verification
                  ├──► 2. Edge JSON Parsing & Event Filtering
                  │
                  ▼  (Dispatches via GitHub REST API)
[ FlowMind Action Runner (`flowmind-audit.yml`) ]
                  │
                  ├──► 3. Mines Git History & AST Call Boundaries
                  ├──► 4. 4-Perspective Deliberation Council Review
                  ├──► 5. Posts Check Run & Interactive Mermaid PR Scorecard
                  └──► 6. Gated Invariant Merge Protection
```

---

## 🚀 Deployment Options

### Option A: Deploy via Cloudflare Dashboard (No Terminal Required)

1. Log into your [Cloudflare Dashboard](https://dash.cloudflare.com/) and select your account.
2. In the left navigation, click **Workers & Pages** → **Create application** → **Create Worker**.
3. Name it `flowmind-webhook-gateway` and click **Deploy**.
4. Click **Edit code**:
   * Replace the entire code editor with the contents of [`worker.js`](./worker.js).
   * Click **Save and deploy**.
5. Add your custom domain on `new-world-arkitech.dev`:
   * Go to **Settings** → **Triggers** → **Custom Domains** → **Add Custom Domain**.
   * Enter: `webhook.new-world-arkitech.dev` (Cloudflare automatically sets up the DNS record and SSL certificate).
6. Configure Secrets:
   * Go to **Settings** → **Variables and Secrets**.
   * Add:
     * `GITHUB_WEBHOOK_SECRET`: A secret string shared with GitHub (e.g. `flowmind_sec_...`).
     * `GITHUB_TOKEN`: A GitHub Personal Access Token (Fine-Grained or Classic) with `actions:write`, `checks:write`, and `pull-requests:write` permissions.
     * `WORKFLOW_ID`: (Optional, defaults to `flowmind-audit.yml`).

---

### Option B: Deploy via Wrangler CLI

If you have Node.js installed, deploy in one command:

```bash
cd cloudflare-worker

# 1. Login to Cloudflare
npx wrangler login

# 2. Set Secrets
npx wrangler secret put GITHUB_WEBHOOK_SECRET
npx wrangler secret put GITHUB_TOKEN

# 3. Deploy to new-world-arkitech.dev
npx wrangler deploy
```

---

## 🔗 Configuring in GitHub App or Webhook Settings

Once deployed, set your GitHub Webhook URL:

* **Payload URL**: `https://webhook.new-world-arkitech.dev/`
* **Content type**: `application/json`
* **Secret**: The exact secret entered for `GITHUB_WEBHOOK_SECRET`.
* **Events**:
  * ☑️ `Pull requests`
  * ☑️ `Issue comments` (supports `/flowmind audit` slash commands)
  * ☑️ `Check runs` / `Check suites`
