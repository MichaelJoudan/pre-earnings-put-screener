"""
Cloud & Local iVolatility EOD REST API Client.
Supports switching seamlessly between API Key authentication and Username/Password token authentication.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import logging
import os
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import ivolatility as ivol
from ivolatility import ivolatility as ivol_mod
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT_DIR.parent if ROOT_DIR.name == "app_files" else ROOT_DIR
CREDENTIALS_FILE = PROJECT_ROOT / "ivol_credentials.json"
CACHE_DIR = Path(os.environ.get("IVOL_CACHE_DIR", str(ROOT_DIR / "cache")))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def load_ivol_credentials() -> dict[str, str]:
    """Load credentials dynamically from env vars -> ivol_credentials.json -> defaults."""
    file_creds: dict[str, str] = {}
    if CREDENTIALS_FILE.exists():
        try:
            file_creds = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
        except Exception:
            file_creds = {}
    api_key = (os.environ.get("IVOL_API_KEY") or file_creds.get("api_key", "")).strip()
    username = (os.environ.get("IVOL_USERNAME") or file_creds.get("username", "")).strip()
    password = (os.environ.get("IVOL_PASSWORD") or file_creds.get("password", "")).strip()
    auth_mode = (os.environ.get("IVOL_AUTH_MODE") or file_creds.get("auth_mode", "")).strip()
    if auth_mode not in ("api_key", "user_pass"):
        auth_mode = "api_key" if api_key else "user_pass"
    return {
        "api_key": api_key,
        "username": username,
        "password": password,
        "auth_mode": auth_mode,
    }


class IVolClient:
    """Self-contained wrapper around iVolatility SDK with local disk cache & CSV repair."""

    _rate_lock = threading.Lock()
    _inflight_sem = threading.BoundedSemaphore(2)
    _last_req_ts: float = 0.0
    _min_req_interval: float = 0.65

    def __init__(
        self,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        auth_mode: str | None = None,
        cache_dir: Path = CACHE_DIR,
    ) -> None:
        creds = load_ivol_credentials()
        self.api_key = creds["api_key"] if api_key is None else api_key
        self.username = creds["username"] if username is None else username
        self.password = creds["password"] if password is None else password
        self.auth_mode = creds["auth_mode"] if auth_mode is None else auth_mode
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._query_auth_params: dict[str, str] = {}

        use_user_pass = (self.auth_mode == "user_pass" and self.username and self.password) or (
            not self.api_key and self.username and self.password
        )

        if use_user_pass:
            tok = ivol.getToken(self.username, self.password).strip().strip('"')
            ivol.setLoginParams(username=self.username, password=self.password, token=tok)
            self._query_auth_params = {"token": tok}
        elif self.api_key:
            ivol.setLoginParams(apiKey=self.api_key)
        else:
            raise ValueError(
                "Missing iVolatility credentials. Enter an API Key or Username & Password in iVolatility API Keys."
            )

        _polite_retry = Retry(total=2, backoff_factor=1.5, status_forcelist=[500, 502, 503, 504])
        _hi_adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=_polite_retry)
        ivol_mod._session.mount("https://", _hi_adapter)
        ivol_mod._session.mount("http://", _hi_adapter)

        self._get_underlying_info = ivol.setMethod("/equities/underlying-info")
        self._get_opts_by_param = ivol.setMethod("/equities/eod/stock-opts-by-param")

    @classmethod
    def _throttle(cls) -> None:
        with cls._rate_lock:
            now = time.monotonic()
            wait = cls._min_req_interval - (now - cls._last_req_ts)
            if wait > 0:
                time.sleep(wait)
            cls._last_req_ts = time.monotonic()

    def _cache_path(self, namespace: str, key_str: str) -> Path:
        ns_dir = self.cache_dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in key_str)
        if len(safe) > 100:
            digest = hashlib.md5(key_str.encode("utf-8")).hexdigest()[:12]
            safe = f"{safe[:80]}_{digest}"
        return ns_dir / f"{safe}.csv.gz"

    def _read_cache(self, path: Path) -> pd.DataFrame | None:
        if not path.exists():
            return None
        try:
            if path.stat().st_size == 0:
                return pd.DataFrame()
            return pd.read_csv(path, compression="gzip", low_memory=False)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except Exception:
            return None

    def _write_cache(self, path: Path, df: pd.DataFrame) -> None:
        tmp_path = path.with_suffix(".tmp.gz")
        if df is None or df.empty:
            with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
                f.write("")
        else:
            df.to_csv(tmp_path, index=False, compression="gzip")
        tmp_path.replace(path)

    def get_stock_market_data(self, trade_date: str, stock_group: str = "ALL_USA") -> pd.DataFrame:
        cpath = self._cache_path("stock_market_data", f"{stock_group}_{trade_date}")
        cached = self._read_cache(cpath)
        if cached is not None:
            return cached

        url = (
            f"{ivol_mod.restApiURL}/equities/stock-market-data"
            f"?stockGroup={stock_group}&from={trade_date}&to={trade_date}"
        )
        for attempt in range(1, 7):
            try:
                self._throttle()
                resp = ivol_mod._session.get(
                    url,
                    params=self._query_auth_params or None,
                    auth=ivol_mod.__auth__,
                    timeout=120,
                )
                if resp.status_code == 429:
                    time.sleep(10.0 * attempt)
                    continue
                resp.raise_for_status()
                if resp.status_code == 204 or not resp.content:
                    df = pd.DataFrame()
                    self._write_cache(cpath, df)
                    return df

                ctype = resp.headers.get("content-type", "")
                if "json" in ctype or "text/plain" in ctype:
                    payload = resp.json()
                    if isinstance(payload, list):
                        df = pd.DataFrame(payload)
                    else:
                        det_url = payload.get("status", {}).get("urlForDetails")
                        if det_url:
                            df = self._download_and_repair_smd_csv(det_url)
                        else:
                            df = pd.DataFrame(payload.get("data", []))
                elif "csv" in ctype:
                    df = self._parse_repaired_csv_bytes(resp.content, is_gzip=False)
                else:
                    df = pd.read_csv(BytesIO(resp.content), low_memory=False)

                self._write_cache(cpath, df)
                return df
            except Exception as exc:
                logger.warning("Attempt %d failed for SMD %s: %s", attempt, trade_date, exc)
                if attempt == 6:
                    raise
                time.sleep(8.0 * attempt)
        return pd.DataFrame()

    def _download_and_repair_smd_csv(self, det_url: str, timeout: float = 360.0) -> pd.DataFrame:
        start = time.time()
        dl_url = None
        while time.time() - start < timeout:
            self._throttle()
            r = ivol_mod._session.get(
                det_url,
                params=self._query_auth_params or None,
                auth=ivol_mod.__auth__,
                timeout=120,
            )
            r.raise_for_status()
            j = r.json()
            status = j[0]["meta"]["status"]
            if status == "COMPLETE":
                data_list = j[0].get("data", [])
                if data_list and "urlForDownload" in data_list[0]:
                    dl_url = data_list[0]["urlForDownload"]
                    break
                return pd.DataFrame()
            time.sleep(0.5)

        if not dl_url:
            raise TimeoutError(f"Timed out waiting for iVolatility file: {det_url}")

        with ivol_mod._download_semaphore:
            self._throttle()
            rc = ivol_mod._session.get(dl_url, auth=ivol_mod.__auth__, timeout=timeout)
            rc.raise_for_status()
        return self._parse_repaired_csv_bytes(rc.content, is_gzip=True)

    @staticmethod
    def _parse_repaired_csv_bytes(raw_bytes: bytes, is_gzip: bool = True) -> pd.DataFrame:
        text = gzip.decompress(raw_bytes).decode("utf-8", errors="replace") if is_gzip else raw_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if not lines:
            return pd.DataFrame()

        reader = csv.reader(lines)
        header = next(reader, None)
        if not header:
            return pd.DataFrame()

        ncol = len(header)
        ind_idx = header.index("industry") if "industry" in header else 45
        fixed_rows: list[list[str]] = []
        for row in reader:
            if not row:
                continue
            rlen = len(row)
            if rlen != ncol:
                if rlen > ncol:
                    extra = rlen - ncol
                    row = row[:ind_idx] + [",".join(row[ind_idx : ind_idx + 1 + extra])] + row[ind_idx + 1 + extra :]
                    if len(row) != ncol:
                        continue
                else:
                    continue
            fixed_rows.append(row)

        df = pd.DataFrame(fixed_rows, columns=header)
        num_cols = [
            "close", "open", "high", "low", "ask", "bid", "VWAP", "marketCap",
            "outstandingShares", "stockVolume", "optVol", "openInterest",
            "ivx30", "ivx60", "ivx90", "ivr30", "ivr60", "ivr90", "ivp30", "ivp60", "ivp90",
        ]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    def get_underlying_info(self, date_str: str) -> pd.DataFrame:
        cpath = self._cache_path("underlying_info", date_str)
        cached = self._read_cache(cpath)
        if cached is not None:
            return cached
        df = self._call_with_retry(self._get_underlying_info, date=date_str)
        self._write_cache(cpath, df)
        return df

    def get_options_by_param(
        self,
        symbol: str,
        trade_date: str,
        dte_from: int,
        dte_to: int,
        moneyness_from: float,
        moneyness_to: float,
        cp: str,
    ) -> pd.DataFrame:
        key = f"{symbol}_{trade_date}_{dte_from}_{dte_to}_{int(moneyness_from)}_{int(moneyness_to)}_{cp}"
        cpath = self._cache_path("opts_by_param", key)
        cached = self._read_cache(cpath)
        if cached is not None:
            return cached
        df = self._call_with_retry(
            self._get_opts_by_param,
            symbol=symbol,
            tradeDate=trade_date,
            dteFrom=dte_from,
            dteTo=dte_to,
            moneynessFrom=moneyness_from,
            moneynessTo=moneyness_to,
            cp=cp,
            region="USA",
        )
        self._write_cache(cpath, df)
        return df

    @classmethod
    def _call_with_retry(cls, fn: Any, **kwargs: Any) -> pd.DataFrame:
        for attempt in range(1, 7):
            try:
                with cls._inflight_sem:
                    cls._throttle()
                    res = fn(**kwargs)
                return res if isinstance(res, pd.DataFrame) else pd.DataFrame()
            except requests.HTTPError as exc:
                sc = exc.response.status_code if exc.response is not None else 0
                if sc in (400, 404):
                    return pd.DataFrame()
                wait_s = min(60.0, (12.0 if sc == 429 else 8.0) * attempt)
                if attempt == 6:
                    raise
                time.sleep(wait_s)
            except requests.RequestException:
                if attempt == 6:
                    raise
                time.sleep(min(60.0, 10.0 * attempt))
        return pd.DataFrame()
