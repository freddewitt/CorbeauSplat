import platform
import os
import shutil
import subprocess
from pathlib import Path

def resolve_project_root() -> Path:
    """Finds project root relative to this script (app/core/system.py)"""
    return Path(__file__).resolve().parent.parent.parent

def is_apple_silicon():
    """Détecte si on est sur Apple Silicon"""
    return platform.system() == 'Darwin' and platform.machine() == 'arm64'


def get_optimal_threads():
    """Retourne le nombre optimal de threads pour Apple Silicon (P-cores) ou autres plateformes"""
    if is_apple_silicon():
        # Apple Silicon has heterogeneous P-cores (performance) + E-cores (efficiency).
        # For compute-heavy tasks (COLMAP, ffmpeg), we prefer P-cores only.
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                p_cores = int(result.stdout.strip())
                if p_cores > 0:
                    return p_cores
        except (ValueError, subprocess.SubprocessError, OSError):
            pass
        # Fallback: assume P-cores are half of total (conservative for M1/M2/M3)
        cpu_count = os.cpu_count() or 8
        return max(1, cpu_count // 2)
    return os.cpu_count() or 4

def resolve_binary(name):
    """
    Résoud le chemin d'un binaire en priorisant le dossier 'engines' local.
    Retourne le chemin absolu ou le nom si trouvé dans le PATH, sinon None.
    """
    # 1. Chercher dans le dossier engines à la racine du projet
    engines_dir = resolve_project_root() / "engines"
    
    local_path = engines_dir / name
    
    # Cas binaire direct
    if local_path.exists() and os.access(local_path, os.X_OK):
        return str(local_path)
        
    # Cas macOS .app bundle pour COLMAP
    if name == "colmap":
        colmap_app = engines_dir / "COLMAP.app" / "Contents" / "MacOS" / "colmap"
        if colmap_app.exists() and os.access(colmap_app, os.X_OK):
            return str(colmap_app)
            
    # 2. Chercher dans le PATH système
    return shutil.which(name)

def get_device():
    """Centralized device selection: mps, cuda, or cpu"""
    if is_apple_silicon():
        return "mps"
    import shutil
    if shutil.which("nvidia-smi") is not None:
        return "cuda"
    return "cpu"

def get_memory_info():
    """Returns memory info for UMA/caching strategies"""
    import psutil
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "available": mem.available,
        "percent": mem.percent
    }

def check_dependencies():
    """Vérifie si les dépendances nécessaires sont installées"""
    missing = []
    
    # Check ffmpeg
    if resolve_binary('ffmpeg') is None:
        missing.append('ffmpeg')
        
    # Check colmap
    if resolve_binary('colmap') is None:
        missing.append('colmap')

    # Check send2trash
    try:
        import send2trash  # noqa: F401
    except ImportError:
        missing.append('send2trash')

    return missing
