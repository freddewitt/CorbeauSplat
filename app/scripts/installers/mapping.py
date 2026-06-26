"""COLMAP, FFmpeg and Glomap engine dependency installers (Windows/CUDA)."""
import json
import os
import shutil
import subprocess
import urllib.request

from app.core.system import has_cuda
from app.scripts.installers.base import EngineDependency
from app.scripts.installers.tools import (
    check_cmake_ninja,
    download_and_extract_zip,
    install_build_tools,
)

GLOMAP_REPO = "https://github.com/colmap/glomap.git"
COLMAP_RELEASES_API = "https://api.github.com/repos/colmap/colmap/releases/latest"
# Static "latest release essentials" build — stable URL, contains bin/ffmpeg.exe
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def find_colmap_windows_asset(assets: list, prefer_cuda: bool = True) -> dict | None:
    """Selects the Windows COLMAP release asset.

    Prefers the CUDA build (`*-windows-cuda.zip`) and explicitly avoids the
    `nocuda` build. Falls back to any Windows .zip.
    """
    def is_zip(a):
        return a.get("name", "").lower().endswith(".zip")

    if prefer_cuda:
        for a in assets:
            name = a.get("name", "").lower()
            if "windows" in name and "cuda" in name and "nocuda" not in name and is_zip(a):
                return a
    # Fallback: any windows zip (nocuda or generic)
    for a in assets:
        name = a.get("name", "").lower()
        if "windows" in name and is_zip(a):
            return a
    return None


class ColmapEngineDep(EngineDependency):
    """COLMAP on Windows — auto-downloads the pre-built CUDA release into engines/.

    The CUDA build (`colmap-x64-windows-cuda.zip`) is fetched from GitHub
    releases and extracted into ``engines/colmap``. ``resolve_binary("colmap")``
    then finds ``colmap.exe`` anywhere in that subtree.
    """
    ask_before_update = False

    def __init__(self):
        super().__init__("colmap")
        self.target_dir = self.engines_dir / "colmap"

    def is_installed(self) -> bool:
        from app.core.system import resolve_binary
        return resolve_binary("colmap") is not None

    def is_enabled_in_config(self, config: dict) -> bool:
        return True  # COLMAP is required by the core pipeline

    def _fetch_latest(self) -> dict | None:
        try:
            req = urllib.request.Request(
                COLMAP_RELEASES_API,
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CorbeauSplat"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"⚠️ Could not fetch COLMAP release info: {e}")
            return None

    def get_remote_version(self) -> str:
        data = self._fetch_latest()
        return data.get("tag_name", "") if data else ""

    def install(self):
        if self.is_installed() and self.get_local_version():
            return

        data = self._fetch_latest()
        if not data:
            print("❌ Impossible de contacter GitHub pour télécharger COLMAP.")
            return

        asset = find_colmap_windows_asset(data.get("assets", []), prefer_cuda=has_cuda())
        if not asset:
            print("❌ Aucun binaire COLMAP Windows trouvé dans la dernière release.")
            print("   Téléchargez-le manuellement : https://github.com/colmap/colmap/releases")
            return

        tag = data.get("tag_name", "")
        print(f">>> Installation automatique de COLMAP {tag} ({asset['name']})...")

        # Clean any previous extraction so updates don't accumulate
        if self.target_dir.exists():
            shutil.rmtree(str(self.target_dir), ignore_errors=True)

        if not download_and_extract_zip(asset["browser_download_url"], self.target_dir):
            print("❌ Échec du téléchargement/extraction de COLMAP.")
            return

        if self.is_installed():
            self.save_local_version(tag)
            print(f"✅ COLMAP {tag} installé dans {self.target_dir}.")
        else:
            print("⚠️ COLMAP extrait mais colmap.exe introuvable dans l'archive.")


class FfmpegEngineDep(EngineDependency):
    """FFmpeg on Windows — auto-downloads a static build into engines/ffmpeg.

    Tries `winget` first (if available) for a system-wide install, then falls
    back to extracting a static "essentials" build into ``engines/ffmpeg``.
    """
    ask_before_update = False

    def __init__(self):
        super().__init__("ffmpeg")
        self.target_dir = self.engines_dir / "ffmpeg"

    def is_installed(self) -> bool:
        from app.core.system import resolve_binary
        return resolve_binary("ffmpeg") is not None

    def is_enabled_in_config(self, config: dict) -> bool:
        return True  # FFmpeg is required for video input

    def get_remote_version(self) -> str:
        return ""  # No version tracking for the static build

    def install(self):
        # is_installed() also matches a system ffmpeg on PATH (e.g. via winget),
        # so we only download a self-contained build when none is present.
        if self.is_installed():
            return

        print(">>> Installation automatique de FFmpeg (build statique) dans engines/...")
        if self.target_dir.exists():
            shutil.rmtree(str(self.target_dir), ignore_errors=True)
        if not download_and_extract_zip(FFMPEG_ZIP_URL, self.target_dir):
            print("❌ Échec du téléchargement de FFmpeg. Installez-le manuellement et ajoutez-le au PATH.")
            return

        if self.is_installed():
            self.save_local_version("essentials")
            print(f"✅ FFmpeg installé dans {self.target_dir}.")
        else:
            print("⚠️ FFmpeg extrait mais ffmpeg.exe introuvable dans l'archive.")


class GlomapEngineDep(EngineDependency):
    ask_before_update = True
    install_on_startup = False  # Source build (MSVC + CUDA); only when use_glomap is on

    def __init__(self):
        super().__init__("glomap", GLOMAP_REPO)
        # Source code lives in a separate dir, not replacing the binary
        self.target_dir = self.engines_dir / "glomap-source"

    def is_enabled_in_config(self, config: dict) -> bool:
        return config.get("params", {}).get("use_glomap", False)

    def is_installed(self) -> bool:
        from app.core.system import resolve_binary
        return resolve_binary("glomap") is not None

    def install(self):
        if not check_cmake_ninja():
            if not install_build_tools():
                print("⚠️ CMake/Ninja requis pour compiler Glomap. Installez-les et relancez.")
                return

        self.update_git()
        source_dir = self.target_dir

        build_dir = source_dir / "build"
        if build_dir.exists():
            shutil.rmtree(str(build_dir))
        build_dir.mkdir(exist_ok=True)

        # GLOMAP fetches/builds its own COLMAP. On Windows we let CMake pick the
        # default (MSVC) generator; CUDA is auto-detected by COLMAP's CMake.
        cmake_args = ["cmake", "..", "-DCMAKE_BUILD_TYPE=Release", "-DFETCH_COLMAP=ON"]
        env = os.environ.copy()

        try:
            subprocess.check_call(cmake_args, cwd=str(build_dir), env=env)
            subprocess.check_call(
                ["cmake", "--build", ".", "--config", "Release"],
                cwd=str(build_dir), env=env,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"⚠️ Glomap build failed: {e}")
            return

        # Locate the built binary (glomap.exe on Windows)
        built_bin = None
        for pattern in ("glomap.exe", "glomap"):
            for found in build_dir.rglob(pattern):
                if found.is_file():
                    built_bin = found
                    break
            if built_bin:
                break

        if built_bin:
            dest = self.engines_dir / ("glomap.exe" if built_bin.suffix == ".exe" else "glomap")
            shutil.copy2(str(built_bin), str(dest))
            self.save_local_version(self.get_remote_version())
