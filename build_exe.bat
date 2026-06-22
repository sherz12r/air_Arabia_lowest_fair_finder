@echo off
:: Build VFS Global Automation as a single Windows .exe (opens the dashboard)
setlocal EnableDelayedExpansion

set VENV_DIR=venv
set SPEC=vfs_automation.spec

echo ======================================
echo   Building VFS Global Automation.exe
echo ======================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    pause
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [INFO] Creating virtual environment...
    python -m venv %VENV_DIR%
)

call "%VENV_DIR%\Scripts\activate.bat"

echo [INFO] Installing project and build dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet

echo [INFO] Running PyInstaller (this may take several minutes)...
pyinstaller --noconfirm --clean %SPEC%

if errorlevel 1 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo ======================================
echo   Build complete
echo ======================================
echo.
echo   Your app is here:
echo   dist\VFS Global Automation.exe
echo.
echo   Send that .exe to your client. They still need:
echo   - Google Chrome installed
echo   - Internet connection
echo.
echo   config.json, billing.json, and logs\ are created
echo   in the same folder as the .exe when they run it.
echo.
pause >nul
endlocal
