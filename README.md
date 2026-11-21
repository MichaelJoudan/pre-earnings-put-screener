# Pre-Earnings Short 3-Month Put — Online Portfolio Signal Screener (Post-Audit Edition)

Live Online App: **https://michaeljoudan.github.io/pre-earnings-put-screener/**

Peer-review-audited online & local edition of the **10-Year Pre-Earnings Short 3-Month Put Fixed-Slot Buy-and-Hold Screener** across US primary common stocks `> $10B` market cap & `>= 10,000` option Open Interest (`18,814` strictly causal trades, `2016–2026`):
- **Default Loaded Strategy — Strict Core Low-IVR `< 25` Fixed-Slot Buy-and-Hold (`10` Slots @ `10%`, `<= 0.35%` Half-Spread):** **`+7.72%` Blind Out-of-Sample Net CAGR** (`+3.65%` standalone excess over T-Bills, **`0.55` OOS Net Sharpe**, **`-7.23%` OOS MaxDD**) | **`+6.24%` Full 10-Year Net CAGR** (`0.54` Net Sharpe, `-13.37%` MaxDD) after `25%` bid-ask spread concessions and `$0.65`/contract/leg commissions.
- **Alternative Selectable Mode — Diversified `25`-Slot (`4%`) Dual-Sleeve Calendar (`Core < 25` + `Post-Stress Thaw >= 50`):** **`+6.18%` Blind Out-of-Sample Net CAGR** (`0.37` Net Sharpe, `-8.26%` OOS MaxDD) | **`+5.41%` Full 10-Year Net CAGR** (`0.48` Net Sharpe, `-10.40%` MaxDD).

## Key Features & Post-Audit Safeguards
1. **Default Optimal Strategy on Load (`Strict Low-IVR < 25 Only`):** Loads directly into the highest-Sharpe, lowest-drawdown 10-slot Fixed Buy-and-Hold specification while allowing instant one-click comparison against Dual-Sleeve (`25`-slot), Post-Stress Thaw Preview, High-IVR `>= 50`, and Unfiltered baselines.
2. **Strictly Causal Execution & Data Guards:** Prior-session (`Day -21`) CBOE VIX gating (eliminating `4:15 PM` VIX vs. `4:00 PM` option close leakage), uniform `>= 10,000` underlying option Open Interest floor, Nasdaq-vs-iVolatility ADR share-ratio cross-check, `60–135` DTE corrupt-quote filter, strict `<= 0.35%` entry half-spread rejection (`0%` rejected weight), and live 10-slot capacity tracking.
3. **1-Second Live Stock & Strategy Put Quote Bubble + Multi-Account Switcher:** Click any ticker (Columns 1–4) for a live 1s streaming option order ticket (`Mid - 25% Half-Spread`), and switch iVolatility API Key or Username/Password accounts anytime with shared IndexedDB EOD caching.
4. **Zero-Quota Scheduled Calendar Refresh (`.github/workflows/live_scan.yml`):** Automated daily refresh of upcoming Nasdaq earnings and causal VIX macro regime using `0` iVolatility API calls, preserving `100%` of API quota for on-demand scans.
