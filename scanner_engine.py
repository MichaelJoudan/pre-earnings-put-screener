"""
Portable Portfolio-Level Pre-Earnings Short 3-Month Put Signal Scanner.
Zero external workspace dependencies — runs identically on any computer.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import yfinance as yf

APP_FILES_DIR = Path(__file__).resolve().parent
if str(APP_FILES_DIR) not in sys.path:
    sys.path.insert(0, str(APP_FILES_DIR))

from ivol_client import IVolClient

logger = logging.getLogger(__name__)

REF_DATA_DIR = APP_FILES_DIR / "reference_data"
SCREENER_OUT_DIR = APP_FILES_DIR / "output"
SCREENER_OUT_DIR.mkdir(parents=True, exist_ok=True)

SECONDARY_SHARE_CLASSES = {
    "GOOG", "BRK/A", "BRK.A", "FOX", "PBR/A", "PBR.A",
    "BBL", "RDS/B", "RDS.B", "NWS", "UA", "Z", "HEI/A",
}


def third_friday(year: int, month: int) -> date:
    """Return the standard 3rd Friday monthly option expiration date for `(year, month)`."""
    first = date(year, month, 1)
    days_to_fri = (4 - first.weekday()) % 7
    first_fri = first + timedelta(days=days_to_fri)
    return first_fri + timedelta(days=14)


def clean_option_quote(bid_raw: Any, ask_raw: Any, mid_raw: Any) -> tuple[float, float, float, bool]:
    """Validate and compute clean `(bid, ask, mid, is_valid)` option quote."""
    b = float(bid_raw) if pd.notna(bid_raw) else np.nan
    a = float(ask_raw) if pd.notna(ask_raw) else np.nan
    m = float(mid_raw) if pd.notna(mid_raw) else np.nan
    if pd.notna(b) and pd.notna(a) and a > 0 and b >= 0 and a >= b:
        mid_calc = 0.5 * (b + a)
        return (b, a, mid_calc, mid_calc > 0)
    if pd.notna(m) and m > 0:
        return (b, a, m, True)
    return (np.nan, np.nan, np.nan, False)


def _us_market_holidays(years: list[int]) -> set[date]:
    holidays: set[date] = set()
    try:
        from pandas.tseries.holiday import (
            AbstractHolidayCalendar,
            GoodFriday,
            Holiday,
            USLaborDay,
            USMartinLutherKingJr,
            USMemorialDay,
            USPresidentsDay,
            USThanksgivingDay,
            nearest_workday,
        )

        class NYSECalendar(AbstractHolidayCalendar):
            rules = [
                Holiday("New Years Day", month=1, day=1, observance=nearest_workday),
                USMartinLutherKingJr,
                USPresidentsDay,
                GoodFriday,
                USMemorialDay,
                Holiday("Juneteenth", month=6, day=19, observance=nearest_workday, start_date="2022-01-01"),
                Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
                USLaborDay,
                USThanksgivingDay,
                Holiday("Christmas", month=12, day=25, observance=nearest_workday),
            ]

        cal = NYSECalendar()
        dt_hols = cal.holidays(start=f"{min(years)}-01-01", end=f"{max(years)}-12-31")
        holidays = {d.date() for d in dt_hols}
    except Exception:
        explicit = [
            "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
            "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
            "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
        ]
        holidays = {datetime.strptime(x, "%Y-%m-%d").date() for x in explicit}
    return holidays


def build_nyse_trading_days(start_dt: date, end_dt: date) -> list[str]:
    yrs = list(range(start_dt.year, end_dt.year + 1))
    hols = _us_market_holidays(yrs)
    out: list[str] = []
    cur = start_dt
    while cur <= end_dt:
        if cur.weekday() < 5 and cur not in hols:
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def fetch_macro_regime(as_of_str: str, vix_spike_thresh: float = 24.0) -> dict[str, Any]:
    end_dt = (datetime.strptime(as_of_str, "%Y-%m-%d").date() + timedelta(days=2)).strftime("%Y-%m-%d")
    start_dt = (datetime.strptime(as_of_str, "%Y-%m-%d").date() - timedelta(days=400)).strftime("%Y-%m-%d")

    vix_close, vix_sma10, vix_sma30, vix_hi20 = 18.5, 18.5, 18.5, 20.0
    vix3m_close, vix3m_ivr = 20.0, 30.0
    tbill_yield_pct = 4.25
    spy_close, spy_sma200 = 580.0, 540.0
    vix_date = as_of_str

    try:
        vix_df = yf.Ticker("^VIX").history(start=start_dt, end=end_dt)
        if vix_df is not None and not vix_df.empty:
            vs = pd.Series(vix_df["Close"].values, index=pd.to_datetime(vix_df.index).strftime("%Y-%m-%d"))
            vs = vs[~vs.index.duplicated(keep="last")]
            vs = vs[vs.index <= as_of_str]
            if not vs.empty:
                vix_date = str(vs.index[-1])
                vix_close = float(vs.iloc[-1])
                vix_sma10 = float(vs.tail(10).mean())
                vix_sma30 = float(vs.tail(30).mean())
                vix_hi20 = float(vs.tail(20).max())
    except Exception as exc:
        logger.warning("VIX fetch warning: %s", exc)

    try:
        v3_df = yf.Ticker("^VIX3M").history(start=start_dt, end=end_dt)
        if v3_df is not None and not v3_df.empty:
            v3 = pd.Series(v3_df["Close"].values, index=pd.to_datetime(v3_df.index).strftime("%Y-%m-%d"))
            v3 = v3[~v3.index.duplicated(keep="last")]
            v3 = v3[v3.index <= as_of_str]
            if not v3.empty:
                vix3m_close = float(v3.iloc[-1])
                lo252 = float(v3.tail(252).min())
                hi252 = float(v3.tail(252).max())
                vix3m_ivr = float(100.0 * (vix3m_close - lo252) / max(hi252 - lo252, 1e-6))
    except Exception:
        pass

    try:
        irx_df = yf.Ticker("^IRX").history(start=start_dt, end=end_dt)
        if irx_df is not None and not irx_df.empty:
            irx = irx_df["Close"].dropna()
            if not irx.empty:
                tbill_yield_pct = float(irx.iloc[-1])
    except Exception:
        pass

    try:
        spy_df = yf.Ticker("SPY").history(start=start_dt, end=end_dt)
        if spy_df is not None and not spy_df.empty:
            sp = spy_df["Close"].dropna()
            if not sp.empty:
                spy_close = float(sp.iloc[-1])
                spy_sma200 = float(sp.tail(200).mean())
    except Exception:
        pass

    is_panic = (vix_hi20 > vix_spike_thresh) and (vix_sma10 >= vix_sma30)
    is_thaw = (vix_hi20 > vix_spike_thresh) and (vix_sma10 < vix_sma30)

    if is_panic:
        regime_code = "PANIC_CIRCUIT_BREAKER"
        regime_label = "Active Market Stress — Circuit-Breaker Engaged"
        regime_guidance = (
            "Market volatility spiked above the 24.0 VIX stress threshold and remains elevated (10-day VIX average >= 30-day average). "
            "High-volatility entries are BLOCKED; only Core Low-IVR (< 25) names qualify, idle portfolio slots remain parked in 3-Month US Treasury Bills, "
            "and existing open positions are held calmly until their scheduled Day -1 pre-earnings exit."
        )
    elif is_thaw:
        regime_code = "POST_STRESS_THAW"
        regime_label = "Post-Stress Volatility Thaw — Dual-Sleeve Unlocked"
        regime_guidance = (
            "Market volatility recently exceeded 24.0 VIX (20-day peak) and is now subsiding (10-day VIX average < 30-day average). "
            "Both the Core Calm Sleeve (3M IV Rank < 25) AND the Opportunistic Post-Stress Mean-Reversion Sleeve (3M IV Rank >= 50) "
            "are UNLOCKED for idle portfolio capacity."
        )
    else:
        regime_code = "CALM_HARVEST"
        regime_label = "Calm Market Harvest — Core Low-IVR Sleeve Active"
        regime_guidance = (
            "Broad equity volatility is calm (20-day VIX peak <= 24.0). Deploy strictly into Core Low-Volatility candidates "
            "(Starting 3M IV Rank < 25) entering Day -20 before earnings while earning 3-Month Treasury yield on unused cash."
        )

    return {
        "as_of_date": as_of_str,
        "vix_quote_date": vix_date,
        "regime_code": regime_code,
        "regime_label": regime_label,
        "regime_guidance": regime_guidance,
        "vix_close": round(vix_close, 2),
        "vix_sma10": round(vix_sma10, 2),
        "vix_sma30": round(vix_sma30, 2),
        "vix_high20": round(vix_hi20, 2),
        "vix_spike_threshold": vix_spike_thresh,
        "vix3m_close": round(vix3m_close, 2),
        "vix3m_ivr_52w": round(vix3m_ivr, 1),
        "tbill_3m_yield_pct": round(tbill_yield_pct, 2),
        "spy_close": round(spy_close, 2),
        "spy_sma200": round(spy_sma200, 2),
        "spy_above_sma200": bool(spy_close >= spy_sma200),
        "core_sleeve_enabled": True,
        "post_stress_high_ivr_enabled": bool(is_thaw),
    }


def _parse_nasdaq_mcap(raw_str: Any) -> float:
    if not raw_str or not isinstance(raw_str, str):
        return 0.0
    s = raw_str.strip().replace("$", "").replace(",", "")
    if not s or s.upper() == "N/A":
        return 0.0
    mult = 1.0
    if s.endswith("T"):
        mult, s = 1e12, s[:-1]
    elif s.endswith("B"):
        mult, s = 1e9, s[:-1]
    elif s.endswith("M"):
        mult, s = 1e6, s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def _fetch_single_nasdaq_earnings_day(dt_str: str) -> list[dict[str, Any]]:
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    }
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={dt_str}"
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=hdrs, timeout=12)
            if resp.status_code == 200:
                rows = ((resp.json().get("data") or {}).get("rows")) or []
                return [{**dict(r), "report_date": dt_str} for r in rows]
        except Exception:
            time.sleep(0.5 * (attempt + 1))
    return []


def _load_latest_ivol_universe(client: IVolClient, as_of_dt: date) -> tuple[str, pd.DataFrame, set[str]]:
    smd = pd.DataFrame()
    smd_date = as_of_dt.strftime("%Y-%m-%d")
    for offset in range(0, 8):
        cand_dt = as_of_dt - timedelta(days=offset)
        if cand_dt.weekday() >= 5:
            continue
        cand_str = cand_dt.strftime("%Y-%m-%d")
        df_try = client.get_stock_market_data(cand_str)
        if df_try is not None and len(df_try) > 1000:
            smd = df_try.copy()
            smd_date = cand_str
            break

    common_stocks: set[str] = set()
    ref_wl = REF_DATA_DIR / "us_common_stocks.json"
    if ref_wl.exists():
        try:
            common_stocks.update(json.loads(ref_wl.read_text(encoding="utf-8")))
        except Exception:
            pass

    if not common_stocks:
        u_df = client.get_underlying_info(date_str=smd_date)
        if u_df is not None and not u_df.empty and "Security type" in u_df.columns:
            sym_c = next((c for c in ("Stock ticker", "Stock symbol", "Symbol", "symbol") if c in u_df.columns), None)
            if sym_c:
                m = u_df["Security type"].astype(str).str.strip() == "S"
                if "Region" in u_df.columns:
                    m = m & (u_df["Region"].astype(str).str.strip() == "USA")
                common_stocks.update(u_df.loc[m, sym_c].dropna().astype(str).str.strip().tolist())

    if not smd.empty:
        smd["symbol"] = smd["symbol"].astype(str).str.strip()
        smd = smd[~smd["symbol"].isin(SECONDARY_SHARE_CLASSES)].copy()
        if common_stocks and len(smd[smd["symbol"].isin(common_stocks)]) > 500:
            smd = smd[smd["symbol"].isin(common_stocks)].copy()

    return smd_date, smd, common_stocks


def _select_best_90d_atm_put(client: IVolClient, symbol: str, quote_date: str, fallback_spot: float) -> dict[str, Any]:
    empty_res = {
        "opt_matched": False, "option_symbol": "", "expiration_date": "", "dte": None,
        "strike": None, "bid": None, "ask": None, "mid": None, "limit_25_price": None,
        "entry_credit_pct": None, "half_spread_pct": None, "opt_iv_pct": None,
        "delta": None, "theta": None, "vega": None, "opt_oi": None, "opt_volume": None,
    }
    q_cands = [symbol]
    if "/" in symbol:
        q_cands.append(symbol.replace("/", "."))
    elif "." in symbol:
        q_cands.append(symbol.replace(".", "/"))

    dfc = pd.DataFrame()
    for qs in q_cands:
        dfc = client.get_options_by_param(qs, quote_date, 55, 135, -12.0, 12.0, "P")
        if dfc is not None and not dfc.empty:
            break
    if dfc is None or dfc.empty:
        return empty_res

    dfc = dfc.copy()
    for c in ["dte", "price_strike", "price", "Ask", "Bid", "iv", "delta", "theta", "vega", "underlying_price", "openinterest", "volume"]:
        if c in dfc.columns:
            dfc[c] = pd.to_numeric(dfc[c], errors="coerce")

    cands = []
    for _, r in dfc.iterrows():
        spot = float(r["underlying_price"]) if pd.notna(r.get("underlying_price")) and float(r["underlying_price"]) > 0 else fallback_spot
        ks = float(r["price_strike"]) if pd.notna(r.get("price_strike")) else np.nan
        dte_v = int(r["dte"]) if pd.notna(r.get("dte")) else 0
        if pd.isna(spot) or spot <= 0 or pd.isna(ks) or ks <= 0 or not (55 <= dte_v <= 135):
            continue
        rel_m = abs(ks - spot) / spot
        if rel_m > 0.12:
            continue
        bb, aa, mm, _ok = clean_option_quote(r.get("Bid", np.nan), r.get("Ask", np.nan), r.get("price", np.nan))
        if pd.isna(mm) or mm <= 0:
            continue
        exp_s = str(r.get("expiration_date", ""))[:10]
        try:
            d_exp = datetime.strptime(exp_s, "%Y-%m-%d").date()
            tf = third_friday(d_exp.year, d_exp.month)
            monthly_pen = 0.0 if abs((d_exp - tf).days) <= 1 else 0.005
        except ValueError:
            monthly_pen = 0.005
        oi_v = float(r.get("openinterest", 0) or 0)
        score = rel_m + 0.0015 * abs(dte_v - 90) + monthly_pen
        cands.append((score, -oi_v, r, spot, ks, dte_v, exp_s, bb, aa, mm))

    if not cands:
        return empty_res

    cands.sort(key=lambda x: (x[0], x[1]))
    _, _, rb, spot, ks, dte_v, exp_s, bb, aa, mm = cands[0]
    hs_val = max(0.0, (float(aa) - float(bb)) * 0.5) if (pd.notna(aa) and pd.notna(bb) and float(aa) >= float(bb)) else 0.0
    lim25 = max(0.01, float(mm) - 0.25 * hs_val)
    iv_raw = float(rb["iv"]) if pd.notna(rb.get("iv")) and float(rb["iv"]) > 0 else np.nan
    iv_pct = iv_raw * 100.0 if (pd.notna(iv_raw) and iv_raw < 3.0) else iv_raw

    return {
        "opt_matched": True,
        "option_symbol": str(rb.get("option_symbol", "")).strip(),
        "expiration_date": exp_s,
        "dte": int(dte_v),
        "strike": round(float(ks), 2),
        "bid": round(float(bb), 2) if pd.notna(bb) else None,
        "ask": round(float(aa), 2) if pd.notna(aa) else None,
        "mid": round(float(mm), 2),
        "limit_25_price": round(float(lim25), 2),
        "entry_credit_pct": round(float(mm / spot * 100.0), 2),
        "half_spread_pct": round(float(hs_val / spot * 100.0), 3),
        "opt_iv_pct": round(float(iv_pct), 2) if pd.notna(iv_pct) else None,
        "delta": round(float(rb["delta"]), 3) if pd.notna(rb.get("delta")) else None,
        "theta": round(float(rb["theta"]), 3) if pd.notna(rb.get("theta")) else None,
        "vega": round(float(rb["vega"]), 3) if pd.notna(rb.get("vega")) else None,
        "opt_oi": int(float(rb["openinterest"])) if pd.notna(rb.get("openinterest")) else 0,
        "opt_volume": int(float(rb["volume"])) if pd.notna(rb.get("volume")) else 0,
    }


def run_portfolio_signal_scan(
    as_of_date: str | None = None,
    min_market_cap_b: float = 10.0,
    core_ivr_max: float = 25.0,
    reversion_ivr_min: float = 50.0,
    max_half_spread_pct: float = 0.35,
    vix_spike_thresh: float = 24.0,
    price_option_chains: bool = True,
) -> dict[str, Any]:
    t0 = time.time()
    today_dt = datetime.strptime(as_of_date, "%Y-%m-%d").date() if as_of_date else date.today()
    nyse_days = build_nyse_trading_days(today_dt - timedelta(days=60), today_dt + timedelta(days=75))

    future_or_today = [d for d in nyse_days if d >= today_dt.strftime("%Y-%m-%d")]
    ref_trading_day = future_or_today[0]
    ref_idx = nyse_days.index(ref_trading_day)

    client = IVolClient()
    macro = fetch_macro_regime(ref_trading_day, vix_spike_thresh=vix_spike_thresh)
    smd_date, smd_df, common_whitelist = _load_latest_ivol_universe(client, today_dt)
    smd_map = {str(r["symbol"]).strip(): r.to_dict() for _, r in smd_df.iterrows()} if not smd_df.empty else {}

    norm_ivr90_map: dict[str, float] = {}
    ref_norm = REF_DATA_DIR / "normal_ivr_baselines.json"
    if ref_norm.exists():
        try:
            norm_ivr90_map = json.loads(ref_norm.read_text(encoding="utf-8")).get("norm_ivr90", {})
        except Exception:
            pass

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

    seen_syms: set[str] = set()
    candidates: list[dict[str, Any]] = []
    min_mc_usd = min_market_cap_b * 1e9

    raw_earn_rows.sort(key=lambda x: str(x.get("report_date", "")))
    for er in raw_earn_rows:
        raw_sym = str(er.get("symbol", "")).strip().upper()
        if not raw_sym or raw_sym in SECONDARY_SHARE_CLASSES:
            continue
        ivol_sym = raw_sym.replace(".", "/") if raw_sym in ("BRK.B", "BF.B") else raw_sym
        if "." in raw_sym and raw_sym not in ("BRK.B", "BF.B"):
            continue
        if ivol_sym in seen_syms:
            continue

        smd_row = smd_map.get(ivol_sym)
        if smd_row is None:
            continue
        if common_whitelist and ivol_sym not in common_whitelist:
            continue

        nasdaq_mc = _parse_nasdaq_mcap(er.get("marketCap"))
        ivol_mc = float(smd_row.get("marketCap", 0) or 0)
        best_mc = ivol_mc if (ivol_mc >= 1e8 and not pd.isna(ivol_mc)) else nasdaq_mc
        if nasdaq_mc >= 1e9 and ivol_mc <= 0:
            best_mc = nasdaq_mc
        if best_mc < min_mc_usd:
            continue

        ivx90 = float(smd_row.get("ivx90", np.nan))
        ivr90 = float(smd_row.get("ivr90", np.nan))
        ivx30 = float(smd_row.get("ivx30", np.nan))
        ivr30 = float(smd_row.get("ivr30", np.nan))
        spot = float(smd_row.get("close", np.nan))
        if pd.isna(ivr90) or pd.isna(spot) or spot <= 0:
            continue

        seen_syms.add(ivol_sym)
        rep_dt = str(er["report_date"])
        t_raw = str(er.get("time", "")).lower()
        if "after" in t_raw:
            tod_code = "AMC"
            tod_label = "After Market Close"
            later_days = [d for d in nyse_days if d > rep_dt]
            if not later_days:
                continue
            reaction_dt = later_days[0]
        else:
            tod_code = "BMO" if "pre" in t_raw else "BMO (Unconfirmed Time)"
            tod_label = "Before Market Open" if "pre" in t_raw else "Before Open (Conservative Default)"
            later_or_eq = [d for d in nyse_days if d >= rep_dt]
            if not later_or_eq:
                continue
            reaction_dt = later_or_eq[0]

        if reaction_dt not in nyse_days:
            continue
        r_idx = nyse_days.index(reaction_dt)
        if r_idx < 20:
            continue

        exit_dt = nyse_days[r_idx - 1]
        entry_dt = nyse_days[r_idx - 20]
        td_to_reaction = r_idx - ref_idx
        td_to_entry = (r_idx - 20) - ref_idx

        if td_to_reaction < 0 or td_to_reaction > 27:
            continue

        if td_to_reaction == 0:
            window_bucket = "REACTING_TODAY"
        elif td_to_reaction in (1, 2):
            window_bucket = "EXIT_ALERT"
        elif 18 <= td_to_reaction <= 22:
            window_bucket = "ENTRY_WINDOW"
        elif 23 <= td_to_reaction <= 27:
            window_bucket = "WATCHLIST_UPCOMING"
        else:
            window_bucket = "ACTIVE_COHORT"

        norm90 = float(norm_ivr90_map.get(ivol_sym, 27.3))
        excess_norm90 = float(ivr90 - norm90)

        candidates.append({
            "symbol": ivol_sym,
            "company_name": str(smd_row.get("companyName") or er.get("name") or ivol_sym).strip(),
            "industry": str(smd_row.get("industry") or "").replace('"', "").strip(),
            "market_cap_b": round(best_mc / 1e9, 2),
            "spot_price": round(spot, 2),
            "quote_date": smd_date,
            "report_date": rep_dt,
            "release_timing": tod_code,
            "release_timing_label": tod_label,
            "reaction_date": reaction_dt,
            "scheduled_entry_date": entry_dt,
            "scheduled_exit_date": exit_dt,
            "trading_days_to_reaction": int(td_to_reaction),
            "trading_days_to_entry": int(td_to_entry),
            "window_bucket": window_bucket,
            "ivx30_pct": round(ivx30, 2) if pd.notna(ivx30) else None,
            "ivx90_pct": round(ivx90, 2) if pd.notna(ivx90) else None,
            "ivr30": round(ivr30, 1) if pd.notna(ivr30) else None,
            "ivr90": round(ivr90, 1),
            "ivp90": round(float(smd_row.get("ivp90", np.nan)), 1) if pd.notna(smd_row.get("ivp90")) else None,
            "norm_ivr90_baseline": round(norm90, 1),
            "ivr90_excess_vs_norm": round(excess_norm90, 1),
            "total_opt_oi": int(float(smd_row.get("openInterest", 0) or 0)),
            "eps_forecast": str(er.get("epsForecast", "")).strip(),
        })

    active_cohort = [c for c in candidates if c["window_bucket"] == "ACTIVE_COHORT"]
    est_active_core_names = [c for c in active_cohort if c["ivr90"] < (core_ivr_max + 3.0)]
    n_core_active = len(est_active_core_names)
    core_alloc_pct = min(100.0, n_core_active * 10.0)
    idle_capacity_pct = max(0.0, 100.0 - core_alloc_pct)
    idle_slots_count = max(0, 10 - n_core_active)

    chain_targets = [c for c in candidates if c["window_bucket"] in ("ENTRY_WINDOW", "WATCHLIST_UPCOMING", "EXIT_ALERT")]
    opt_results: dict[str, dict[str, Any]] = {}
    if price_option_chains and chain_targets:
        with ThreadPoolExecutor(max_workers=2) as pool:
            fmap = {
                pool.submit(_select_best_90d_atm_put, client, c["symbol"], smd_date, c["spot_price"]): c["symbol"]
                for c in chain_targets
            }
            for fut in as_completed(fmap):
                sym_k = fmap[fut]
                try:
                    opt_results[sym_k] = fut.result()
                except Exception:
                    opt_results[sym_k] = {"opt_matched": False}

    for c in candidates:
        opt_info = opt_results.get(c["symbol"], {"opt_matched": False})
        c.update(opt_info)
        wb = c["window_bucket"]
        ivr = c["ivr90"]
        td_r = c["trading_days_to_reaction"]
        hs = c.get("half_spread_pct")
        spread_ok = (hs is None) or (hs <= max_half_spread_pct)

        if wb == "REACTING_TODAY":
            c["signal_code"] = "FLAT_EARNINGS_REACTION"
            c["signal_label"] = "DO NOT HOLD — Earnings Reaction Today"
            c["signal_tier"] = "EXIT"
            c["recommended_weight_pct"] = 0.0
        elif wb == "EXIT_ALERT":
            c["signal_code"] = "MANDATORY_EXIT_TODAY" if td_r == 1 else "EXIT_NEXT_SESSION"
            c["signal_label"] = "CLOSE POSITION AT EOD TODAY (Day -1)" if td_r == 1 else "PREPARE EXIT NEXT SESSION (Day -2)"
            c["signal_tier"] = "EXIT"
            c["recommended_weight_pct"] = 0.0
        elif wb == "ENTRY_WINDOW":
            if ivr < core_ivr_max:
                if spread_ok and c.get("opt_matched", False):
                    c["signal_code"] = "ENTER_CORE_SLEEVE"
                    c["signal_label"] = "SELL 3M ATM PUT — Core Low-IVR Sleeve"
                    c["signal_tier"] = "ACTIONABLE_ENTRY"
                    c["recommended_weight_pct"] = 10.0
                else:
                    c["signal_code"] = "LIMIT_ONLY_WIDE_SPREAD"
                    c["signal_label"] = "LIMIT ORDER ONLY — Wide Option Spread"
                    c["signal_tier"] = "CAUTION_ENTRY"
                    c["recommended_weight_pct"] = 5.0
            elif ivr >= reversion_ivr_min:
                if macro["post_stress_high_ivr_enabled"] and idle_capacity_pct > 0:
                    if (hs is not None and hs <= (max_half_spread_pct + 0.05)) and c.get("opt_matched", False):
                        c["signal_code"] = "ENTER_POST_STRESS_SLEEVE"
                        c["signal_label"] = "SELL 3M ATM PUT — Post-Stress Mean-Reversion"
                        c["signal_tier"] = "ACTIONABLE_ENTRY"
                        c["recommended_weight_pct"] = min(10.0, idle_capacity_pct)
                    else:
                        c["signal_code"] = "LIMIT_ONLY_WIDE_SPREAD"
                        c["signal_label"] = "LIMIT ORDER ONLY — Post-Stress Wide Spread"
                        c["signal_tier"] = "CAUTION_ENTRY"
                        c["recommended_weight_pct"] = 5.0
                else:
                    c["signal_code"] = "BLOCKED_HIGH_IVR"
                    c["signal_label"] = "BLOCKED — Circuit-Breaker Active (IVR >= 50)"
                    c["signal_tier"] = "FILTERED_OUT"
                    c["recommended_weight_pct"] = 0.0
            else:
                c["signal_code"] = "SKIP_MID_IVR"
                c["signal_label"] = "SKIP / DO NOT TRADE — Mid IV Rank Zone (25–50)"
                c["signal_tier"] = "FILTERED_OUT"
                c["recommended_weight_pct"] = 0.0
        elif wb == "WATCHLIST_UPCOMING":
            c["signal_code"] = "WATCHLIST_UPCOMING"
            c["signal_label"] = f"WATCHLIST (Enters {c['scheduled_entry_date']})"
            c["signal_tier"] = "WATCHLIST"
            c["recommended_weight_pct"] = 0.0
        else:
            c["signal_code"] = "ACTIVE_HOLD"
            c["signal_label"] = f"IN HOLDING WINDOW (Exit {c['scheduled_exit_date']})"
            c["signal_tier"] = "COHORT"
            c["recommended_weight_pct"] = 10.0 if ivr < (core_ivr_max + 3.0) else 0.0

    tier_rank = {"ACTIONABLE_ENTRY": 0, "CAUTION_ENTRY": 1, "EXIT": 2, "WATCHLIST": 3, "FILTERED_OUT": 4, "COHORT": 5}
    candidates.sort(key=lambda x: (tier_rank.get(x["signal_tier"], 9), x["trading_days_to_reaction"], -x["market_cap_b"]))

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scan_elapsed_sec": round(time.time() - t0, 2),
        "macro_regime": macro,
        "portfolio_capacity": {
            "active_cohort_total_gt10b": len(active_cohort),
            "estimated_active_core_positions": n_core_active,
            "estimated_core_allocation_pct": round(core_alloc_pct, 1),
            "available_idle_capacity_pct": round(idle_capacity_pct, 1),
            "available_idle_slots": int(idle_slots_count),
            "cash_collateral_tbill_yield_pct": macro["tbill_3m_yield_pct"],
            "actionable_entry_signals_today": sum(1 for c in candidates if c["signal_tier"] == "ACTIONABLE_ENTRY"),
            "caution_limit_signals_today": sum(1 for c in candidates if c["signal_tier"] == "CAUTION_ENTRY"),
            "mandatory_exit_alerts": sum(1 for c in candidates if c["signal_tier"] == "EXIT" and c["window_bucket"] == "EXIT_ALERT"),
            "upcoming_watchlist_count": sum(1 for c in candidates if c["signal_tier"] == "WATCHLIST"),
        },
        "signals": candidates,
    }

    with open(SCREENER_OUT_DIR / "latest_signals.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    pd.DataFrame(candidates).to_csv(SCREENER_OUT_DIR / "latest_signals.csv", index=False)
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
    with open(SCREENER_OUT_DIR / "nasdaq_earnings_window.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "as_of_date": ref_trading_day,
                "generated_at": payload["generated_at"],
                "macro_regime": macro,
                "raw_earn_rows": compact_earn,
            },
            f,
            separators=(",", ":"),
        )
    return payload
