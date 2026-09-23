from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.core.i18n import add_language_observer, tr
from app.core.media import IMAGE_EXTENSIONS, convert_image
from app.upscayl_models import get_model


class ModelCard(QFrame):
    """One row of the Upscale model gallery: name, description, size, action.

    The panel's dropdown only tells installed models from missing ones; the
    gallery is where a model is described, weighed, fetched or removed. The card
    owns no worker: it emits, the panel downloads and calls ``refresh``.
    """

    download_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, model, models_dir: Path):
        super().__init__()
        self.model = model
        self.models_dir = models_dir
        self._action_handler = None
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._build()
        add_language_observer(self.refresh)

    def _set_action_handler(self, handler):
        """(Re)connect the action button, disconnecting only the previous
        handler — a bare disconnect() raises a RuntimeWarning under PySide6."""
        if self._action_handler is not None:
            self.btn_action.clicked.disconnect(self._action_handler)
        self._action_handler = handler
        self.btn_action.clicked.connect(handler)

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        info = QVBoxLayout()
        self.lbl_name = QLabel(f"<b>{self.model.label}</b>")
        self.lbl_desc = QLabel(self.model.description)
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #888; font-size: 11px;")
        info.addWidget(self.lbl_name)
        info.addWidget(self.lbl_desc)
        layout.addLayout(info, stretch=1)

        badge = QLabel(f"x{self.model.scale}")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedWidth(32)
        badge.setStyleSheet(
            "background: #2a82da; color: white; border-radius: 4px; "
            "font-size: 11px; font-weight: bold; padding: 2px 4px;"
        )
        layout.addWidget(badge)

        self.lbl_status = QLabel()
        self.lbl_status.setFixedWidth(120)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.lbl_status)

        self.btn_action = QPushButton()
        self.btn_action.setFixedWidth(90)
        layout.addWidget(self.btn_action)

        self.refresh()

    def refresh(self):
        """Re-read the model's state on disk and rebuild the row's right side."""
        if self.model.is_downloaded(self.models_dir):
            size = self.model.size_on_disk_mb(self.models_dir)
            self.lbl_status.setText(f"✅ {size} MB")
            self.lbl_status.setStyleSheet("color: #44aa44; font-size: 11px;")
            self.btn_action.setText(tr("up_delete", "Supprimer"))
            self.btn_action.setStyleSheet("color: #cc4444;")
            self._set_action_handler(lambda: self.delete_requested.emit(self.model.id))
            self.btn_action.setEnabled(True)
        elif self.model.bundled and not self.model.url_bin:
            # Shipped inside the upscayl-bin archive: nothing to fetch, nothing
            # to delete, and no files of our own to measure.
            self.lbl_status.setText(tr("up_bundled", "Inclus"))
            self.lbl_status.setStyleSheet("color: #888; font-size: 11px;")
            self.btn_action.setText("—")
            self.btn_action.setEnabled(False)
        else:
            self.lbl_status.setText(tr("up_not_installed", "Non installé"))
            self.lbl_status.setStyleSheet("color: #888; font-size: 11px;")
            self.btn_action.setText(tr("up_download", "Télécharger"))
            self.btn_action.setStyleSheet("")
            self._set_action_handler(lambda: self.download_requested.emit(self.model.id))
            self.btn_action.setEnabled(True)

    def set_downloading(self, active: bool):
        self.btn_action.setEnabled(not active)
        if active:
            self.lbl_status.setText(tr("up_downloading", "Téléchargement…"))
            self.lbl_status.setStyleSheet("color: #2a82da; font-size: 11px;")


class ModelDownloadWorker(QThread):
    """Downloads a model's .bin/.param files off the GUI thread.

    ``download_model_files`` makes blocking network requests (up to a 120s
    timeout per file): calling it directly from a Qt slot would freeze the
    interface.
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
    """Run an upscayl-bin upscale and return ``(success, message)``.

    Extracted from :class:`TestWorker`'s body to be shared with
    :class:`UpscaleImagesWorker` (OPTIONS "Upscale" step): both need exactly
    the same invocation (x1 mode = upscale then resize back to original size,
    folder or single file), only their destination differs.
    """
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

    # Stage every source image under a name that already carries the model
    # and scale used (<stem>_<model_id>_x<scale>.<fmt>) *before* upscayl-bin
    # ever runs. This guarantees the output file can never collide with —
    # and so never silently overwrite — an existing file, including the
    # original itself when input and output folders happen to be the same.
    suffix = f"_{model_id}_x{req_scale}"
    # Recursive on purpose: the chain's previous step may nest its images
    # (360Extractor writes <images_360>/equi_processed/), and Reconstruction
    # itself collects the source folder recursively.
    sources = (
        sorted(f for f in src.rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)
        if src.is_dir()
        else [src]
    )

    staged_names = _staged_names(sources, suffix, fmt, root=src if src.is_dir() else None)

    with _tempfile.TemporaryDirectory(prefix="upscayl_in_") as tmp_in:
        tmp_in_path = Path(tmp_in)
        orig_sizes = {}
        for f in sources:
            staged_name = staged_names[f]
            _copy_as_supported_image(f, tmp_in_path / staged_name)
            if x1_mode:
                from PIL import Image as _PIL
                # Read back the staged copy: the original may be a format
                # Pillow cannot open (HEIC), the staged one never is.
                with _PIL.open(tmp_in_path / staged_name) as im:
                    orig_sizes[staged_name] = im.size

        success = [False]
        run_upscayl(tmp_in, output_dir, upscayl_params,
                    log_callback=log_callback,
                    done_callback=lambda ok: success.__setitem__(0, ok),
                    cancel_check=cancel_check)
        if success[0] and x1_mode:
            resize_to_original(output_dir, orig_sizes)

    return success[0], (output_dir if success[0] else "Upscale échoué.")


def _staged_names(sources, suffix, fmt, root=None):
    """Map each source to its staged file name (``<stem><suffix>.<fmt>``).

    Sources sharing a stem (``a.jpg`` and ``a.png``, or ``x/a.jpg`` and
    ``y/a.jpg`` when *root* is scanned recursively) would get the same name
    and silently overwrite each other, so those alone also carry their
    sub-folder (relative to *root*) and original extension
    (``a_y_jpg<suffix>.<fmt>``). Other names are unchanged.
    """
    counts = {}
    for f in sources:
        counts[f.stem.lower()] = counts.get(f.stem.lower(), 0) + 1
    names = {}
    for f in sources:
        tag = ""
        if counts[f.stem.lower()] > 1:
            parts = []
            if root is not None:
                try:
                    parts = list(f.parent.relative_to(root).parts)
                except ValueError:
                    parts = []
            parts.append(f.suffix.lower().lstrip("."))
            tag = "_" + "_".join(parts)
        names[f] = f"{f.stem}{tag}{suffix}.{fmt}"
    return names


def _copy_as_supported_image(src: Path, dest: Path) -> None:
    """Copies *src* to *dest*, re-encoding it as 8-bit RGB/RGBA first.

    upscayl-bin's image loader rejects some real-world scans (CMYK, 16-bit,
    palette/indexed color, interlaced PNG…) with a generic "channels: 0"
    error. Re-saving through Pillow normalizes the pixel format before the
    binary ever sees the file. Falls back to a raw copy if Pillow can't open
    it (e.g. an already-unsupported format), so the original error surfaces.
    """
    from PIL import Image as _PIL
    try:
        with _PIL.open(src) as im:
            has_alpha = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
            im.convert("RGBA" if has_alpha else "RGB").save(dest)
    except Exception:
        # HEIC and friends: Pillow has no decoder here, macOS sips does.
        fmt = "jpeg" if dest.suffix.lower() in (".jpg", ".jpeg") else "png"
        if convert_image(src, dest, fmt):
            return
        import shutil as _shutil
        _shutil.copy2(src, dest)


class TestWorker(QThread):
    """Local upscale launch from the OPTIONS › Upscale page
    (paths entered in the panel, outside the pipeline chain)."""

    log_signal = Signal(str)
    finished   = Signal(bool, str)

    def __init__(self, input_path: str, output_dir: str, params: dict):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.params     = params
        self.stopped_by_user = False

    def stop(self):
        """Clean cancellation: run_upscayl terminates the upscayl-bin
        subprocess as soon as ``cancel_check`` (isInterruptionRequested) turns true."""
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
    """``upscale`` chain step: enlarges the project's source images into
    ``output_dir``, which Reconstruction will then consume instead of the
    original folder (cf. ``StudioWindow._build_colmap_worker``).

    The user's source folder is never modified: same precautionary principle
    as ``ColmapEngine._run_upscale``, which moves the originals into
    ``images_src`` rather than overwriting them. Exposes ``finished_signal``
    (not ``finished`` like :class:`TestWorker`) to be drivable by
    ``_start_pipeline_worker``, like the other step workers.
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
            # Same path safeguard as all engines (BaseEngine.validate_path):
            # this step writes an entire folder, it's no exception.
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
