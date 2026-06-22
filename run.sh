#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  run.sh  –  VFS Global Automation  (macOS / Linux)
#  Sets up a virtual environment, installs requirements,
#  and runs main.py.
# ─────────────────────────────────────────────────────────────

set -e  # Exit immediately on any error

VENV_DIR="venv"
REQUIREMENTS="requirements.txt"
MAIN_SCRIPT="main.py"

echo "======================================"
echo "  VFS Global Automation – Setup & Run"
echo "======================================"
echo ""

# ── 1. Check Python availability ──────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "[ERROR] Python is not installed or not on your PATH."
    echo "        Please install Python 3.9+ from https://www.python.org"
    exit 1
fi

echo "[INFO] Using Python: $($PYTHON --version)"

# ── 2. Create virtual environment if it doesn't exist ─────────
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Creating virtual environment in './$VENV_DIR' ..."
    $PYTHON -m venv "$VENV_DIR"
    echo "[OK]   Virtual environment created."
else
    echo "[INFO] Virtual environment already exists. Skipping creation."
fi

# ── 3. Activate the virtual environment ───────────────────────
echo "[INFO] Activating virtual environment ..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ── 4. Install / upgrade requirements if needed ───────────────
if [ ! -f "$REQUIREMENTS" ]; then
    echo "[WARN] '$REQUIREMENTS' not found. Skipping package installation."
else
    echo "[INFO] Installing packages from '$REQUIREMENTS' ..."
    pip install --upgrade pip --quiet
    pip install -r "$REQUIREMENTS" --quiet
    echo "[OK]   All packages installed."
fi

echo ""
echo "────────────────────────────────────"
echo "  Starting automation ...           "
echo "────────────────────────────────────"
echo ""

# ── 5. Run the script ─────────────────────────────────────────
$PYTHON "$MAIN_SCRIPT"
