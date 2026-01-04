import os
import sys
import shutil
import subprocess

BRUSH_REPO = "https://github.com/ArthurBrussee/brush.git"
SHARP_REPO = "https://github.com/apple/ml-sharp.git"

def resolve_project_root():
    """Finds project root relative to this script"""
    current = os.path.dirname(os.path.abspath(__file__))
    # app/scripts -> app -> root
    return os.path.dirname(os.path.dirname(current))

def check_cargo():
    """Checks if cargo is available"""
    return shutil.which("cargo") is not None

def get_remote_version(repo_url):
    """Gets the latest commit hash from the remote git repository"""
    try:
        # git ls-remote returns tab-separated list of refs. We want HEAD.
        output = subprocess.check_output(["git", "ls-remote", repo_url, "HEAD"], text=True).strip()
        if output:
            return output.split()[0]
    except Exception as e:
        print(f"Attention: Impossible de verifier la version distante pour {repo_url}: {e}")
    return None

def get_local_version(version_file):
    """Reads the installed version from a file"""
    if os.path.exists(version_file):
        try:
            with open(version_file, "r") as f:
                return f.read().strip()
        except:
            pass
    return None

def save_local_version(version_file, version):
    """Saves the installed version to a file"""
    if version:
        try:
            with open(version_file, "w") as f:
                f.write(version)
        except Exception as e:
            print(f"Attention: Impossible d'enregistrer la version locale: {e}")

def install_brush(engines_dir, version_file, target_version=None):
    """Installs brush using cargo"""
    print("--- Installation de Brush (Gaussian Splatting Engine) ---")
    
    if not check_cargo():
        print("ERREUR: 'cargo' (Rust) n'est pas installe.")
        print("Veuillez installer Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
        return False
        
    print("Cargo detecte. Telechargement et compilation de Brush depuis GitHub...")
    print("Cette operation peut prendre plusieurs minutes la premiere fois.")
    
    if target_version is None:
        target_version = get_remote_version(BRUSH_REPO)

    try:
        cmd = [
            "cargo", "install", 
            "--git", BRUSH_REPO, 
            "brush-app", 
            "--root", engines_dir 
        ]
        
        subprocess.check_call(cmd)
        
        # Move from engines/bin/brush (or brush-app) to engines/brush
        bin_dir = os.path.join(engines_dir, "bin")
        
        possible_names = ["brush", "brush-app"]
        installed_bin = None
        
        for name in possible_names:
            path = os.path.join(bin_dir, name)
            if os.path.exists(path):
                installed_bin = path
                break
                
        target_path = os.path.join(engines_dir, "brush")
        
        if installed_bin:
            shutil.move(installed_bin, target_path)
            try:
                shutil.rmtree(bin_dir) 
            except:
                pass 
            
            # Save version
            save_local_version(version_file, target_version)
            
            print(f"Brush installe avec succes: {target_path}")
            return True
        else:
            print("Erreur: Le binaire compile n'a pas ete trouve dans 'bin'.")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de la compilation de Brush: {e}")
        return False
    except Exception as e:
        print(f"Erreur inattendue: {e}")
        return False

def install_sharp(engines_dir, version_file, target_version=None):
    """Installs apple/ml-sharp"""
    print("--- Installation de Sharp (Apple ML) ---")
    
    target_dir = os.path.join(engines_dir, "ml-sharp")
    
    try:
        if target_version is None:
            target_version = get_remote_version(SHARP_REPO)

        # Clone or Pull
        if not os.path.exists(target_dir):
            print(f"Clonage de {SHARP_REPO}...")
            subprocess.check_call(["git", "clone", SHARP_REPO, target_dir])
        else:
            print(f"Mise a jour de Sharp...")
            subprocess.check_call(["git", "-C", target_dir, "pull"])
            
        # Install dependencies
        print("Installation des dependances Python de Sharp...")
        # Sharp recommended: python 3.13, pip install -r requirements.txt
        # We use current python env
        requirements_file = os.path.join(target_dir, "requirements.txt")
        if os.path.exists(requirements_file):
            # Important: run from target_dir because requirements.txt contains '-e .'
            loose_req_file = os.path.join(target_dir, "requirements_loose.txt")
            relax_requirements(requirements_file, loose_req_file)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_loose.txt"], cwd=target_dir)
        
        # Install the package itself in editable mode usually, or just dependencies?
        if os.path.exists(os.path.join(target_dir, "setup.py")) or os.path.exists(os.path.join(target_dir, "pyproject.toml")):
             print("Installation du package sharp...")
             subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "."], cwd=target_dir)
        
        save_local_version(version_file, target_version)
        print("Sharp installe avec succes.")
        return True
    
    except Exception as e:
        print(f"Erreur lors de l'installation de Sharp: {e}")
        return False

SUPERPLAT_REPO = "https://github.com/playcanvas/supersplat.git"

def check_node():
    """Checks if node and npm are available"""
    node = shutil.which("node")
    npm = shutil.which("npm")
    return node is not None and npm is not None

def install_supersplat(engines_dir, version_file, target_version=None):
    """Installs Supersplat"""
    print("--- Installation de SuperSplat ---")
    
    if not check_node():
        print("ERREUR: 'node' et 'npm' sont requis pour SuperSplat.")
        print("Veuillez installer Node.js -> https://nodejs.org/")
        return False
        
    target_dir = os.path.join(engines_dir, "supersplat")
    
    try:
        if target_version is None:
            target_version = get_remote_version(SUPERPLAT_REPO)

        # Clone or Pull
        if not os.path.exists(target_dir):
            print(f"Clonage de {SUPERPLAT_REPO}...")
            subprocess.check_call(["git", "clone", SUPERPLAT_REPO, target_dir])
        else:
            print(f"Mise a jour de SuperSplat...")
            subprocess.check_call(["git", "-C", target_dir, "pull"])
            
        # Install dependencies
        print("Installation des dependances NPM de SuperSplat...")
        subprocess.check_call(["npm", "install"], cwd=target_dir)
        
        # Build
        print("Compilation de SuperSplat (Build)...")
        subprocess.check_call(["npm", "run", "build"], cwd=target_dir)
        
        save_local_version(version_file, target_version)
        print("SuperSplat installe avec succes.")
        return True
    
    except Exception as e:
        print(f"Erreur lors de l'installation de SuperSplat: {e}")
        return False

def relax_requirements(src, dst):
    """
    Creates a copy of requirements.txt with relaxed version constraints 
    for packages that might cause issues (like torch).
    """
    with open(src, 'r') as f_in, open(dst, 'w') as f_out:
        for line in f_in:
            # Relax torch and torchvision strict pins
            if line.strip().startswith('torch==') or line.strip().startswith('torchvision=='):
                line = line.replace('==', '>=')
            f_out.write(line)

def check_brew():
    """Checks if homebrew is available"""
    return shutil.which("brew") is not None

def install_system_dependencies():
    """Installs COLMAP and FFmpeg via Homebrew"""
    print("--- Verification des dependances systeme (Homebrew) ---")
    
    missing = []
    if shutil.which("colmap") is None: 
        missing.append("colmap")
    if shutil.which("ffmpeg") is None: 
        missing.append("ffmpeg")
        
    if not missing:
        print("Dependances systeme (COLMAP, FFmpeg) presentes.")
        return True
        
    print(f"Dependances manquantes : {', '.join(missing)}")
    
    if not check_brew():
        print("ERREUR: Homebrew n'est pas installe. Impossible d'installer COLMAP/FFmpeg automatiquement.")
        print("Veuillez installer Homebrew : https://brew.sh/")
        print("Ou installez manuellement: brew install colmap ffmpeg")
        return False
        
    print("Tentative d'installation via Homebrew...")
    try:
        if "colmap" in missing:
            print("Installation de COLMAP...")
            subprocess.check_call(["brew", "install", "colmap"])
        if "ffmpeg" in missing:
            print("Installation de FFmpeg...")
            subprocess.check_call(["brew", "install", "ffmpeg"])
        print("Dependances systeme installees.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'installation Homebrew: {e}")
        return False

def main():
    root = resolve_project_root()
    engines_dir = os.path.join(root, "engines")
    os.makedirs(engines_dir, exist_ok=True)
    
    # 1. System Dependencies (COLMAP, FFmpeg via Brew)
    install_system_dependencies()
    
    # --- BRUSH ---
    brush_path = os.path.join(engines_dir, "brush")
    brush_version_file = os.path.join(engines_dir, "brush.version")
    
    brush_remote = get_remote_version(BRUSH_REPO)
    brush_local = get_local_version(brush_version_file)
    
    brush_install_needed = False
    
    if not os.path.exists(brush_path):
        print("Moteur 'brush' manquant.")
        brush_install_needed = True
    elif brush_remote and brush_local and brush_remote != brush_local:
        print(f"Nouvelle version de Brush disponible!")
        print(f"Installée: {brush_local[:7]}")
        print(f"Récente:   {brush_remote[:7]}")
        if sys.stdin.isatty():
             response = input("Voulez-vous mettre a jour Brush ? (y/N) : ").strip().lower()
             if response == 'y':
                 brush_install_needed = True
    
    if brush_install_needed:
        install_brush(engines_dir, brush_version_file, brush_remote)
    else:
        if os.path.exists(brush_path):
             print("Brush est a jour.")

    # --- SHARP ---
    sharp_path = os.path.join(engines_dir, "ml-sharp")
    sharp_version_file = os.path.join(engines_dir, "sharp.version")
    
    sharp_remote = get_remote_version(SHARP_REPO)
    sharp_local = get_local_version(sharp_version_file)
    
    sharp_install_needed = False
    
    if not os.path.exists(sharp_path):
        print("Moteur 'ml-sharp' manquant.")
        sharp_install_needed = True
    elif sharp_remote and sharp_local and sharp_remote != sharp_local:
        print(f"Nouvelle version de Sharp disponible!")
        print(f"Installée: {sharp_local[:7]}")
        print(f"Récente:   {sharp_remote[:7]}")
        if sys.stdin.isatty():
             response = input("Voulez-vous mettre a jour Sharp ? (y/N) : ").strip().lower()
             if response == 'y':
                 sharp_install_needed = True
    
    # Check if user force requests checking requirements every time
    # (Implicitly done if we call install_sharp, but if local version matches, we might want to check deps too?)
    # For speed, we assume matching version means deps are OK, UNLESS user requests "A chaque demarrage... on ajoute tous les requierements"
    # To satisfy "A chaque demarrage... on ajoute tous les requierements", we can just run pip install requirements.txt even if version matches.
    # But that slows down startup.
    # However, user explicitly asked for it. 
    # Let's do it if update is NOT needed but path exists.
    
    if sharp_install_needed:
        install_sharp(engines_dir, sharp_version_file, sharp_remote)
    elif os.path.exists(sharp_path):
        print("Sharp est a jour. Verification rapide des dependances...")
        # Run pip install requirements just to be sure
        try:
             req_file = os.path.join(sharp_path, "requirements.txt")
             loose_req_file = os.path.join(sharp_path, "requirements_loose.txt")
             if os.path.exists(req_file):
                 relax_requirements(req_file, loose_req_file)
                 subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_loose.txt", "--quiet"], cwd=sharp_path)
        except:
            print("Attention: Echec verification dependances Sharp")
            
    # --- SUPERPLAT ---
    splat_path = os.path.join(engines_dir, "supersplat")
    splat_version_file = os.path.join(engines_dir, "supersplat.version")
    
    splat_remote = get_remote_version(SUPERPLAT_REPO)
    splat_local = get_local_version(splat_version_file)
    
    splat_install_needed = False
    
    if not os.path.exists(splat_path):
        print("Moteur 'supersplat' manquant.")
        splat_install_needed = True
    elif splat_remote and splat_local and splat_remote != splat_local:
        print(f"Nouvelle version de SuperSplat disponible!")
        print(f"Installée: {splat_local[:7]}")
        print(f"Récente:   {splat_remote[:7]}")
        if sys.stdin.isatty():
             response = input("Voulez-vous mettre a jour SuperSplat ? (y/N) : ").strip().lower()
             if response == 'y':
                 splat_install_needed = True
    
    if splat_install_needed:
        install_supersplat(engines_dir, splat_version_file, splat_remote)
    elif os.path.exists(splat_path):
        print("SuperSplat est a jour. Verification dependances NPM...")
        try:
             # Always run npm install to satisfy "A chaque demarrage... on ajoute tous les requierements"
             subprocess.check_call(["npm", "install", "--no-audit", "--no-fund"], cwd=splat_path)
        except:
             print("Attention: Echec verification NPM SuperSplat (npm install)")

if __name__ == "__main__":
    main()
