"""Extractor 360 engine dependency installer."""

from app.scripts.installers.base import PipEngine

EXTRACTOR_360_REPO = "https://github.com/nicolasdiolez/360Extractor"


class Extractor360EngineDep(PipEngine):
    ask_before_update = True
    install_on_startup = False  # Heavy venv (YOLO/PySide6); only when the 360 mode is enabled

    def __init__(self):
        super().__init__("extractor_360", EXTRACTOR_360_REPO, ".venv_360")
        self.script_path = self.target_dir / "src" / "main.py"

    def is_enabled_in_config(self, config: dict) -> bool:
        return config.get("extractor_360_params", {}).get("enabled", False) or config.get("extractor_360_enabled", False)

    def install(self):
        self.update_git()
        self.create_venv()
        req_file = self.target_dir / "requirements.txt"
        if req_file.exists():
            self.pip_install(["-r", str(req_file)])
        self.save_local_version(self.get_remote_version())
