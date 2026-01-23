#!/bin/bash

# Se placer dans le dossier du script
cd "$(dirname "$0")"

# --- Auto Update Check ---
if [ -d ".git" ]; then
    echo "Verification des mises a jour..."
    # Fetch latest changes silently
    git fetch > /dev/null 2>&1
    
    # Check if we have an upstream configured
    if git rev-parse --abbrev-ref --symbolic-full-name @{u} > /dev/null 2>&1; then
        # Count commits behind
        BEHIND_COUNT=$(git rev-list --count HEAD..@{u})
        
        if [ "$BEHIND_COUNT" -gt 0 ]; then
             echo ">>> Une nouvelle version est disponible ($BEHIND_COUNT commits de retard)."
             read -p ">>> Voulez-vous mettre a jour maintenant ? (o/n) " -n 1 -r
             echo
             if [[ $REPLY =~ ^[OoYy]$ ]]; then
                 echo "Mise a jour en cours..."
                 git pull
                 echo "Mise a jour terminee."
             else
                 echo "Mise a jour ignoree."
             fi
        else
             echo "CorbeauSplat est a jour."
        fi
    fi
fi
# -------------------------

# Nom du dossier d'environnement virtuel
VENV_DIR=".venv"

# Vérifier si l'environnement virtuel existe
if [ ! -d "$VENV_DIR" ]; then
    echo "Creation de l'environnement virtuel..."
    
    # Tentative de trouver une version stable de Python (3.11 ou 3.10)
    # Python 3.14+ (bleeding edge) pose probleme avec basicsr/numpy
    PY_CANDIDATES=("python3.11" "python3.10" "python3")
    SELECTED_PY=""
    
    for py in "${PY_CANDIDATES[@]}"; do
        if command -v $py >/dev/null 2>&1; then
            VER=$($py -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            # Check si < 3.12 (safety preference) ou juste use valid one
            echo "Trouve: $py ($VER)"
            SELECTED_PY=$py
            break
        fi
    done
    
    if [ -z "$SELECTED_PY" ]; then
        echo "Aucun Python compatible trouve. Utilisation par defaut de python3..."
        SELECTED_PY="python3"
    fi
    
    echo "Utilisation de $SELECTED_PY pour le venv..."
    $SELECTED_PY -m venv $VENV_DIR
fi

# echo "Activation de l'environnement..."
# source $VENV_DIR/bin/activate
# On utilise directement le binaire du venv pour éviter les problèmes de PEP 668 (externally managed)
PYTHON_CMD="$VENV_DIR/bin/python3"

# Vérification basique
if [ ! -f "$PYTHON_CMD" ]; then
    echo "ERREUR: Python non trouvé dans le venv ($PYTHON_CMD)"
    exit 1
fi

# Mise a jour de pip
echo "Mise a jour de pip..."
# Mise a jour de pip via le venv explicitement
echo "Mise a jour de pip..."
"$PYTHON_CMD" -m pip install --upgrade pip > /dev/null 2>&1

# Toujours vérifier/installer les dépendances
if [ -f "requirements.lock" ]; then
    DEP_FILE="requirements.lock"
    echo "Utilisation de requirements.lock pour une installation reproductible."
elif [ -f "requirements.txt" ]; then
    DEP_FILE="requirements.txt"
    echo "Utilisation de requirements.txt (requirements.lock manquant)."
else
    echo "ERREUR: Ni requirements.lock ni requirements.txt trouves!"
    exit 1
fi

echo "Verification des dependances Python ($DEP_FILE)..."
# Capture output and exit code
# Capture output and exit code
if ! "$PYTHON_CMD" -m pip install -r $DEP_FILE > /dev/null 2>&1; then
    echo "ERREUR: L'installation des dependances a echoue."
    echo "Tentative de reinstallation avec affichage des erreurs :"
    "$PYTHON_CMD" -m pip install -r $DEP_FILE
    echo "Veuillez corriger les erreurs ci-dessus avant de relancer."
    exit 1
fi

# Verification specifique pour PyQt6 qui pose souvent probleme
# Verification specifique pour PyQt6 qui pose souvent probleme
if ! "$PYTHON_CMD" -c "import PyQt6" > /dev/null 2>&1; then
    echo "ERREUR: PyQt6 semble manquant malgre l'installation."
    echo "Tentative d'installation forcee de PyQt6..."
    "$PYTHON_CMD" -m pip install PyQt6
    
    if ! "$PYTHON_CMD" -c "import PyQt6" > /dev/null 2>&1; then
            echo "ECHEC FATAL: Impossible d'importer PyQt6."
            exit 1
    fi
fi

# Vérification et Installation des dépendances externes (Brush)
echo "Verification des moteurs..."
"$PYTHON_CMD" -m app.scripts.setup_dependencies

# Lancer l'application
echo "Lancement de CorbeauSplat..."
"$PYTHON_CMD" main.py "$@"
