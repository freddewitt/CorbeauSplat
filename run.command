#!/bin/bash

# Se placer dans le dossier du script
cd "$(dirname "$0")"

# Nom du dossier d'environnement virtuel
VENV_DIR=".venv"

# Vérifier si l'environnement virtuel existe
if [ ! -d "$VENV_DIR" ]; then
    echo "Creation de l'environnement virtuel..."
    python3 -m venv $VENV_DIR
    
    echo "Activation de l'environnement..."
    source $VENV_DIR/bin/activate
    
    echo "Installation des dependances..."
    # Mise à jour pip par sécurité
    pip install --upgrade pip
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        echo "ERREUR: requirements.txt non trouve!"
        exit 1
    fi
else
    echo "Activation de l'environnement..."
    source $VENV_DIR/bin/activate
    source $VENV_DIR/bin/activate
fi

# Vérification et Installation des dépendances externes (Brush)
echo "Verification des moteurs..."
python3 -m app.scripts.setup_dependencies

# Lancer l'application
echo "Lancement de CorbeauSplat..."
python3 main.py "$@"
