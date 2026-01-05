#!/usr/bin/env python3
import sys
import argparse
import time
import signal
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.core.params import ColmapParams
from app.core.engine import ColmapEngine
from app.core.brush_engine import BrushEngine
from app.core.sharp_engine import SharpEngine
from app.core.superplat_engine import SuperSplatEngine
from app.core.system import check_dependencies
from app.gui.main_window import ColmapGUI

def get_parser():
    """Configure et retourne le parseur d'arguments"""
    parser = argparse.ArgumentParser(description="CorbeauSplat v0.16 - CLI & GUI Toolkit")
    
    # Mode GUI
    parser.add_argument('--gui', action='store_true', help="Lancer l'interface graphique (Défaut si aucun argument)")
    
    # Modes d'opérations (Mutuellement exclusifs)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--train', action='store_true', help="Mode BRUSH: Entraîner un splat")
    group.add_argument('--predict', action='store_true', help="Mode SHARP: Prédire un splat (Image -> 3D)")
    group.add_argument('--view', action='store_true', help="Mode SUPERSPLAT: Visualiser un fichier PLY")
    
    # Arguments Communs
    parser.add_argument('--input', '-i', help="Fichier/Dossier d'entrée")
    parser.add_argument('--output', '-o', help="Fichier/Dossier de sortie")
    
    # --- Arguments COLMAP ---
    colmap_group = parser.add_argument_group('Options COLMAP')
    colmap_group.add_argument('--type', choices=['images', 'video'], default='images', help="Type d'entrée")
    colmap_group.add_argument('--fps', type=int, default=5, help="FPS extraction vidéo")
    colmap_group.add_argument('--camera_model', default='SIMPLE_RADIAL', help="Modèle caméra")
    colmap_group.add_argument('--undistort', action='store_true', help="Active l'undistortion")
    
    # --- Arguments BRUSH ---
    brush_group = parser.add_argument_group('Options BRUSH')
    brush_group.add_argument('--iterations', type=int, default=30000, help="Nombre d'itérations")
    brush_group.add_argument('--sh_degree', type=int, default=3, help="Harmoniques Sphériques")
    brush_group.add_argument('--device', default="auto", help="Device (auto, mps, cpu...)")
    
    # --- Arguments SHARP ---
    sharp_group = parser.add_argument_group('Options SHARP')
    sharp_group.add_argument('--checkpoint', help="Chemin vers un checkpoint (.pt)")
    
    # --- Arguments SUPERSPLAT ---
    splat_group = parser.add_argument_group('Options SUPERSPLAT')
    splat_group.add_argument('--port', type=int, default=3000, help="Port du serveur web")
    splat_group.add_argument('--data_port', type=int, default=8000, help="Port du serveur de données")
    
    return parser

def run_colmap(args):
    """Exécution Pipeline COLMAP"""
    if not args.input or not args.output:
        print("Erreur: --input et --output sont requis pour COLMAP.")
        sys.exit(1)
        
    params = ColmapParams(
        camera_model=args.camera_model,
        undistort_images=args.undistort
    )
    
    print(f"--- Démarrage COLMAP ---")
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
    else:
        print(f"\nERREUR: {msg}")
        sys.exit(1)

def run_brush(args):
    """Exécution Training BRUSH"""
    if not args.input or not args.output:
        print("Erreur: --input (dossier colmap) et --output (dossier destination) sont requis pour BRUSH.")
        sys.exit(1)
        
    engine = BrushEngine()
    print(f"--- Démarrage BRUSH Training ---")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    
    process = engine.train(
        args.input, args.output,
        iterations=args.iterations,
        sh_degree=args.sh_degree,
        device=args.device
    )
    
    try:
        process.wait()
        if process.returncode == 0:
            print("Entraînement terminé avec succès.")
        else:
            print("Erreur durant l'entraînement.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nArrêt demandé...")
        engine.stop()

def run_sharp(args):
    """Exécution Prediction SHARP"""
    if not args.input or not args.output:
        print("Erreur: --input (image) et --output (dossier) sont requis pour SHARP.")
        sys.exit(1)
        
    engine = SharpEngine()
    print(f"--- Démarrage SHARP Prediction ---")
    
    process = engine.predict(
        args.input, args.output,
        checkpoint=args.checkpoint,
        device=args.device if args.device != "auto" else "default",
        verbose=True
    )
    
    try:
        process.wait()
        if process.returncode == 0:
            print("Prédiction terminée avec succès.")
        else:
            print("Erreur durant la prédiction.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nArrêt demandé...")
        engine.stop()

def run_supersplat(args):
    """Exécution Viewer SUPERSPLAT"""
    if not args.input:
        print("Erreur: --input (fichier .ply ou dossier) est requis pour SUPERSPLAT.")
        sys.exit(1)
        
    engine = SuperSplatEngine()
    print(f"--- Démarrage SUPERSPLAT ---")
    
    # Démarrer Data Server
    # Si input est fichier
    import os
    if os.path.isfile(args.input):
        data_dir = os.path.dirname(args.input)
        filename = os.path.basename(args.input)
    else:
        data_dir = args.input
        filename = ""
        
    ok, msg = engine.start_data_server(data_dir, port=args.data_port)
    if not ok:
        print(f"Erreur Data Server: {msg}")
        sys.exit(1)
    print(msg)
    
    ok, msg = engine.start_supersplat(port=args.port)
    if not ok:
        print(f"Erreur SuperSplat: {msg}")
        engine.stop_all()
        sys.exit(1)
    print(msg)
    
    # URL construction logic duplicated from Tab for convenience
    url = f"http://localhost:{args.port}?url=http://localhost:{args.data_port}/{filename}"
    print(f"\nAccédez à : {url}\n")
    print("Appuyez sur Ctrl+C pour arrêter les serveurs.")
    
    try:
        # Keep alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt des serveurs...")
        engine.stop_all()

def main():
    parser = get_parser()
    args = parser.parse_args()
    
    # Vérification dépendances (sauf si juste --help implicite)
    # On le fait au début
    missing_deps = check_dependencies()
    if missing_deps:
        msg = f"Attention: Dépendances manquantes: {', '.join(missing_deps)}\nCertaines fonctions peuvent échouer."
        print(msg)

    # Dispatch logic
    if args.gui:
        app = QApplication(sys.argv)
        window = ColmapGUI()
        window.show()
        sys.exit(app.exec())
        
    elif args.train:
        run_brush(args)
        
    elif args.predict:
        run_sharp(args)
        
    elif args.view:
        run_supersplat(args)
        
    elif args.input and args.output:
        # Default behavior: COLMAP processing
        run_colmap(args)
        
    else:
        # Si aucun argument, lancer GUI par défaut (comportement utilisateur classique double-clic)
        if len(sys.argv) == 1:
            app = QApplication(sys.argv)
            window = ColmapGUI()
            window.show()
            sys.exit(app.exec())
        else:
            parser.print_help()
            sys.exit(0)

if __name__ == "__main__":
    main()
