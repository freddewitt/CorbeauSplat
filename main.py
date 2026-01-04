#!/usr/bin/env python3
import sys
import argparse
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.core.params import ColmapParams
from app.core.engine import ColmapEngine
from app.core.system import check_dependencies
from app.gui.main_window import ColmapGUI

def get_parser():
    """Configure et retourne le parseur d'arguments"""
    parser = argparse.ArgumentParser(description="CorbeauSplat v0.1 - COLMAP Dataset Creator")
    
    # Mode GUI
    parser.add_argument('--gui', action='store_true', help="Lancer l'interface graphique")
    
    # Arguments CLI (optionnels dans le parser car non requis pour le GUI)
    parser.add_argument('--input', help="Chemin vers le dossier d'images ou le fichier vidéo (Requis pour CLI)")
    parser.add_argument('--output', help="Dossier de sortie (Requis pour CLI)")
    
    # Arguments optionnels CLI
    parser.add_argument('--type', choices=['images', 'video'], default='images', help="Type d'entrée (défaut: images)")
    parser.add_argument('--fps', type=int, default=5, help="FPS pour l'extraction vidéo (défaut: 5)")
    
    # Paramètres COLMAP
    parser.add_argument('--camera_model', default='SIMPLE_RADIAL', help="Modèle de caméra (défaut: SIMPLE_RADIAL)")
    parser.add_argument('--single_camera', action='store_true', help="Caméra unique (défaut: False)")
    parser.add_argument('--matcher', choices=['exhaustive', 'sequential', 'vocab_tree'], default='exhaustive', help="Type de matching (défaut: exhaustive)")
    parser.add_argument('--undistort', action='store_true', help="Générer des images non-distordues")
    parser.add_argument('--min_matches', type=int, default=15, help="Nombre minimum de matches (défaut: 15)")
    
    return parser

def run_batch(args):
    """Exécution en mode CLI (Batch)"""
    # Configuration
    params = ColmapParams(
        camera_model=args.camera_model,
        single_camera=args.single_camera,
        matcher_type=args.matcher,
        undistort_images=args.undistort,
        min_num_matches=args.min_matches
    )
    
    print(f"Démarrage en mode CLI...")
    print(f"Entrée: {args.input}")
    print(f"Sortie: {args.output}")
    
    engine = ColmapEngine(
        params, args.input, args.output, args.type, args.fps,
        logger_callback=print,
        progress_callback=lambda x: print(f"Progression: {x}%")
    )
    
    success, msg = engine.run()
    
    if success:
        print(f"\nSUCCÈS: {msg}")
        sys.exit(0)
    else:
        print(f"\nERREUR: {msg}")
        sys.exit(1)

def main():
    parser = get_parser()
    args = parser.parse_args()
    
    # Vérification des dépendances commune
    missing_deps = check_dependencies()
    if missing_deps:
        msg = f"Erreur: Dépendances manquantes: {', '.join(missing_deps)}\nVeuillez les installer (ex: brew install ffmpeg colmap)"
        if args.gui:
            # On essaie d'afficher une popup si possible, sinon print
            try:
                app = QApplication(sys.argv)
                QMessageBox.critical(None, "Dépendances manquantes", msg)
            except:
                print(msg)
        else:
            print(msg)
        sys.exit(1)

    # Mode GUI
    if args.gui:
        app = QApplication(sys.argv)
        # Style set in ColmapGUI init or here
        window = ColmapGUI()
        window.show()
        sys.exit(app.exec())
        
    # Mode CLI
    elif args.input and args.output:
        run_batch(args)
        
    # Aucun mode
    else:
        # Default to GUI if no args provided? 
        # The original behavior was print help if no args.
        # But usually double clicking script launches GUI.
        # Let's check sys.argv len.
        if len(sys.argv) == 1:
            # Launch GUI by default if no args
            app = QApplication(sys.argv)
            window = ColmapGUI()
            window.show()
            sys.exit(app.exec())
        else:
            parser.print_help()
            sys.exit(0)

if __name__ == "__main__":
    main()
