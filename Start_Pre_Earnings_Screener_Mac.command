#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

printf '\033]0;Pre-Earnings Short 3M Put - Portfolio Signal Screener\007'
echo "============================================================================"
echo " Pre-Earnings Short 3-Month Put - Portfolio Signal Screener (macOS)"
echo "============================================================================"

PY_CMD=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
            PY_CMD="$candidate"
            break
        fi
    fi
done

if [ -z "$PY_CMD" ]; then
    echo ""
    echo "[ERROR] Python 3.9+ was not found on this Mac."
    echo "Please install Python from https://www.python.org/downloads/macos/"
    read -r -p "Press Enter to close..."
    exit 1
fi

VENV_DIR="$SCRIPT_DIR/.venv_mac"
if ! "$VENV_DIR/bin/python" -c "import sys" >/dev/null 2>&1; then
    echo ""
    echo "[First-Time Setup] Creating local Python virtual environment..."
    rm -rf "$VENV_DIR"
    "$PY_CMD" -m venv "$VENV_DIR" || exit 1
fi

VENV_PY="$VENV_DIR/bin/python"

if ! "$VENV_PY" -c "import ivolatility, pandas, numpy, requests, yfinance" >/dev/null 2>&1; then
    echo ""
    echo "[First-Time Setup] Installing required Python libraries..."
    "$VENV_PY" -m pip install --upgrade pip
    "$VENV_PY" -m pip install -r "$SCRIPT_DIR/requirements.txt" || exit 1
fi

CERT_PATH="$("$VENV_PY" -c "import certifi; print(certifi.where())" 2>/dev/null)"
if [ -n "$CERT_PATH" ]; then
    export SSL_CERT_FILE="$CERT_PATH"
fi

echo ""
echo " Launching Web Dashboard at: http://127.0.0.1:8501"
echo "============================================================================"
"$VENV_PY" "$SCRIPT_DIR/app.py" "$@"
read -r -p "Press Enter to close..."
