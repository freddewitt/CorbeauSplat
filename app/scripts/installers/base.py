"""Base classes for engine dependency management."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.core.system import resolve_project_root


class EngineDependency:
    """Represents an external engine (Colmap, Glomap, Brush, etc.)"""
    auto_update_default = False  # Subclasses can override to enable auto-update by default
    ask_before_update = False    # If True, prompt user at startup before updating
    install_on_startup = True    # If False, only auto-installs when enabled in config
                                 # (for heavy/optional engines built from source)

    def on_startup_ready(self):
        """Called at startup when the engine is installed and up to date."""
        pass

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

    def is_enabled_in_config(self, config: dict) -> bool:
        """SOLID-OCP : Permet au moteur de decider s'il est actif"""
        return config.get(f"{self.name}_enabled", True)

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
        if self.venv_dir.exists() and not self.python_bin.exists():
            print(f"Broken venv detected at {self.venv_dir} (symlink or binary missing). Removing...")
            shutil.rmtree(str(self.venv_dir))

        if not self.venv_dir.exists():
            print(f"Creating venv: {self.venv_dir}")
            subprocess.check_call([python_cmd, "-m", "venv", str(self.venv_dir)])

        # Ensure pip is present (sometimes venv is created --without-pip on some systems)
        try:
            subprocess.check_call([str(self.python_bin), "-m", "ensurepip", "--upgrade"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
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
            try:
                return json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def main_install(self, check_only=False, startup=False):
        from app.scripts.installers.tools import install_system_dependencies

        print("--- System Dependency Check ---")
        install_system_dependencies(check_only=check_only or startup)

        config = self.get_config()
        missing_engines_startup = False

        for name, engine in self.engines.items():
            # OCP : Le moteur decide s'il est active
            enabled = engine.is_enabled_in_config(config)

            # During --check or --startup, we audit everything. During install, we respect enablement.
            if not enabled and not (check_only or startup):
                continue

            # Heavy/optional engines (e.g. source-built Glomap, 360 Extractor) must
            # not auto-install at startup unless the user has enabled them. They
            # install lazily when their feature is turned on.
            if startup and not enabled and not engine.install_on_startup:
                continue

            remote = engine.get_remote_version()
            local = engine.get_local_version()
            # Normalize local version for comparison (strip build-mode suffixes like -source)
            local_clean = local.replace("-source", "") if local else local

            if not engine.is_installed():
                if check_only:
                    pass # Just report status later
                elif startup:
                    print(f">>> Auto-installing {name.capitalize()} on startup...")
                    try:
                        engine.install()
                        print(f"✅ {name.capitalize()} installed automatically.")
                        engine.on_startup_ready()
                    except Exception as e:
                        print(f"❌ Auto-install failed for {name}: {e}")
                else:
                    print(f">>> Auto-installing missing engine [{name}]...")
                    engine.install()

                # Report status for check/startup
                if not engine.is_installed():
                    status = f"  ❌ {name.capitalize()}: Missing"
                    if startup or check_only: print(status)
                    missing_engines_startup = True

            elif remote and local and remote != local_clean:
                # Update Available

                # Check Auto-Update Preference
                cfg_section = config.get("config", {})
                auto_update = config.get(f"{name}_auto_update", engine.auto_update_default) or cfg_section.get(f"{name}_auto_update", engine.auto_update_default)

                if startup and engine.ask_before_update:
                    print(f"\n>>> Mise à jour disponible pour {name.capitalize()} ({local_clean} → {remote})")
                    try:
                        answer = input("    Mettre à jour maintenant ? (o/n) : ").strip().lower()
                    except EOFError:
                        answer = "n"
                    if answer in ("o", "y", "oui", "yes"):
                        print(f">>> Mise à jour de {name.capitalize()}...")
                        try:
                            engine.install()
                            print(f"✅ {name.capitalize()} mis à jour.")
                        except Exception as e:
                            print(f"❌ Échec de la mise à jour de {name}: {e}")
                    else:
                        print(f"    Mise à jour de {name.capitalize()} ignorée.")
                elif startup and auto_update:
                     print(f">>> Auto-updating {name.capitalize()}...")
                     try:
                         engine.install()
                         print(f"✅ {name.capitalize()} updated.")
                     except Exception as e:
                         print(f"❌ Auto-update failed for {name}: {e}")
                elif check_only:
                     print(f"  ⚠️  {name.capitalize()}: Update available ({local_clean} -> {remote})")
                else:
                    print(f">>> Auto-updating {name} ({local_clean} -> {remote})...")
                    engine.install()
            else:
                if startup:
                    engine.on_startup_ready()
                if check_only:
                    print(f"  ✅ {name.capitalize()}: Ready")

        if missing_engines_startup:
            print("\nℹ️  Note: Automatically installed missing engines.")
