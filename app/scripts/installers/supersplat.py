"""SuperSplat engine dependency installer."""
import os
import shutil
import subprocess
from pathlib import Path

from app.scripts.installers.base import EngineDependency
from app.scripts.installers.tools import install_node_js

SUPERPLAT_REPO = "https://github.com/playcanvas/supersplat.git"


def _npm(args):
    """Build an npm command. On Windows npm is a .cmd shim that CreateProcess
    cannot launch directly, so route it through cmd.exe."""
    if os.name == "nt":
        return ["cmd", "/c", "npm", *args]
    return ["npm", *args]


class SuperSplatEngineDep(EngineDependency):
    ask_before_update = True

    def __init__(self):
        super().__init__("supersplat", SUPERPLAT_REPO)

    def _git_is_own_repo(self) -> bool:
        """Returns True if target_dir is an independent git repo (not a parent repo)."""
        result = subprocess.run(
            ["git", "-C", str(self.target_dir), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return False
        return Path(result.stdout.strip()) == self.target_dir

    def _npm_install(self):
        target = str(self.target_dir)
        result = subprocess.run(_npm(["install"]), cwd=target)
        if result.returncode == 0:
            return
        # npm bug #4828: optional deps fail silently, leaving native modules missing.
        # Fix: wipe node_modules + package-lock.json and reinstall clean.
        print(f"  npm install failed ({result.returncode}), retrying after cleaning node_modules...")
        shutil.rmtree(str(self.target_dir / "node_modules"), ignore_errors=True)
        lock = self.target_dir / "package-lock.json"
        if lock.exists():
            lock.unlink()
        subprocess.check_call(_npm(["install"]), cwd=target)

    def install(self):
        if not shutil.which("node"):
            if not install_node_js(): return

        if self.target_dir.exists() and self._git_is_own_repo():
            try:
                subprocess.check_call(["git", "-C", str(self.target_dir), "reset", "--hard", "HEAD"])
            except subprocess.CalledProcessError as e:
                print(f"  Warning: git reset failed for {self.name}: {e}")
            print(f"Updating {self.name}...")
            try:
                subprocess.check_call(["git", "-C", str(self.target_dir), "fetch", "origin"])
                subprocess.check_call(["git", "-C", str(self.target_dir), "reset", "--hard", "FETCH_HEAD"])
            except Exception as e:
                print(f"  Warning: git update failed for {self.name}: {e}")
        else:
            self.update_git()

        self._npm_install()
        subprocess.check_call(_npm(["run", "build"]), cwd=str(self.target_dir))
        self.save_local_version(self.get_remote_version())
