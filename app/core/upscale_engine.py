"""
upscale_engine.py — Thin wrapper around the upscayl-bin CLI.

No Python venv required. upscayl-bin is a standalone NCNN-based binary.
"""
import subprocess
import tempfile
import shutil
from pathlib import Path
from .base_engine import BaseEngine


class UpscaleEngine(BaseEngine):

    def __init__(self, logger_callback=None):
        super().__init__("Upscale", logger_callback)

    def _binary(self) -> Path | None:
        from app.upscayl_manager import find_binary
        return find_binary()

    def _models_dir(self) -> Path:
        from app.upscayl_manager import get_effective_models_dir
        return get_effective_models_dir()

    # ----------------------------------------------------------------- public

    def is_installed(self) -> bool:
        return self._binary() is not None

    def load_model(self, model_id="realesrgan-x4plus", scale=4,
                   output_format="png", tile=0, tta=False,
                   compression=0, **_) -> dict | None:
        """Returns a params dict used by upscale_image/upscale_folder."""
        if not self.is_installed():
            self.log("upscayl-bin not found.")
            return None
        return {
            "model_id": model_id, "scale": scale,
            "format": output_format, "tile": tile,
            "tta": tta, "compression": compression,
        }

    def upscale_image(self, input_path, output_path, upsampler,
                      face_enhance=False) -> bool:
        """
        upsampler — dict returned by load_model().
        upscayl-bin works on folders; we use a temp dir for single-image calls.
        """
        if not upsampler:
            return False
        input_path = Path(input_path)
        output_path = Path(output_path)
        with tempfile.TemporaryDirectory() as tmp_in:
            shutil.copy2(input_path, Path(tmp_in) / input_path.name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            success, _ = self.upscale_folder(
                input_dir=tmp_in,
                output_dir=str(output_path.parent),
                **upsampler,
            )
            return success

    def upscale_folder(self, input_dir, output_dir,
                       model_id="realesrgan-x4plus", scale=4,
                       output_format="png", tile=0, tta=False,
                       compression=0, custom_scale=None, **_) -> tuple:
        binary = self._binary()
        if not binary:
            return False, "upscayl-bin not found."

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        cmd = [
            str(binary),
            "-i", str(input_dir),
            "-o", str(output_dir),
            "-n", model_id,
            "-z", str(scale),
            "-f", output_format,
            "-t", str(tile),
        ]
        models_dir = self._models_dir()
        if models_dir:
            cmd += ["-m", str(models_dir)]
        if tta:
            cmd.append("-x")
        if custom_scale:
            cmd += ["-s", str(custom_scale)]
        if compression > 0 and output_format in ("jpg", "webp"):
            cmd += ["-c", str(compression)]

        self.log(f"upscayl-bin: {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                self.log(line.rstrip())
            proc.wait()
            if proc.returncode != 0:
                return False, f"upscayl-bin exited with code {proc.returncode}"
            return True, "Upscale complete."
        except Exception as e:
            return False, str(e)
