
import os
import sys
import shutil
import subprocess
import time
import json
from pathlib import Path
from app.core.system import resolve_binary, resolve_project_root

# Constants
EXTRACTOR_360_REPO = "https://github.com/nicolasdiolez/360Extractor"
BRUSH_REPO = "https://github.com/ArthurBrussee/brush.git"
SHARP_REPO = "https://github.com/apple/ml-sharp.git"
GLOMAP_REPO = "https://github.com/colmap/glomap.git"
SUPERPLAT_REPO = "https://github.com/playcanvas/supersplat.git"
REALESRGAN_PIP = "realesrgan"

class EngineDependency:
    """Represents an external engine (Colmap, Glomap, Brush, etc.)"""
    def __init__(self, name, repo_url=None, bin_name=None):
        self.name = name
        self.repo_url = repo_url
        self.bin_name = bin_name
        self.root = self.resolve_project_root()
        self.engines_dir = self.root / "engines"
        self.version_file = self.engines_dir / f"{name}.version"
        self.target_dir = self.engines_dir / name
        self.bin_path = self.engines_dir / (bin_name if bin_name else name)

    def resolve_project_root(self) -> Path:
        return resolve_project_root()

    def is_installed(self) -> bool:
        return self.bin_path.exists()

    def get_local_version(self) -> str:
        if self.version_file.exists():
            return self.version_file.read_text().strip()
        return ""

    def save_local_version(self, version: str):
        self.engines_dir.mkdir(parents=True, exist_ok=True)
        self.version_file.write_text(version)

    def get_remote_version(self) -> str:
        if not self.repo_url: return ""
        try:
            output = subprocess.check_output(["git", "ls-remote", self.repo_url, "HEAD"], text=True).strip()
            return output.split()[0] if output else ""
        except Exception as e:
            print(f"Warning: Failed to get remote version for {self.repo_url}: {e}")
            return ""

    def update_git(self):
        """Clones or pulls the repository"""
        if not self.repo_url: return
        self.engines_dir.mkdir(parents=True, exist_ok=True)
        if not self.target_dir.exists():
            print(f"Cloning {self.name}...")
            subprocess.check_call(["git", "clone", self.repo_url, str(self.target_dir)])
        else:
            print(f"Updating {self.name}...")
            subprocess.check_call(["git", "-C", str(self.target_dir), "pull"])

    def install(self):
        """Must be overridden"""
        raise NotImplementedError()

    def uninstall(self):
        """Standard uninstallation: remove target_dir and version file"""
        if self.target_dir.exists():
            print(f"Removing {self.target_dir}...")
            shutil.rmtree(str(self.target_dir))
        if self.version_file.exists():
            self.version_file.unlink()
        print(f"{self.name} uninstalled.")
        return True

class PipEngine(EngineDependency):
    """Engine installed via pip in a dedicated venv"""
    def __init__(self, name, repo_url, venv_name):
        super().__init__(name, repo_url)
        self.venv_dir = self.root / venv_name
        self.python_bin = self.venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
        self.bin_path = self.python_bin # For pip engines, the python bin is the marker

    def is_installed(self) -> bool:
        return self.python_bin.exists()

    def create_venv(self, python_cmd=sys.executable):
        if not self.venv_dir.exists():
            print(f"Creating venv: {self.venv_dir}")
            subprocess.check_call([python_cmd, "-m", "venv", str(self.venv_dir)])
        
        # Ensure pip is present (sometimes venv is created --without-pip on some systems)
        try:
            subprocess.check_call([str(self.python_bin), "-m", "ensurepip", "--upgrade"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass
            
        # Upgrade pip
        try:
            subprocess.check_call([str(self.python_bin), "-m", "pip", "install", "--upgrade", "pip", "--no-input"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Warning: Failed to upgrade pip in {self.venv_dir}: {e}")

    def pip_install(self, args, cwd=None):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.check_call([str(self.python_bin), "-m", "pip", "install"] + args + ["--no-input", "--progress-bar", "off"], env=env, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def uninstall(self):
        """Remove venv and target_dir"""
        if self.venv_dir.exists():
            print(f"Removing venv {self.venv_dir}...")
            shutil.rmtree(str(self.venv_dir))
        return super().uninstall()


class DependencyManager:
    def __init__(self, engines_dir: Path):
        self.engines_dir = engines_dir
        self.engines = {}

    def register(self, engine: EngineDependency):
        self.engines[engine.name] = engine

    def get_config(self) -> dict:
        p = self.engines_dir.parent / "config.json"
        if p.exists():
            try: return json.loads(p.read_text())
            except: pass
        return {}

    def main_install(self, check_only=False, startup=False):
        print("--- System Dependency Check ---")
        install_system_dependencies(check_only=check_only or startup)
        
        config = self.get_config()
        
        # Sequentially check/install registered engines
        for name, engine in self.engines.items():
            # Check if enabled in config
            enabled = True
            if name == "sharp":
                enabled = config.get("sharp_params", {}).get("enabled", False) or config.get("sharp_enabled", False)
            elif name == "upscale":
                enabled = config.get("upscale_params", {}).get("enabled", False) or config.get("upscale_enabled", False)
            elif name == "extractor_360":
                enabled = config.get("extractor_360_params", {}).get("enabled", False) or config.get("extractor_360_enabled", False)
            elif name == "brush":
                enabled = config.get("brush_params", {}).get("enabled", False) or config.get("brush_enabled", False)
            elif name == "glomap":
                enabled = config.get("glomap_enabled", True) # Default enabled for Glomap
            elif name == "supersplat":
                enabled = config.get("supersplat_enabled", True)
            
            # During --check or --startup, we audit everything. During install, we respect enablement.
            # actually for startup we might want to skip disabled ones to be faster?
            # Let's keep auditing but only act on enabled ones if auto-update is on.
            if not enabled and not (check_only or startup):
                continue

            remote = engine.get_remote_version()
            local = engine.get_local_version()
            
            if not engine.is_installed():
                if check_only or startup:
                    pass # Just report status later
                else:
                    print(f">>> Engine [{name}] missing.")
                    if sys.stdin.isatty():
                        res = input(f"Would you like to install {name}? (y/n): ").strip().lower()
                        if res == 'y': engine.install()
                    else: 
                        engine.install()
                        
                # Report status for check/startup
                if not engine.is_installed():
                    status = f"  ❌ {name.capitalize()}: Missing"
                    if startup: print(status)
                    elif check_only: print(status)

            elif remote and local and remote != local:
                # Update Available
                
                # Check Auto-Update Preference
                # Look in top level or in "config" sub-dict
                cfg_section = config.get("config", {})
                auto_update = config.get(f"{name}_auto_update", False) or cfg_section.get(f"{name}_auto_update", False)
                
                if startup and auto_update:
                     print(f">>> Auto-updating {name.capitalize()}...")
                     try:
                         engine.install()
                         print(f"✅ {name.capitalize()} updated.")
                     except Exception as e:
                         print(f"❌ Auto-update failed for {name}: {e}")
                elif check_only:
                     print(f"  ⚠️  {name.capitalize()}: Update available ({local[:7]} -> {remote[:7]})")
                     continue
                else:
                    # Interactive mode (Normal install OR Startup without auto-update)
                    print(f">>> An update for [{name}] is available ({local[:7]} -> {remote[:7]}).")
                    if sys.stdin.isatty():
                        res = input(f"Update {name} now? (y/n): ").strip().lower()
                        if res == 'y': engine.install()
            else:
                if check_only:
                    print(f"  ✅ {name.capitalize()}: Ready")

class Extractor360EngineDep(PipEngine):
    def __init__(self):
        super().__init__("extractor_360", EXTRACTOR_360_REPO, ".venv_360")
        self.script_path = self.target_dir / "src" / "main.py"

    def install(self):
        self.update_git()
        self.create_venv()
        req_file = self.target_dir / "requirements.txt"
        if req_file.exists():
            self.pip_install(["-r", str(req_file)])
        self.save_local_version(self.get_remote_version())

class BrushEngineDep(EngineDependency):
    def __init__(self):
        super().__init__("brush", BRUSH_REPO)

    def install(self):
        if not shutil.which("cargo"):
            if not install_rust_toolchain(): return
        
        remote = self.get_remote_version()
        subprocess.check_call(["cargo", "install", "--git", self.repo_url, "brush-app", "--root", str(self.engines_dir)])
        
        # Move bin
        bin_dir = self.engines_dir / "bin"
        for name in ["brush", "brush-app"]:
            src = bin_dir / name
            if src.exists():
                shutil.move(str(src), str(self.engines_dir / "brush"))
                break
        shutil.rmtree(str(bin_dir), ignore_errors=True)
        self.save_local_version(remote)

class SharpEngineDep(PipEngine):
    def __init__(self):
        super().__init__("sharp", SHARP_REPO, ".venv_sharp")

    def install(self):
        self.update_git()
        # Sharp needs 3.11/3.10 ideally
        py311 = shutil.which("python3.11") or shutil.which("python3.10")
        if not py311:
            print("Python 3.11/3.10 missing for Sharp.")
            return

        self.create_venv(py311)
        req_file = self.target_dir / "requirements.txt"
        if req_file.exists():
            loose = self.target_dir / "requirements_loose.txt"
            relax_requirements(str(req_file), str(loose))
            self.pip_install(["-r", str(loose)], cwd=str(self.target_dir))
        
        if (self.target_dir / "setup.py").exists() or (self.target_dir / "pyproject.toml").exists():
            self.pip_install(["-e", "."], cwd=str(self.target_dir))
            
        self.save_local_version(self.get_remote_version())

def load_config():
    """Loads config.json from project root/cwd"""
    p = Path("config.json")
    if p.exists():
        try: return json.loads(p.read_text())
        except: pass
    return {}

def relax_requirements(src, dst):
    """Refactor utils: Relax strict torch deps"""
    with open(src, 'r') as f_in, open(dst, 'w') as f_out:
        for line in f_in:
            if line.strip().startswith('torch==') or line.strip().startswith('torchvision=='):
                line = line.replace('==', '>=')
            f_out.write(line)

def install_system_dependencies(check_only=False):
    print("--- System Dependency Check (Homebrew) ---")
    missing = []
    for cmd in ["colmap", "ffmpeg"]:
        if shutil.which(cmd) is None: missing.append(cmd)
        
    if sys.platform == "darwin":
        try:
             # Check for libomp and freeimage
             if subprocess.run(["brew", "list", "libomp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                 missing.append("libomp")
             if subprocess.run(["brew", "list", "freeimage"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                 missing.append("freeimage")
        except: pass

    if not missing:
        print("✅ System dependencies present.")
        return True
        
    print(f"Missing: {', '.join(missing)}")
    if check_only:
        print("ℹ️ Audit mode: automatic installation skipped.")
        return False

    if shutil.which("brew") is None:
        print("ERROR: Homebrew required.")
        return False
        
    print("Installing via Homebrew...")
    try:
        if "colmap" in missing: subprocess.check_call(["brew", "install", "colmap"])
        if "ffmpeg" in missing: subprocess.check_call(["brew", "install", "ffmpeg"])
        if "libomp" in missing: subprocess.check_call(["brew", "install", "libomp"])
        if "freeimage" in missing: subprocess.check_call(["brew", "install", "freeimage"])
        return True
    except:
        print("System installation failed.")
        return False

def install_node_js():
    print("Installing Node.js via Homebrew...")
    try:
        subprocess.check_call(["brew", "install", "node"])
        return True
    except: return False

def install_build_tools():
    print("Installing CMake & Ninja via Homebrew...")
    try:
        subprocess.check_call(["brew", "install", "cmake", "ninja"])
        return True
    except: return False



# resolve_project_root is now imported from app.core.system

def uninstall_sharp():
    return SharpEngineDep().uninstall()

def install_sharp(engines_dir=None, version_file=None):
    # Compatibility wrapper
    dep = SharpEngineDep()
    dep.install()
    return dep.is_installed()

def uninstall_upscale():
    return UpscaleEngineDep().uninstall()

def install_upscale():
    dep = UpscaleEngineDep()
    dep.install()
    return dep.is_installed()

def uninstall_extractor_360():
    return Extractor360EngineDep().uninstall()

def install_extractor_360():
    dep = Extractor360EngineDep()
    dep.install()
    return dep.is_installed()

def get_venv_360_python():
    """Returns path to python executable in .venv_360"""
    root = resolve_project_root()
    if sys.platform == "win32":
        return root / ".venv_360" / "Scripts" / "python.exe"
    return root / ".venv_360" / "bin" / "python"

def get_remote_version(repo_url):
    """Gets the latest commit hash from the remote git repository"""
    try:
        output = subprocess.check_output(["git", "ls-remote", repo_url, "HEAD"], text=True).strip()
        if output:
            return output.split()[0]
    except Exception as e:
        print(f"Attention: Impossible de verifier la version distante pour {repo_url}: {e}")
    return None

def get_local_version(version_file: Path):
    if version_file.exists():
        try:
            return version_file.read_text().strip()
        except:
            pass
    return None

def save_local_version(version_file: Path, version):
    if version:
        try:
            version_file.parent.mkdir(parents=True, exist_ok=True)
            version_file.write_text(version)
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

# --- INSTALLERS HELPERS ---

def install_rust_toolchain():
    print("Installing Rust (cargo)...")
    try:
        # Install rustup non-interactively
        subprocess.check_call("curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y", shell=True)
        
        # Add to current path for this session
        cargo_bin = Path.home() / ".cargo" / "bin"
        if cargo_bin.exists():
            os.environ["PATH"] = str(cargo_bin) + os.pathsep + os.environ["PATH"]
            print("Rust installed and added to PATH.")
            return True
    except Exception as e:
        print(f"Error installing Rust: {e}")
    return False

class SuperSplatEngineDep(EngineDependency):
    def __init__(self):
        super().__init__("supersplat", SUPERPLAT_REPO)

    def install(self):
        if not shutil.which("node"):
            if not install_node_js(): return
        
        # Reset local changes before pull to avoid conflicts (package-lock.json)
        if self.target_dir.exists():
             try:
                 subprocess.check_call(["git", "-C", str(self.target_dir), "reset", "--hard", "HEAD"])
             except: pass
             
        self.update_git()
        subprocess.check_call(["npm", "install"], cwd=str(self.target_dir))
        subprocess.check_call(["npm", "run", "build"], cwd=str(self.target_dir))
        self.save_local_version(self.get_remote_version())

class GlomapEngineDep(EngineDependency):
    def __init__(self):
        super().__init__("glomap", GLOMAP_REPO)
        # Fix: source code is in a separate dir, not replacing the binary
        self.target_dir = self.engines_dir / "glomap-source"

    def install(self):
        if sys.platform == "darwin" and not check_xcode_tools():
            print("Xcode Command Line Tools required.")
            return
        
        if not check_cmake_ninja():
            if not install_build_tools(): return
            
        self.update_git()
        # Source dir is now handled by update_git via self.target_dir
        source_dir = self.target_dir

        build_dir = source_dir / "build"
        # Fix CMakeCache error by cleaning build dir if it exists
        if build_dir.exists():
            shutil.rmtree(str(build_dir))
        build_dir.mkdir(exist_ok=True)
        
        cmake_args = ["cmake", "..", "-GNinja", "-DCMAKE_BUILD_TYPE=Release"]
        env = os.environ.copy()
        
        if sys.platform == "darwin":
            try:
                libomp = subprocess.check_output(["brew", "--prefix", "libomp"], text=True).strip()
                include_p = f"{libomp}/include"
                lib_p = f"{libomp}/lib"
                cmake_args.extend([
                    f"-DOpenMP_ROOT={libomp}",
                    "-DOpenMP_C_FLAGS=-Xpreprocessor -fopenmp",
                    "-DOpenMP_CXX_FLAGS=-Xpreprocessor -fopenmp"
                ])
                env["LDFLAGS"] = f"-L{lib_p} -lomp"
                env["CPPFLAGS"] = f"-I{include_p} -Xpreprocessor -fopenmp"
            except: pass

        subprocess.check_call(cmake_args, cwd=str(build_dir), env=env)
        subprocess.check_call(["ninja"], cwd=str(build_dir), env=env)
        
        # Binary name is glomap
        built_bin = None
        for p in [build_dir / "glomap" / "glomap", build_dir / "glomap"]:
            if p.exists() and not p.is_dir():
                built_bin = p
                break
        
        if built_bin:
            shutil.copy2(str(built_bin), str(self.engines_dir / "glomap"))
            self.save_local_version(self.get_remote_version())

class UpscaleEngineDep(PipEngine):
    """Upscale is special as it installs in main sys.executable (usually)"""
    def __init__(self):
        # We use a fake venv name to satisfy PipEngine but we'll override
        super().__init__("upscale", None, "fake")
        self.python_bin = Path(sys.executable)

    def is_installed(self) -> bool:
        return shutil.which("realesrgan") is not None or self.check_pkg("realesrgan")

    def check_pkg(self, name):
        try:
            subprocess.check_call([sys.executable, "-c", f"import {name}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except: return False

    def install(self):
        pkgs = ["torch", "torchvision", "realesrgan"]
        print(f"Installing/Updating: {', '.join(pkgs)}...")
        self.pip_install(pkgs)

def main():
    root = Path(__file__).resolve().parent.parent.parent
    engines_dir = root / "engines"
    engines_dir.mkdir(parents=True, exist_ok=True)
    
    manager = DependencyManager(engines_dir)
    manager.register(GlomapEngineDep())
    manager.register(BrushEngineDep())
    manager.register(SharpEngineDep())
    manager.register(SuperSplatEngineDep())
    manager.register(UpscaleEngineDep())
    manager.register(Extractor360EngineDep())
    
    check_only = "--check" in sys.argv
    startup = "--startup" in sys.argv
    manager.main_install(check_only=check_only, startup=startup)

if __name__ == "__main__":
    main()
