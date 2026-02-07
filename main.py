#!/usr/bin/env python3
import sys
import argparse
import time
import signal
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.core.i18n import tr
from app.core.params import ColmapParams
from app.core.engine import ColmapEngine
from app.core.brush_engine import BrushEngine
from app.core.sharp_engine import SharpEngine
from app.core.superplat_engine import SuperSplatEngine
from app.core.system import check_dependencies
from app.gui.main_window import ColmapGUI

def get_parser():
    """Configure and return the argument parser"""
    parser = argparse.ArgumentParser(description=tr("cli_desc"))
    
    # GUI Mode
    parser.add_argument('--gui', action='store_true', help=tr("cli_gui_help"))
    
    # Operation Modes
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--train', action='store_true', help=tr("cli_train_help"))
    group.add_argument('--predict', action='store_true', help=tr("cli_predict_help"))
    group.add_argument('--view', action='store_true', help=tr("cli_view_help"))
    
    # Common Arguments
    parser.add_argument('--input', '-i', help=tr("cli_input_help"))
    parser.add_argument('--output', '-o', help=tr("cli_output_help"))
    
    # --- COLMAP Arguments ---
    colmap_group = parser.add_argument_group('COLMAP Options')
    colmap_group.add_argument('--type', choices=['images', 'video'], default='images', help=tr("cli_type_help"))
    colmap_group.add_argument('--fps', type=int, default=5, help=tr("cli_fps_help"))
    colmap_group.add_argument('--camera_model', default='SIMPLE_RADIAL', help=tr("cli_cam_help"))
    colmap_group.add_argument('--undistort', action='store_true', help=tr("cli_undistort_help"))
    
    # --- BRUSH Arguments ---
    brush_group = parser.add_argument_group('BRUSH Options')
    brush_group.add_argument('--iterations', type=int, default=30000, help=tr("cli_iter_help"))
    brush_group.add_argument('--sh_degree', type=int, default=3, help=tr("cli_sh_degree_help"))
    brush_group.add_argument('--device', default="auto", help=tr("brush_tip_device"))
    
    # --- SHARP Arguments ---
    sharp_group = parser.add_argument_group('SHARP Options')
    sharp_group.add_argument('--checkpoint', help=tr("cli_checkpoint_help"))
    
    # --- SUPERSPLAT Arguments ---
    splat_group = parser.add_argument_group('SUPERSPLAT Options')
    splat_group.add_argument('--port', type=int, default=3000, help=tr("cli_port_help"))
    splat_group.add_argument('--data_port', type=int, default=8000, help=tr("cli_data_port_help"))
    
    return parser

def run_colmap(args):
    """Exécution Pipeline COLMAP"""
    if not args.input or not args.output:
        print(tr("cli_err_colmap_args"))
        sys.exit(1)
        
    params = ColmapParams(
        camera_model=args.camera_model,
        undistort_images=args.undistort
    )
    
    print(tr("cli_start_colmap"))
    print(tr("cli_input", args.input))
    print(tr("cli_output", args.output))
    
    engine = ColmapEngine(
        params, args.input, args.output, args.type, args.fps,
        logger_callback=print,
        progress_callback=lambda x: print(tr("cli_progression", x))
    )
    
    success, msg = engine.run()
    if success:
        print(tr("cli_success", msg))
    else:
        print(tr("cli_error", msg))
        sys.exit(1)

def run_brush(args):
    """Exécution Training BRUSH"""
    if not args.input or not args.output:
        print(tr("cli_err_brush_args"))
        sys.exit(1)
        
    engine = BrushEngine()
    print(tr("cli_start_brush"))
    print(tr("cli_input", args.input))
    print(tr("cli_output", args.output))
    
    params = {
        "total_steps": args.iterations,
        "sh_degree": args.sh_degree,
        "device": args.device
    }
    
    process = engine.train(args.input, args.output, params=params)
    
    try:
        process.wait()
        if process.returncode == 0:
            print(tr("msg_success"))
        else:
            print(tr("msg_error"))
            sys.exit(1)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()

def run_sharp(args):
    """Exécution Prediction SHARP"""
    if not args.input or not args.output:
        print(tr("cli_err_sharp_args"))
        sys.exit(1)
        
    engine = SharpEngine()
    print(tr("cli_start_sharp"))
    
    params = {
        "checkpoint": args.checkpoint,
        "device": args.device if args.device != "auto" else "default",
        "verbose": True
    }
    
    process = engine.predict(args.input, args.output, params=params)
    
    try:
        process.wait()
        if process.returncode == 0:
            print(tr("msg_success"))
        else:
            print(tr("msg_error"))
            sys.exit(1)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()

def run_supersplat(args):
    """Exécution Viewer SUPERSPLAT"""
    if not args.input:
        print(tr("cli_err_view_args"))
        sys.exit(1)
        
    engine = SuperSplatEngine()
    print(tr("cli_start_view"))
    
    # Démarrer Data Server
    import os
    if os.path.isfile(args.input):
        data_dir = os.path.dirname(args.input)
        filename = os.path.basename(args.input)
    else:
        data_dir = args.input
        filename = ""
        
    ok, msg = engine.start_data_server(data_dir, port=args.data_port)
    if not ok:
        print(f"{tr('msg_error')}: {msg}")
        sys.exit(1)
    print(msg)
    
    ok, msg = engine.start_supersplat(port=args.port)
    if not ok:
        print(f"{tr('msg_error')}: {msg}")
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
        print(tr("cli_server_stop"))
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
