#!/bin/bash
set -euo pipefail

# Move to script directory
cd "$(dirname "$0")"

# --- Verbosity: default mode shows simple French messages; --verbose (or
# CORBEAU_VERBOSE=1) restores the full technical output for debugging.
VERBOSE=false
if [ "${CORBEAU_VERBOSE:-0}" = "1" ]; then
    VERBOSE=true
fi

say() {
    # Friendly, reassuring message shown in both modes.
    echo "$@"
}

detail() {
    # Technical detail, shown only when VERBOSE=true.
    if [ "$VERBOSE" = true ]; then
        echo "$@"
    fi
}

# --- Phase 0: Clean Reset (--clean flag) & argument filtering ---
CLEAN_MODE=false
FILTERED_ARGS=()
# --verbose is only intercepted here when no CLI subcommand is present, since
# "sharp" already defines its own --verbose flag that must keep flowing through
# to main.py unchanged when used from the command line.
KNOWN_SUBCOMMANDS="pipeline colmap brush sharp view upscale 4dgs clean splattransform extract360"
HAS_SUBCOMMAND=false
for arg in "$@"; do
    for sub in $KNOWN_SUBCOMMANDS; do
        if [ "$arg" = "$sub" ]; then
            HAS_SUBCOMMAND=true
        fi
    done
done

for arg in "$@"; do
    if [ "$arg" = "--clean" ]; then
        CLEAN_MODE=true
    elif [ "$arg" = "--verbose" ] && [ "$HAS_SUBCOMMAND" = false ]; then
        VERBOSE=true
    else
        FILTERED_ARGS+=("$arg")
    fi
done

detail "Working directory: $(pwd)"

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
detail "--- Phase 0.5: Checking prerequisites ---"
say "Vérification de l'installation…"

# 1. Xcode Command Line Tools
if ! xcode-select -p > /dev/null 2>&1; then
    echo ""
    echo "⚠️  Un composant Apple nécessaire (outils de développement en ligne de commande) n'est pas installé."
    echo "    Il est requis pour que CorbeauSplat puisse fonctionner correctement."
    read -p "    L'installer maintenant ? (o/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[OoYy]$ ]]; then
        say ">>> Ouverture de l'installateur Apple (une fenêtre va s'ouvrir)..."
        xcode-select --install 2>/dev/null
        echo ""
        echo "    Terminez l'installation dans la fenêtre qui s'est ouverte, puis appuyez sur Entrée."
        read -p "    Appuyez sur Entrée quand c'est fait..."
        if ! xcode-select -p > /dev/null 2>&1; then
            echo "❌ Installation non détectée. Merci de l'installer manuellement, puis relancez CorbeauSplat."
            exit 1
        fi
        say "✅ Installation terminée."
    else
        echo "⚠️  Installation ignorée. Certaines fonctionnalités pourraient ne pas fonctionner."
    fi
else
    detail "✅ Xcode Command Line Tools: $(xcode-select -p)"
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
    echo "⚠️  Un composant nécessaire (Homebrew) n'est pas installé."
    echo "    Il permet d'installer les outils utilisés par CorbeauSplat (ffmpeg, COLMAP, Node.js...)."
    read -p "    L'installer maintenant ? (o/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[OoYy]$ ]]; then
        say ">>> Téléchargement de l'installateur Homebrew..."
        BREW_INSTALL_SCRIPT="/tmp/homebrew-install.sh"
        # Pin to a specific commit tag for integrity (avoids MITM on the raw.githubusercontent CDN)
        # Update BREW_TAG and BREW_SHA256 when a new Homebrew release is needed.
        BREW_TAG="4.4.23"
        BREW_SHA256="c63e04915a08f4ded2f5f710fb6b83d8070245e5e30bdffb5d6b462fd1c9089e"
        curl -fsSL "https://raw.githubusercontent.com/Homebrew/install/${BREW_TAG}/install.sh" -o "$BREW_INSTALL_SCRIPT" || {
            echo "❌ Le téléchargement de l'installateur Homebrew a échoué."
            exit 1
        }
        say ">>> Vérification de l'intégrité du fichier téléchargé..."
        COMPUTED_SHA=$(shasum -a 256 "$BREW_INSTALL_SCRIPT" | cut -d' ' -f1)
        if [ "$COMPUTED_SHA" != "$BREW_SHA256" ]; then
            echo "❌ Le fichier téléchargé ne correspond pas à celui attendu (SHA256 différent) !"
            echo "   Attendu : $BREW_SHA256"
            echo "   Obtenu  : $COMPUTED_SHA"
            echo "   Installez Homebrew manuellement depuis https://brew.sh puis relancez CorbeauSplat."
            rm -f "$BREW_INSTALL_SCRIPT"
            exit 1
        fi
        say "✅ Vérification réussie. Installation de Homebrew en cours..."
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
            echo "❌ L'installation de Homebrew a échoué ou n'a pas été détectée."
            echo "   Installez-le manuellement depuis https://brew.sh puis relancez CorbeauSplat."
            exit 1
        fi
        say "✅ Homebrew installé."
        detail "$("$BREW_BIN" --version | head -1)"
    else
        echo "⚠️  Installation ignorée. Certains outils système pourraient ne pas s'installer correctement."
    fi
else
    # Ensure brew is in PATH for the rest of this session
    eval "$("$BREW_BIN" shellenv)" 2>/dev/null
    detail "✅ Homebrew: $("$BREW_BIN" --version | head -1)"
fi

# --- Phase 1: Update Check ---
if [ -d ".git" ]; then
    detail "--- Phase 1: Checking for updates ---"
    git fetch > /dev/null 2>&1 || true

    if git rev-parse --abbrev-ref --symbolic-full-name @{u} > /dev/null 2>&1; then
        BEHIND_COUNT=$(git rev-list --count HEAD..@{u})
        AHEAD_COUNT=$(git rev-list --count @{u}..HEAD)

        if [ "$AHEAD_COUNT" -gt 0 ]; then
            detail "ℹ️  Local version is ahead of GitHub ($AHEAD_COUNT commit(s)). No update applied."
        elif [ "$BEHIND_COUNT" -gt 0 ]; then
             echo ""
             echo "ℹ️  Une nouvelle version de CorbeauSplat est disponible."
             read -p "    La mettre à jour maintenant ? (o/n) " -n 1 -r
             echo
             if [[ $REPLY =~ ^[OoYy]$ ]]; then
                 say "Mise à jour en cours…"
                 git pull
                 say "✅ Mise à jour terminée."
             else
                 say "Mise à jour ignorée."
             fi
        else
             detail "✅ Software is up to date."
        fi
    fi
else
    detail "--- Phase 1: Skipping update check (not a git repository) ---"
fi

# --- Phase 2: Environment & Venv Health ---
detail "--- Phase 2: Environment configuration ---"
say "Préparation en cours…"
VENV_DIR=".venv"
PYTHON_CMD="$VENV_DIR/bin/python3"

if [ ! -d "$VENV_DIR" ] || [ ! -f "$PYTHON_CMD" ]; then
    detail "Creating virtual environment..."
    if [ -d "$VENV_DIR" ]; then detail "⚠️ Venv corrupted. Rebuilding..."; rm -rf "$VENV_DIR"; fi

    PY_CANDIDATES=("python3.13" "python3.12" "python3.11" "python3.10" "python3")
    SELECTED_PY=""
    for py in "${PY_CANDIDATES[@]}"; do
        if command -v $py >/dev/null 2>&1; then SELECTED_PY=$py; break; fi
    done

    if [ -z "$SELECTED_PY" ]; then
        echo "❌ Python 3 introuvable. Merci d'installer Python 3.13 (ou plus récent) puis de relancer CorbeauSplat."
        exit 1
    fi
    detail "Detected Python candidate: $SELECTED_PY"
    $SELECTED_PY -m venv $VENV_DIR
    detail "✅ Virtual environment created."
fi

detail "Using environment Python: $($PYTHON_CMD --version)"
detail "✅ Environment configured."

# Integrity check
_REBUILD_COUNT="${_REBUILD_COUNT:-0}"
if ! "$PYTHON_CMD" -c "import json, os, sys" > /dev/null 2>&1; then
    _REBUILD_COUNT=$((_REBUILD_COUNT + 1))
    if [ "$_REBUILD_COUNT" -gt 2 ]; then
        echo "❌ Impossible de préparer l'environnement après plusieurs tentatives. Abandon."
        exit 1
    fi
    echo "⚠️  L'environnement Python est instable. Reconstruction en cours (tentative ${_REBUILD_COUNT}/2)..."
    rm -rf "$VENV_DIR"
    exec env _REBUILD_COUNT="$_REBUILD_COUNT" "$0" "$@"
    exit 1
fi
detail "✅ Python environment integrity verified."

# --- Phase 3: Dependency Sync ---
detail "--- Phase 3: Synchronizing dependencies ---"
detail "Checking for pip updates..."
"$PYTHON_CMD" -m pip install --upgrade pip > /dev/null 2>&1

if [ -f "requirements.lock" ]; then
    DEP_FILE="requirements.lock"
    detail "Found lockfile: $DEP_FILE"
else
    DEP_FILE="requirements.txt"
    detail "Found dependency list: $DEP_FILE"
fi

detail "Verifying installed packages (this may take a moment)..."
if ! "$PYTHON_CMD" -m pip install -r $DEP_FILE > /dev/null 2>&1; then
    echo "⚠️  L'installation silencieuse a échoué. Nouvelle tentative avec les détails..."
    "$PYTHON_CMD" -m pip install -r $DEP_FILE
fi
detail "✅ Dependencies synchronized and verified."

# PySide6 specific check
if ! "$PYTHON_CMD" -c "import PySide6" > /dev/null 2>&1; then
    echo "🔧 Installation de PySide6..."
    "$PYTHON_CMD" -m pip install PySide6
fi

# send2trash specific check
if ! "$PYTHON_CMD" -c "import send2trash" > /dev/null 2>&1; then
    echo "🔧 Installation de send2trash..."
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

# --- Apply the CorbeauSplat icon to this launcher file in the Finder ---
# Best-effort and idempotent: metadata is not tracked by git, so this must
# run on every launch (see app/scripts/set_launcher_icon.py for details).
"$PYTHON_CMD" -m app.scripts.set_launcher_icon > /dev/null 2>&1 || true

# --- Phase 4: Engine & Core Component Monitoring ---
detail "--- Phase 4: Verifying engines and external binaries ---"
if [ "$VERBOSE" = true ]; then
    "$PYTHON_CMD" -m app.scripts.setup_dependencies --startup
else
    _PHASE4_LOG=$(mktemp)
    if ! "$PYTHON_CMD" -m app.scripts.setup_dependencies --startup > "$_PHASE4_LOG" 2>&1; then
        echo "❌ Une erreur est survenue pendant la vérification des outils :"
        cat "$_PHASE4_LOG"
        rm -f "$_PHASE4_LOG"
        exit 1
    fi
    rm -f "$_PHASE4_LOG"
fi
detail "✅ System check complete (Engines & Binaries)."

if [[ $(uname -m) == 'arm64' ]]; then
    detail "✅ Architecture: Apple Silicon detected (Optimizations active)."
else
    detail "ℹ️  Architecture: x86_64 detected."
fi

# --- Phase 5: Launch ---
detail "--- Phase 5: Launching CorbeauSplat ---"
say "Lancement de CorbeauSplat…"
detail "------------------------------------------------"
if [ ${#FILTERED_ARGS[@]} -gt 0 ]; then
    "$PYTHON_CMD" main.py "${FILTERED_ARGS[@]}"
else
    "$PYTHON_CMD" main.py
fi
