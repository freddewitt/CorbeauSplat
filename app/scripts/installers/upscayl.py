"""Upscayl engine dependency installer."""

from app.scripts.installers.base import EngineDependency


class UpscaylEngineDep(EngineDependency):
    """upscayl-ncnn — downloaded from GitHub releases, no build required."""
    ask_before_update = True

    def __init__(self):
        super().__init__("upscayl", "https://github.com/upscayl/upscayl-ncnn")

    def is_enabled_in_config(self, config: dict) -> bool:
        return True  # Always check; upscayl is used globally by the upscale workflow

    def is_installed(self) -> bool:
        from app.upscayl_manager import find_binary
        return find_binary() is not None

    def get_local_version(self) -> str:
        if self.version_file.exists():
            return self.version_file.read_text().strip()
        return ""

    def get_remote_version(self) -> str:
        import json as _json
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/upscayl/upscayl-ncnn/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CorbeauSplat"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = _json.loads(resp.read())
                tag = data.get("tag_name", "")
                if tag:
                    print(f"Latest upscayl-ncnn release: {tag}")
                    return tag
        except Exception as e:
            print(f"⚠️ Could not fetch upscayl-ncnn version: {e}")
        return ""

    def install(self):
        from app.upscayl_manager import download_binary
        dest = download_binary(log_callback=print)
        self.save_local_version(self.get_remote_version())
        print(f"✅ upscayl-bin installed: {dest}")

    def on_startup_ready(self):
        """Log model availability at startup."""
        from app.upscayl_manager import get_models_dir
        from app.upscayl_models import MODELS
        models_dir = get_models_dir()
        downloaded = [m.id for m in MODELS if m.is_downloaded(models_dir)]
        if not downloaded:
            print("  ⚠️  Upscale: no models in ./models/upscayl/ — open the Upscale tab to download.")
        else:
            print(f"  ✅ Upscale models available: {', '.join(downloaded)}")
