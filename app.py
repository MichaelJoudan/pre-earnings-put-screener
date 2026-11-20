"""
Cloud-Ready Online Web Server for the Pre-Earnings Short 3-Month Put Screener.
Primary online deployment runs serverless via GitHub Pages (`index.html`) + GitHub Actions (`scripts/run_scan.py`).
This server is also provided so the exact same repo can run on Render, Railway, Fly.io, or Docker (`0.0.0.0:$PORT`)
with non-blocking background scan polling and zero credential leakage.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ivol_client import load_ivol_credentials
from scanner_engine import SCREENER_OUT_DIR, run_portfolio_signal_scan

PORT = int(os.environ.get("PORT", "8501"))
HOST = os.environ.get("HOST", "0.0.0.0")

_scan_lock = threading.Lock()
_scan_state: dict[str, object] = {"running": False, "error": None, "last_updated": None}


def _background_scan_worker() -> None:
    try:
        data = run_portfolio_signal_scan()
        _scan_state["last_updated"] = data.get("generated_at")
        _scan_state["error"] = None
    except Exception as exc:
        logging.exception("Background live scan failed")
        _scan_state["error"] = str(exc)
    finally:
        _scan_state["running"] = False


class OnlineScreenerHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        pass

    def _send_bytes(self, raw: bytes, content_type: str, status: int = 200, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _send_json(self, obj: dict, status: int = 200) -> None:
        self._send_bytes(json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8", status=status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        p = parsed.path

        if p in ("/", "/index.html"):
            raw = (ROOT_DIR / "index.html").read_bytes()
            self._send_bytes(raw, "text/html; charset=utf-8")
        elif p == "/api/health":
            creds = load_ivol_credentials()
            has_creds = bool(creds["api_key"] or (creds["username"] and creds["password"]))
            self._send_json({"ok": True, "credentials_configured": has_creds})
        elif p == "/api/scan-status":
            self._send_json(dict(_scan_state))
        elif p in ("/api/signals", "/output/latest_signals.json"):
            jpath = SCREENER_OUT_DIR / "latest_signals.json"
            if not jpath.exists():
                data = run_portfolio_signal_scan()
                self._send_json(data)
            else:
                self._send_bytes(jpath.read_bytes(), "application/json; charset=utf-8")
        elif p in ("/api/export.csv", "/output/latest_signals.csv"):
            cpath = SCREENER_OUT_DIR / "latest_signals.csv"
            if not cpath.exists():
                run_portfolio_signal_scan()
            self._send_bytes(
                cpath.read_bytes(),
                "text/csv; charset=utf-8",
                extra_headers={"Content-Disposition": 'attachment; filename="pre_earnings_put_signals.csv"'},
            )
        elif p == "/companion/Pre_Earnings_Portfolio_Regime_Companion.pine":
            ppath = ROOT_DIR / "companion" / "Pre_Earnings_Portfolio_Regime_Companion.pine"
            if ppath.exists():
                self._send_bytes(ppath.read_bytes(), "text/plain; charset=utf-8")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/refresh":
            with _scan_lock:
                if not _scan_state["running"]:
                    _scan_state["running"] = True
                    _scan_state["error"] = None
                    threading.Thread(target=_background_scan_worker, daemon=True).start()
            self._send_json({"ok": True, "running": True})
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    jpath = SCREENER_OUT_DIR / "latest_signals.json"
    if "--scan" in sys.argv or not jpath.exists():
        logging.info("Running initial Portfolio-Calendar scan...")
        run_portfolio_signal_scan()

    server = ThreadingHTTPServer((HOST, PORT), OnlineScreenerHandler)
    logging.info("Pre-Earnings Short Put Screener listening on http://%s:%d", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
