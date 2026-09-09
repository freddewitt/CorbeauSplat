"""COLMAP engine dependency installer."""
import json
import os
import re
import shutil
import subprocess
import sys

from app.scripts.installers.base import EngineDependency


class ColmapBrewDep(EngineDependency):
    """COLMAP géré via Homebrew — vérifie la version et met à jour si nécessaire"""
    ask_before_update = True

    def __init__(self):
        super().__init__("colmap")

    def is_installed(self) -> bool:
        return shutil.which("colmap") is not None

    def is_enabled_in_config(self, config: dict) -> bool:
        return sys.platform == "darwin" and shutil.which("brew") is not None

    def get_local_version(self) -> str:
        try:
            out = subprocess.check_output(
                ["brew", "list", "--versions", "colmap"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            parts = out.split()
            if len(parts) >= 2:
                # Strip Homebrew revision suffix (e.g., 4.0.4_2 → 4.0.4)
                ver = parts[1]
                return re.split(r'_\d+$', ver)[0]
            return ""
        except (subprocess.CalledProcessError, OSError):
            return ""

    def get_remote_version(self) -> str:
        try:
            out = subprocess.check_output(
                ["brew", "info", "--json", "colmap"],
                text=True, stderr=subprocess.DEVNULL, timeout=10
            )
            data = json.loads(out)
            if data and isinstance(data, list):
                return data[0].get("versions", {}).get("stable", "")
        except Exception as e:
            print(f"⚠️ Could not fetch latest COLMAP version: {e}")
        return ""

    def install(self):
        if not shutil.which("brew"):
            print("❌ Homebrew requis pour mettre à jour COLMAP.")
            return
        # Homebrew always upgrades a formula's own dependencies as needed
        # (unavoidable, required for compatibility). Without this env var it
        # also cascades to upgrading unrelated formulae that merely depend on
        # colmap ("installed dependents check"), which is the invasive part.
        env = {**os.environ, "HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK": "1"}
        try:
            if self.is_installed():
                print("Mise à jour de COLMAP via Homebrew...")
                subprocess.check_call(["brew", "upgrade", "colmap"], env=env)
            else:
                print("Installation de COLMAP via Homebrew...")
                subprocess.check_call(["brew", "install", "colmap"], env=env)
        except subprocess.CalledProcessError:
            print("⚠️ brew upgrade/install colmap a échoué (peut-être déjà à jour).")
