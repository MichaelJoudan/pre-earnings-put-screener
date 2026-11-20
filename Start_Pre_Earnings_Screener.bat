@echo off
setlocal
title Pre-Earnings Short 3M Put - Portfolio Signal Screener
cd /d "%~dp0"

echo ============================================================================
echo  Pre-Earnings Short 3-Month Put - Portfolio Signal Screener
echo ============================================================================

set "PY_CMD="
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=python"
    goto :check_deps
)

py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py -3"
    goto :check_deps
)

echo [ERROR] Python 3.9+ was not found on this computer.
pause
exit /b 1

:check_deps
%PY_CMD% -c "import ivolatility, pandas, numpy, requests, yfinance" >nul 2>nul
if %ERRORLEVEL% EQU 0 goto :launch_app

echo [First-Time Setup] Installing required Python libraries...
%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install -r "%~dp0requirements.txt"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Package installation failed.
    pause
    exit /b 1
)

:launch_app
echo  Launching Web Dashboard at: http://127.0.0.1:8501
echo ============================================================================
%PY_CMD% "%~dp0app.py"
pause
