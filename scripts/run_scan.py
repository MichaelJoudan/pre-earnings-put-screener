"""
Headless CLI runner for GitHub Actions & automated cron scans.
Executes `run_portfolio_signal_scan()` and writes:
  - output/latest_signals.json
  - output/latest_signals.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scanner_engine import run_portfolio_signal_scan


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pre-Earnings Short 3M Put Portfolio Signal Scan")
    parser.add_argument("--as-of-date", type=str, default=None, help="Optional YYYY-MM-DD override")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    as_of = args.as_of_date.strip() if args.as_of_date and args.as_of_date.strip() else None

    print(f"Starting Pre-Earnings Short 3M Put live scan (as_of_date={as_of or 'today'})...")
    payload = run_portfolio_signal_scan(as_of_date=as_of)

    m = payload["macro_regime"]
    cap = payload["portfolio_capacity"]
    print("=" * 72)
    print(f"Scan Complete in {payload['scan_elapsed_sec']}s | Updated: {payload['generated_at']}")
    print(f"Calendar Ref : {m['as_of_date']} | Macro Regime: {m['regime_code']} (VIX {m['vix_close']})")
    print(
        f"Signals      : {len(payload['signals'])} total | "
        f"Actionable={cap['actionable_entry_signals_today']} | "
        f"Limit={cap['caution_limit_signals_today']} | "
        f"Exits={cap['mandatory_exit_alerts']} | "
        f"Watchlist={cap['upcoming_watchlist_count']}"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
