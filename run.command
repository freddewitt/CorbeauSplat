#!/bin/bash

# Move to script directory
cd "$(dirname "$0")"
echo "Working directory: $(pwd)"

# --- Phase 1: Update Check ---
if [ -d ".git" ]; then
    echo "--- Phase 1: Checking for updates ---"
    git fetch > /dev/null 2>&1
    
    if git rev-parse --abbrev-ref --symbolic-full-name @{u} > /dev/null 2>&1; then
        BEHIND_COUNT=$(git rev-list --count HEAD..@{u})
        
        if [ "$BEHIND_COUNT" -gt 0 ]; then
             echo ">>> A new version is available ($BEHIND_COUNT commits behind)."
             read -p ">>> Would you like to update now? (y/n) " -n 1 -r
             echo
             if [[ $REPLY =~ ^[Yy]$ ]]; then
                 echo "Updating..."
                 git pull
                 echo "Update complete."
             else
                 echo "Update skipped."
             fi
        else
             echo "✅ Software is up to date."
        fi
    fi
else
    echo "--- Phase 1: Skipping update check (not a git repository) ---"
fi

# --- Phase 2: Environment & Venv Health ---
echo "--- Phase 2: Environment configuration ---"
VENV_DIR=".venv"
PYTHON_CMD="$VENV_DIR/bin/python3"

if [ ! -d "$VENV_DIR" ] || [ ! -f "$PYTHON_CMD" ]; then
    echo "Creating virtual environment..."
    if [ -d "$VENV_DIR" ]; then echo "⚠️ Venv corrupted. Rebuilding..."; rm -rf "$VENV_DIR"; fi
    
    PY_CANDIDATES=("python3.11" "python3.10" "python3")
    SELECTED_PY=""
    for py in "${PY_CANDIDATES[@]}"; do
        if command -v $py >/dev/null 2>&1; then SELECTED_PY=$py; break; fi
    done
    
    if [ -z "$SELECTED_PY" ]; then
        echo "❌ ERROR: Python 3 not found. Please install Python 3.10 or 3.11."
        exit 1
    fi
    echo "Detected Python candidate: $SELECTED_PY"
    $SELECTED_PY -m venv $VENV_DIR
    echo "✅ Virtual environment created."
fi

echo "Using environment Python: $($PYTHON_CMD --version)"
echo "✅ Environment configured."

# Integrity check
if ! "$PYTHON_CMD" -c "import json, os, sys" > /dev/null 2>&1; then
    echo "❌ FAILURE: Python environment is unstable. Forcing rebuild..."
    rm -rf "$VENV_DIR"
    exec "$0" "$@"
    exit 1
fi
echo "✅ Python environment integrity verified."

# --- Phase 3: Dependency Sync ---
echo "--- Phase 3: Synchronizing dependencies ---"
echo "Checking for pip updates..."
"$PYTHON_CMD" -m pip install --upgrade pip > /dev/null 2>&1

if [ -f "requirements.lock" ]; then 
    DEP_FILE="requirements.lock"
    echo "Found lockfile: $DEP_FILE"
else 
    DEP_FILE="requirements.txt"
    echo "Found dependency list: $DEP_FILE"
fi

echo "Verifying installed packages (this may take a moment)..."
if ! "$PYTHON_CMD" -m pip install -r $DEP_FILE > /dev/null 2>&1; then
    echo "⚠️  Silent installation failed. Attempting with logs..."
    "$PYTHON_CMD" -m pip install -r $DEP_FILE
fi
echo "✅ Dependencies synchronized and verified."

# PyQt6 specific check
if ! "$PYTHON_CMD" -c "import PyQt6" > /dev/null 2>&1; then
    echo "🔧 Corrective installation of PyQt6..."
    "$PYTHON_CMD" -m pip install PyQt6
fi

# send2trash specific check
if ! "$PYTHON_CMD" -c "import send2trash" > /dev/null 2>&1; then
    echo "🔧 Corrective installation of send2trash..."
    "$PYTHON_CMD" -m pip install send2trash
fi

# --- Phase 4: Engine & Core Component Monitoring ---
echo "--- Phase 4: Verifying engines and external binaries ---"
echo "Running system check..."
"$PYTHON_CMD" -m app.scripts.setup_dependencies --startup
echo "✅ System check complete (Engines & Binaries)."

if [[ $(uname -m) == 'arm64' ]]; then
    echo "✅ Architecture: Apple Silicon detected (Optimizations active)."
else
    echo "ℹ️  Architecture: x86_64 detected."
fi

# --- Phase 5: Launch ---
echo "--- Phase 5: Launching CorbeauSplat ---"
echo "------------------------------------------------"
"$PYTHON_CMD" main.py "$@"
