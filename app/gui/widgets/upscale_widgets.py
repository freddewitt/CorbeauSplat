from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.upscayl_models import get_model


class ModelDownloadWorker(QThread):
    """Télécharge les fichiers .bin/.param d'un modèle hors du thread GUI.

    ``download_model_files`` fait des requêtes réseau bloquantes (jusqu'à 120 s
    de timeout par fichier) : l'appeler directement depuis un slot Qt gèlerait
    l'interface.
    """

    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, model_id: str):
        super().__init__()
        self.model_id = model_id

    def run(self):
        from app.upscayl_manager import download_model_files

        model = get_model(self.model_id)
        if model is None:
            self.finished_signal.emit(False, self.model_id)
            return
        try:
            ok = download_model_files(
                model.url_bin, model.url_param, model.id,
                log_callback=self.log_signal.emit,
            )
        except Exception as e:
            self.log_signal.emit(str(e))
            ok = False
        self.finished_signal.emit(ok, model.label)


def run_upscale_job(input_path, output_dir, params, log_callback, cancel_check):
    """Exécute un upscale upscayl-bin et retourne ``(succès, message)``.

    Extrait du corps de :class:`TestWorker` pour être partagé avec
    :class:`UpscaleImagesWorker` (étape PARAMÈTRES « Upscale ») : les deux ont
    besoin exactement de la même invocation (mode x1 = upscale puis retour à la
    taille d'origine, dossier ou fichier unique), seule leur destination diffère.
    """
    import shutil as _shutil
    import tempfile as _tempfile

    from app.upscayl_manager import find_binary, resize_to_original, run_upscayl

    model_id = params.get("model_id", "")
    if not model_id:
        return False, "Aucun modèle sélectionné."
    if not find_binary():
        return False, "upscayl-bin introuvable."

    fmt = params.get("format", "png")
    req_scale = params.get("scale", 4)
    src = Path(input_path)

    x1_mode = (req_scale == 1)
    if x1_mode:
        m = get_model(model_id)
        actual_scale = m.scale if m else 4
    else:
        actual_scale = req_scale

    upscayl_params = {
        "model_id":    model_id,
        "scale":       actual_scale,
        "format":      fmt,
        "tile":        params.get("tile", 0),
        "tta":         params.get("tta", False),
        "compression": params.get("compression", 0),
    }

    if src.is_dir():
        if x1_mode:
            from PIL import Image as _PIL
            image_exts = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
            orig_sizes = {}
            for f in src.iterdir():
                if f.is_file() and f.suffix.lower() in image_exts:
                    with _PIL.open(f) as im:
                        orig_sizes[f.stem + "." + fmt] = im.size

        success = [False]
        run_upscayl(str(src), output_dir, upscayl_params,
                    log_callback=log_callback,
                    done_callback=lambda ok: success.__setitem__(0, ok),
                    cancel_check=cancel_check)
        if success[0] and x1_mode:
            resize_to_original(output_dir, orig_sizes)
    else:
        if x1_mode:
            from PIL import Image as _PIL
            with _PIL.open(src) as im:
                orig_sizes = {src.stem + "." + fmt: im.size}

        with _tempfile.TemporaryDirectory(prefix="upscayl_in_") as tmp_in:
            _shutil.copy2(src, Path(tmp_in) / src.name)
            success = [False]
            run_upscayl(tmp_in, output_dir, upscayl_params,
                        log_callback=log_callback,
                        done_callback=lambda ok: success.__setitem__(0, ok),
                        cancel_check=cancel_check)
            if success[0] and x1_mode:
                resize_to_original(output_dir, orig_sizes)

    return success[0], (output_dir if success[0] else "Upscale échoué.")


class TestWorker(QThread):
    """Lancement local de l'upscale depuis la page PARAMÈTRES › Upscale
    (chemins saisis dans le panneau, hors chaîne pipeline)."""

    log_signal = Signal(str)
    finished   = Signal(bool, str)

    def __init__(self, input_path: str, output_dir: str, params: dict):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.params     = params
        self.stopped_by_user = False

    def stop(self):
        """Annulation propre : run_upscayl termine le sous-processus upscayl-bin
        dès que ``cancel_check`` (isInterruptionRequested) devient vrai."""
        self.stopped_by_user = True
        self.requestInterruption()

    def run(self):
        try:
            ok, message = run_upscale_job(
                self.input_path, self.output_dir, self.params,
                log_callback=self.log_signal.emit,
                cancel_check=self.isInterruptionRequested,
            )
            self.finished.emit(ok, message)
        except Exception as e:
            self.finished.emit(False, str(e))


class UpscaleImagesWorker(QThread):
    """Étape ``upscale`` de la chaîne : agrandit les images sources du projet
    vers ``output_dir``, que Reconstruction consommera ensuite à la place du
    dossier d'origine (cf. ``StudioWindow._build_colmap_worker``).

    Le dossier source de l'utilisateur n'est jamais modifié : même principe de
    précaution que ``ColmapEngine._run_upscale``, qui déplace les originaux dans
    ``images_src`` plutôt que de les écraser. Expose ``finished_signal`` (et non
    ``finished`` comme :class:`TestWorker`) pour être pilotable par
    ``_start_pipeline_worker``, comme les autres workers d'étape.
    """

    log_signal = Signal(str)
    finished_signal = Signal(bool, str)

    def __init__(self, images_dir: str, output_dir: str, params: dict):
        super().__init__()
        self.images_dir = images_dir
        self.output_dir = output_dir
        self.params = params
        self.stopped_by_user = False

    def stop(self):
        self.stopped_by_user = True
        self.requestInterruption()

    def run(self):
        from app.core.upscale_engine import UpscaleEngine

        try:
            # Même garde-fou de chemin que tous les moteurs (BaseEngine.validate_path) :
            # l'étape écrit un dossier entier, elle ne fait pas exception.
            engine = UpscaleEngine(logger_callback=self.log_signal.emit)
            safe_in = engine.validate_path(self.images_dir)
            if safe_in is None or not safe_in.is_dir():
                self.finished_signal.emit(False, f"Dossier d'images invalide : {self.images_dir}")
                return
            out = Path(self.output_dir)
            safe_out = engine.validate_path(str(out.parent))
            if safe_out is None:
                self.finished_signal.emit(False, f"Destination invalide : {self.output_dir}")
                return
            dest = safe_out / out.name
            dest.mkdir(parents=True, exist_ok=True)

            ok, message = run_upscale_job(
                str(safe_in), str(dest), self.params,
                log_callback=self.log_signal.emit,
                cancel_check=self.isInterruptionRequested,
            )
            self.finished_signal.emit(ok, message)
        except Exception as e:
            self.finished_signal.emit(False, str(e))
