# Pre-Earnings Short 3-Month Put — Online Portfolio Signal Screener

Live Online App: **https://michaeljoudan.github.io/pre-earnings-put-screener/**

Turnkey online edition of the **10-Year Verified Pre-Earnings Short 3-Month Put Portfolio Signal Screener** (`+10.24% CAGR | 0.88 Sharpe | -11.11% MaxDD`), preserving 100% of the exact screening logic, credentials, and workflow out of the box with zero extra setup.

## How It Works Online (Zero Configuration Required)
1. **Instant Live Dashboard (`index.html`):**
   - Loads pre-configured credentials directly from `ivol_credentials.json` (and allows live in-browser edits via **iVolatility API Keys**).
   - Clicking **Run Fresh Live Scan** queries `restapi.ivolatility.com` directly from your browser (`ALL_USA` stock universe + 55–135 DTE ATM Put chains) using the exact same `scanner_engine.py` rules, updating signals and **Export CSV** on the spot.
2. **Automated Background Refresh (`.github/workflows/live_scan.yml`):**
   - Runs `scripts/run_scan.py` automatically 4× every US trading day (Open, Mid-Day, Pre-Close, Post-Close EOD) using `ivol_credentials.json` in the repo — keeping `output/latest_signals.json`, `output/latest_signals.csv`, and `output/nasdaq_earnings_window.json` continuously updated.
3. **Enable GitHub Pages (1 Click if not already active):**
   - In **[Settings → Pages](https://github.com/MichaelJoudan/pre-earnings-put-screener/settings/pages)**, set **Source** to **Deploy from a branch** → Branch **`main` / `/ (root)`** (or **GitHub Actions** — both are fully supported).
