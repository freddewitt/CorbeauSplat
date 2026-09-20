"""Upscayl engine dependency installer."""

from app.scripts.checksum_verifier import load_expected_checksums
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
        """Target version: **pinned** to the release frozen in ``checksums.json``.

        We deliberately do not follow the latest upstream release. The archive
        is verified against a fingerprint frozen in this repository
        (``darwin_upscayl``/``linux_upscayl``) for the tag stored in
        ``upscayl_release``: following "latest" guaranteed that, on the first
        tag published upstream, the fingerprint would no longer match and the
        installation would be refused. Version and fingerprint therefore live
        side by side in ``checksums.json`` and are bumped together, in a single
        reviewed change. Adopting a new release stays a deliberate act, not a
        side effect of a third party's release calendar.
        """
        pinned = load_expected_checksums().get("upscayl_release", "")
        if not pinned:
            print("⚠️ Aucune version upscayl épinglée (clé 'upscayl_release' de checksums.json).")
            return ""

        latest = self._fetch_latest_release_tag()
        if latest and latest != pinned:
            print(
                f"ℹ️  upscayl-ncnn {latest} est disponible en amont ; ce dépôt épingle {pinned}.\n"
                f"   Pour l'adopter : mettre à jour 'upscayl_release' ET l'empreinte "
                f"'darwin_upscayl'/'linux_upscayl' dans app/scripts/checksums.json."
            )
        return pinned

    def _fetch_latest_release_tag(self) -> str:
        """Latest tag published upstream — purely informative.

        It is **not** used to choose what gets installed (cf.
        ``get_remote_version``): only to signal that bumping the pin is
        possible.
        """
        import json as _json
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/upscayl/upscayl-ncnn/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CorbeauSplat"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:  # nosec B310 - literal https URL (GitHub releases API)
                return _json.loads(resp.read()).get("tag_name", "")
        except Exception as e:
            print(f"⚠️ Could not fetch latest upscayl version: {e}")
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
