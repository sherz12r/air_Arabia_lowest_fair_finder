@echo off
:: ─────────────────────────────────────────────────────────────
::  run_dashboard.bat  -  VFS Global Automation GUI (Windows)
:: ─────────────────────────────────────────────────────────────

setlocal EnableDelayedExpansion

set VENV_DIR=venv
set REQUIREMENTS=requirements.txt
set DASHBOARD_SCRIPT=dashboard.py

echo ======================================
echo   VFS Global Automation - Dashboard
echo ======================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on your PATH.
    pause
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment ...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"

if exist "%REQUIREMENTS%" (
    python -m pip install --upgrade pip --quiet
    python -m pip install -r %REQUIREMENTS% --quiet
)

echo [INFO] Launching dashboard ...
python %DASHBOARD_SCRIPT%

echo.
pause >nul
endlocal
