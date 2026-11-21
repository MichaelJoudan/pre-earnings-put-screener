================================================================================
 PRE-EARNINGS SHORT 3-MONTH PUT — PORTABLE & ONLINE PORTFOLIO SIGNAL SCREENER
================================================================================

HOW TO RUN ON MACOS (MACBOOK / IMAC / MAC MINI):
1. Keep `Start_Pre_Earnings_Screener_Mac.command`, `ivol_credentials.json`,
   and the `app_files` folder (or root source files) together in the same folder.
2. Make sure Python 3.9+ is installed (`https://www.python.org/downloads/macos/`
   or `brew install python`).
3. Double-click `Start_Pre_Earnings_Screener_Mac.command` in Finder
   (or run `bash Start_Pre_Earnings_Screener_Mac.command` in Terminal):
   - First launch automatically creates `.venv_mac` and installs the required
     libraries (`ivolatility`, `pandas`, `numpy`, `requests`, `yfinance`).
   - Your web browser will automatically open `http://127.0.0.1:8501`.

HOW TO RUN ON ANY WINDOWS COMPUTER:
1. Unzip `Pre_Earnings_Screener_Portable` anywhere on the target computer
   (e.g., Desktop or Documents). Keep `Start_Pre_Earnings_Screener.bat`,
   `ivol_credentials.json`, and `app_files` together in the same folder.
2. Make sure Python 3.9+ is installed on that computer:
   - Download from https://www.python.org/downloads/ (check "Add python.exe to PATH").
   - On the very first launch, `Start_Pre_Earnings_Screener.bat` automatically
     creates `.venv_win` and installs the 5 required libraries (`ivolatility`,
     `pandas`, `numpy`, `requests`, `yfinance`).
3. Double-click `Start_Pre_Earnings_Screener.bat`:
   - Your web browser will automatically open `http://127.0.0.1:8501`.

NEW FEATURES INCLUDED IN THIS PEER-REVIEW AUDITED EDITION:
- Default Optimal Strategy on Load — Strict Low-IVR < 25 Fixed-Slot Buy-and-Hold:
  Defaults on site load to the peer-review audited #1 risk-adjusted strategy
  (Strict Core Low-IVR < 25 Only, <= 0.35% Half-Spread Cap, >= 10,000 Option OI,
  prior-session causal VIX gating: +7.72% OOS / +6.24% 10Y Net CAGR, 0.55 OOS Sharpe,
  -7.23% OOS MaxDD), while keeping 25-Slot Dual-Sleeve Calendar (+6.18% OOS / +5.41%
  10Y Net CAGR), Post-Stress Thaw Preview, High-IVR >= 50, and Unfiltered > $10B
  selectable in the top-bar dropdown.
- 1-Second Live Stock & Strategy Put Quote Bubble:
  Click any stock ticker (or Columns 1-4 across Tabs 1-4) to open a live floating
  quote ticket polling `restapi.ivolatility.com` every 1.0s for live stock price,
  exact strategy 3M ATM Put Strike & Expiration (60-135 DTE), live Bid/Ask, and the
  `25%-Mid` Sell Limit order price until crossed out (`x`).
- Multi-Account Switcher (`iVolatility API Keys` button in top-right bar):
  Switch iVolatility accounts anytime via either API Key OR Username & Password,
  with live connection verification, saved account history, and disk sync to
  `ivol_credentials.json`.
- TradingView Pine Script v6 Companions (v2.1 Audited):
  Includes both `Pre_Earnings_Portfolio_Regime_Companion.pine` and the standalone
  `Pre_Earnings_Circuit_Breaker_Gatekeeper.pine` indicator with causal `close[1]` VIX
  gating and fixed panic-block separation.
================================================================================
