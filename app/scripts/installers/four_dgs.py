"""4DGS engine dependency installer (Nerfstudio, isolated in .venv_4dgs)."""

from app.scripts.installers.base import PipEngine

NERFSTUDIO_REPO = "https://github.com/nerfstudio-project/nerfstudio.git"


class FourDGSEngineDep(PipEngine):
    ask_before_update = True

    def __init__(self):
        super().__init__("four_dgs", NERFSTUDIO_REPO, ".venv_4dgs")

    def is_enabled_in_config(self, config: dict) -> bool:
        return config.get("four_dgs_params", {}).get("enabled", False) or config.get("four_dgs_enabled", False)

    def install(self):
        self.update_git()
        self.create_venv()
        req_file = self.target_dir / "requirements.txt"
        if req_file.exists():
            self.pip_install(["-r", str(req_file)])
        self.pip_install(["-e", "."], cwd=str(self.target_dir))
        self.save_local_version(self.get_remote_version())
