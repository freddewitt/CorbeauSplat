# CorbeauSplat

## Stack
- Python 3.13+ (JIT activé), macOS Apple Silicon uniquement
- GUI : PySide6/tkinter
- Dépendances externes : COLMAP, Glomap, Brush, SuperSplat, FFmpeg, Homebrew
- Pas de framework de test formel pour l'instant

## Commandes essentielles
- Lancer : `./run.command`
- Installer les dépendances Python : `pip install -r requirements.txt`
- Point d'entrée : `main.py`

## Architecture
- `app/` : modules GUI par onglet (un module = un onglet)
- `main.py` : orchestrateur principal
- Les processus externes (COLMAP, Brush...) sont lancés via `subprocess`

## Règles importantes
- macOS Silicon UNIQUEMENT — ne jamais suggérer de solution Linux/Windows
- Toujours vérifier la disponibilité d'une dépendance avant de l'utiliser
- Les sorties utilisateur vont dans `[OutputFolder]/[ProjectName]/`
- IMPORTANT : avant tout changement GUI, lire le module concerné dans `app/`

## Contexte Obsidian
Vault : /Users/frederick/Documents/Obsidian/Sandbox2000/03_dev/CorbeauSplat/
Consulter decisions.md pour l'historique des choix d'architecture

## Gestion du contexte
Quand le contexte dépasse 50% d'utilisation (visible via /context), 
lance automatiquement /compact avant de continuer.
