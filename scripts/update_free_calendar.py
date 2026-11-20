"""
Zero-Quota Daily Nasdaq Earnings & Macro Regime Refresher.
Uses ONLY free public endpoints (`yfinance` + `api.nasdaq.com`) and makes ZERO iVolatility API calls,
preserving 100% of iVolatility API quota for on-demand manual scans when TradingView shows the Circuit Breaker is off.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scanner_engine import (
    SCREENER_OUT_DIR,
    _fetch_single_nasdaq_earnings_day,
    build_nyse_trading_days,
    fetch_macro_regime,
)


def main() -> None:
    today_dt = date.today()
    nyse_days = build_nyse_trading_days(today_dt - timedelta(days=60), today_dt + timedelta(days=75))
    future_or_today = [d for d in nyse_days if d >= today_dt.strftime("%Y-%m-%d")]
    ref_trading_day = future_or_today[0]

    macro = fetch_macro_regime(ref_trading_day)
    scan_dates = [
        (today_dt + timedelta(days=k)).strftime("%Y-%m-%d")
        for k in range(0, 45)
        if (today_dt + timedelta(days=k)).weekday() < 5
    ]
    raw_earn_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_fetch_single_nasdaq_earnings_day, d) for d in scan_dates]
        for f in as_completed(futs):
            raw_earn_rows.extend(f.result())

    compact_earn = [
        {
            "symbol": r.get("symbol", ""),
            "name": r.get("name", ""),
            "marketCap": r.get("marketCap", ""),
            "time": r.get("time", ""),
            "epsForecast": r.get("epsForecast", ""),
            "report_date": r.get("report_date", ""),
        }
        for r in raw_earn_rows
        if str(r.get("symbol", "")).strip()
    ]
    out_path = SCREENER_OUT_DIR / "nasdaq_earnings_window.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "as_of_date": ref_trading_day,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "macro_regime": macro,
                "raw_earn_rows": compact_earn,
            },
            f,
            separators=(",", ":"),
        )
    print(f"Refreshed free Nasdaq calendar & macro regime ({len(compact_earn)} earnings rows, 0 iVolatility calls).")


if __name__ == "__main__":
    main()
