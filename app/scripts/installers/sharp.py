"""Sharp engine dependency installer."""
import shutil

from app.scripts.installers.base import PipEngine
from app.scripts.installers.tools import relax_requirements

SHARP_REPO = "https://github.com/apple/ml-sharp.git"
# apple/ml-sharp publishes no tags, so the pin is a commit SHA: the only
# reproducible reference available. Bump it deliberately, after a read.
SHARP_PINNED_REF = "aed6527499ef91cba3b54c18d49a870f25947190"  # main, 2026-09-20


class SharpEngineDep(PipEngine):
    ask_before_update = True

    def __init__(self):
        super().__init__("sharp", SHARP_REPO, ".venv_sharp", pinned_ref=SHARP_PINNED_REF)

    def is_enabled_in_config(self, config: dict) -> bool:
        return config.get("sharp_params", {}).get("enabled", False) or config.get("sharp_enabled", False)

    def get_remote_version(self) -> str:
        """Target version: the pinned commit SHA, with no network call.

        Overrides the base implementation, which resolves the moving remote
        HEAD: recording that here would make every upstream push look like an
        update for code that has not changed.
        """
        return SHARP_PINNED_REF

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
