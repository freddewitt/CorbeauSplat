#!/bin/bash
set -euo pipefail

# Move to script directory
cd "$(dirname "$0")"

# --- Verbatim output (step-by-step), cleanly formatted ---
say() {
	# Informational message, always displayed.
	echo "$@"
}

phase() {
	# Section header visually separates major launch stages.
	echo ""
	echo "── $1 ──"
}

# --- Phase 0: Clean Reset (--clean flag) & argument filtering ---
CLEAN_MODE=false
FILTERED_ARGS=()
for arg in "$@"; do
	if [ "$arg" = "--clean" ]; then
		CLEAN_MODE=true
	else
		FILTERED_ARGS+=("$arg")
	fi
done

say "Working directory: $(pwd)"

if [ "$CLEAN_MODE" = true ]; then
	echo ""
	echo "⚠️  CLEAN MODE DETECTED"
	echo "    This will delete:"
	echo "      - .venv, .venv_sharp, .venv_360, .venv_4dgs  (Python environments)"
	echo "      - engines/  (COLMAP, Brush, Glomap binaries...)"
	echo "      - config.json  (configuration)"
	echo ""
	read -p "    Confirm full reset? (y/n): " -n 1 -r
	echo
	if [[ $REPLY =~ ^[YyOo]$ ]]; then
		echo "🧹 Cleaning up..."
		# The four venvs of the project: .venv_4dgs (nerfstudio) was being omitted,
		# leaving the heaviest one survive a "complete reset".
		# See _VENV_4DGS in app/core/four_dgs_engine.py.
		rm -rf ".venv" ".venv_sharp" ".venv_360" ".venv_4dgs" "engines" "config.json"
		say "✅ Cleanup complete."
	else
		say "ℹ️  Cleanup skipped."
	fi
	CLEAN_MODE=false
fi

# --- Phase 0.5: CLT (Command Line Tools) ---
phase "Phase 0.5 — Xcode Command Line Tools Check"

if ! xcode-select -p > /dev/null 2>&1; then
	echo ""
	echo "⚠️  Xcode Command Line Tools not installed."
	echo "    CorbeauSplat requires development tools."
	read -p "    Install now? (y/n) " -n 1 -r
	echo
	if [[ $REPLY =~ ^[YyOo]$ ]]; then
		say ">>> Opening Apple installer (a window will appear)..."
		xcode-select --install 2>/dev/null
		echo ""
		echo "    Complete the installation in the window, then press Enter."
		read -p "    Press Enter when done..."
		if ! xcode-select -p > /dev/null 2>&1; then
			echo "❌ Installation not detected. Please install manually, then relaunch CorbeauSplat."
			exit 1
		fi
		say "✅ Installation complete."
	else
		echo "⚠️  Skipped. Some features may not work."
	fi
else
	say "✅ Xcode Command Line Tools: $(xcode-select -p)"
fi

# 2. Homebrew
BREW_BIN=""
# Check known locations before relying on PATH (especially after fresh Apple Silicon install)
if [[ -x "/opt/homebrew/bin/brew" ]]; then BREW_BIN="/opt/homebrew/bin/brew"
elif [[ -x "/usr/local/bin/brew" ]]; then BREW_BIN="/usr/local/bin/brew"
elif command -v brew > /dev/null 2>&1; then BREW_BIN="$(command -v brew)"
fi

if [ -z "$BREW_BIN" ]; then
	echo ""
	echo "⚠️  Required component missing: Homebrew."
	echo "    It installs tools used by CorbeauSplat (ffmpeg, COLMAP, Node.js...)."
	read -p "    Install now? (y/n) " -n 1 -r
	echo
	if [[ $REPLY =~ ^[YyOo]$ ]]; then
		say ">>> Downloading installer..."
		BREW_INSTALL_SCRIPT="/tmp/homebrew-install.sh"
		# Pinned to known version + SHA256 to prevent MITM
		BREW_TAG="4.4.23"
		BREW_SHA256="c63e04915a08f4ded2f5f710fb6b83d8070245e5e30bdffb5d6b462fd1c9089e"
		curl -fsSL "https://raw.githubusercontent.com/Homebrew/install/${BREW_TAG}/install.sh" -o "$BREW_INSTALL_SCRIPT"

		# Verify SHA256
		COMPUTED_SHA=$(shasum -a 256 "$BREW_INSTALL_SCRIPT" | cut -d' ' -f1)
		if [ "$COMPUTED_SHA" != "$BREW_SHA256" ]; then
			echo "❌ SHA256 mismatch (Homebrew installer)."
			echo "    Expected: $BREW_SHA256"
			echo "    Got:      $COMPUTED_SHA"
			echo "    Install Homebrew manually from https://brew.sh then relaunch CorbeauSplat."
			rm -f "$BREW_INSTALL_SCRIPT"
			exit 1
		fi
		say "✅ Verification passed. Installing Homebrew..."
		/bin/bash "$BREW_INSTALL_SCRIPT"
		rm -f "$BREW_INSTALL_SCRIPT"
		# Activate Homebrew in current shell session
		if [[ -x "/opt/homebrew/bin/brew" ]]; then
			eval "$(/opt/homebrew/bin/brew shellenv)"
			BREW_BIN="/opt/homebrew/bin/brew"
		elif [[ -x "/usr/local/bin/brew" ]]; then
			eval "$(/usr/local/bin/brew shellenv)"
			BREW_BIN="/usr/local/bin/brew"
		fi
		if [ -z "$BREW_BIN" ]; then
			echo "❌ Homebrew installation failed or not detected."
			echo "    Install manually from https://brew.sh then relaunch CorbeauSplat."
			exit 1
		fi
		say "✅ Homebrew installed."
		say "$("$BREW_BIN" --version | head -1)"
	else
		echo "⚠️  Skipped. Some system tools may not install correctly."
	fi
else
	# Ensure brew in PATH for rest of session
	eval "$("$BREW_BIN" shellenv)" 2>/dev/null
	say "✅ Homebrew: $("$BREW_BIN" --version | head -1)"
fi

# --- Phase 1: Update Check ---
if [ -d ".git" ]; then
	phase "Phase 1 — Checking for Updates"
	git fetch > /dev/null 2>&1 || true

	if git rev-parse --abbrev-ref --symbolic-full-name @{u} > /dev/null 2>&1; then
		BEHIND_COUNT=$(git rev-list --count HEAD..@{u})
		AHEAD_COUNT=$(git rev-list --count @{u}..HEAD)

		if [ "$AHEAD_COUNT" -gt 0 ]; then
			say "ℹ️  Local branch ahead of GitHub ($AHEAD_COUNT commit(s)). No updates applied."
		fi
		if [ "$BEHIND_COUNT" -gt 0 ]; then
			echo ""
			echo "ℹ️  Updates available on GitHub ($BEHIND_COUNT commit(s) behind)."
			echo "    CorbeauSplat can be updated."
			read -p "    Update now? (y/n) " -n 1 -r
			echo
			if [[ $REPLY =~ ^[YyOo]$ ]]; then
				say ">>> Pulling updates..."
				git pull
				say "✅ Updated to latest version (new launcher session will use updated code)."
				exit 0
			fi
		fi
	fi
else
	phase "Phase 1 — Update Check (skipped — not a git repo)"
fi

# --- Phase 2: Environment & Venv Health ---
phase "Phase 2 — Preparing Environment"
VENV_DIR=".venv"
PYTHON_CMD="$VENV_DIR/bin/python3"

if [ ! -d "$VENV_DIR" ] || [ ! -f "$PYTHON_CMD" ]; then
	say "Creating virtual environment..."
	if [ -d "$VENV_DIR" ]; then echo "⚠️  Corrupted environment detected. Rebuilding..."; rm -rf "$VENV_DIR"; fi

	PY_CANDIDATES=("python3.13" "python3.12" "python3.11" "python3.10" "python3")
	SELECTED_PY=""
	for py in "${PY_CANDIDATES[@]}"; do
		if command -v $py >/dev/null 2>&1; then SELECTED_PY=$py; break; fi
	done

	if [ -z "$SELECTED_PY" ]; then
		echo "❌ Python 3 not found. Please install Python 3.13 (or newer) then relaunch CorbeauSplat."
		exit 1
	fi
	say "Python detected: $SELECTED_PY"
	$SELECTED_PY -m venv $VENV_DIR
	say "✅ Virtual environment created."
fi

say "Python in use: $($PYTHON_CMD --version)"
say "✅ Environment configured."

# Integrity check
_REBUILD_COUNT="${_REBUILD_COUNT:-0}"
if ! "$PYTHON_CMD" -c "import json, os, sys" > /dev/null 2>&1; then
	_REBUILD_COUNT=$((_REBUILD_COUNT + 1))
	if [ "$_REBUILD_COUNT" -gt 2 ]; then
		echo "❌ Unable to prepare environment after multiple attempts. Aborting."
		exit 1
	fi
	echo "⚠️  Python environment is unstable. Rebuilding (${_REBUILD_COUNT}/2)..."
	rm -rf "$VENV_DIR"
	_REBUILD_COUNT="$_REBUILD_COUNT" "$0" "${FILTERED_ARGS[@]}"
	exit $?
fi

# --- Phase 3: Dependency Synchronization ---
phase "Phase 3 — Synchronizing Dependencies"
"$PYTHON_CMD" -m pip install --upgrade pip > /dev/null 2>&1

if [ -f "requirements.lock" ]; then
	say "Lockfile found: requirements.lock"
	DEP_FILE="requirements.lock"
else
	say "Lockfile not found. Using requirements.txt"
	DEP_FILE="requirements.txt"
fi

if ! "$PYTHON_CMD" -m pip install -r $DEP_FILE > /dev/null 2>&1; then
	echo "⚠️  Installation encountered issues. Retrying with full output..."
	"$PYTHON_CMD" -m pip install -r $DEP_FILE
fi

say "Checking critical modules..."
# These four modules were previously reinstalled one-by-one via a bare
# "pip install <package>" when the import failed. Two problems: the version
# installed would silently overwrite the one in the lockfile, and trimesh was
# never declared anywhere — it reached the venv only via this workaround,
# invisible to anyone reading requirements.lock. They are now declared; this
# remains a check only, no installation.
MISSING_MODULES=""
for mod in PySide6 send2trash plyfile trimesh; do
	if ! "$PYTHON_CMD" -c "import $mod" > /dev/null 2>&1; then
		MISSING_MODULES="$MISSING_MODULES $mod"
	fi
done
if [ -n "$MISSING_MODULES" ]; then
	echo "❌ Modules missing despite sync:$MISSING_MODULES"
	echo "    The $DEP_FILE file could not be fully applied."
	echo "    Relaunch, or reinstall manually: $PYTHON_CMD -m pip install -r $DEP_FILE"
	exit 1
fi
say "✅ Dependencies synchronized and verified."

# --- Apply CorbeauSplat icon to launcher file in Finder ---
# Best-effort idempotent: metadata not tracked by git, so
# run on every launch (see app/scripts/set_launcher_icon.py details).
"$PYTHON_CMD" -m app.scripts.set_launcher_icon > /dev/null 2>&1 || true

# --- Phase 4: Engine & Core Component Monitoring ---
phase "Phase 4 — Checking Engines and External Binaries"
"$PYTHON_CMD" -m app.scripts.setup_dependencies --startup

# --- Phase 5: Launching CorbeauSplat ---
phase "Phase 5 — Launching CorbeauSplat"
say "CorbeauSplat…"
echo ""

if [ ${#FILTERED_ARGS[@]} -gt 0 ]; then
	"$PYTHON_CMD" main.py "${FILTERED_ARGS[@]}"
else
	"$PYTHON_CMD" main.py
fi
