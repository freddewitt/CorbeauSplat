"""SuperSplat engine dependency installer."""
import shutil
import subprocess
from pathlib import Path

from app.scripts.installers.base import EngineDependency
from app.scripts.installers.tools import install_node_js

SUPERPLAT_REPO = "https://github.com/playcanvas/supersplat.git"

# Pinned upstream release. Deliberately not "latest": before this pin the
# installer tracked PlayCanvas' main branch, so any commit pushed upstream made
# the local version differ from the remote one and CorbeauSplat offered an
# update at nearly every startup. Bumping this constant is a reviewed gesture,
# not a side effect of someone else's merge schedule.
SUPERSPLAT_PINNED_TAG = "v3.3.0"


class SuperSplatEngineDep(EngineDependency):
    ask_before_update = True

    def __init__(self):
        super().__init__("supersplat", SUPERPLAT_REPO)

    def get_remote_version(self) -> str:
        """Target version: the pinned tag, with no network call.

        Overrides the base implementation, which resolves the remote HEAD.
        """
        return SUPERSPLAT_PINNED_TAG

    def _fetch_latest_tag(self) -> str:
        """Highest tag published upstream — purely informative.

        Does **not** decide what gets installed (cf. ``get_remote_version``):
        only tells the user that bumping the pin is possible.
        """
        try:
            out = subprocess.check_output(
                ["git", "ls-remote", "--tags", "--refs", "--sort=-v:refname", self.repo_url],
                text=True, timeout=10,
            ).strip()
        except Exception as e:
            print(f"⚠️ Could not fetch latest SuperSplat tag: {e}")
            return ""
        if not out:
            return ""
        return out.splitlines()[0].rsplit("/", 1)[-1]

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
        result = subprocess.run(["npm", "install"], cwd=target)
        if result.returncode == 0:
            return
        # npm bug #4828: optional deps fail silently, leaving native modules missing.
        # Fix: wipe node_modules + package-lock.json and reinstall clean.
        print(f"  npm install failed ({result.returncode}), retrying after cleaning node_modules...")
        shutil.rmtree(str(self.target_dir / "node_modules"), ignore_errors=True)
        lock = self.target_dir / "package-lock.json"
        if lock.exists():
            lock.unlink()
        subprocess.check_call(["npm", "install"], cwd=target)

    def install(self):
        if not shutil.which("node") and not install_node_js():
            return

        if not (self.target_dir.exists() and self._git_is_own_repo()):
            self.update_git()

        print(f"Checking out {self.name} {SUPERSPLAT_PINNED_TAG}...")
        try:
            subprocess.check_call(["git", "-C", str(self.target_dir), "reset", "--hard", "HEAD"])
            subprocess.check_call(
                ["git", "-C", str(self.target_dir), "fetch", "origin",
                 f"refs/tags/{SUPERSPLAT_PINNED_TAG}"]
            )
            subprocess.check_call(["git", "-C", str(self.target_dir), "reset", "--hard", "FETCH_HEAD"])
        except Exception as e:
            print(f"  Warning: could not check out {SUPERSPLAT_PINNED_TAG} for {self.name}: {e}")
            return

        latest = self._fetch_latest_tag()
        if latest and latest != SUPERSPLAT_PINNED_TAG:
            print(
                f"ℹ️  SuperSplat {latest} est disponible en amont ; ce dépôt épingle "
                f"{SUPERSPLAT_PINNED_TAG}.\n"
                f"   Pour l'adopter : mettre à jour SUPERSPLAT_PINNED_TAG dans "
                f"app/scripts/installers/supersplat.py."
            )

        self._npm_install()
        subprocess.check_call(["npm", "run", "build"], cwd=str(self.target_dir))
        self.save_local_version(SUPERSPLAT_PINNED_TAG)
