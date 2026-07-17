"""SPZ engine dependency installer.

Architecture note: Unlike PipEngine (which creates a dedicated venv), SpzEngineDep
installs the 'spz' module directly into the running Python interpreter (main .venv)
via sys.executable. This is required because ExportEngine imports 'spz' at runtime
in the same process as the app. A dedicated venv would require IPC, which is
disproportionate for a compiled Python binding.

is_installed() checks both the version file (written after successful pip install)
and whether the module is importable, so partial or broken installations are detected.
"""
import shutil
import subprocess
import sys

from app.scripts.installers.base import EngineDependency

SPZ_REPO = "https://github.com/nianticlabs/spz.git"
SPZ_TAG = "v3.0.0"


class SpzEngineDep(EngineDependency):
    """Installs the nianticlabs/spz Python module into the main .venv."""

    def __init__(self):
        super().__init__("spz", SPZ_REPO)
        # Source cloned here; bin_path is not meaningful for a Python module.
        self.source_dir = self.engines_dir / "spz-source"

    def is_installed(self) -> bool:
        if not self.version_file.exists():
            return False
        try:
            import importlib
            importlib.import_module("spz")
            return True
        except ImportError:
            return False

    def get_remote_version(self) -> str:
        return SPZ_TAG

    def install(self):
        if not self._check_cmake():
            return

        self._clone_or_update()
        self._pip_install()
        self.save_local_version(SPZ_TAG)
        print(f"✅ spz {SPZ_TAG} installed into main venv.")

    def _check_cmake(self) -> bool:
        if shutil.which("cmake") is None:
            print(
                "❌ CMake not found. The spz library requires CMake to compile its C++ bindings.\n"
                "   Install it via Homebrew:  brew install cmake\n"
                "   Then re-run the dependency setup."
            )
            return False
        return True

    def _clone_or_update(self):
        self.engines_dir.mkdir(parents=True, exist_ok=True)
        if self.source_dir.exists():
            print(f"Updating spz source to {SPZ_TAG}...")
            subprocess.check_call(
                ["git", "-C", str(self.source_dir), "fetch", "--tags", "origin"]
            )
            subprocess.check_call(
                ["git", "-C", str(self.source_dir), "checkout", SPZ_TAG]
            )
        else:
            print(f"Cloning spz {SPZ_TAG}...")
            subprocess.check_call(
                ["git", "clone", "--depth", "1", "--branch", SPZ_TAG,
                 self.repo_url, str(self.source_dir)]
            )

    def _pip_install(self):
        print("Compiling and installing spz (this may take a few minutes)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", ".", "--no-input"],
            cwd=str(self.source_dir),
        )

    def uninstall(self):
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "uninstall", "spz", "-y", "--no-input"]
            )
            print("spz uninstalled from venv.")
        except subprocess.CalledProcessError as e:
            print(f"Warning: pip uninstall spz failed: {e}")
        if self.source_dir.exists():
            import shutil as _shutil
            _shutil.rmtree(str(self.source_dir), ignore_errors=True)
        if self.version_file.exists():
            self.version_file.unlink()
        print("spz uninstalled.")
        return True
