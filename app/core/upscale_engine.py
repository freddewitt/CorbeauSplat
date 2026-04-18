import subprocess
from pathlib import Path
from .base_engine import BaseEngine
from .system import resolve_project_root


class UpscaleEngine(BaseEngine):
    """
    Engine for Real-ESRGAN upscaling.
    Délègue l'exécution à upscale_runner.py via .venv_upscale (Python 3.11).
    """

    def __init__(self, logger_callback=None):
        super().__init__("Upscale", logger_callback)

    def _venv_python(self) -> Path:
        return resolve_project_root() / ".venv_upscale" / "bin" / "python3"

    def _runner(self) -> Path:
        return resolve_project_root() / "app" / "scripts" / "upscale_runner.py"

    def is_installed(self) -> bool:
        py = self._venv_python()
        if not py.exists():
            return False
        try:
            result = subprocess.run(
                [str(py), "-m", "pip", "show", "realesrgan", "torch"],
                capture_output=True, timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            print(f"DEBUG: Upscale check failed: {e}")
            return False

    def get_version(self) -> str:
        py = self._venv_python()
        if not py.exists():
            return None
        try:
            out = subprocess.check_output(
                [str(py), "-m", "pip", "show", "realesrgan"],
                text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return None

    def get_models_path(self) -> Path:
        root = resolve_project_root() / "app"
        weights_dir = root / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)
        return weights_dir

    def check_model_availability(self, model_name: str) -> bool:
        file_map = {
            "RealESRGAN_x4plus": "RealESRGAN_x4plus.pth",
            "RealESRNet_x4plus": "RealESRNet_x4plus.pth",
            "RealESRGAN_x4plus_anime_6B": "RealESRGAN_x4plus_anime_6B.pth",
        }
        filename = file_map.get(model_name)
        if not filename:
            return False
        return (self.get_models_path() / filename).exists()

    def download_model(self, model_name: str) -> bool:
        """Télécharge les poids du modèle (urllib, pas de subprocess nécessaire)."""
        urls = {
            "RealESRGAN_x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            "RealESRNet_x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth",
            "RealESRGAN_x4plus_anime_6B": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        }
        checksums = {
            "RealESRGAN_x4plus": "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1",
        }

        url = urls.get(model_name)
        if not url:
            self.log(f"Aucune URL pour {model_name}")
            return False

        save_path = self.get_models_path() / f"{model_name}.pth"
        expected_hash = checksums.get(model_name)

        if save_path.exists() and save_path.stat().st_size > 1024 * 1024:
            if expected_hash and self._verify_checksum(str(save_path), expected_hash):
                self.log(f"Modèle {model_name} valide (checksum OK).")
                return True
            elif not expected_hash:
                self.log(f"Modèle {model_name} présent (pas de checksum).")
                return True
            else:
                self.log(f"Modèle {model_name} corrompu. Suppression.")
                save_path.unlink()

        self.log(f"Téléchargement de {model_name}...")
        try:
            import urllib.request
            urllib.request.urlretrieve(url, str(save_path))
            if not save_path.exists() or save_path.stat().st_size < 1024 * 1024:
                self.log("Téléchargement échoué (fichier trop petit).")
                return False
            if expected_hash:
                if not self._verify_checksum(str(save_path), expected_hash):
                    self.log("AVERTISSEMENT SÉCURITÉ: checksum incorrect !")
                    save_path.unlink()
                    return False
                self.log("Checksum OK.")
            return True
        except Exception as e:
            self.log(f"Téléchargement échoué: {e}")
            return False

    def _verify_checksum(self, file_path: str, expected_hash: str) -> bool:
        import hashlib
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest() == expected_hash
        except Exception:
            return False

    def load_model(self, model_name="RealESRGAN_x4plus", tile=0, target_scale=4, half=False):
        """Retourne un dict de paramètres (utilisé comme handle par upscale_image/folder)."""
        if not self.is_installed():
            self.log("Dépendances non installées.")
            return None
        if not self.check_model_availability(model_name):
            self.log(f"Modèle {model_name} manquant. Téléchargement...")
            if not self.download_model(model_name):
                self.log(f"Impossible de télécharger {model_name}.")
                return None
        return {"model_name": model_name, "tile": tile, "target_scale": target_scale, "half": half}

    def _build_cmd(self, mode: str, input_path: str, output_path: str, params: dict) -> list:
        cmd = [
            str(self._venv_python()), str(self._runner()),
            "--mode", mode,
            "--input", str(input_path),
            "--output", str(output_path),
            "--model", params.get("model_name", "RealESRGAN_x4plus"),
            "--weights-dir", str(self.get_models_path()),
            "--tile", str(params.get("tile", 512)),
            "--scale", str(params.get("target_scale", 4)),
        ]
        if params.get("half"):
            cmd.append("--half")
        return cmd

    def upscale_image(self, input_path, output_path, upsampler, face_enhance=False) -> bool:
        """upsampler est un dict de params retourné par load_model()."""
        if upsampler is None:
            return False
        cmd = self._build_cmd("image", input_path, output_path, upsampler)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            for line in result.stdout.splitlines():
                self.log(line)
            if result.returncode != 0:
                self.log(f"Erreur upscale: {result.stderr[:500]}")
                return False
            return True
        except Exception as e:
            self.log(f"Erreur subprocess upscale: {e}")
            return False

    def upscale_folder(self, input_dir, output_dir, extension="jpg",
                       model_name="RealESRGAN_x4plus", tile=0,
                       target_scale=4, face_enhance=False) -> tuple:
        """Lance l'upscale d'un dossier entier via subprocess avec suivi de progression."""
        params = {"model_name": model_name, "tile": tile, "target_scale": target_scale}
        cmd = self._build_cmd("folder", input_dir, output_dir, params)

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            success_count, total = 0, 0
            for line in proc.stdout:
                line = line.strip()
                if line.startswith("PROGRESS:"):
                    _, counts, name = line.split(":", 2)
                    current, total = map(int, counts.split("/"))
                    self.log(f"Upscale [{current}/{total}]: {name}")
                elif line.startswith("DONE:"):
                    parts = line[5:].split("/")
                    success_count, total = int(parts[0]), int(parts[1])
                else:
                    self.log(line)
            proc.wait()
            if proc.returncode != 0:
                err = proc.stderr.read(500) if proc.stderr else ""
                return False, f"Erreur upscale: {err}"
            return True, f"{success_count}/{total} images traitées."
        except Exception as e:
            return False, str(e)
