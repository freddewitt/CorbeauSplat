#!/bin/bash
set -euo pipefail

# Move to script directory
cd "$(dirname "$0")"
echo "Working directory: $(pwd)"

# --- Phase 0: Clean Reset (--clean flag) ---
CLEAN_MODE=false
FILTERED_ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--clean" ]; then
        CLEAN_MODE=true
    else
        FILTERED_ARGS+=("$arg")
    fi
done

if [ "$CLEAN_MODE" = true ]; then
    echo ""
    echo "⚠️  MODE CLEAN DÉTECTÉ"
    echo "    Ceci va supprimer :"
    echo "      - .venv, .venv_sharp, .venv_360  (environnements Python)"
    echo "      - engines/                        (binaires COLMAP, Brush, Glomap...)"
    echo "      - config.json                     (configuration)"
    echo ""
    read -p "    Confirmer la réinitialisation complète ? (o/n) : " -n 1 -r
    echo
    if [[ $REPLY =~ ^[OoYy]$ ]]; then
        echo "🧹 Nettoyage en cours..."
        rm -rf ".venv" ".venv_sharp" ".venv_360" "engines" "config.json"
        echo "✅ Réinitialisation complète effectuée."
    else
        echo "Annulé. Lancement normal."
        CLEAN_MODE=false
    fi
    echo ""
fi

# --- Phase 0.5: Prerequisites (Xcode CLT + Homebrew) ---
echo "--- Phase 0.5: Checking prerequisites ---"

# 1. Xcode Command Line Tools
if ! xcode-select -p > /dev/null 2>&1; then
    echo ""
    echo "⚠️  Xcode Command Line Tools not found."
    echo "    Required for: git, compilers, build tools."
    read -p "    Install now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ">>> Launching Xcode CLT installer (a dialog will open)..."
        xcode-select --install 2>/dev/null
        echo ""
        echo "    Complete the installation in the dialog, then press Enter to continue."
        read -p "    Press Enter when done..."
        if ! xcode-select -p > /dev/null 2>&1; then
            echo "❌ Xcode CLT still not detected. Please install manually and relaunch."
            exit 1
        fi
        echo "✅ Xcode Command Line Tools installed."
    else
        echo "⚠️  Skipped. Some features may not work without Xcode CLT."
    fi
else
    echo "✅ Xcode Command Line Tools: $(xcode-select -p)"
fi

# 2. Homebrew
BREW_BIN=""
# Check known locations before relying on PATH (especially after a fresh Apple Silicon install)
if   [[ -x "/opt/homebrew/bin/brew" ]]; then BREW_BIN="/opt/homebrew/bin/brew"
elif [[ -x "/usr/local/bin/brew"    ]]; then BREW_BIN="/usr/local/bin/brew"
elif command -v brew > /dev/null 2>&1;  then BREW_BIN="$(command -v brew)"
fi

if [ -z "$BREW_BIN" ]; then
    echo ""
    echo "⚠️  Homebrew not found."
    echo "    Required for: ffmpeg, COLMAP, Node.js, libomp, cmake..."
    read -p "    Install Homebrew now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ">>> Downloading Homebrew install script..."
        BREW_INSTALL_SCRIPT="/tmp/homebrew-install.sh"
        # Pin to a specific commit tag for integrity (avoids MITM on the raw.githubusercontent CDN)
        # Update BREW_TAG and BREW_SHA256 when a new Homebrew release is needed.
        BREW_TAG="4.4.23"
        BREW_SHA256="c63e04915a08f4ded2f5f710fb6b83d8070245e5e30bdffb5d6b462fd1c9089e"
        curl -fsSL "https://raw.githubusercontent.com/Homebrew/install/${BREW_TAG}/install.sh" -o "$BREW_INSTALL_SCRIPT" || {
            echo "❌ Failed to download Homebrew install script."
            exit 1
        }
        echo ">>> Verifying checksum..."
        COMPUTED_SHA=$(shasum -a 256 "$BREW_INSTALL_SCRIPT" | cut -d' ' -f1)
        if [ "$COMPUTED_SHA" != "$BREW_SHA256" ]; then
            echo "❌ SHA256 mismatch!"
            echo "   Expected: $BREW_SHA256"
            echo "   Got:      $COMPUTED_SHA"
            echo "   Install manually from https://brew.sh and relaunch."
            rm -f "$BREW_INSTALL_SCRIPT"
            exit 1
        fi
        echo "✅ Checksum verified. Installing Homebrew..."
        /bin/bash "$BREW_INSTALL_SCRIPT"
        rm -f "$BREW_INSTALL_SCRIPT"
        # Activate Homebrew in the current shell session
        if   [[ -x "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
            BREW_BIN="/opt/homebrew/bin/brew"
        elif [[ -x "/usr/local/bin/brew" ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
            BREW_BIN="/usr/local/bin/brew"
        fi
        if [ -z "$BREW_BIN" ]; then
            echo "❌ Homebrew installation failed or not found."
            echo "   Install manually from https://brew.sh and relaunch."
            exit 1
        fi
        echo "✅ Homebrew installed: $("$BREW_BIN" --version | head -1)"
    else
        echo "⚠️  Skipped. System tools (ffmpeg, COLMAP...) may fail to install."
    fi
else
    # Ensure brew is in PATH for the rest of this session
    eval "$("$BREW_BIN" shellenv)" 2>/dev/null
    echo "✅ Homebrew: $("$BREW_BIN" --version | head -1)"
fi

# --- Phase 1: Update Check ---
if [ -d ".git" ]; then
    echo "--- Phase 1: Checking for updates ---"
    git fetch > /dev/null 2>&1 || true
    
    if git rev-parse --abbrev-ref --symbolic-full-name @{u} > /dev/null 2>&1; then
        BEHIND_COUNT=$(git rev-list --count HEAD..@{u})
        AHEAD_COUNT=$(git rev-list --count @{u}..HEAD)

        if [ "$AHEAD_COUNT" -gt 0 ]; then
            echo "ℹ️  Local version is ahead of GitHub ($AHEAD_COUNT commit(s)). No update applied."
        elif [ "$BEHIND_COUNT" -gt 0 ]; then
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
    
    PY_CANDIDATES=("python3.13" "python3.12" "python3.11" "python3.10" "python3")
    SELECTED_PY=""
    for py in "${PY_CANDIDATES[@]}"; do
        if command -v $py >/dev/null 2>&1; then SELECTED_PY=$py; break; fi
    done

    if [ -z "$SELECTED_PY" ]; then
        echo "❌ ERROR: Python 3 not found. Please install Python 3.13+."
        exit 1
    fi
    echo "Detected Python candidate: $SELECTED_PY"
    $SELECTED_PY -m venv $VENV_DIR
    echo "✅ Virtual environment created."
fi

echo "Using environment Python: $($PYTHON_CMD --version)"
echo "✅ Environment configured."

# Integrity check
_REBUILD_COUNT="${_REBUILD_COUNT:-0}"
if ! "$PYTHON_CMD" -c "import json, os, sys" > /dev/null 2>&1; then
    _REBUILD_COUNT=$((_REBUILD_COUNT + 1))
    if [ "$_REBUILD_COUNT" -gt 2 ]; then
        echo "❌ FATAL: Environment rebuild loop detected. Aborting."
        exit 1
    fi
    echo "❌ FAILURE: Python environment is unstable. Forcing rebuild (attempt ${_REBUILD_COUNT}/2)..."
    rm -rf "$VENV_DIR"
    exec env _REBUILD_COUNT="$_REBUILD_COUNT" "$0" "$@"
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

# PySide6 specific check
if ! "$PYTHON_CMD" -c "import PySide6" > /dev/null 2>&1; then
    echo "🔧 Corrective installation of PySide6..."
    "$PYTHON_CMD" -m pip install PySide6
fi

# send2trash specific check
if ! "$PYTHON_CMD" -c "import send2trash" > /dev/null 2>&1; then
    echo "🔧 Corrective installation of send2trash..."
    "$PYTHON_CMD" -m pip install send2trash
fi

# Export module dependencies check
if ! "$PYTHON_CMD" -c "import plyfile" > /dev/null 2>&1; then
    echo "🔧 Installation de plyfile (export PLY)..."
    "$PYTHON_CMD" -m pip install plyfile
fi

# trimesh for GLB export
if ! "$PYTHON_CMD" -c "import trimesh" > /dev/null 2>&1; then
    echo "🔧 Installation de trimesh (export GLB)..."
    "$PYTHON_CMD" -m pip install trimesh
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
if [ ${#FILTERED_ARGS[@]} -gt 0 ]; then
    "$PYTHON_CMD" main.py "${FILTERED_ARGS[@]}"
else
    "$PYTHON_CMD" main.py
fi
