#!/usr/bin/env bash

# Switch to the folder containing this script (macOS equivalent of cd /d "%~dp0")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Include common macOS Python locations (Homebrew on Apple Silicon/Intel & python.org)
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

printf '\033]0;Pre-Earnings Short 3M Put - Portable Signal Screener\007'
echo "============================================================================"
echo " Pre-Earnings Short 3-Month Put - Portfolio Signal Screener (macOS)"
echo "============================================================================"

# Auto-detect portable layout (app_files/) vs flat repo layout
if [ -f "$SCRIPT_DIR/app_files/app.py" ]; then
    APP_SCRIPT="$SCRIPT_DIR/app_files/app.py"
    REQ_FILE="$SCRIPT_DIR/app_files/requirements.txt"
else
    APP_SCRIPT="$SCRIPT_DIR/app.py"
    REQ_FILE="$SCRIPT_DIR/requirements.txt"
fi

# Detect Python 3.9+ executable
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
    echo "or via Homebrew: brew install python"
    echo ""
    read -r -p "Press Enter to close..."
    exit 1
fi

# Create (or repair if moved between Macs) a local virtual environment (.venv_mac)
VENV_DIR="$SCRIPT_DIR/.venv_mac"
if ! "$VENV_DIR/bin/python" -c "import sys" >/dev/null 2>&1; then
    echo ""
    echo "[First-Time Setup] Creating local Python virtual environment..."
    rm -rf "$VENV_DIR"
    if ! "$PY_CMD" -m venv "$VENV_DIR"; then
        echo "[ERROR] Failed to create virtual environment."
        read -r -p "Press Enter to close..."
        exit 1
    fi
fi

VENV_PY="$VENV_DIR/bin/python"

# Auto-check & install required packages on first run
if ! "$VENV_PY" -c "import ivolatility, pandas, numpy, requests, yfinance" >/dev/null 2>&1; then
    echo ""
    echo "[First-Time Setup] Installing required Python libraries on this Mac..."
    "$VENV_PY" -m pip install --upgrade pip
    if ! "$VENV_PY" -m pip install -r "$REQ_FILE"; then
        echo ""
        echo "[ERROR] Package installation failed. Check internet connection and retry."
        read -r -p "Press Enter to close..."
        exit 1
    fi
    echo "[First-Time Setup] Completed successfully!"
fi

# Ensure macOS python.org builds use certifi CA bundle if needed
CERT_PATH="$("$VENV_PY" -c "import certifi; print(certifi.where())" 2>/dev/null)"
if [ -n "$CERT_PATH" ]; then
    export SSL_CERT_FILE="$CERT_PATH"
fi

echo ""
echo " Launching Web Dashboard at: http://127.0.0.1:8501"
echo " Keep this window open while using the screener. Close or press Ctrl+C to stop."
echo "============================================================================"
"$VENV_PY" "$APP_SCRIPT" "$@"
read -r -p "Press Enter to close..."
