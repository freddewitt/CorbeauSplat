"""Sharp engine dependency installer."""
import shutil

from app.scripts.installers.base import PipEngine
from app.scripts.installers.tools import relax_requirements

SHARP_REPO = "https://github.com/apple/ml-sharp.git"


class SharpEngineDep(PipEngine):
    ask_before_update = True

    def __init__(self):
        super().__init__("sharp", SHARP_REPO, ".venv_sharp")

    def is_enabled_in_config(self, config: dict) -> bool:
        return config.get("sharp_params", {}).get("enabled", False) or config.get("sharp_enabled", False)

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
