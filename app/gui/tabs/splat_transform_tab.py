from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QCheckBox, QComboBox, QScrollArea, QFrame,
    QSpinBox,
)
from PyQt6.QtCore import pyqtSignal

from app.core.i18n import tr, add_language_observer
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.dialog_utils import get_open_file_name, get_existing_directory


# Output format → file extension mapping
OUTPUT_FORMATS = [
    ("PLY",              "ply"),
    ("Compressed PLY",   "ply"),   # same ext, tool detects via content
    ("SPZ",              "spz"),
    ("GLB",              "glb"),
    ("CSV",              "csv"),
]


class SplatTransformTab(QWidget):
    """Tab for the PlayCanvas splat-transform CLI tool."""

    transformRequested = pyqtSignal(str, str, dict)  # input, output, params
    stopRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        add_language_observer(self.retranslate_ui)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(6)

        # ── Status bar (fixed top) ───────────────────────────────────────────
        from app.core.splat_transform_engine import SplatTransformEngine
        engine = SplatTransformEngine()
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_lbl = QLabel()
        if engine.is_available():
            self.status_lbl.setText(tr("st_detected", "splat-transform detected"))
            self.status_lbl.setStyleSheet("color: #44aa44;")
        else:
            self.status_lbl.setText(tr("st_not_found", "splat-transform not found — install via dependency setup"))
            self.status_lbl.setStyleSheet("color: #aa4444; font-weight: bold;")
        status_layout.addWidget(self.status_lbl)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        # ── Scrollable parameter area ────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 10, 4)
        layout.setSpacing(8)

        # ── Input group ──────────────────────────────────────────────────────
        input_group = QGroupBox(tr("st_group_input", "Input File"))
        input_gl = QVBoxLayout(input_group)
        input_gl.setContentsMargins(8, 10, 8, 8)
        input_gl.setSpacing(0)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(4)
        self.lbl_input = QLabel(tr("st_lbl_input", "Input:"))
        self.lbl_input.setFixedWidth(56)
        self.input_path = DropLineEdit()
        self.input_path.setPlaceholderText(tr("st_ph_input", "Path to .ply, .spz, .splat …"))
        self.btn_browse_input = QPushButton("…")
        self.btn_browse_input.setFixedWidth(32)
        self.btn_browse_input.clicked.connect(self._browse_input)
        input_row.addWidget(self.lbl_input)
        input_row.addWidget(self.input_path)
        input_row.addWidget(self.btn_browse_input)
        input_gl.addLayout(input_row)
        layout.addWidget(input_group)

        # ── Output group ─────────────────────────────────────────────────────
        output_group = QGroupBox(tr("st_group_output", "Output"))
        output_gl = QVBoxLayout(output_group)
        output_gl.setContentsMargins(8, 10, 8, 8)
        output_gl.setSpacing(6)

        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(4)
        self.lbl_output_dir = QLabel(tr("st_lbl_output_dir", "Folder:"))
        self.lbl_output_dir.setFixedWidth(56)
        self.output_dir = DropLineEdit()
        self.output_dir.setPlaceholderText(tr("st_ph_output_dir", "Destination folder"))
        self.btn_browse_output = QPushButton("…")
        self.btn_browse_output.setFixedWidth(32)
        self.btn_browse_output.clicked.connect(self._browse_output)
        output_row.addWidget(self.lbl_output_dir)
        output_row.addWidget(self.output_dir)
        output_row.addWidget(self.btn_browse_output)
        output_gl.addLayout(output_row)

        format_row = QHBoxLayout()
        format_row.setContentsMargins(0, 0, 0, 0)
        format_row.setSpacing(4)
        self.lbl_format = QLabel(tr("st_lbl_format", "Format:"))
        self.lbl_format.setFixedWidth(56)
        self.combo_format = QComboBox()
        for label, _ in OUTPUT_FORMATS:
            self.combo_format.addItem(label)
        self.combo_format.setMinimumWidth(160)
        format_row.addWidget(self.lbl_format)
        format_row.addWidget(self.combo_format)
        format_row.addStretch()
        output_gl.addLayout(format_row)
        layout.addWidget(output_group)

        # ── Filters group ────────────────────────────────────────────────────
        filter_group = QGroupBox(tr("st_group_filters", "Filters & Transformations"))
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setContentsMargins(8, 10, 8, 8)
        filter_layout.setSpacing(8)

        self.check_filter_nan = QCheckBox(
            tr("st_check_filter_nan",
               "Remove degenerate splats (--filter-nan)  [filterFloaters equivalent]")
        )
        self.check_filter_nan.setToolTip(
            tr("st_tip_filter_nan",
               "Removes splats with NaN or invalid values — "
               "equivalent to 'filterFloaters' cleaning.")
        )
        filter_layout.addWidget(self.check_filter_nan)

        self.check_morton = QCheckBox(
            tr("st_check_morton", "Optimize spatial ordering (--morton-order)")
        )
        self.check_morton.setToolTip(
            tr("st_tip_morton",
               "Reorders splats using Morton curve for better GPU cache locality.")
        )
        filter_layout.addWidget(self.check_morton)

        # SH band reduction — two-line layout avoids overflow with long labels
        self.check_sh = QCheckBox(tr("st_check_sh", "Reduce spherical harmonics (--filter-harmonics):"))
        filter_layout.addWidget(self.check_sh)

        sh_combo_row = QHBoxLayout()
        sh_combo_row.setContentsMargins(20, 0, 0, 0)
        sh_combo_row.setSpacing(4)
        self.combo_sh = QComboBox()
        self.combo_sh.addItem(tr("st_sh_0", "Band 0 only (smallest)"), "0")
        self.combo_sh.addItem(tr("st_sh_1", "Up to band 1"), "1")
        self.combo_sh.addItem(tr("st_sh_2", "Up to band 2"), "2")
        self.combo_sh.addItem(tr("st_sh_3", "Up to band 3 (default)"), "3")
        self.combo_sh.setCurrentIndex(3)
        self.combo_sh.setMinimumWidth(180)
        self.combo_sh.setEnabled(False)
        self.check_sh.toggled.connect(self.combo_sh.setEnabled)
        sh_combo_row.addWidget(self.combo_sh)
        sh_combo_row.addStretch()
        filter_layout.addLayout(sh_combo_row)

        # Decimation
        self.check_decimate = QCheckBox(tr("st_check_decimate", "Decimate (--decimate):"))
        filter_layout.addWidget(self.check_decimate)

        dec_spin_row = QHBoxLayout()
        dec_spin_row.setContentsMargins(20, 0, 0, 0)
        dec_spin_row.setSpacing(6)
        self.spin_decimate = QSpinBox()
        self.spin_decimate.setRange(1, 99)
        self.spin_decimate.setValue(50)
        self.spin_decimate.setSuffix(" %")
        self.spin_decimate.setFixedWidth(80)
        self.spin_decimate.setEnabled(False)
        self.check_decimate.toggled.connect(self.spin_decimate.setEnabled)
        self.lbl_decimate_tip = QLabel(tr("st_lbl_decimate_tip", "of points to keep"))
        self.lbl_decimate_tip.setStyleSheet("color: #888888; font-size: 11px;")
        dec_spin_row.addWidget(self.spin_decimate)
        dec_spin_row.addWidget(self.lbl_decimate_tip)
        dec_spin_row.addStretch()
        filter_layout.addLayout(dec_spin_row)

        layout.addWidget(filter_group)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # ── Action buttons (fixed bottom) ────────────────────────────────────
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self.btn_run = QPushButton(tr("st_btn_run", "Run splat-transform"))
        self.btn_run.setMinimumHeight(40)
        self.btn_run.setStyleSheet(
            "background-color: #2a82da; color: white; font-weight: bold; border-radius: 4px;"
        )
        self.btn_run.clicked.connect(self._on_run_clicked)
        action_layout.addWidget(self.btn_run)

        self.btn_stop = QPushButton(tr("btn_stop", "Stop"))
        self.btn_stop.setFixedWidth(100)
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setStyleSheet(
            "background-color: #555555; color: white; font-weight: bold; border-radius: 4px;"
        )
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stopRequested.emit)
        action_layout.addWidget(self.btn_stop)

        main_layout.addLayout(action_layout)

    # ── Event handlers ───────────────────────────────────────────────────────

    def _browse_input(self):
        path, _ = get_open_file_name(
            self,
            tr("st_dlg_input", "Select input file"),
            filter="Splat files (*.ply *.spz *.splat *.ksplat);;All files (*)",
        )
        if path:
            self.input_path.setText(path)

    def _browse_output(self):
        path = get_existing_directory(self, tr("st_dlg_output", "Select output folder"))
        if path:
            self.output_dir.setText(path)

    def _on_run_clicked(self):
        input_p = self.input_path.text().strip()
        output_d = self.output_dir.text().strip()

        if not input_p:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("msg_warning"), tr("st_err_no_input", "Please select an input file."))
            return
        if not output_d:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("msg_warning"), tr("st_err_no_output", "Please select an output folder."))
            return

        # Build output file path from input stem + chosen format
        input_stem = Path(input_p).stem
        fmt_idx = self.combo_format.currentIndex()
        _, ext = OUTPUT_FORMATS[fmt_idx]
        output_file = str(Path(output_d) / f"{input_stem}.{ext}")

        params = self._build_params()
        self.transformRequested.emit(input_p, output_file, params)

    def _build_params(self) -> dict:
        params = {}
        if self.check_filter_nan.isChecked():
            params["--filter-nan"] = True
        if self.check_morton.isChecked():
            params["--morton-order"] = True
        if self.check_sh.isChecked():
            params["--filter-harmonics"] = self.combo_sh.currentData()
        if self.check_decimate.isChecked():
            params["--decimate"] = f"{self.spin_decimate.value()}%"
        params["--overwrite"] = True
        return params

    # ── State management ─────────────────────────────────────────────────────

    def set_processing_state(self, is_processing: bool):
        self.btn_run.setEnabled(not is_processing)
        self.btn_stop.setEnabled(is_processing)

    def get_state(self) -> dict:
        return {
            "input_path": self.input_path.text(),
            "output_dir": self.output_dir.text(),
            "format_index": self.combo_format.currentIndex(),
            "filter_nan": self.check_filter_nan.isChecked(),
            "morton_order": self.check_morton.isChecked(),
            "sh_enabled": self.check_sh.isChecked(),
            "sh_bands": self.combo_sh.currentIndex(),
            "decimate_enabled": self.check_decimate.isChecked(),
            "decimate_pct": self.spin_decimate.value(),
        }

    def set_state(self, state: dict):
        if not state:
            return
        if "input_path" in state:
            self.input_path.setText(state["input_path"])
        if "output_dir" in state:
            self.output_dir.setText(state["output_dir"])
        if "format_index" in state:
            self.combo_format.setCurrentIndex(state["format_index"])
        if "filter_nan" in state:
            self.check_filter_nan.setChecked(state["filter_nan"])
        if "morton_order" in state:
            self.check_morton.setChecked(state["morton_order"])
        if "sh_enabled" in state:
            self.check_sh.setChecked(state["sh_enabled"])
        if "sh_bands" in state:
            self.combo_sh.setCurrentIndex(state["sh_bands"])
        if "decimate_enabled" in state:
            self.check_decimate.setChecked(state["decimate_enabled"])
        if "decimate_pct" in state:
            self.spin_decimate.setValue(state["decimate_pct"])

    # ── i18n ─────────────────────────────────────────────────────────────────

    def retranslate_ui(self):
        self.btn_run.setText(tr("st_btn_run", "Run splat-transform"))
        self.btn_stop.setText(tr("btn_stop", "Stop"))
        self.lbl_input.setText(tr("st_lbl_input", "Input:"))
        self.lbl_output_dir.setText(tr("st_lbl_output_dir", "Folder:"))
        self.lbl_format.setText(tr("st_lbl_format", "Format:"))
        self.check_filter_nan.setText(
            tr("st_check_filter_nan",
               "Remove degenerate splats (--filter-nan)  [filterFloaters equivalent]")
        )
        self.check_morton.setText(
            tr("st_check_morton", "Optimize spatial ordering (--morton-order)")
        )
        self.check_sh.setText(tr("st_check_sh", "Reduce spherical harmonics (--filter-harmonics):"))
        self.check_decimate.setText(tr("st_check_decimate", "Decimate (--decimate):"))
        self.lbl_decimate_tip.setText(tr("st_lbl_decimate_tip", "of points to keep"))
