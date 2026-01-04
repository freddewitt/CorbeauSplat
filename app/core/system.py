import platform
import os
import shutil

def resolve_project_root():
    """Finds project root relative to this script (app/core/system.py)"""
    # app/core/system.py -> app/core -> app -> root
    current = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(current))

def is_apple_silicon():
    """Détecte si on est sur Apple Silicon"""
    return platform.system() == 'Darwin' and platform.machine() == 'arm64'

def get_optimal_threads():
    """Retourne le nombre optimal de threads pour Apple Silicon"""
    if is_apple_silicon():
        cpu_count = os.cpu_count() or 8
        return max(1, int(cpu_count * 0.75))
    return os.cpu_count() or 4

def resolve_binary(name):
    """
    Résoud le chemin d'un binaire en priorisant le dossier 'engines' local.
    Retourne le chemin absolu ou le nom si trouvé dans le PATH, sinon None.
    """
    # 1. Chercher dans le dossier engines à la racine du projet
    # On remonte de app/core/ à la racine
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir)) # app -> project
    engines_dir = os.path.join(project_root, "engines")
    
    local_path = os.path.join(engines_dir, name)
    
    # Cas binaire direct
    if os.path.exists(local_path) and os.access(local_path, os.X_OK):
        return local_path
        
    # Cas macOS .app bundle pour COLMAP
    if name == "colmap":
        colmap_app = os.path.join(engines_dir, "COLMAP.app", "Contents", "MacOS", "colmap")
        if os.path.exists(colmap_app) and os.access(colmap_app, os.X_OK):
            return colmap_app
            
    # 2. Chercher dans le PATH système
    return shutil.which(name)

def check_dependencies():
    """Vérifie si les dépendances nécessaires sont installées"""
    missing = []
    
    # Check ffmpeg
    if resolve_binary('ffmpeg') is None:
        missing.append('ffmpeg')
        
    # Check colmap
    if resolve_binary('colmap') is None:
        missing.append('colmap')
        
    return missing
