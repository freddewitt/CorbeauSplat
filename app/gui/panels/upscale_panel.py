"""OPTIONS step: Upscale (upscayl-ncnn), run before Reconstruction.

Dual purpose, like the other steps in the group: the local button launches a
standalone upscale on the paths entered here, while the "Launch" chain only
includes the step if the ``upscaler_avant`` flag is active (cf.
``pipeline_planner.plan_pipeline``), in which case it works on the project's
images rather than on these paths.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.i18n import add_language_observer, tr
from app.gui.widgets.cancel_button import CancelButton
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_name
from app.gui.widgets.drop_line_edit import DropLineEdit


class UpscalePanel:
    def __init__(self, run_state):
        self.run_state = run_state
        self._dl_worker = None
        self.center = self._build_center()
        self.right = self._build_right()
        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()
        self.refresh_models()

    def _build_center(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        self.lbl_status = QLabel()
        layout.addWidget(self.lbl_status)
        self.lbl_catalog = QLabel()
        self.lbl_catalog.setWordWrap(True)
        layout.addWidget(self.lbl_catalog)

        self.lbl_input = QLabel()
        layout.addWidget(self.lbl_input)
        in_row = QHBoxLayout()
        self.input_path = DropLineEdit()
        in_row.addWidget(self.input_path)
        self.btn_browse_input = QPushButton("\U0001F4C1")
        self.btn_browse_input.clicked.connect(self._browse_input)
        in_row.addWidget(self.btn_browse_input)
        layout.addLayout(in_row)

        self.lbl_output = QLabel()
        layout.addWidget(self.lbl_output)
        out_row = QHBoxLayout()
        self.output_path = QLineEdit()
        out_row.addWidget(self.output_path)
        self.btn_browse_output = QPushButton("\U0001F4C1")
        self.btn_browse_output.clicked.connect(self._browse_output)
        out_row.addWidget(self.btn_browse_output)
        layout.addLayout(out_row)

        # ── Moved out of _build_right: model, scale, format, tiles, TTA,
        # compression (same "everything in the centre" convention as the other Paramètres steps) ──
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # \u00e9vite d\u00e9bordement horizontal (libell\u00e9s longs)

        self.combo_model = QComboBox()
        # `activated`, not `currentIndexChanged`: it fires only when the user
        # picks an entry. currentIndexChanged also fires on setCurrentIndex(),
        # which set_state() calls — so reloading a saved configuration naming an
        # uninstalled model used to start a network download nobody asked for.
        # refresh_models() repopulating the combo triggered it too.
        self.combo_model.activated.connect(self._on_model_activated)
        self.combo_model.currentIndexChanged.connect(self._refresh_model_status)
        self.lbl_model = QLabel()
        form.addRow(self.lbl_model, self.combo_model)
        self.combo_scale = QComboBox()
        # Same set as the CLI --scale. x1 is kept on purpose: it performs no
        # upscaling but still runs the format conversion, which is how mixed
        # HEIC/TIFF folders are normalised.
        for s in (1, 2, 3, 4):
            self.combo_scale.addItem(f"x{s}", s)
        self.combo_scale.setCurrentIndex(3)  # x4
        self.lbl_scale = QLabel()
        form.addRow(self.lbl_scale, self.combo_scale)
        self.combo_format = QComboBox()
        self.combo_format.addItems(["PNG", "JPEG", "WebP"])
        self.lbl_format = QLabel()
        form.addRow(self.lbl_format, self.combo_format)
        self.spin_tile = QSpinBox()
        self.spin_tile.setRange(0, 1024)
        self.lbl_tile = QLabel()
        form.addRow(self.lbl_tile, self.spin_tile)

        self.chk_tta = QCheckBox()
        self.lbl_tta = QLabel()
        form.addRow(self.lbl_tta, self.chk_tta)
        self.spin_compression = QSpinBox()
        self.spin_compression.setRange(0, 9)
        self.lbl_compression = QLabel()
        form.addRow(self.lbl_compression, self.spin_compression)
        layout.addLayout(form)

        layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.btn_run = QPushButton()
        self.btn_run.setStyleSheet("font-weight: bold;")
        outer.addWidget(self.btn_run)
        self.btn_cancel = CancelButton()
        outer.addWidget(self.btn_cancel)
        return w

    def _build_right(self):
        """Model gallery: one ``ModelCard`` per catalogue entry.

        The centre pane's dropdown only marks installed vs missing; the gallery
        is where each model is described, weighed and managed. Cards are built
        once and refreshed in place, so their signal connections survive.
        """
        from app.gui.widgets.upscale_widgets import ModelCard
        from app.upscayl_manager import get_models_dir
        from app.upscayl_models import MODELS

        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)

        self.lbl_gallery = QLabel()
        self.lbl_gallery.setWordWrap(True)
        outer.addWidget(self.lbl_gallery)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        cards_layout = QVBoxLayout(container)
        cards_layout.setSpacing(4)
        cards_layout.setContentsMargins(0, 0, 0, 0)

        models_dir = get_models_dir()
        self._model_cards = {}
        for model in MODELS:
            card = ModelCard(model, models_dir)
            card.download_requested.connect(self._download_model)
            card.delete_requested.connect(self._delete_model)
            self._model_cards[model.id] = card
            cards_layout.addWidget(card)
        cards_layout.addStretch(1)

        scroll.setWidget(container)
        outer.addWidget(scroll)
        return w

    # ── Model gallery actions ────────────────────────────────────────────────

    def _download_model(self, model_id):
        """Fetch a model on the gallery's demand, reusing the combo's worker.

        One download at a time: ``_dl_worker`` is the shared guard, so a card
        click and a dropdown change cannot start two transfers at once.
        """
        from app.gui.widgets.upscale_widgets import ModelDownloadWorker
        from app.upscayl_models import get_model

        if self._dl_worker is not None:
            return
        model = get_model(model_id)
        if model is None or not model.url_bin:
            return
        card = self._model_cards.get(model_id)
        if card is not None:
            card.set_downloading(True)
        self.lbl_status.setText(tr("up_model_downloading").format(model.label))
        self.combo_model.setEnabled(False)
        self.btn_run.setEnabled(False)

        self._dl_worker = ModelDownloadWorker(model_id)
        self._dl_worker.finished_signal.connect(self._on_model_downloaded)
        self._dl_worker.start()

    def _delete_model(self, model_id):
        """Remove a downloaded model's two files, after confirmation.

        Only touches ``<models_dir>/<id>.bin`` and ``.param``, never the
        bundled models shipped inside the upscayl-bin archive (their cards
        offer no action).
        """
        from app.upscayl_manager import get_models_dir
        from app.upscayl_models import get_model

        model = get_model(model_id)
        label = model.label if model is not None else model_id
        reply = QMessageBox.question(
            self.center,
            tr("up_delete_title", "Supprimer le modèle"),
            tr("up_delete_body", "Supprimer « {} » du disque ?").format(label),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        models_dir = get_models_dir()
        for ext in (".bin", ".param"):
            (models_dir / f"{model_id}{ext}").unlink(missing_ok=True)
        self.refresh_models()

    def _browse_input(self):
        """Input accepts a single image OR a folder of images (cf. the
        ``run_upscale_job`` docstring: "folder or single file") — ask which one
        to browse for, since Qt has no native picker that lets the user pick
        either."""
        box = QMessageBox(self.center)
        box.setWindowTitle(tr("btn_browse", "Parcourir"))
        box.setText(tr("up_browse_kind", "Sélectionner une image ou un dossier ?"))
        btn_file = box.addButton(tr("up_browse_file", "Image"), QMessageBox.ButtonRole.AcceptRole)
        btn_dir = box.addButton(tr("up_browse_dir", "Dossier"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_file:
            path, _ = get_open_file_name(
                self.center, tr("btn_browse", "Parcourir"), "",
                "Images (*.png *.jpg *.jpeg *.webp *.tif *.tiff)",
            )
        elif clicked is btn_dir:
            path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        else:
            path = None
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self.center, tr("btn_browse", "Parcourir"))
        if path:
            self.output_path.setText(path)

    # ── Model catalog ────────────────────────────────────────────────────────────

    def refresh_models(self):
        """Populate the model list, ✅ installed / ⬇️ to download.

        Called on construction and after each download. Without this call the
        combo stays empty and ``get_params()`` returns an empty ``model_id``,
        which makes ``run_upscayl`` fail with "No model selected".
        """
        from app.upscayl_manager import get_models_dir
        from app.upscayl_models import MODELS

        models_dir = get_models_dir()
        previous = self.combo_model.currentData()

        self.combo_model.blockSignals(True)
        self.combo_model.clear()
        for m in MODELS:
            marker = "✅" if m.is_downloaded(models_dir) else "⬇️"
            self.combo_model.addItem(f"{marker} {m.label}", m.id)
            self.combo_model.setItemData(
                self.combo_model.count() - 1, m.description, Qt.ItemDataRole.ToolTipRole
            )
        if self.combo_model.count() == 0:
            self.combo_model.addItem(tr("up_no_models", "Aucun modèle disponible"), None)
        idx = self.combo_model.findData(previous) if previous else -1
        if idx < 0:
            # By default, preselect an already-installed model: otherwise the
            # first one in the list is selected without being downloaded and
            # "Launch" fails on a model that can't be found.
            installed = next((m.id for m in MODELS if m.is_downloaded(models_dir)), None)
            idx = self.combo_model.findData(installed) if installed else -1
        if idx >= 0:
            self.combo_model.setCurrentIndex(idx)
        self.combo_model.blockSignals(False)

        # Both views read the same catalogue; keep them in step.
        for card in getattr(self, "_model_cards", {}).values():
            card.refresh()

    def _missing_model(self):
        """The selected model when it is not installed, else None."""
        from app.upscayl_manager import get_models_dir
        from app.upscayl_models import get_model

        model_id = self.combo_model.currentData()
        if not model_id:
            return None
        model = get_model(model_id)
        if model is None or model.is_downloaded(get_models_dir()):
            return None
        return model

    def _refresh_model_status(self, _index=None):
        """Report whether the selected model is installed. Never downloads.

        Reached on programmatic selection too — restoring a configuration, or
        refresh_models() rebuilding the list. Those must not reach the network,
        but staying silent would let the user discover the missing model only
        when the run fails.
        """
        if self._dl_worker is not None:
            return
        model = self._missing_model()
        if model is not None:
            self.lbl_status.setText(tr("up_model_not_installed").format(model.label))

    def _on_model_activated(self, _index=None):
        """Download the chosen model when the *user* selects an uninstalled one."""
        if self._dl_worker is not None:
            return
        model = self._missing_model()
        if model is None:
            return

        from app.gui.widgets.upscale_widgets import ModelDownloadWorker

        self.lbl_status.setText(tr("up_model_downloading").format(model.label))
        self.combo_model.setEnabled(False)
        self.btn_run.setEnabled(False)

        self._dl_worker = ModelDownloadWorker(model.id)
        self._dl_worker.finished_signal.connect(self._on_model_downloaded)
        self._dl_worker.start()

    def _on_model_downloaded(self, ok, label):
        self._dl_worker = None
        self.combo_model.setEnabled(True)
        self.btn_run.setEnabled(True)
        key = "up_model_downloaded" if ok else "up_model_download_failed"
        self.lbl_status.setText(tr(key).format(label))
        self.refresh_models()

    def get_params(self):
        """Return the upscale parameters as a dict."""
        return {
            "model_id": self.combo_model.currentData() or "",
            "scale": self.combo_scale.currentData(),
            "format": self.combo_format.currentText().lower(),
            "tile": self.spin_tile.value(),
            "tta": self.chk_tta.isChecked(),
            "compression": self.spin_compression.value(),
        }

    def get_state(self):
        """State serializable into a named configuration (ChainConfig.upscale).

        Paths aren't taken from ``get_params``: they only concern the local
        launch from this page (the chain itself works on the project's
        images, cf. ``StudioWindow._build_upscale_worker``)."""
        return {
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "model_id": self.combo_model.currentData() or "",
            "scale": self.combo_scale.currentData(),
            "format": self.combo_format.currentText(),
            "tile": self.spin_tile.value(),
            "tta": self.chk_tta.isChecked(),
            "compression": self.spin_compression.value(),
        }

    def set_state(self, state):
        if not state:
            return
        self.input_path.setText(state.get("input_path", ""))
        self.output_path.setText(state.get("output_path", ""))
        if state.get("model_id"):
            idx = self.combo_model.findData(state["model_id"])
            if idx >= 0:
                self.combo_model.setCurrentIndex(idx)
        if state.get("scale"):
            idx = self.combo_scale.findData(state["scale"])
            if idx >= 0:
                self.combo_scale.setCurrentIndex(idx)
        if state.get("format"):
            idx = self.combo_format.findText(state["format"])
            if idx >= 0:
                self.combo_format.setCurrentIndex(idx)
        if "tile" in state:
            self.spin_tile.setValue(state["tile"])
        self.chk_tta.setChecked(state.get("tta", False))
        if "compression" in state:
            self.spin_compression.setValue(state["compression"])

    def retranslate_ui(self):
        self.lbl_status.setText(tr("up_status", "Moteur Upscale"))
        self.lbl_catalog.setText(tr("up_catalog", "Catalogue des modèles (à télécharger/gérer)"))
        self.lbl_gallery.setText(tr("up_models", "Modèles disponibles"))
        self.lbl_input.setText(tr("up_input", "Source (fichier ou dossier)"))
        self.lbl_output.setText(tr("up_output", "Destination"))
        self.lbl_model.setText(tr("up_model", "Modèle actif"))
        self.lbl_scale.setText(tr("up_output_scale", "Échelle de sortie"))
        self.lbl_format.setText(tr("up_output_format", "Format de sortie"))
        self.lbl_tile.setText(tr("up_tile", "Taille des tuiles"))
        self.lbl_tta.setText(tr("up_tta", "TTA (Test-Time Augmentation)"))
        self.lbl_compression.setText(tr("up_compression", "Compression"))
        self.btn_run.setText(tr("btn_run", "Lancer"))
