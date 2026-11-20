# Pre-Earnings Short 3-Month Put — Online Portfolio Signal Screener

Live Link: **https://michaeljoudan.github.io/pre-earnings-put-screener/**

Purely online cloud edition of the **10-Year Verified Pre-Earnings Short 3-Month Put Portfolio Signal Screener** (`+10.24% CAGR | 0.88 Sharpe | -11.11% MaxDD`), preserving 100% of the exact strategy, calendar, macro regime, and option chain selection logic.

---

## Architecture & Exact Strategy Preservation

- **Online Web Dashboard (`index.html` on GitHub Pages):**
  - Open-access browser dashboard with all 5 Strategy Modes (`Dual-Sleeve`, `Post-Stress Thaw Preview`, `Strict Low-IVR < 25`, `High-IVR >= 50`, `Unfiltered > $10B`), Market Cap & Half-Spread filters, ticker search, CSV export, TradingView Pine v6 Companion viewer, and automatic 30-second live signal polling.
- **Automated & On-Demand Python Scanner (`scanner_engine.py` + `ivol_client.py` on GitHub Actions):**
  - Runs automatically every US trading day (Open, Mid-Day, Pre-Close for Day -20 entries & Day -1 exits, and Post-Close EOD) and on-demand via `workflow_dispatch`.
  - Pulls live CBOE `^VIX`, `^VIX3M`, `^IRX` (3M T-Bill yield), and `SPY` regime indicators via `yfinance`, Nasdaq 45-day earnings calendar & release timing (`BMO` vs `AMC`), iVolatility `ALL_USA` stock market IVR/IVP universe (`us_common_stocks.json` & `normal_ivr_baselines.json`), and 55–135 DTE ATM Put chains (`Midpoint - 25% of Half-Spread` limit target).
- **TradingView Companion (`companion/Pre_Earnings_Portfolio_Regime_Companion.pine`):**
  - Pine Script v6 chart indicator aligned with the portfolio regime & T-20 / T-1 countdown rules.

---

## One-Time GitHub Setup (60 Seconds)

### 1. Add Encrypted iVolatility Secrets
Go to **[Settings → Secrets and variables → Actions](https://github.com/MichaelJoudan/pre-earnings-put-screener/settings/secrets/actions)** and add the repository secrets from your local `ivol_credentials.json`:
- `IVOL_API_KEY` — Your iVolatility REST API Key
- `IVOL_USERNAME` — Your iVolatility Username
- `IVOL_PASSWORD` — Your iVolatility Password

### 2. Enable GitHub Pages
Go to **[Settings → Pages](https://github.com/MichaelJoudan/pre-earnings-put-screener/settings/pages)**:
- Under **Build and deployment → Source**, select **GitHub Actions**.
- *(Note: GitHub Pro supports public GitHub Pages on Private repositories. If your account is on GitHub Free, GitHub requires switching repository visibility to Public under Settings → General to enable Pages — your iVolatility credentials remain 100% private inside encrypted Actions Secrets and are never in the repository.)*

### 3. Triggering On-Demand Scans from the Web App ("Run Fresh Live Scan")
- **Automatic Schedule:** No setup required — GitHub Actions updates signals automatically throughout every US trading session, and open browsers auto-refresh.
- **Zero-Login Open-Access Button for All Visitors (Optional):** Deploy [`cloudflare-worker/worker.js`](./cloudflare-worker/worker.js) to Cloudflare Workers (Free) with a single secret `GITHUB_PAT` (`Actions: Read & Write` on `pre-earnings-put-screener`), and paste the Worker URL into **Cloud Scan Config** (or `DEFAULT_RELAY_URL` in `index.html`). Any visitor with the app URL can then click **Run Fresh Live Scan** with zero login.
- **Direct Browser Dispatch (Owner Quick Setup):** Click **Cloud Scan Config** in the top bar and paste a fine-grained GitHub token scoped only to `pre-earnings-put-screener` (`Actions: Read & write` and `Contents: Read`), saved strictly in your browser's `localStorage`.

---

## Repository Structure

```text
├── .github/workflows/live_scan.yml   # Automated NYSE schedule + manual scan + GitHub Pages deploy
├── cloudflare-worker/                # Optional stateless relay for zero-login public scan triggering
├── companion/                        # TradingView Pine Script v6 companion indicator
├── output/                           # Latest generated portfolio signals (JSON & CSV)
├── reference_data/                   # US common stock universe & historical normal IVR90 baselines
├── scripts/run_scan.py               # Headless CLI scanner entrypoint for GitHub Actions
├── index.html                        # Standalone online web application (GitHub Pages)
├── app.py                            # Optional cloud Python HTTP server (Render / Railway / Docker)
├── scanner_engine.py                 # Core 10Y Verified Pre-Earnings Short 3M Put screening engine
├── ivol_client.py                    # iVolatility EOD REST API client & CSV repair
└── requirements.txt                  # Python scanner dependencies
```
