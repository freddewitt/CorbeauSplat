"""
upscayl_models.py — Catalogue of upscayl-ncnn compatible models.

Models marked bundled=True are included in the upscayl-bin release archive.
Custom models require individual download via url_bin / url_param.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_CUSTOM = "https://raw.githubusercontent.com/upscayl/custom-models/main/models"


@dataclass
class UpscaylModel:
    id: str
    label: str
    scale: int
    description: str
    bundled: bool
    url_bin: str = ""
    url_param: str = ""

    def is_downloaded(self, models_dir: Path) -> bool:
        return (
            (models_dir / f"{self.id}.bin").exists() and
            (models_dir / f"{self.id}.param").exists()
        )

    def size_on_disk_mb(self, models_dir: Path) -> float:
        total = sum(
            (models_dir / f"{self.id}{ext}").stat().st_size
            for ext in (".bin", ".param")
            if (models_dir / f"{self.id}{ext}").exists()
        )
        return round(total / 1024 / 1024, 1)


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
    ),
    UpscaylModel(
        id="RealESRGAN_General_x4_v3",
        label="Real-ESRGAN General — Fast",
        scale=4,
        description="Lighter and faster than x4+. Good for quick batch processing.",
        bundled=False,
        url_bin=f"{_CUSTOM}/RealESRGAN_General_x4_v3.bin",
        url_param=f"{_CUSTOM}/RealESRGAN_General_x4_v3.param",
    ),
    UpscaylModel(
        id="4xLSDIR",
        label="4xLSDIR — Ultra Fidelity",
        scale=4,
        description="Maximum detail for high-quality photography. Slower but sharper.",
        bundled=False,
        url_bin=f"{_CUSTOM}/4xLSDIR.bin",
        url_param=f"{_CUSTOM}/4xLSDIR.param",
    ),
    UpscaylModel(
        id="4xNomos8kSC",
        label="4xNomos8kSC — Texture Detail",
        scale=4,
        description="Excellent for preserving fine textures and structural details.",
        bundled=False,
        url_bin=f"{_CUSTOM}/4xNomos8kSC.bin",
        url_param=f"{_CUSTOM}/4xNomos8kSC.param",
    ),
    UpscaylModel(
        id="realesrgan-x4plus-anime",
        label="Real-ESRGAN Anime — Stylized",
        scale=4,
        description="Optimized for drawn, illustrated or stylized content.",
        bundled=False,
        url_bin=f"{_CUSTOM}/realesr-animevideov3-x4.bin",
        url_param=f"{_CUSTOM}/realesr-animevideov3-x4.param",
    ),
    UpscaylModel(
        id="4x_NMKD-Siax_200k",
        label="NMKD-Siax — Low Compression",
        scale=4,
        description="Best results on lightly compressed or high-quality source images.",
        bundled=False,
        url_bin=f"{_CUSTOM}/4x_NMKD-Siax_200k.bin",
        url_param=f"{_CUSTOM}/4x_NMKD-Siax_200k.param",
    ),
]


def get_model(model_id: str) -> Optional[UpscaylModel]:
    return next((m for m in MODELS if m.id == model_id), None)


def get_downloaded_models(models_dir: Path) -> list[UpscaylModel]:
    return [m for m in MODELS if m.is_downloaded(models_dir)]
