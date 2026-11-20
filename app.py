"""
Interactive Online & Local Web Server for the Portfolio-Level Pre-Earnings Put-Selling Screener.
Works identically locally (`python app.py`), on cloud Python hosts (`0.0.0.0:$PORT`),
while `index.html` also runs 100% serverless on GitHub Pages!
"""
from __future__ import annotations

import json
import logging
import os
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ivol_client import CREDENTIALS_FILE, load_ivol_credentials
from scanner_engine import SCREENER_OUT_DIR, run_portfolio_signal_scan

PORT = int(os.environ.get("PORT", "8501"))
HOST = os.environ.get("HOST", "0.0.0.0")


class ScreenerRequestHandler(BaseHTTPRequestHandler):
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

    def _send_json(self, obj: dict | list, status: int = 200) -> None:
        self._send_bytes(json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8", status=status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        p = parsed.path

        if p in ("/", "/index.html"):
            self._send_bytes((ROOT_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif p == "/api/health":
            self._send_json({"ok": True})
        elif p in ("/api/signals", "/output/latest_signals.json"):
            jpath = SCREENER_OUT_DIR / "latest_signals.json"
            if not jpath.exists():
                data = run_portfolio_signal_scan()
                self._send_json(data)
            else:
                self._send_bytes(jpath.read_bytes(), "application/json; charset=utf-8")
        elif p == "/output/nasdaq_earnings_window.json":
            epath = SCREENER_OUT_DIR / "nasdaq_earnings_window.json"
            if not epath.exists():
                run_portfolio_signal_scan()
            self._send_bytes(epath.read_bytes(), "application/json; charset=utf-8")
        elif p in ("/api/credentials", "/ivol_credentials.json"):
            self._send_json(load_ivol_credentials())
        elif p in ("/api/export.csv", "/output/latest_signals.csv"):
            cpath = SCREENER_OUT_DIR / "latest_signals.csv"
            if not cpath.exists():
                run_portfolio_signal_scan()
            self._send_bytes(
                cpath.read_bytes(),
                "text/csv; charset=utf-8",
                extra_headers={"Content-Disposition": 'attachment; filename="pre_earnings_put_signals.csv"'},
            )
        elif p in ("/reference_data/us_common_stocks.json", "/reference_data/normal_ivr_baselines.json"):
            rpath = ROOT_DIR / p.lstrip("/")
            if rpath.exists():
                self._send_bytes(rpath.read_bytes(), "application/json; charset=utf-8")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
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
            data = run_portfolio_signal_scan()
            self._send_json(data)
        elif parsed.path == "/api/credentials":
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            clean_creds = {
                "api_key": str(body.get("api_key", "")).strip(),
                "username": str(body.get("username", "")).strip(),
                "password": str(body.get("password", "")).strip(),
                "auth_mode": str(body.get("auth_mode", "")).strip() or ("api_key" if str(body.get("api_key", "")).strip() else "user_pass"),
            }
            CREDENTIALS_FILE.write_text(json.dumps(clean_creds, indent=2) + "\n", encoding="utf-8")
            self._send_json({"ok": True})
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    jpath = SCREENER_OUT_DIR / "latest_signals.json"
    if "--scan" in sys.argv or not jpath.exists():
        print("Running live Portfolio-Calendar scan...")
        run_portfolio_signal_scan()

    chosen_port = PORT
    server = None
    for p_try in range(PORT, PORT + 10):
        try:
            server = ThreadingHTTPServer((HOST, p_try), ScreenerRequestHandler)
            chosen_port = p_try
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError(f"Could not bind port in {PORT}..{PORT + 9}.")

    local_url = f"http://127.0.0.1:{chosen_port}"
    print("=" * 78)
    print(f" Portfolio Pre-Earnings Short Put Screener running at: {local_url}")
    print(" Press Ctrl+C to stop.")
    print("=" * 78)
    if "--no-browser" not in sys.argv and not os.environ.get("PORT"):
        try:
            webbrowser.open(local_url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
