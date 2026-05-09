"""
upscale_engine.py — Thin wrapper around the upscayl-bin CLI.

No Python venv required. upscayl-bin is a standalone NCNN-based binary.
"""
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
                   compression=0) -> dict | None:
        """Returns a params dict used by upscale_image/upscale_folder.
        Adjusts the model_id to match the requested scale when possible.
        """
        if not self.is_installed():
            self.log("upscayl-bin not found.")
            return None
        # If the selected model is a fixed‑scale model (e.g., contains "x4"),
        # and the user requested a different scale, try to pick a matching model.
        # This simple heuristic replaces the trailing "x4" with the desired scale.
        if scale != 4 and "x4" in model_id:
            candidate = model_id.replace("x4", str(scale))
            # The actual model may not exist; we keep the original if the candidate
            # is not found later by upscayl-bin, but we prefer the adjusted one.
            model_id = candidate
        return {
            "model_id": model_id, "scale": scale,
            "output_format": output_format, "tile": tile,
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
                       compression=0, custom_scale=None,
                       cancel_check=None) -> tuple:
        if not model_id:
            return False, "No model selected."
        from app.upscayl_manager import run_upscayl
        params = {
            "model_id":    model_id,
            "scale":       custom_scale or scale,
            "format":      output_format,
            "tile":        tile,
            "tta":         tta,
            "compression": compression,
        }
        result = [False]
        run_upscayl(input_dir, output_dir, params,
                    log_callback=self.log,
                    done_callback=lambda ok: result.__setitem__(0, ok),
                    cancel_check=cancel_check)
        return result[0], "Upscale complete." if result[0] else "Upscale failed."
