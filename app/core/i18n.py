import json
import os
import locale

TRANSLATIONS = {
    "fr": {
        # Tabs
        "tab_config": "Configuration",
        "tab_params": "Parametres COLMAP",
        "tab_logs": "Logs",
        
        # Header
        # RULE: Increment by 0.01 on every modification
        "app_title": "CorbeauSplat",
        
        # Config Tab - Inputs
        "group_input": "Donnees d'entree",
        "label_type": "Type :",
        "radio_images": "Images",
        "radio_video": "Video",
        "label_path": "Dossier/Fichier :",
        "btn_browse": "Parcourir",
        "label_fps": "FPS extraction video :",
        
        # Config Tab - Outputs
        "group_output": "Sortie",
        "label_out_path": "Dossier de sortie :",
        "btn_delete": "Supprimer Dataset Existant",
        "check_undistort": "Generer images non-distordues (pour dense reconstruction)",
        
        # Config Tab - Actions
        "btn_process": "Creer Dataset COLMAP",
        "btn_stop": "Arreter",
        "btn_save_cfg": "Sauvegarder Config",
        "btn_load_cfg": "Charger Config",
        "btn_open_brush": "Ouvrir dans Brush",
        "btn_quit": "Quitter",
        "btn_relaunch": "Relancer",
        
        # Params Tab
        "info_cpu": "Apple Silicon detecte - {} threads optimises",
        "group_extract": "Feature Extraction",
        "lbl_camera_model": "Modele camera :",
        "check_single_cam": "Camera unique :",
        "lbl_max_img": "Taille max image :",
        "lbl_max_feat": "Features max :",
        "check_force_cpu": "Forcer CPU :",
        "check_affine": "Affine shape :",
        "check_domain": "Domain pooling :",
        
        "group_match": "Feature Matching",
        "lbl_match_type": "Type de matching :",
        "lbl_max_ratio": "Max ratio :",
        "lbl_max_dist": "Max distance :",
        "check_cross": "Cross check :",
        "check_guided": "Guided matching (non supporte) :",
        
        "group_mapper": "Reconstruction (Mapper)",
        "lbl_min_model": "Min model size :",
        "check_multi_model": "Multiple models :",
        "check_focal": "Refine focal :",
        "check_principal": "Refine principal :",
        "check_extra": "Refine extra :",
        "lbl_min_match": "Min matches :",
        "check_use_glomap": "Utiliser Glomap (Experimental)",
        "lbl_glomap": "GLOMAP :",
        
        # Brush Tab
        "tab_brush": "Brush",
        "brush_detected": "Moteur Brush detecte : {}",
        "brush_not_found": "Attention : Executable 'brush' non trouve dans engines/ ou PATH",
        "brush_params": "Parametres d'entrainement",
        "brush_iterations": "Iterations :",
        "brush_args": "Arguments suppl. :",
        "brush_viewer": "Activer le visualiseur pendant l'entrainement",
        "btn_train_brush": "Lancer Entrainement Brush",
        "check_auto_brush": "Lancer entrainement Brush automatiquement",
        "msg_brush_start": "Lancement Brush sur : {}",
        "msg_brush_out": "Sortie Brush : {}",
        "check_brush_independent": "Mode Manuel / Independant",
        "brush_group_paths": "Chemins (Mode Manuel)",
        "brush_lbl_input": "Dossier Dataset (sparse+images) :",
        "brush_lbl_output": "Dossier Export :",
        "brush_lbl_ply": "Nom du fichier PLY (optionnel) :",
        "brush_lbl_res": "Résolution Maximum :",
        "brush_res_warn": "0 = résolution par défaut (1080)",
        "brush_res_default": "0",
        
        # Brush Densification
        "brush_group_densify": "Densification & Avancé",
        "brush_lbl_preset": "Preset :",
        "brush_preset_default": "Par défaut",
        "brush_preset_fast": "Test Rapide (15k)",
        "brush_preset_std": "Standard (30k)",
        "brush_preset_dense": "Densification Agressive",
        "brush_init_ply": "Fichier Init PLY :",
        "brush_btn_init_ply": "Choisir .ply...",
        "brush_lbl_mode": "Mode d'entraînement :",
        "brush_mode_new": "Nouvel Entraînement (De zéro)",
        "brush_mode_refine": "Raffiner / Continuer (Auto)",
        "brush_check_refine": "Refine depuis dernier checkpoint (Auto)", # Consider deprecating
        "brush_lbl_steps": "Steps Total :",
        "brush_lbl_start": "Start Iter :",
        "brush_lbl_refine": "Refine Every :",
        "brush_lbl_threshold": "Growth Threshold :",
        "brush_lbl_fraction": "Growth Fraction :",
        "brush_lbl_stop": "Growth Stop Iter :",
        "brush_lbl_max_splats": "Max Splats :",

        # SuperSplat Tab
        "tab_supersplat": "SuperSplat",
        "superplat_info": "SuperSplat est un outil web developpe par PlayCanvas pour editer et visualiser les Gaussian Splats.\nCe module lance un serveur local.",
        "group_server_config": "Configuration Serveur",
        "lbl_splat_port": "Port SuperSplat :",
        "lbl_data_port": "Port Donnees :",
        "group_data": "Donnees a Visualiser",
        "placeholder_ply": "Chemin vers un fichier .ply ou dossier",
        "group_url_options": "Options de Vue",
        "check_no_ui": "Masquer l'interface (No UI)",
        "lbl_cam_pos": "Position Camera :",
        "lbl_cam_rot": "Rotation Camera :",
        "btn_start_server": "Demarrer Serveurs",
        "btn_stop_server": "Arreter Serveurs",
        "btn_open_browser": "Ouvrir Navigateur",
        "status_running": "Statut : En cours d'execution",
        "status_stopped": "Statut : Arrete",
        "select_ply": "Selectionner fichier PLY",

        # Logs Tab
        "btn_clear_log": "Effacer logs",
        "btn_save_log": "Sauvegarder logs",
        
        # Messages / Dialogs
        "msg_ready": "Pret",
        "msg_processing": "Traitement en cours...",
        "msg_stopping": "Arret en cours...",
        "msg_success": "Succes",
        "msg_error": "Erreur",
        "msg_warning": "Attention",
        "confirm_stop": "Voulez-vous vraiment arreter le processus en cours ?",
        "confirm_delete": "Voulez-vous vraiment supprimer le dataset ?\n\n{}\n\nCette action est irreversible!",
        "confirm_delete_nodata": "Le dossier ne semble pas contenir de dataset COLMAP.\nVoulez-vous quand meme le supprimer ?\n\n{}",
        "err_no_paths": "Veuillez selectionner les dossiers d'entree et de sortie",
        "err_path_not_exists": "Le dossier n'existe pas encore",
        "success_created": "Dataset cree : {}",
        "success_open_brush": "Vous pouvez maintenant l'ouvrir dans Brush!",
        "lang_restart": "Changement de langue : Le redemarrage de l'application est necessaire.",
        "lang_change": "Langue",
    },
    "en": {
        # Tabs
        "tab_config": "Configuration",
        "tab_params": "COLMAP Parameters",
        "tab_logs": "Logs",
        
        # Header
        "app_title": "CorbeauSplat",
        
        # Config Tab - Inputs
        "group_input": "Input Data",
        "label_type": "Type:",
        "radio_images": "Images",
        "radio_video": "Video",
        "label_path": "Folder/File:",
        "btn_browse": "Browse",
        "label_fps": "Video extraction FPS:",
        
        # Config Tab - Outputs
        "group_output": "Output",
        "label_out_path": "Output Folder:",
        "btn_delete": "Delete Existing Dataset",
        "check_undistort": "Generate undistorted images (for dense reconstruction)",
        
        # Config Tab - Actions
        "btn_process": "Create COLMAP Dataset",
        "btn_stop": "Stop",
        "btn_save_cfg": "Save Config",
        "btn_load_cfg": "Load Config",
        "btn_open_brush": "Open in Brush",
        "btn_quit": "Quit",
        "btn_relaunch": "Relaunch",
        
        # Params Tab
        "info_cpu": "Apple Silicon detected - {} threads optimized",
        "group_extract": "Feature Extraction",
        "lbl_camera_model": "Camera Model:",
        "check_single_cam": "Single Camera:",
        "lbl_max_img": "Max Image Size:",
        "lbl_max_feat": "Max Features:",
        "check_force_cpu": "Force CPU:",
        "check_affine": "Affine Shape:",
        "check_domain": "Domain Pooling:",
        
        "group_match": "Feature Matching",
        "lbl_match_type": "Matching Type:",
        "lbl_max_ratio": "Max Ratio:",
        "lbl_max_dist": "Max Distance:",
        "check_cross": "Cross Check:",
        "check_guided": "Guided Matching (unsupported):",
        
        "group_mapper": "Reconstruction (Mapper)",
        "lbl_min_model": "Min Model Size:",
        "check_multi_model": "Multiple Models:",
        "check_focal": "Refine Focal:",
        "check_principal": "Refine Principal:",
        "check_extra": "Refine Extra:",
        "lbl_min_match": "Min Matches:",
        "check_use_glomap": "Use Glomap (Experimental)",
        "lbl_glomap": "GLOMAP:",
        
        # Brush Tab
        "tab_brush": "Brush",
        "brush_detected": "Brush engine detected: {}",
        "brush_not_found": "Warning: 'brush' executable not found in engines/ or PATH",
        "brush_params": "Training parameters",
        "brush_iterations": "Iterations:",
        "brush_args": "Extra args:",
        "brush_viewer": "Enable visualizer during training",
        "btn_train_brush": "Start Brush Training",
        "check_auto_brush": "Auto-start Brush training",
        "msg_brush_start": "Starting Brush on: {}",
        "msg_brush_out": "Brush Output: {}",
        "check_brush_independent": "Manual / Independent Mode",
        "brush_group_paths": "Paths (Manual Mode)",
        "brush_lbl_input": "Dataset Folder (sparse+images):",
        "brush_lbl_output": "Export Folder:",
        "brush_lbl_ply": "PLY Filename (optional):",
        "brush_sh_degree": "SH Degree:",
        "brush_device": "Device:",
        "brush_lbl_res": "Max Resolution:",
        "brush_res_warn": "0 = default resolution (1080)",
        "brush_res_default": "0",
        
        # Brush Densification
        "brush_group_densify": "Densification & Advanced",
        "brush_lbl_preset": "Preset:",
        "brush_preset_default": "Default",
        "brush_preset_fast": "Quick Test (15k)",
        "brush_preset_std": "Standard (30k)",
        "brush_preset_dense": "Aggressive Densification",
        "brush_init_ply": "Init PLY File:",
        "brush_btn_init_ply": "Choose .ply...",
        "brush_lbl_mode": "Training Mode:",
        "brush_mode_new": "Start New Training (From Scratch)",
        "brush_mode_refine": "Refine / Continue (Auto)",
        "brush_check_refine": "Refine from latest checkpoint (Auto)",
        "brush_check_details": "Show Advanced Details",
        "brush_lbl_steps": "Total Steps:",
        "brush_lbl_start": "Start Iter:",
        "brush_lbl_refine": "Refine Every:",
        "brush_lbl_threshold": "Growth Threshold:",
        "brush_lbl_fraction": "Growth Fraction:",
        "brush_lbl_stop": "Growth Stop Iter:",
        "brush_lbl_max_splats": "Max Splats:",
        
        # SuperSplat Tab
        "tab_supersplat": "SuperSplat",
        "superplat_info": "SuperSplat is a web tool developed by PlayCanvas to edit and visualize Gaussian Splats.\nThis module launches a local server.",
        "group_server_config": "Server Config",
        "lbl_splat_port": "SuperSplat Port:",
        "lbl_data_port": "Data Port:",
        "group_data": "Data to Visualize",
        "placeholder_ply": "Path to .ply file or folder",
        "group_url_options": "View Options",
        "check_no_ui": "Hide UI (No UI)",
        "lbl_cam_pos": "Camera Position:",
        "lbl_cam_rot": "Camera Rotation:",
        "btn_start_server": "Start Servers",
        "btn_stop_server": "Stop Servers",
        "btn_open_browser": "Open Browser",
        "status_running": "Status: Running",
        "status_stopped": "Status: Stopped",
        "select_ply": "Select PLY File",

        # Logs Tab
        "btn_clear_log": "Clear Logs",
        "btn_save_log": "Save Logs",
        
        # Messages / Dialogs
        "msg_ready": "Ready",
        "msg_processing": "Processing...",
        "msg_stopping": "Stopping...",
        "msg_success": "Success",
        "msg_error": "Error",
        "msg_warning": "Warning",
        "confirm_stop": "Do you really want to stop the current process?",
        "confirm_delete": "Do you really want to delete the dataset?\n\n{}\n\nThis action is irreversible!",
        "confirm_delete_nodata": "The folder does not seem to contain a COLMAP dataset.\nDo you want to delete it anyway?\n\n{}",
        "err_no_paths": "Please select input and output folders",
        "err_path_not_exists": "Folder does not exist yet",
        "success_created": "Dataset created: {}",
        "success_open_brush": "You can now open it in Brush!",
        "lang_restart": "Language change: Application restart is required.",
        "lang_change": "Language",
    }
}

class LanguageManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageManager, cls).__new__(cls)
            cls._instance.current_lang = "fr" # Default
            cls._instance.load_config()
        return cls._instance
    
    def load_config(self):
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    config = json.load(f)
                    self.current_lang = config.get("language", "fr")
            else:
                # Auto-detect? For now default to FR as per request history implies French user
                pass
        except:
            pass
            
    def save_config(self):
        try:
            config = {}
            if os.path.exists("config.json"):
                with open("config.json", "r") as f:
                    config = json.load(f)
            
            config["language"] = self.current_lang
            
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
        except:
            pass

    def set_language(self, lang_code):
        if lang_code in TRANSLATIONS:
            self.current_lang = lang_code
            self.save_config()

    def tr(self, key, *args):
        lang_dict = TRANSLATIONS.get(self.current_lang, TRANSLATIONS["fr"])
        text = lang_dict.get(key, key)
        if args:
            try:
                text = text.format(*args)
            except:
                pass
        return text

# Global instance convenience
_lm = LanguageManager()

def tr(key, *args):
    return _lm.tr(key, *args)

def get_current_lang():
    return _lm.current_lang

def set_language(lang_code):
    _lm.set_language(lang_code)
