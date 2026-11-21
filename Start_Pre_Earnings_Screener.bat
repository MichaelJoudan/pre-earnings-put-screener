@echo off
setlocal
title Pre-Earnings Short 3M Put - Portable Signal Screener
cd /d "%~dp0"

echo ============================================================================
echo  Pre-Earnings Short 3-Month Put - Portfolio Signal Screener (Windows)
echo ============================================================================

rem Auto-detect portable layout (app_files\) vs flat repo layout
if exist "%~dp0app_files\app.py" (
    set "APP_SCRIPT=%~dp0app_files\app.py"
    set "REQ_FILE=%~dp0app_files\requirements.txt"
) else (
    set "APP_SCRIPT=%~dp0app.py"
    set "REQ_FILE=%~dp0requirements.txt"
)

rem Detect Python 3.9+ executable (supports standard `python` or Windows `py -3`)
set "PY_CMD="

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=python"
    goto :setup_venv
)

py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py -3"
    goto :setup_venv
)

echo.
echo [ERROR] Python 3.9+ was not found on this computer.
echo Please install Python from https://www.python.org/downloads/
echo IMPORTANT: Check the box "Add python.exe to PATH" during installation,
echo then double-click this .bat file again.
echo.
pause
exit /b 1

:setup_venv
set "VENV_DIR=%~dp0.venv_win"
set "RUN_PY=%VENV_DIR%\Scripts\python.exe"

"%RUN_PY%" -c "import sys" >nul 2>nul
if %ERRORLEVEL% EQU 0 goto :check_deps

echo.
echo [First-Time Setup] Creating isolated Windows virtual environment (.venv_win)...
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
%PY_CMD% -m venv "%VENV_DIR%" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    set "RUN_PY=%PY_CMD%"
)

:check_deps
%RUN_PY% -c "import ivolatility, pandas, numpy, requests, yfinance" >nul 2>nul
if %ERRORLEVEL% EQU 0 goto :launch_app

echo.
echo [First-Time Setup] Installing required Python libraries on this device...
%RUN_PY% -m pip install --upgrade pip
%RUN_PY% -m pip install -r "%REQ_FILE%"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Package installation failed. Check internet connection and retry.
    pause
    exit /b 1
)
echo [First-Time Setup] Completed successfully!

:launch_app
echo.
echo  Launching Web Dashboard at: http://127.0.0.1:8501
echo  Keep this window open while using the screener. Close or press Ctrl+C to stop.
echo ============================================================================
%RUN_PY% "%APP_SCRIPT%"
pause
