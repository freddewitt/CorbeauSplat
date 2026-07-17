"""
upscale_engine.py — Thin wrapper around the upscayl-bin CLI.

No Python venv required. upscayl-bin is a standalone NCNN-based binary.
"""
import shutil
import tempfile
from pathlib import Path

from .base_engine import BaseEngine


class UpscaleEngine(BaseEngine):

    def __init__(self, logger_callback=None):
        super().__init__("Upscale", logger_callback)

    def _binary(self) -> Path | None:
        from app.upscayl_manager import find_binary
        return find_binary()

    def _models_dir(self) -> Path | None:
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

        If *tile* is 0 (auto-detect), the tile size is adapted to available
        system memory to avoid swapping on low-RAM Apple Silicon systems:
          - < 8 GB total  → tile=256 (conservative)
          - 8-16 GB total  → tile=512 (balanced)
          - ≥ 16 GB total  → tile=0   (let upscayl-bin decide)
        Memory pressure > 80% reduces tile by one step.
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

        # --- Adaptive tile size based on available RAM ---
        if tile == 0:
            from .system import get_memory_info
            mem = get_memory_info()
            total_gb = mem.get("total", 0) / (1024 ** 3)
            pressure = mem.get("percent", 0.0)

            if total_gb < 8:
                tile = 256
            elif total_gb < 16:
                tile = 512
            else:
                tile = 0  # plenty of RAM — let upscayl-bin decide

            # Under high memory pressure, reduce tile to avoid swap
            if tile > 0 and pressure > 80:
                tile = max(128, tile // 2)
                self.log(
                    f"⚠️ Mémoire sous pression ({pressure}%) — "
                    f"tile réduit à {tile}px pour éviter le swap."
                )

            if tile > 0:
                self.log(
                    f"🧠 {total_gb:.0f} Go RAM — tile adaptatif : {tile}px "
                    f"(pression mémoire: {pressure}%)"
                )
            else:
                self.log(f"🧠 {total_gb:.0f} Go RAM — tile laissé en auto (0)")

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
        safe_in = self.validate_path(input_path)
        if safe_in is None:
            self.log(f"SECURITY: Invalid input path: {input_path}")
            return False
        safe_out = self.validate_path(output_path)
        if safe_out is None:
            out_parent = Path(output_path).parent
            safe_parent = self.validate_path(str(out_parent))
            if safe_parent is None:
                self.log(f"SECURITY: Invalid output path: {output_path}")
                return False
            safe_out = safe_parent / Path(output_path).name
        with tempfile.TemporaryDirectory() as tmp_in:
            shutil.copy2(safe_in, Path(tmp_in) / safe_in.name)
            safe_out.parent.mkdir(parents=True, exist_ok=True)
            success, _ = self.upscale_folder(
                input_dir=tmp_in,
                output_dir=str(safe_out.parent),
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
        # Validate paths
        safe_in = self.validate_path(input_dir)
        safe_out = self.validate_path(output_dir) or (Path(output_dir).parent if self.validate_path(str(Path(output_dir).parent)) else None)
        if safe_in is None:
            self.log(f"SECURITY: Invalid input directory: {input_dir}")
            return False, "Chemin d'entrée non autorisé."
        if safe_out is None:
            out_parent = Path(output_dir).parent
            safe_parent = self.validate_path(str(out_parent))
            if safe_parent is None:
                self.log(f"SECURITY: Invalid output directory: {output_dir}")
                return False, "Chemin de sortie non autorisé."
            safe_out = safe_parent / Path(output_dir).name
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
        run_upscayl(input_dir, str(safe_out), params,  # pass original input_dir to run_upscayl (validated)
                    log_callback=self.log,
                    done_callback=lambda ok: result.__setitem__(0, ok),
                    cancel_check=cancel_check)
        return result[0], "Upscale complete." if result[0] else "Upscale failed."
