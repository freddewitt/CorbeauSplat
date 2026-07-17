"""splat-transform engine dependency installer.

Installs @playcanvas/splat-transform locally in engines/splat-transform/ via npm.
This mirrors the supersplat.py pattern (local npm installation, no global pollution).

The binary is available at:
  engines/splat-transform/node_modules/.bin/splat-transform
"""
import json
import shutil
import subprocess

from app.scripts.installers.base import EngineDependency
from app.scripts.installers.tools import install_node_js

SPLAT_TRANSFORM_PACKAGE = "@playcanvas/splat-transform"
SPLAT_TRANSFORM_VERSION = "2.7.1"


class SplatTransformEngineDep(EngineDependency):
    """Installs the PlayCanvas splat-transform CLI via npm (local install)."""

    def __init__(self):
        super().__init__("splat-transform", None)
        self.target_dir = self.engines_dir / "splat-transform"
        self.bin_path = self.target_dir / "node_modules" / ".bin" / "splat-transform"

    def is_installed(self) -> bool:
        return self.bin_path.exists()

    def get_remote_version(self) -> str:
        return SPLAT_TRANSFORM_VERSION

    def get_local_version(self) -> str:
        if self.version_file.exists():
            return self.version_file.read_text().strip()
        pkg_json = self.target_dir / "node_modules" / SPLAT_TRANSFORM_PACKAGE / "package.json"
        if pkg_json.exists():
            try:
                return json.loads(pkg_json.read_text()).get("version", "")
            except (OSError, json.JSONDecodeError):
                pass
        return ""

    def install(self):
        if not shutil.which("node") and not install_node_js():
            return
        if not shutil.which("npm"):
            print("❌ npm not found. Install Node.js first: brew install node")
            return

        self.target_dir.mkdir(parents=True, exist_ok=True)

        # Create a minimal package.json if it doesn't exist, so npm install
        # stays local and doesn't walk up to a parent package.json.
        pkg_init = self.target_dir / "package.json"
        if not pkg_init.exists():
            pkg_init.write_text(json.dumps({
                "name": "splat-transform-wrapper",
                "version": "1.0.0",
                "private": True,
            }, indent=2))

        versioned_pkg = f"{SPLAT_TRANSFORM_PACKAGE}@{SPLAT_TRANSFORM_VERSION}"
        print(f"Installing {versioned_pkg} locally...")
        subprocess.check_call(
            ["npm", "install", versioned_pkg, "--no-audit", "--no-fund"],
            cwd=str(self.target_dir),
        )

        if not self.bin_path.exists():
            print("⚠️  splat-transform binary not found after npm install.")
            return

        self.save_local_version(SPLAT_TRANSFORM_VERSION)
        print(f"✅ splat-transform {SPLAT_TRANSFORM_VERSION} installed.")

    def uninstall(self):
        if self.target_dir.exists():
            shutil.rmtree(str(self.target_dir), ignore_errors=True)
        if self.version_file.exists():
            self.version_file.unlink()
        print("splat-transform uninstalled.")
        return True
