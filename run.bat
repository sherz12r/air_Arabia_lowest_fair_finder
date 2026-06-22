@echo off
:: ─────────────────────────────────────────────────────────────
::  run.bat  -  VFS Global Automation  (Windows)
::  Sets up a virtual environment, installs requirements,
::  and runs main.py.
:: ─────────────────────────────────────────────────────────────

setlocal EnableDelayedExpansion

set VENV_DIR=venv
set REQUIREMENTS=requirements.txt
set MAIN_SCRIPT=main.py

echo ======================================
echo   VFS Global Automation - Setup ^& Run
echo ======================================
echo.

:: ── 1. Check Python availability ──────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on your PATH.
    echo         Please install Python 3.9+ from https://www.python.org
    echo         Make sure to tick "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
echo [INFO] Using %PY_VERSION%

:: ── 2. Create virtual environment if it doesn't exist ─────────
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment in ".\%VENV_DIR%" ...
    python -m venv %VENV_DIR%
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK]   Virtual environment created.
) else (
    echo [INFO] Virtual environment already exists. Skipping creation.
)

:: ── 3. Activate the virtual environment ───────────────────────
echo [INFO] Activating virtual environment ...
call "%VENV_DIR%\Scripts\activate.bat"

:: ── 4. Install / upgrade requirements if needed ───────────────
if not exist "%REQUIREMENTS%" (
    echo [WARN] "%REQUIREMENTS%" not found. Skipping package installation.
) else (
    echo [INFO] Installing packages from "%REQUIREMENTS%" ...
    python -m pip install --upgrade pip --quiet
    python -m pip install -r %REQUIREMENTS% --quiet
    if errorlevel 1 (
        echo [ERROR] Failed to install one or more packages.
        pause
        exit /b 1
    )
    echo [OK]   All packages installed.
)

echo.
echo ------------------------------------
echo   Starting automation ...
echo ------------------------------------
echo.

:: ── 5. Run the script ─────────────────────────────────────────
python %MAIN_SCRIPT%

echo.
echo [INFO] Script finished. Press any key to exit.
pause >nul
endlocal
