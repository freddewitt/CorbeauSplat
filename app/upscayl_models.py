"""
upscayl_models.py — Catalogue of upscayl-ncnn compatible models.

Models marked bundled=True are included in the upscayl-bin release archive.
Custom models require individual download via url_bin / url_param.
"""
import contextlib
from dataclasses import dataclass
from pathlib import Path

# Pinned to a commit, not to `main`: these files are downloaded and fed to
# upscayl-bin, so a moving branch means the bytes can change under us between
# two installs while the declared checksums stay put.
_CUSTOM_COMMIT = "4b6d2cfa59c7442af115dfc6e50fd8d7d40b96ef"
_CUSTOM = f"https://raw.githubusercontent.com/upscayl/custom-models/{_CUSTOM_COMMIT}/models"


@dataclass
class UpscaylModel:
    id: str
    label: str
    scale: int
    description: str
    bundled: bool
    url_bin: str = ""
    url_param: str = ""
    sha256_bin: str = ""
    sha256_param: str = ""

    def is_downloaded(self, models_dir: Path) -> bool:
        return (
            (models_dir / f"{self.id}.bin").exists() and
            (models_dir / f"{self.id}.param").exists()
        )

    def size_on_disk_mb(self, models_dir: Path) -> int:
        """Rounded megabytes taken by the model's two files, 0 if absent.

        Shown on the gallery cards so the user can weigh a download or a
        deletion; models range from a few MB to ~70 MB.
        """
        total = 0
        for ext in (".bin", ".param"):
            path = models_dir / f"{self.id}{ext}"
            with contextlib.suppress(OSError):
                total += path.stat().st_size
        return round(total / (1024 * 1024))


# ---------------------------------------------------------------------------
# Catalogue  (6 models, each with a distinct use case)
# ---------------------------------------------------------------------------

MODELS: list[UpscaylModel] = [
    UpscaylModel(
        id="realesrgan-x4plus",
        label="Real-ESRGAN x4+ — General  ⭐",
        scale=4,
        description="Best all-round model for real-world photos. Click Download to install.",
        bundled=False,
        url_bin=f"{_CUSTOM}/RealESRGAN_General_x4_v3.bin",
        url_param=f"{_CUSTOM}/RealESRGAN_General_x4_v3.param",
        sha256_bin="85ee266b632a765a725425ba6a5620c088c8aa2939a03063b2d83b3462724cc1",
        sha256_param="22174924330297357434ad21ed0af7f4b820008d2a502b492754d130d4142714",
    ),
    UpscaylModel(
        id="4xLSDIR",
        label="4xLSDIR — Ultra Fidelity",
        scale=4,
        description="Maximum detail for high-quality photography. Slower but sharper.",
        bundled=False,
        url_bin=f"{_CUSTOM}/4xLSDIR.bin",
        url_param=f"{_CUSTOM}/4xLSDIR.param",
        sha256_bin="0622f182f0a940b395e4fc70e2707b285e016fa4b014e855205eb40efddfb853",
        sha256_param="4576ed5c2fc5fa250d3c3d585ef02248f26abdfc1867088078f501fe71e5d61e",
    ),
    UpscaylModel(
        id="4xNomos8kSC",
        label="4xNomos8kSC — Texture Detail",
        scale=4,
        description="Excellent for preserving fine textures and structural details.",
        bundled=False,
        url_bin=f"{_CUSTOM}/4xNomos8kSC.bin",
        url_param=f"{_CUSTOM}/4xNomos8kSC.param",
        sha256_bin="da16e3880d87b177b7c6b659bbd880f8a101b868eb9ebc08d69eaa6d3edc4517",
        sha256_param="4576ed5c2fc5fa250d3c3d585ef02248f26abdfc1867088078f501fe71e5d61e",
    ),
    UpscaylModel(
        id="realesrgan-x4plus-anime",
        label="Real-ESRGAN Anime — Stylized",
        scale=4,
        description="Optimized for drawn, illustrated or stylized content.",
        bundled=False,
        url_bin=f"{_CUSTOM}/realesr-animevideov3-x4.bin",
        url_param=f"{_CUSTOM}/realesr-animevideov3-x4.param",
        sha256_bin="548a36f9c3f4ab8da56cd3b13badf23968bee207b396dad14d04b830e5f2ab2d",
        sha256_param="850a248e7c14c27e5bd8cf7265113a9441036a7db63963bb8aa5169d788a435e",
    ),
    UpscaylModel(
        id="4x_NMKD-Siax_200k",
        label="NMKD-Siax — Low Compression",
        scale=4,
        description="Best results on lightly compressed or high-quality source images.",
        bundled=False,
        url_bin=f"{_CUSTOM}/4x_NMKD-Siax_200k.bin",
        url_param=f"{_CUSTOM}/4x_NMKD-Siax_200k.param",
        sha256_bin="b2abdffa30fb15be752ac681e0c0edf8b543745c33a989aadc9d7d3394dd3110",
        sha256_param="519bffb4912e295155d3cb5d6a29639d217ccca55f80962d8f677ef777a65b7a",
    ),
]


# Ids that no longer have their own entry, mapped to the one that replaced them.
# "RealESRGAN_General_x4_v3" was a second entry pointing at the exact same two
# files as "realesrgan-x4plus"; it is kept resolvable so a saved configuration
# naming it does not suddenly fail with "Modèle introuvable".
_MODEL_ALIASES = {
    "RealESRGAN_General_x4_v3": "realesrgan-x4plus",
}


def get_model(model_id: str) -> UpscaylModel | None:
    resolved = _MODEL_ALIASES.get(model_id, model_id)
    return next((m for m in MODELS if m.id == resolved), None)


def get_downloaded_models(models_dir: Path) -> list[UpscaylModel]:
    return [m for m in MODELS if m.is_downloaded(models_dir)]
