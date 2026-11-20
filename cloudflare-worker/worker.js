/**
 * Optional Zero-Login Open-Access Webhook Relay (Cloudflare Worker)
 * Allows ANY visitor with the GitHub Pages URL to click "Run Fresh Live Scan"
 * without needing a GitHub account or token, while keeping GITHUB_PAT & iVolatility
 * secrets 100% server-side.
 *
 * Required Cloudflare Worker Secret:
 *   wrangler secret put GITHUB_PAT   (Fine-grained PAT with Actions: Read & Write on pre-earnings-put-screener)
 */
const OWNER = "MichaelJoudan";
const REPO = "pre-earnings-put-screener";
const WORKFLOW = "live_scan.yml";
const COOLDOWN_MS = 45_000;

let lastTriggerTs = 0;

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json; charset=utf-8",
  };
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "*";
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    const url = new URL(request.url);
    const ghHeaders = {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${env.GITHUB_PAT}`,
      "User-Agent": "pre-earnings-screener-relay",
      "X-GitHub-Api-Version": "2022-11-28",
    };

    if (request.method === "POST" && url.pathname === "/trigger") {
      const now = Date.now();
      if (now - lastTriggerTs < COOLDOWN_MS) {
        return new Response(
          JSON.stringify({ ok: true, throttled: true, message: "Scan already in progress." }),
          { status: 200, headers: corsHeaders(origin) }
        );
      }
      lastTriggerTs = now;

      const ghResp = await fetch(
        `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
        {
          method: "POST",
          headers: { ...ghHeaders, "Content-Type": "application/json" },
          body: JSON.stringify({ ref: "main" }),
        }
      );

      if (!ghResp.ok) {
        const txt = await ghResp.text();
        return new Response(
          JSON.stringify({ ok: false, error: `GitHub dispatch HTTP ${ghResp.status}: ${txt}` }),
          { status: ghResp.status, headers: corsHeaders(origin) }
        );
      }

      return new Response(
        JSON.stringify({ ok: true, dispatched_at: new Date().toISOString() }),
        { status: 200, headers: corsHeaders(origin) }
      );
    }

    if (request.method === "GET" && url.pathname === "/status") {
      const runsResp = await fetch(
        `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=1`,
        { headers: ghHeaders }
      );
      if (!runsResp.ok) {
        return new Response(
          JSON.stringify({ ok: false, error: `GitHub runs HTTP ${runsResp.status}` }),
          { status: runsResp.status, headers: corsHeaders(origin) }
        );
      }
      const data = await runsResp.json();
      const latest = (data.workflow_runs || [])[0];
      return new Response(
        JSON.stringify({
          ok: true,
          status: latest ? latest.status : "unknown",
          conclusion: latest ? latest.conclusion : null,
          updated_at: latest ? latest.updated_at : null,
        }),
        { status: 200, headers: corsHeaders(origin) }
      );
    }

    return new Response(JSON.stringify({ service: "pre-earnings-put-screener-relay", ok: true }), {
      status: 200,
      headers: corsHeaders(origin),
    });
  },
};
