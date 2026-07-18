from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from app import VERSION
from app.core.engine import ColmapEngine
from app.core.i18n import add_language_observer, tr
from app.gui.managers import AppLifecycle, SessionManager
from app.gui.styles import set_dark_theme
from app.gui.tabs.brush_tab import BrushTab
from app.gui.tabs.cleaner_export_tab import CleanerExportTab
from app.gui.tabs.config_tab import ConfigTab
from app.gui.tabs.extractor_360_tab import Extractor360Tab
from app.gui.tabs.four_dgs_tab import FourDGSTab
from app.gui.tabs.logs_tab import LogsTab
from app.gui.tabs.params_tab import ParamsTab
from app.gui.tabs.sharp_tab import SharpTab
from app.gui.tabs.splat_transform_tab import SplatTransformTab
from app.gui.tabs.superplat_tab import SuperSplatTab
from app.gui.tabs.upscale_tab import UpscaleTab
from app.gui.workers import (
    BrushWorker,
    ColmapWorker,
    FourDGSWorker,
    PostTrainingWorker,
    SharpVideoWorker,
    SharpWorker,
    SplatTransformWorker,
)


class ColmapGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.brush_worker = None
        self.sharp_worker = None
        self.splat_transform_worker = None
        self.post_training_worker = None
        self._last_brush_output_path = None
        # cleaner_worker est géré par CleanerExportTab
        self.cleaner_export_tab = None  # initialisé dans init_ui

        self.session_manager = SessionManager(self)

        self.init_ui()
        set_dark_theme(QApplication.instance())
        add_language_observer(self.retranslate_ui)
        self.session_manager.load()



    def init_ui(self):
        """Initialise l'interface"""
        self.setWindowTitle(tr("app_title"))
        self.setMinimumSize(900, 600)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.resize(int(geo.width() * 0.88), int(geo.height() * 0.88))
            self.move(geo.topLeft())

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Init Tabs — order: Entraînement, Brush, SuperSplat, ML Sharp,
        #                    4DGS, 360 Extractor, Upscale, Params COLMAP, Logs
        self.config_tab = ConfigTab()
        self.tabs.addTab(self.config_tab, tr("tab_config"))

        self.brush_tab = BrushTab()
        self.tabs.addTab(self.brush_tab, tr("tab_brush"))

        self.superplat_tab = SuperSplatTab()
        self.tabs.addTab(self.superplat_tab, tr("tab_supersplat"))

        self.cleaner_export_tab = CleanerExportTab()
        self.tabs.addTab(self.cleaner_export_tab, tr("tab_cleaner"))

        self.splat_transform_tab = SplatTransformTab()
        self.tabs.addTab(self.splat_transform_tab, tr("tab_splat_transform"))

        self.sharp_tab = SharpTab()
        self.tabs.addTab(self.sharp_tab, tr("tab_sharp"))

        self.four_dgs_tab = FourDGSTab()
        self.tabs.addTab(self.four_dgs_tab, tr("tab_four_dgs"))

        self.extractor_360_tab = Extractor360Tab()
        self.tabs.addTab(self.extractor_360_tab, tr("tab_360"))

        self.upscale_tab = UpscaleTab()
        self.tabs.addTab(self.upscale_tab, tr("tab_upscale"))

        self.params_tab = ParamsTab()
        self.tabs.addTab(self.params_tab, tr("tab_params"))

        self.logs_tab = LogsTab()
        self.tabs.addTab(self.logs_tab, tr("tab_logs"))

        # Discreet Version Label (Status Bar)
        version_label = QLabel(f"v{VERSION}")
        version_label.setStyleSheet("color: #666666; font-size: 10px; padding: 2px;")
        self.statusBar().addPermanentWidget(version_label)
        self.statusBar().setStyleSheet("background-color: transparent;")

        # Connect signals
        self.config_tab.processRequested.connect(self.process)
        self.config_tab.resumeColmapRequested.connect(self.resume_colmap)
        self.config_tab.stopRequested.connect(self.stop_process)
        self.config_tab.deleteDatasetRequested.connect(self.delete_dataset)
        self.config_tab.quitRequested.connect(self.close)
        self.config_tab.relaunchRequested.connect(self.restart_application)
        self.config_tab.resetRequested.connect(self.reset_factory)

        self.brush_tab.trainRequested.connect(self.train_brush)
        self.brush_tab.stopRequested.connect(self.stop_brush)
        self.brush_tab.restartRequested.connect(self.restart_application)



        self.sharp_tab.predictRequested.connect(self.run_sharp)
        self.sharp_tab.stopRequested.connect(self.stop_sharp)

        self.cleaner_export_tab.log_signal.connect(self.logs_tab.append_log)

        self.splat_transform_tab.transformRequested.connect(self.run_splat_transform)
        self.splat_transform_tab.stopRequested.connect(self.stop_splat_transform)

        # Apply visual hierarchy to utility tabs
        self.apply_tab_styling()

    def retranslate_ui(self):
        """Update window title and tab names when language changes"""
        self.setWindowTitle(tr("app_title"))

        # Tabs are identified by index, but we can match them with our members
        tab_names = {
            self.config_tab: tr("tab_config"),
            self.params_tab: tr("tab_params"),
            self.brush_tab: tr("tab_brush"),
            self.superplat_tab: tr("tab_supersplat"),
            self.cleaner_export_tab: tr("tab_cleaner"),
            self.splat_transform_tab: tr("tab_splat_transform"),
            self.upscale_tab: tr("tab_upscale"),
            self.sharp_tab: tr("tab_sharp"),
            self.four_dgs_tab: tr("tab_four_dgs"),
            self.extractor_360_tab: tr("tab_360"),
            self.logs_tab: tr("tab_logs")
        }

        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget in tab_names:
                self.tabs.setTabText(i, tab_names[widget])

        # Re-apply styling (colors etc) as setTabText might reset them in some Qt versions
        self.apply_tab_styling()

    def apply_tab_styling(self):
        """Applies a slightly lighter/muted gray color to secondary/utility tabs"""
        secondary_tabs = [
            self.config_tab,
            self.cleaner_export_tab,
            self.upscale_tab,
            self.sharp_tab,
            self.four_dgs_tab,
            self.extractor_360_tab,
            self.logs_tab
            # splat_transform_tab is primary (white) — same level as Brush/SuperSplat
        ]

        tab_bar = self.tabs.tabBar()
        # Light gray text for secondary/option tabs
        secondary_color = QColor("#aaaaaa")

        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget in secondary_tabs:
                tab_bar.setTabTextColor(i, secondary_color)
            else:
                # Keep main tabs (Params, Brush, SuperSplat) in bright white
                tab_bar.setTabTextColor(i, Qt.GlobalColor.white)

    def get_current_params(self):
        """Récupère les paramètres actuels de l'onglet params et ajoute ceux de config"""
        params = self.params_tab.get_params()
        params.undistort_images = self.config_tab.get_undistort()
        params.filter_blurry = self.config_tab.get_filter_blur()
        params.blur_factor = {"light": 0.5, "medium": 0.7, "strong": 0.9}.get(
            self.config_tab.get_blur_strength(), 0.7
        )
        if self.config_tab.get_robust():
            from app.cli.commands import _apply_robust
            params = _apply_robust(params)
        return params

    def get_upscale_config(self):
        """Combine global upscale settings with the toggle from Config Tab"""
        upscale_params = self.upscale_tab.get_params()
        upscale_params["active"] = self.config_tab.get_upscale()
        # For Sharp worker, it expects 'upscale' key
        upscale_params["upscale"] = upscale_params["active"]
        return upscale_params

    def get_extractor_360_config(self):
        """Combines params from Extractor Tab with current mode"""
        params = self.extractor_360_tab.get_params()
        params["enabled"] = (self.config_tab.get_training_mode() == "360")
        return params

    def process(self):
        """Lance le traitement en fonction du mode sélectionné"""
        input_path = self.config_tab.get_input_path()
        output_path = self.config_tab.get_output_path()

        if not input_path or not output_path:
            QMessageBox.critical(self, tr("msg_error"), tr("err_no_paths"))
            return

        mode = self.config_tab.get_training_mode()
        self.config_tab.set_processing_state(True)
        self.logs_tab.clear_log()

        if mode == "gsplat":
            self.logs_tab.append_log(tr("msg_processing") + " (Gsplat)")
            self.worker = ColmapWorker(
                self.get_current_params(),
                input_path, output_path, self.config_tab.get_input_type(),
                self.config_tab.get_fps(),
                self.config_tab.get_project_name(),
                upscale_params=self.get_upscale_config(),
                extractor_360_params=None # Disabled
            )
            self.worker.log_signal.connect(self.logs_tab.append_log)
            self.worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.worker.status_signal.connect(self.config_tab.lbl_status.setText)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()

        elif mode == "sharp":
            self.logs_tab.append_log(tr("msg_processing") + " (ML Sharp)")
            sharp_params = self.sharp_tab.get_params()

            # Retrieve upscale settings but keep the 'upscale' checkbox value from sharp_tab!
            sharp_upscale_checked = sharp_params.get("upscale", False)
            sharp_params.update(self.get_upscale_config())
            sharp_params["upscale"] = sharp_upscale_checked

            input_type = self.config_tab.get_input_type()
            if input_type == "video":
                sharp_params["mode"] = "video"
                if hasattr(self.config_tab, "spin_sharp_skip"):
                    sharp_params["skip_frames"] = self.config_tab.spin_sharp_skip.value()
                self.sharp_worker = SharpVideoWorker(input_path, output_path, sharp_params)
            else:
                sharp_params["mode"] = "image"
                self.sharp_worker = SharpWorker(input_path, output_path, sharp_params)

            self.sharp_worker.log_signal.connect(self.logs_tab.append_log)
            self.sharp_worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.sharp_worker.status_signal.connect(self.config_tab.lbl_status.setText)
            self.sharp_worker.finished_signal.connect(self.on_sharp_finished)
            self.sharp_worker.start()

        elif mode == "360":
            self.logs_tab.append_log(tr("msg_processing") + " (360 Extractor)")
            ext_params = self.extractor_360_tab.get_params()
            ext_params["enabled"] = True

            self.worker = ColmapWorker(
                self.get_current_params(),
                input_path, output_path, "video",
                self.config_tab.get_fps(),
                self.config_tab.get_project_name(),
                upscale_params=self.get_upscale_config(),
                extractor_360_params=ext_params
            )
            self.worker.log_signal.connect(self.logs_tab.append_log)
            self.worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.worker.status_signal.connect(self.config_tab.lbl_status.setText)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()

        elif mode == "4dgs":
            self.logs_tab.append_log(tr("msg_processing") + " (4DGS)")
            self.fourdgs_worker = FourDGSWorker(input_path, output_path, self.config_tab.get_fps())
            self.fourdgs_worker.log_signal.connect(self.logs_tab.append_log)
            self.fourdgs_worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.fourdgs_worker.status_signal.connect(self.config_tab.lbl_status.setText)
            self.fourdgs_worker.finished_signal.connect(self.on_finished)
            self.fourdgs_worker.start()

    def resume_colmap(self):
        """Relance COLMAP en réutilisant les images déjà extraites (saute extraction/upscale).

        Écrase la reconstruction COLMAP précédente. Enchaîne l'entraînement Brush
        si la case 'auto-brush' est cochée (via on_finished).
        """
        output_path = self.config_tab.get_output_path()
        project_name = self.config_tab.get_project_name()

        if not output_path:
            QMessageBox.critical(self, tr("msg_error"), tr("err_no_paths"))
            return

        images_dir = Path(output_path) / project_name / "images"
        if not images_dir.exists() or not any(images_dir.iterdir()):
            QMessageBox.warning(
                self, tr("msg_warning"),
                tr("err_resume_no_images",
                   "Reprise impossible : aucune image trouvée dans le dossier du projet. Lancez d'abord l'extraction.")
            )
            return

        self.config_tab.set_processing_state(True)
        self.logs_tab.clear_log()
        self.logs_tab.append_log(tr("msg_resume_colmap", "--- Reprise COLMAP (réutilisation des images) ---"))

        # On pointe l'entrée sur les images déjà extraites : aucune extraction ni upscale.
        self.worker = ColmapWorker(
            self.get_current_params(),
            str(images_dir), output_path, "images",
            self.config_tab.get_fps(),
            project_name,
            upscale_params=None,
            extractor_360_params=None,
        )
        self.worker.engine.resume_colmap = True
        self.worker.log_signal.connect(self.logs_tab.append_log)
        self.worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
        self.worker.status_signal.connect(self.config_tab.lbl_status.setText)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_process(self):
        """Arrête le processus en cours"""
        if (self.worker and self.worker.isRunning()) or \
           (self.sharp_worker and self.sharp_worker.isRunning()) or \
           (hasattr(self, 'fourdgs_worker') and self.fourdgs_worker and self.fourdgs_worker.isRunning()):

            reply = QMessageBox.question(
                self, tr("msg_warning"), tr("confirm_stop"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.logs_tab.append_log(tr("msg_stopping"))
                if self.worker and self.worker.isRunning():
                    self.worker.stop()
                if self.sharp_worker and self.sharp_worker.isRunning():
                    self.sharp_worker.stop()
                if hasattr(self, 'fourdgs_worker') and self.fourdgs_worker and self.fourdgs_worker.isRunning():
                    self.fourdgs_worker.stop()

    def on_finished(self, success, message):
        """Fin du traitement"""
        self.config_tab.set_processing_state(False)

        if success:
            self.logs_tab.append_log(tr("msg_success"))
            if self.config_tab.get_auto_brush():
                self.logs_tab.append_log(tr("msg_brush_start", ""))
                self.train_brush(force_auto=True)
            else:
                QMessageBox.information(self, tr("msg_success"),
                                        f"{message}\n\n{tr('success_open_brush')}")
        else:
            # on_finished est branché sur plusieurs workers (COLMAP, 4DGS) : il faut
            # vérifier stopped_by_user sur l'émetteur réel du signal, pas sur
            # self.worker qui peut être obsolète/None en mode 4DGS.
            sender = self.sender()
            if not (sender and getattr(sender, 'stopped_by_user', False)):
                QMessageBox.warning(self, tr("msg_error"), f"{tr('msg_error')}:\n{message}")

    def delete_dataset(self):
        """Supprime le contenu d'un dataset existant"""
        output_dir_str = self.config_tab.get_output_path()
        project_name = self.config_tab.get_project_name()

        if not output_dir_str:
            QMessageBox.warning(self, tr("msg_warning"), tr("err_no_paths"))
            return

        output_dir = Path(output_dir_str)
        # 1. Target: output_dir/project_name
        target_path = output_dir / project_name

        # 2. Fallback: output_dir (if user pointed directly to it)
        # We check if it looks like a dataset
        if not target_path.exists() and (
            (output_dir / "database.db").exists() or (output_dir / "sparse").exists()
        ):
            target_path = output_dir

        if not target_path.exists():
            QMessageBox.information(self, "Info", tr("err_path_not_exists"))
            return

        # Double check safety: ensure we are deleting a dataset
        has_dataset = (
            (target_path / "database.db").exists() or
            (target_path / "sparse").exists() or
            (target_path / "images").exists()
        )

        if not has_dataset:
            reply = QMessageBox.question(
                self, tr("msg_warning"),
                tr("confirm_delete_nodata", str(target_path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
        else:
            reply = QMessageBox.question(
                self, tr("msg_warning"),
                tr("confirm_delete_dataset", str(target_path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                success, msg = ColmapEngine.delete_project_content(target_path)
                if success:
                    self.logs_tab.append_log(f"Dataset deleted: {target_path}")
                    QMessageBox.information(self, tr("msg_success"), msg)
                else:
                    QMessageBox.critical(self, tr("msg_error"), f"Erreur: {msg}")
            except Exception as e:
                QMessageBox.critical(self, tr("msg_error"), f"Impossible de supprimer le dataset:\n{str(e)}")

    def train_brush(self, force_auto=False):
        """Lance l'entrainement Brush"""
        brush_params = self.brush_tab.get_params()
        project_name = self.config_tab.get_project_name()
        keep_only_latest = False

        if not force_auto and brush_params.get("independent"):
            # Mode Indépendant
            input_path_str = brush_params.get("input_path")

            if not input_path_str:
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier Dataset valide.")
                 return

            input_path = Path(input_path_str)
            if not input_path.exists():
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier Dataset valide.")
                 return

            # Use custom output path if provided, otherwise default to input/checkpoints
            output_path_str = brush_params.get("output_path", "").strip()
            output_path = Path(output_path_str) if output_path_str else input_path / "checkpoints"
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(
                    self, tr("msg_error"),
                    f"Impossible de créer le dossier de sortie :\n{output_path}\n\n"
                    f"Vérifiez que le disque est bien connecté.\n({e})"
                )
                return
            self._last_brush_output_path = output_path

        else:
            # Mode Automatique (via Colmap output)
            colmap_out_root_str = self.config_tab.get_output_path()

            if not colmap_out_root_str:
                 QMessageBox.critical(self, tr("msg_error"), "Le dossier de sortie racine n'existe pas.")
                 return

            colmap_out_root = Path(colmap_out_root_str)
            if not colmap_out_root.exists():
                 QMessageBox.critical(self, tr("msg_error"), "Le dossier de sortie racine n'existe pas.")
                 return

            # Le dataset est dans root/project_name
            dataset_path = colmap_out_root / project_name

            if not dataset_path.exists():
                QMessageBox.critical(self, tr("msg_error"), f"Le dossier du projet n'existe pas:\n{dataset_path}\nAvez-vous lancé la création du dataset ?")
                return

            input_path = dataset_path

            # Destination personnalisée des checkpoints (optionnel)
            ckpt_dest = self.config_tab.get_checkpoint_dest().strip()
            if ckpt_dest:
                output_path = Path(ckpt_dest) / project_name
                keep_only_latest = True
            else:
                output_path = dataset_path / "checkpoints"
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                QMessageBox.critical(
                    self, tr("msg_error"),
                    f"Impossible de créer le dossier de sortie :\n{output_path}\n\n"
                    f"Vérifiez que le disque est bien connecté.\n({e})"
                )
                return
            self._last_brush_output_path = output_path

        self.brush_tab.set_processing_state(True)
        self.logs_tab.append_log(tr("msg_brush_start", str(input_path)))
        self.logs_tab.append_log(tr("msg_brush_out", str(output_path)))

        self.brush_worker = BrushWorker(
            input_path,
            output_path,
            brush_params,
            project_name=project_name,
            keep_only_latest=keep_only_latest,
        )

        self.brush_worker.log_signal.connect(self.logs_tab.append_log)
        self.brush_worker.finished_signal.connect(self.on_brush_finished)

        self.brush_worker.start()

        # Focus logs tab
        self.tabs.setCurrentWidget(self.logs_tab)

    def stop_brush(self):
        """Arrête Brush"""
        if hasattr(self, 'brush_worker') and self.brush_worker and self.brush_worker.isRunning():
            self.brush_worker.stop()
            self.logs_tab.append_log("Arrêt de Brush demandé...")

    def on_brush_finished(self, success, message):
        """Fin entrainement Brush — enchaîne le post-traitement si activé."""
        self.brush_tab.set_processing_state(False)
        self.logs_tab.append_log(message)

        if success:
            do_clean = self.config_tab.get_post_clean()
            do_export = self.config_tab.get_post_export()

            if (do_clean or do_export) and self._last_brush_output_path:
                self._run_post_training(
                    self._last_brush_output_path,
                    do_clean,
                    self.config_tab.get_post_clean_strength(),
                    do_export,
                    self.config_tab.get_post_export_format(),
                )
            else:
                self._show_training_done_dialog(self._last_brush_output_path)
        else:
            if not (self.brush_worker and self.brush_worker.stopped_by_user):
                QMessageBox.warning(self, tr("brush_error_title"), tr("brush_error_body"))

    def _run_post_training(self, output_path, clean, strength, export, fmt):
        self.brush_tab.set_processing_state(True)
        self.logs_tab.append_log(
            f"Post-traitement : {'nettoyage' if clean else ''}"
            f"{' + ' if clean and export else ''}"
            f"{'export ' + fmt.upper() if export else ''} …"
        )
        self.post_training_worker = PostTrainingWorker(
            str(output_path), clean, strength, export, fmt
        )
        self.post_training_worker.log_signal.connect(self.logs_tab.append_log)
        self.post_training_worker.finished_signal.connect(self._on_post_training_finished)
        self.post_training_worker.start()

    def _on_post_training_finished(self, success, message):
        self.brush_tab.set_processing_state(False)
        self.logs_tab.append_log(message)
        if success:
            self._show_training_done_dialog(self._last_brush_output_path)
        else:
            QMessageBox.warning(self, tr("msg_error"), message)

    def _show_training_done_dialog(self, output_path):
        """Affiche la fin d'entrainement avec un raccourci pour ouvrir le splat dans SuperSplat."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr("brush_done_title"))
        box.setText(tr("brush_done_body"))
        btn_open = box.addButton(tr("btn_open_splat", "Ouvrir le splat"), QMessageBox.ButtonRole.ActionRole)
        btn_ok = box.addButton(QMessageBox.StandardButton.Ok)
        box.setDefaultButton(btn_ok)
        box.exec()
        if box.clickedButton() == btn_open:
            self._open_latest_splat(output_path)

    def _open_latest_splat(self, output_path):
        """Ouvre le dernier checkpoint .ply du dossier d'entrainement dans SuperSplat."""
        if not output_path:
            return
        ply_files = [p for p in Path(output_path).rglob("*.ply") if not p.name.startswith('.')]
        if not ply_files:
            QMessageBox.warning(self, tr("msg_warning"), tr("msg_no_ply_found", "Aucun fichier .ply trouvé dans le dossier de sortie."))
            return
        latest_ply = max(ply_files, key=lambda p: p.stat().st_mtime)
        self.superplat_tab.input_path.setText(str(latest_ply))
        self.tabs.setCurrentWidget(self.superplat_tab)
        self.superplat_tab.start_server()



    def run_sharp(self):
        """Lance Sharp"""
        params = self.sharp_tab.get_params()

        # Merge upscale settings for run_sharp as well
        sharp_upscale_checked = params.get("upscale", False)
        params.update(self.upscale_tab.get_params())
        params["upscale"] = sharp_upscale_checked

        mode = params.get("mode", "image")

        self.sharp_tab.set_processing_state(True)
        self.logs_tab.append_log(f"--- Lancement Apple ML Sharp (Mode: {mode}) ---")

        if mode == "image":
            input_path_str = params.get("input_path")
            output_path_str = params.get("output_path")

            if not input_path_str:
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier d'images valide.")
                 self.sharp_tab.set_processing_state(False)
                 return

            input_path = Path(input_path_str)
            if not input_path.exists():
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier d'images valide.")
                 self.sharp_tab.set_processing_state(False)
                 return

            if not output_path_str:
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier de sortie.")
                 self.sharp_tab.set_processing_state(False)
                 return

            output_path = Path(output_path_str)

            self.logs_tab.append_log(f"Input: {input_path}")
            self.logs_tab.append_log(f"Output: {output_path}")

            self.sharp_worker = SharpWorker(str(input_path), str(output_path), params)

        else: # video
            video_path_str = params.get("video_path")
            output_path_str = params.get("video_output_path")

            if not video_path_str:
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un fichier video.")
                 self.sharp_tab.set_processing_state(False)
                 return

            video_path = Path(video_path_str)
            if not video_path.exists():
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un fichier video existant.")
                 self.sharp_tab.set_processing_state(False)
                 return

            if not output_path_str:
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier de sortie.")
                 self.sharp_tab.set_processing_state(False)
                 return

            output_path = Path(output_path_str)

            self.logs_tab.append_log(f"Video Input: {video_path}")
            self.logs_tab.append_log(f"Output: {output_path}")

            self.sharp_worker = SharpVideoWorker(str(video_path), str(output_path), params)

        self.sharp_worker.log_signal.connect(self.logs_tab.append_log)
        if hasattr(self.sharp_worker, "progress_signal"):
            self.sharp_worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.sharp_worker.progress_signal.connect(self.sharp_tab.progress_bar.setValue)
        if hasattr(self.sharp_worker, "status_signal"):
            self.sharp_worker.status_signal.connect(self.config_tab.lbl_status.setText)
        self.sharp_worker.finished_signal.connect(self.on_sharp_finished)
        self.sharp_worker.start()

        self.tabs.setCurrentWidget(self.logs_tab)

    def stop_sharp(self):
        """Arrête Sharp"""
        if self.sharp_worker and self.sharp_worker.isRunning():
            self.sharp_worker.stop()
            self.logs_tab.append_log("Arrêt de Sharp demandé...")

    def on_sharp_finished(self, success, message):
        """Fin Sharp"""
        self.sharp_tab.set_processing_state(False)
        self.config_tab.set_processing_state(False)
        self.logs_tab.append_log(message)

        if success:
            QMessageBox.information(self, tr("sharp_done_title"), tr("sharp_done_body"))
        else:
            QMessageBox.warning(self, tr("sharp_error_title"), tr("sharp_error_body"))



    def run_splat_transform(self, input_path: str, output_path: str, params: dict):
        """Launch a splat-transform conversion in a background thread."""
        self.splat_transform_tab.set_processing_state(True)
        self.logs_tab.append_log(f"--- SplatTransform: {input_path} → {output_path} ---")

        self.splat_transform_worker = SplatTransformWorker(input_path, output_path, params)
        self.splat_transform_worker.log_signal.connect(self.logs_tab.append_log)
        self.splat_transform_worker.finished_signal.connect(self._on_splat_transform_finished)
        self.splat_transform_worker.start()
        self.tabs.setCurrentWidget(self.logs_tab)

    def stop_splat_transform(self):
        if self.splat_transform_worker and self.splat_transform_worker.isRunning():
            self.splat_transform_worker.stop()
            self.logs_tab.append_log("SplatTransform stop requested...")

    def _on_splat_transform_finished(self, success: bool, message: str):
        self.splat_transform_tab.set_processing_state(False)
        self.logs_tab.append_log(message)
        if not success and not (
            self.splat_transform_worker and self.splat_transform_worker.stopped_by_user
        ):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, tr("msg_error"), message)

    def restart_application(self):
        """Redémarre l'application."""
        AppLifecycle.restart(save_callback=lambda: self.session_manager.save(immediate=True))

    def reset_factory(self, deep=False):
        """Supprime les venvs et relance l'installation/application."""
        AppLifecycle.reset_factory(deep)

    # --- Session Persistence Externalisée ---
    # Gérée par SessionManager

    def closeEvent(self, event):
        """Appelé à la fermeture de la fenêtre"""
        self.session_manager.save(immediate=True)
        event.accept()

