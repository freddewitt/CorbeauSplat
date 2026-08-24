"""Étape PARAMÈTRES : Upscale (upscayl-ncnn), exécutée avant Reconstruction.

Double emploi, comme les autres étapes du groupe : le bouton local lance un
upscale indépendant sur les chemins saisis ici, tandis que la chaîne « Lancer »
n'inclut l'étape que si le drapeau ``upscaler_avant`` est actif (cf.
``pipeline_planner.plan_pipeline``), auquel cas elle travaille sur les images du
projet et non sur ces chemins.
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

        # \u2500\u2500 Migr\u00e9 depuis _build_right : mod\u00e8le, \u00e9chelle, format, tuiles, TTA,
        # compression (m\u00eame convention \u00ab tout au centre \u00bb que les autres \u00e9tapes Param\u00e8tres) \u2500\u2500
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)  # \u00e9vite d\u00e9bordement horizontal (libell\u00e9s longs)

        self.combo_model = QComboBox()
        self.combo_model.currentIndexChanged.connect(self._on_model_changed)
        self.lbl_model = QLabel()
        form.addRow(self.lbl_model, self.combo_model)
        self.combo_scale = QComboBox()
        for s in (1, 2, 4):
            self.combo_scale.addItem(f"x{s}", s)
        self.combo_scale.setCurrentIndex(2)
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
        return QWidget()

    def _browse_input(self):
        """Input accepts a single image OR a folder of images (cf. ``run_upscale_job``
        docstring: "dossier ou fichier unique") — ask which one to browse for,
        since Qt has no native picker that lets the user pick either."""
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

    # ── Catalogue de modèles ────────────────────────────────────────────────────

    def refresh_models(self):
        """Peuple la liste des modèles, ✅ installé / ⬇️ à télécharger.

        Appelée à la construction et après chaque téléchargement. Sans cet appel
        le combo reste vide et ``get_params()`` renvoie un ``model_id`` vide, ce
        qui fait échouer ``run_upscayl`` avec « Aucun modèle sélectionné ».
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
            # Par défaut, présélectionner un modèle déjà installé : sinon le
            # premier de la liste est sélectionné sans être téléchargé et
            # « Lancer » échoue sur un modèle introuvable.
            installed = next((m.id for m in MODELS if m.is_downloaded(models_dir)), None)
            idx = self.combo_model.findData(installed) if installed else -1
        if idx >= 0:
            self.combo_model.setCurrentIndex(idx)
        self.combo_model.blockSignals(False)

    def _on_model_changed(self, _index=None):
        """Déclenche le téléchargement si le modèle choisi n'est pas installé."""
        from app.upscayl_manager import get_models_dir
        from app.upscayl_models import get_model

        model_id = self.combo_model.currentData()
        if not model_id or self._dl_worker is not None:
            return
        model = get_model(model_id)
        if model is None or model.is_downloaded(get_models_dir()):
            return

        from app.gui.widgets.upscale_widgets import ModelDownloadWorker

        self.lbl_status.setText(tr("up_model_downloading").format(model.label))
        self.combo_model.setEnabled(False)
        self.btn_run.setEnabled(False)

        self._dl_worker = ModelDownloadWorker(model_id)
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
        """Retourne les paramètres d'upscale sous forme de dict."""
        return {
            "model_id": self.combo_model.currentData() or "",
            "scale": self.combo_scale.currentData(),
            "format": self.combo_format.currentText().lower(),
            "tile": self.spin_tile.value(),
            "tta": self.chk_tta.isChecked(),
            "compression": self.spin_compression.value(),
        }

    def get_state(self):
        """État sérialisable dans une configuration nommée (ChainConfig.upscale).

        Les chemins ne sont pas repris de ``get_params`` : ils ne concernent que
        le lancement local depuis cette page (la chaîne, elle, travaille sur les
        images du projet, cf. ``StudioWindow._build_upscale_worker``)."""
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
        self.lbl_input.setText(tr("up_input", "Source (fichier ou dossier)"))
        self.lbl_output.setText(tr("up_output", "Destination"))
        self.lbl_model.setText(tr("up_model", "Modèle actif"))
        self.lbl_scale.setText(tr("up_output_scale", "Échelle de sortie"))
        self.lbl_format.setText(tr("up_output_format", "Format de sortie"))
        self.lbl_tile.setText(tr("up_tile", "Taille des tuiles"))
        self.lbl_tta.setText(tr("up_tta", "TTA (Test-Time Augmentation)"))
        self.lbl_compression.setText(tr("up_compression", "Compression"))
        self.btn_run.setText(tr("btn_run", "Lancer"))
