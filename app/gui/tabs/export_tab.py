import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QGroupBox, QFormLayout, QLineEdit, QListWidget, QListWidgetItem,
    QCheckBox, QMessageBox, QProgressBar, QFrame, QSpinBox, QDoubleSpinBox,
    QStackedWidget, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from app.core.i18n import tr, add_language_observer
from app.core.export_engine import ExportEngine
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.dialog_utils import get_open_file_name, get_existing_directory


class ExportTab(QWidget):
    """Onglet d'export des fichiers PLY vers différents formats avec options avancées."""

    exportRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = ExportEngine(logger_callback=self.log)
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        status_layout = QHBoxLayout()
        self.status_lbl = QLabel(tr("export_title"))
        self.status_lbl.setStyleSheet("color: #44aa44;")
        status_layout.addWidget(self.status_lbl)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        input_group = QGroupBox(tr("export_group_input"))
        input_layout = QFormLayout()

        self.input_list = QListWidget()
        self.input_list.setMinimumHeight(120)
        self.input_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        input_layout.addRow(tr("export_lbl_files"), self.input_list)

        btn_layout = QHBoxLayout()
        self.btn_add_files = QPushButton(tr("btn_add_files"))
        self.btn_add_files.clicked.connect(self.add_files)
        btn_layout.addWidget(self.btn_add_files)

        self.btn_add_folder = QPushButton(tr("btn_add_folder"))
        self.btn_add_folder.clicked.connect(self.add_folder)
        btn_layout.addWidget(self.btn_add_folder)

        self.btn_clear = QPushButton(tr("btn_clear"))
        self.btn_clear.clicked.connect(self.clear_list)
        btn_layout.addWidget(self.btn_clear)

        input_layout.addRow("", btn_layout)
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        format_group = QGroupBox(tr("export_group_format"))
        format_layout = QFormLayout()

        self.combo_format = QComboBox()
        self.combo_format.addItem("SPZ (Gaussian Splats Web - Compressé)", "spz")
        self.combo_format.addItem("GLB (Web/Three.js)", "glb")
        self.combo_format.addItem("OBJ (Blender/3D)", "obj")
        self.combo_format.addItem("PLY (Original)", "ply")
        self.combo_format.addItem("XYZ (Points)", "xyz")
        self.combo_format.currentIndexChanged.connect(self.on_format_changed)
        format_layout.addRow(tr("export_lbl_format"), self.combo_format)

        # Options spécifiques au format (stacked widget)
        self.options_stack = QStackedWidget()
        self._create_format_options()
        format_layout.addRow("Options:", self.options_stack)

        format_group.setLayout(format_layout)
        main_layout.addWidget(format_group)

        output_group = QGroupBox(tr("export_group_output"))
        output_layout = QFormLayout()

        out_layout = QHBoxLayout()
        self.output_path = DropLineEdit()
        self.btn_browse_output = QPushButton("...")
        self.btn_browse_output.setMaximumWidth(40)
        self.btn_browse_output.clicked.connect(self.browse_output)
        out_layout.addWidget(self.output_path)
        out_layout.addWidget(self.btn_browse_output)
        output_layout.addRow(tr("export_lbl_output"), out_layout)

        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)

        action_layout = QHBoxLayout()
        self.btn_export = QPushButton(tr("btn_export"))
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setStyleSheet(
            "background-color: #2a82da; color: white; font-weight: bold; border-radius: 4px;"
        )
        self.btn_export.clicked.connect(self.start_export)
        action_layout.addWidget(self.btn_export)

        main_layout.addLayout(action_layout)

        main_layout.addStretch()

    def _create_format_options(self):
        """Crée les widgets d'options pour chaque format."""
        # Index 0: SPZ options
        self.spz_widget = QWidget()
        spz_layout = QFormLayout(self.spz_widget)
        self.spz_quantize = QCheckBox("Quantifier les positions (réduit taille)")
        self.spz_quantize.setChecked(False)
        spz_layout.addRow(self.spz_quantize)
        self.spz_sh = QCheckBox("Inclure Spherical Harmonics")
        self.spz_sh.setChecked(True)
        spz_layout.addRow(self.spz_sh)
        self.options_stack.addWidget(self.spz_widget)

        # Index 1: GLB options
        self.glb_widget = QWidget()
        glb_layout = QFormLayout(self.glb_widget)
        self.glb_method = QComboBox()
        self.glb_method.addItem("Auto (recommandé)", "auto")
        self.glb_method.addItem("Trimesh", "trimesh")
        self.glb_method.addItem("Open3D", "open3d")
        self.glb_method.addItem("Assimp", "assimp")
        glb_layout.addRow("Méthode:", self.glb_method)
        self.options_stack.addWidget(self.glb_widget)

        # Index 2: OBJ options
        self.obj_widget = QWidget()
        obj_layout = QFormLayout(self.obj_widget)
        self.obj_colors = QCheckBox("Inclure couleurs des vertices")
        self.obj_colors.setChecked(True)
        obj_layout.addRow(self.obj_colors)
        self.obj_mtl = QCheckBox("Générer fichier matériaux (.mtl)")
        self.obj_mtl.setChecked(True)
        obj_layout.addRow(self.obj_mtl)
        self.obj_scale = QDoubleSpinBox()
        self.obj_scale.setRange(0.001, 1000.0)
        self.obj_scale.setValue(1.0)
        self.obj_scale.setDecimals(3)
        obj_layout.addRow("Scale:", self.obj_scale)
        self.options_stack.addWidget(self.obj_widget)

        # Index 3: PLY options
        self.ply_widget = QWidget()
        ply_layout = QFormLayout(self.ply_widget)
        self.ply_ascii = QCheckBox("Format ASCII (plus lisible, plus gros)")
        self.ply_ascii.setChecked(False)
        ply_layout.addRow(self.ply_ascii)
        self.ply_compress = QCheckBox("Compresser en .gz")
        self.ply_compress.setChecked(False)
        ply_layout.addRow(self.ply_compress)
        self.options_stack.addWidget(self.ply_widget)

        # Index 4: XYZ options
        self.xyz_widget = QWidget()
        xyz_layout = QFormLayout(self.xyz_widget)
        self.xyz_colors = QCheckBox("Inclure couleurs RGB")
        self.xyz_colors.setChecked(False)
        xyz_layout.addRow(self.xyz_colors)
        self.xyz_delimiter = QComboBox()
        self.xyz_delimiter.addItem("Espace", " ")
        self.xyz_delimiter.addItem("Virgule", ",")
        self.xyz_delimiter.addItem("Tabulation", "\t")
        xyz_layout.addRow("Délimiteur:", self.xyz_delimiter)
        self.options_stack.addWidget(self.xyz_widget)

    def add_files(self):
        path, _ = get_open_file_name(
            self, tr("export_group_input"),
            "",
            "PLY Files (*.ply);;Tous (*.*)"
        )
        if path:
            self.add_file(path)

    def add_file(self, path):
        path = Path(path)
        if path.exists() and path.suffix.lower() == '.ply':
            item = QListWidgetItem(str(path))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.input_list.addItem(item)

    def add_folder(self):
        path = get_existing_directory(self, tr("export_group_input"))
        if path:
            folder = Path(path)
            for ply_file in folder.rglob("*.ply"):
                self.add_file(str(ply_file))

    def clear_list(self):
        self.input_list.clear()

    def browse_output(self):
        path = get_existing_directory(self, tr("export_group_output"))
        if path:
            self.output_path.setText(path)

    def on_format_changed(self, index):
        """Change les options affichées selon le format sélectionné."""
        self.options_stack.setCurrentIndex(index)

    def get_export_options(self) -> dict:
        """Retourne les options d'export selon le format sélectionné."""
        fmt = self.combo_format.currentData()
        
        if fmt == "spz":
            return {
                'quantize_positions': self.spz_quantize.isChecked(),
                'include_sh': self.spz_sh.isChecked(),
            }
        elif fmt == "glb":
            return {
                'method': self.glb_method.currentData(),
            }
        elif fmt == "obj":
            return {
                'include_vertex_colors': self.obj_colors.isChecked(),
                'include_materials': self.obj_mtl.isChecked(),
                'scale': self.obj_scale.value(),
            }
        elif fmt == "ply":
            return {
                'ascii_format': self.ply_ascii.isChecked(),
                'compress': self.ply_compress.isChecked(),
            }
        elif fmt == "xyz":
            return {
                'include_colors': self.xyz_colors.isChecked(),
                'delimiter': self.xyz_delimiter.currentData(),
            }
        return {}

    def log(self, msg):
        self.log_signal.emit(msg)

    def start_export(self):
        output_dir = self.output_path.text().strip()
        if not output_dir:
            QMessageBox.warning(self, tr("msg_warning"), tr("err_no_output"))
            return

        if self.input_list.count() == 0:
            QMessageBox.warning(self, tr("msg_warning"), tr("err_no_input"))
            return

        output_dir = Path(output_dir)
        output_format = self.combo_format.currentData()
        options = self.get_export_options()

        self.btn_export.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        success_count = 0
        total = self.input_list.count()

        for i in range(total):
            item = self.input_list.item(i)
            input_path = item.data(Qt.ItemDataRole.UserRole)

            self.progress.setValue(int((i / total) * 100))

            success = self.engine.export(input_path, str(output_dir), output_format, options=options)
            if success:
                success_count += 1

        self.progress.setValue(100)
        self.btn_export.setEnabled(True)
        self.progress.setVisible(False)

        QMessageBox.information(
            self,
            tr("export_done_title"),
            tr("export_done_body", f"{success_count}/{total}")
        )

    def retranslate_ui(self):
        self.status_lbl.setText(tr("export_title"))
        input_group = self.findChild(QGroupBox)
        if input_group:
            input_group.setTitle(tr("export_group_input"))


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = ExportTab()
    window.show()
    sys.exit(app.exec())
