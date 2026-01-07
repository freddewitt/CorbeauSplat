
import os
import sys
import shutil
import subprocess
import time

BRUSH_REPO = "https://github.com/ArthurBrussee/brush.git"
SHARP_REPO = "https://github.com/apple/ml-sharp.git"
GLOMAP_REPO = "https://github.com/colmap/glomap.git"
SUPERPLAT_REPO = "https://github.com/playcanvas/supersplat.git"

def resolve_project_root():
    """Finds project root relative to this script"""
    current = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(current))

def get_remote_version(repo_url):
    """Gets the latest commit hash from the remote git repository"""
    try:
        output = subprocess.check_output(["git", "ls-remote", repo_url, "HEAD"], text=True).strip()
        if output:
            return output.split()[0]
    except Exception as e:
        print(f"Attention: Impossible de verifier la version distante pour {repo_url}: {e}")
    return None

def get_local_version(version_file):
    if os.path.exists(version_file):
        try:
            with open(version_file, "r") as f:
                return f.read().strip()
        except:
            pass
    return None

def save_local_version(version_file, version):
    if version:
        try:
            with open(version_file, "w") as f:
                f.write(version)
        except Exception as e:
            print(f"Attention: Impossible d'enregistrer la version locale: {e}")

# --- CHECKERS ---

def check_cargo():
    return shutil.which("cargo") is not None

def check_brew():
    return shutil.which("brew") is not None

def check_node():
    return shutil.which("node") is not None and shutil.which("npm") is not None

def check_cmake_ninja():
    return shutil.which("cmake") is not None and shutil.which("ninja") is not None

def check_xcode_tools():
    """Checks if Xcode Command Line Tools are installed (macOS only)"""
    if sys.platform != "darwin": return True
    try:
        # xcode-select -p prints the path if installed, or exits with error
        subprocess.check_call(["xcode-select", "-p"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except:
        return False

# --- INSTALLERS ---

def install_brush(engines_dir, version_file, target_version=None):
    print("--- Installation de Brush (Gaussian Splatting Engine) ---")
    if not check_cargo():
        print("ERREUR: 'cargo' (Rust) n'est pas installe.")
        print("Veuillez installer Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
        return False
        
    if target_version is None: target_version = get_remote_version(BRUSH_REPO)

    try:
        cmd = ["cargo", "install", "--git", BRUSH_REPO, "brush-app", "--root", engines_dir]
        subprocess.check_call(cmd)
        
        # Cleanup binary location
        bin_dir = os.path.join(engines_dir, "bin")
        possible_names = ["brush", "brush-app"]
        installed_bin = None
        for name in possible_names:
            p = os.path.join(bin_dir, name)
            if os.path.exists(p):
                installed_bin = p
                break
                
        if installed_bin:
            shutil.move(installed_bin, os.path.join(engines_dir, "brush"))
            shutil.rmtree(bin_dir, ignore_errors=True)
            save_local_version(version_file, target_version)
            print("Brush installe avec succes.")
            return True
        return False
    except Exception as e:
        print(f"Erreur Brush: {e}")
        return False

def relax_requirements(src, dst):
    """Refactor utils: Relax strict torch deps"""
    with open(src, 'r') as f_in, open(dst, 'w') as f_out:
        for line in f_in:
            if line.strip().startswith('torch==') or line.strip().startswith('torchvision=='):
                line = line.replace('==', '>=')
            f_out.write(line)

def install_sharp(engines_dir, version_file, target_version=None):
    print("--- Installation de Sharp (Apple ML) ---")
    target_dir = os.path.join(engines_dir, "ml-sharp")
    try:
        if target_version is None: target_version = get_remote_version(SHARP_REPO)
        
        if not os.path.exists(target_dir):
            subprocess.check_call(["git", "clone", SHARP_REPO, target_dir])
        else:
            subprocess.check_call(["git", "-C", target_dir, "pull"])
            
        # Dependances
        req_file = os.path.join(target_dir, "requirements.txt")
        if os.path.exists(req_file):
            loose = os.path.join(target_dir, "requirements_loose.txt")
            relax_requirements(req_file, loose)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_loose.txt"], cwd=target_dir)
            
        if os.path.exists(os.path.join(target_dir, "setup.py")):
             subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "."], cwd=target_dir)
             
        save_local_version(version_file, target_version)
        print("Sharp installe avec succes.")
        return True
    except Exception as e:
        print(f"Erreur Sharp: {e}")
        return False

def install_supersplat(engines_dir, version_file, target_version=None):
    print("--- Installation de SuperSplat ---")
    if not check_node():
        print("ERREUR: 'node'/'npm' requis. https://nodejs.org/")
        return False
        
    target_dir = os.path.join(engines_dir, "supersplat")
    try:
        if target_version is None: target_version = get_remote_version(SUPERPLAT_REPO)
        
        if not os.path.exists(target_dir):
            subprocess.check_call(["git", "clone", SUPERPLAT_REPO, target_dir])
        else:
             # Reset local changes (package-lock.json often causes conflicts)
            subprocess.check_call(["git", "-C", target_dir, "reset", "--hard", "HEAD"])
            subprocess.check_call(["git", "-C", target_dir, "pull"])
            
        subprocess.check_call(["npm", "install"], cwd=target_dir)
        subprocess.check_call(["npm", "run", "build"], cwd=target_dir)
        
        save_local_version(version_file, target_version)
        print("SuperSplat installe avec succes.")
        return True
    except Exception as e:
        print(f"Erreur SuperSplat: {e}")
        return False

def install_glomap(engines_dir, version_file, target_version=None):
    print("--- Installation de Glomap ---")
    
    # Check Xcode Tools first on macOS
    if sys.platform == "darwin" and not check_xcode_tools():
        print("ERREUR: Xcode Command Line Tools manquants.")
        print("Ils sont nÃ©cessaires pour compiler Glomap.")
        print("The operation may take some time, time to grab a coffee.")
        if sys.stdin.isatty():
             res = input("Voulez-vous lancer l'installation (xcode-select --install) ? (y/N) : ").strip().lower()
             if res == 'y':
                 try:
                     print("Lancement de l'installeur systeme...")
                     subprocess.check_call(["xcode-select", "--install"])
                     print("\nUne boite de dialogue a du s'ouvrir.")
                     input("Veuillez suivre les instructions a l'ecran, puis appuyez sur Entree ici une fois l'installation TERMINEE...")
                     
                     if not check_xcode_tools():
                         print("Erreur: Toujours pas detecte. Essayez de redemarrer le terminal.")
                         return False
                 except Exception as e:
                     print(f"Erreur lancement xcode-select: {e}")
                     return False
             else:
                 return False
        else:
             print("Veuillez lancer 'xcode-select --install' manuellement.")
             return False

    if not check_cmake_ninja():
        print("ERREUR: 'cmake'/'ninja' requis. (brew install cmake ninja)")
        return False
        
    source_dir = os.path.join(engines_dir, "glomap-source")
    try:
        if target_version is None: target_version = get_remote_version(GLOMAP_REPO)
        
        if not os.path.exists(source_dir):
            subprocess.check_call(["git", "clone", GLOMAP_REPO, source_dir])
        else:
            subprocess.check_call(["git", "-C", source_dir, "pull"])
            
        build_dir = os.path.join(source_dir, "build")
        os.makedirs(build_dir, exist_ok=True)
        
        cmake_args = ["cmake", "..", "-GNinja", "-DCMAKE_BUILD_TYPE=Release"]
        
        # macOS OpenMP Support
        env = os.environ.copy()
        if sys.platform == "darwin":
            try:
                libomp = subprocess.check_output(["brew", "--prefix", "libomp"], text=True).strip()
                include_p = f"{libomp}/include"
                lib_p = f"{libomp}/lib"
                
                cmake_args.extend([
                    f"-DOpenMP_ROOT={libomp}",
                    "-DOpenMP_C_FLAGS=-Xpreprocessor -fopenmp",
                    "-DOpenMP_CXX_FLAGS=-Xpreprocessor -fopenmp",
                    f"-DOpenMP_omp_LIBRARY={lib_p}/libomp.dylib",
                    f"-DCMAKE_C_FLAGS=-I{include_p} -Xpreprocessor -fopenmp",
                    f"-DCMAKE_CXX_FLAGS=-I{include_p} -Xpreprocessor -fopenmp",
                    f"-DCMAKE_EXE_LINKER_FLAGS=-L{lib_p} -lomp",
                    f"-DCMAKE_SHARED_LINKER_FLAGS=-L{lib_p} -lomp"
                ])
                # Env vars fallback
                env["CFLAGS"] = f"{env.get('CFLAGS','')} -I{include_p} -Xpreprocessor -fopenmp"
                env["CXXFLAGS"] = f"{env.get('CXXFLAGS','')} -I{include_p} -Xpreprocessor -fopenmp"
                env["LDFLAGS"] = f"{env.get('LDFLAGS','')} -L{lib_p} -lomp"
            except: pass
            
        subprocess.check_call(cmake_args, cwd=build_dir, env=env)
        subprocess.check_call(["ninja"], cwd=build_dir, env=env)
        
        # Find binary
        built_bin = None
        possible = [os.path.join(build_dir, "glomap", "glomap"), os.path.join(build_dir, "glomap")]
        for p in possible:
             if os.path.exists(p) and not os.path.isdir(p) and os.access(p, os.X_OK):
                 built_bin = p; break
                 
        if not built_bin:
            for root, _, files in os.walk(build_dir):
                if "glomap" in files:
                    p = os.path.join(root, "glomap")
                    if os.access(p, os.X_OK): built_bin = p; break
                    
        if built_bin:
            shutil.copy2(built_bin, os.path.join(engines_dir, "glomap"))
            save_local_version(version_file, target_version)
            print("Glomap installe avec succes.")
            return True
        return False
    except Exception as e:
        print(f"Erreur Glomap: {e}")
        return False

def install_system_dependencies():
    print("--- Verification des dependances systeme (Homebrew) ---")
    missing = []
    for cmd in ["colmap", "ffmpeg"]:
        if shutil.which(cmd) is None: missing.append(cmd)
        
    if sys.platform == "darwin":
        try:
             if subprocess.run(["brew", "list", "libomp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                 missing.append("libomp")
        except: pass

    if not missing:
        print("Dependances systeme presentes.")
        return True
        
    print(f"Manquant: {', '.join(missing)}")
    if not check_brew():
        print("ERREUR: Homebrew requis.")
        return False
        
    print("Installation via Homebrew...")
    try:
        if "colmap" in missing: subprocess.check_call(["brew", "install", "colmap"])
        if "ffmpeg" in missing: subprocess.check_call(["brew", "install", "ffmpeg"])
        if "libomp" in missing: subprocess.check_call(["brew", "install", "libomp"])
        return True
    except:
        print("Echec installation systeme.")
        return False

def manage_engine(name, check_path, repo_url, install_func, engines_dir, env_skip_key=None, custom_check=None):
    """
    Generic manager for engines.
    """
    version_file = os.path.join(engines_dir, f"{name}.version")
    
    # Check skip env
    if env_skip_key and int(os.environ.get(env_skip_key, 0)) == 1:
        print(f"{name.capitalize()} installation skipped by env.")
        return

    remote = get_remote_version(repo_url)
    local = get_local_version(version_file)
    
    install_needed = False
    
    is_installed = os.path.exists(check_path)
    if not is_installed:
        print(f"Moteur '{name}' manquant.")
        if sys.stdin.isatty():
             # Special warning for Glomap
             if name == "glomap":
                 print("Glomap requiert Xcode Command Line Tools et ~5min de compilation.")
                 
             res = input(f"Voulez-vous installer {name.capitalize()} ? (y/N) : ").strip().lower()
             if res == 'y': install_needed = True
    elif remote and local and remote != local:
        print(f"Mise a jour {name.capitalize()} disponible ({local[:7]} -> {remote[:7]})")
        if sys.stdin.isatty():
             res = input(f"Mettre a jour {name.capitalize()} ? (y/N) : ").strip().lower()
             if res == 'y': install_needed = True
             
    if install_needed:
        install_func(engines_dir, version_file, remote)
    elif is_installed:
        print(f"{name.capitalize()} est a jour.")
        if custom_check: custom_check()

def main():
    root = resolve_project_root()
    engines_dir = os.path.join(root, "engines")
    os.makedirs(engines_dir, exist_ok=True)
    
    install_system_dependencies()
    
    # Glomap
    manage_engine("glomap", os.path.join(engines_dir, "glomap"), GLOMAP_REPO, install_glomap, engines_dir, "SKIP_GLOMAP")
    
    # Brush
    manage_engine("brush", os.path.join(engines_dir, "brush"), BRUSH_REPO, install_brush, engines_dir)
    
    # Sharp (Custom check for loose deps)
    def check_sharp_deps():
        # Just ensure dependencies are there
        sharp_dir = os.path.join(engines_dir, "ml-sharp")
        try:
             subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements_loose.txt", "--quiet"], cwd=sharp_dir, stderr=subprocess.DEVNULL)
        except: pass
        
    manage_engine("sharp", os.path.join(engines_dir, "ml-sharp"), SHARP_REPO, install_sharp, engines_dir, custom_check=check_sharp_deps)
    
    # SuperSplat (Custom check for npm)
    def check_splat_deps():
        # Always run npm install to be safe
        splat_dir = os.path.join(engines_dir, "supersplat")
        try: subprocess.call(["npm", "install", "--no-audit", "--no-fund"], cwd=splat_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass
        
    manage_engine("supersplat", os.path.join(engines_dir, "supersplat"), SUPERPLAT_REPO, install_supersplat, engines_dir, custom_check=check_splat_deps)

if __name__ == "__main__":
    main()
