#!/usr/bin/env python3
import sys
import argparse
import time
import shutil
import subprocess
import signal
from pathlib import Path as _Path

# ─────────────────────────────────────────────────────────────────────────────
# GUI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _set_macos_dock_icon(icon_path: _Path):
    try:
        from AppKit import NSApplication, NSImage
        ns_image = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
        if ns_image:
            NSApplication.sharedApplication().setApplicationIconImage_(ns_image)
    except Exception:
        pass


def _launch_gui():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from PyQt6.QtCore import QTimer

    app = QApplication(sys.argv)

    assets = _Path(__file__).parent / "assets"
    png_path  = assets / "icon.png"
    icns_path = assets / "icon.icns"
    icon_file = png_path if png_path.exists() else icns_path
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    dock_src = icns_path if icns_path.exists() else png_path
    if dock_src.exists():
        QTimer.singleShot(0, lambda: _set_macos_dock_icon(dock_src))

    window = ColmapGUI()
    window.show()
    sys.exit(app.exec())


# ─────────────────────────────────────────────────────────────────────────────
# Imports (after GUI guard so headless runs don't pull Qt)
# ─────────────────────────────────────────────────────────────────────────────

from app.core.i18n import tr
from app.core.params import ColmapParams
from app.core.engine import ColmapEngine
from app.core.brush_engine import BrushEngine
from app.core.sharp_engine import SharpEngine
from app.core.superplat_engine import SuperSplatEngine
from app.core.system import check_dependencies
from app.gui.main_window import ColmapGUI

# ─────────────────────────────────────────────────────────────────────────────
# Brush defaults and presets
# ─────────────────────────────────────────────────────────────────────────────

BRUSH_DEFAULTS = {
    "total_steps": 30000,
    "sh_degree": 3,
    "start_iter": 0,
    "refine_every": 200,
    "growth_grad_threshold": 0.003,
    "growth_select_fraction": 0.2,
    "growth_stop_iter": 15000,
    "max_splats": 10_000_000,
    "checkpoint_interval": 7000,
    "max_resolution": 0,
    "with_viewer": False,
    "refine_mode": False,
}

BRUSH_PRESETS = {
    "fast": {
        "total_steps": 7000, "refine_every": 100,
        "growth_grad_threshold": 0.01, "growth_select_fraction": 0.2,
        "growth_stop_iter": 6000,
    },
    "std": {
        "total_steps": 30000, "refine_every": 200,
        "growth_grad_threshold": 0.003, "growth_select_fraction": 0.2,
        "growth_stop_iter": 15000,
    },
    "dense": {
        "total_steps": 50000, "refine_every": 100,
        "growth_grad_threshold": 0.0005, "growth_select_fraction": 0.6,
        "growth_stop_iter": 40000,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────────────────────

def get_parser():
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="CorbeauSplat — Pipeline Gaussian Splatting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Sans argument, l'interface graphique est lancée.\n"
            "Chaque sous-commande a sa propre aide : main.py <commande> --help\n\n"
            "Exemples :\n"
            "  python3 main.py pipeline -i video.mp4 -o ~/projets --type video --preset dense\n"
            "  python3 main.py colmap   -i video.mp4 -o ~/projets\n"
            "  python3 main.py brush    -i ~/projets/scene -o ~/projets/scene --preset dense\n"
            "  python3 main.py sharp    -i photo.jpg -o ~/out\n"
            "  python3 main.py view     -i splat.ply\n"
            "  python3 main.py upscale  -i image.png -o ~/out --scale 4\n"
            "  python3 main.py 4dgs     -i ~/videos -o ~/out\n"
            "  python3 main.py extract360 -i 360.mp4 -o ~/out\n"
        ),
    )
    parser.add_argument("--gui", action="store_true", help="Force le lancement de l'interface graphique")

    subs = parser.add_subparsers(dest="command", metavar="COMMANDE")

    # ── pipeline ──────────────────────────────────────────────────────────────
    p = subs.add_parser(
        "pipeline",
        help="Pipeline complet : COLMAP → Brush en une seule commande",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  # Depuis une vidéo\n"
            "  python3 main.py pipeline -i video.mp4 -o ~/projets --type video\n\n"
            "  # Depuis des photos, preset haute qualité\n"
            "  python3 main.py pipeline -i ~/photos -o ~/projets --preset dense\n\n"
            "  # Avec Glomap et un nom de projet\n"
            "  python3 main.py pipeline -i ~/photos -o ~/projets --project_name scene --use_glomap\n"
        ),
    )
    p.add_argument("--input",  "-i", required=True, help="Vidéo ou dossier d'images source")
    p.add_argument("--output", "-o", required=True, help="Dossier de sortie parent")
    p.add_argument("--project_name", default="Untitled", help="Nom du sous-dossier projet (défaut: Untitled)")
    # COLMAP
    p.add_argument("--type", choices=["images", "video"], default="images",
                   help="Type d'entrée (défaut: images)")
    p.add_argument("--fps",  type=int, default=5,   help="FPS d'extraction vidéo (défaut: 5)")
    p.add_argument("--camera_model", default="SIMPLE_RADIAL",
                   choices=["SIMPLE_PINHOLE","PINHOLE","SIMPLE_RADIAL","RADIAL","OPENCV","OPENCV_FISHEYE"],
                   help="Modèle de caméra COLMAP (défaut: SIMPLE_RADIAL)")
    p.add_argument("--undistort",  action="store_true", help="Undistortion après reconstruction")
    p.add_argument("--use_glomap", action="store_true", help="Utiliser Glomap au lieu du mapper COLMAP")
    p.add_argument("--matcher_type", choices=["exhaustive","sequential","vocab_tree"], default="exhaustive",
                   help="Stratégie de matching (défaut: exhaustive)")
    p.add_argument("--max_image_size", type=int, default=3200,
                   help="Résolution max des images pour COLMAP (défaut: 3200)")
    # Brush
    p.add_argument("--preset", choices=["default","fast","std","dense"], default="default",
                   help="Preset d'entraînement Brush (défaut: default)")
    p.add_argument("--iterations", type=int,   default=None, metavar="N",
                   help="Nb total d'itérations Brush (remplace le preset)")
    p.add_argument("--sh_degree",  type=int,   default=None, choices=range(1,5),
                   help="Degré Spherical Harmonics 1-4 (défaut: 3)")
    p.add_argument("--device", default="auto",
                   choices=["auto","mps","cuda","cpu"], help="Device Brush (défaut: auto)")
    p.add_argument("--with_viewer", action="store_true", help="Ouvrir le viewer interactif après entraînement")
    p.add_argument("--ply_name",    default=None,        help="Nom du fichier PLY de sortie")

    # ── colmap ────────────────────────────────────────────────────────────────
    p = subs.add_parser("colmap", help="Pipeline COLMAP (vidéo/images → dataset)")
    p.add_argument("--input",  "-i", required=True, help="Vidéo ou dossier d'images source")
    p.add_argument("--output", "-o", required=True, help="Dossier de sortie")
    p.add_argument("--type", choices=["images", "video"], default="images", help="Type d'entrée (défaut: images)")
    p.add_argument("--fps",  type=int, default=5,         help="FPS d'extraction vidéo (défaut: 5)")
    p.add_argument("--project_name", default="Untitled",  help="Nom du sous-dossier projet")
    # Options de base
    p.add_argument("--camera_model", default="SIMPLE_RADIAL",
                   choices=["SIMPLE_PINHOLE","PINHOLE","SIMPLE_RADIAL","RADIAL","OPENCV","OPENCV_FISHEYE"],
                   help="Modèle de caméra COLMAP (défaut: SIMPLE_RADIAL)")
    p.add_argument("--undistort",  action="store_true", help="Undistortion après reconstruction")
    p.add_argument("--use_glomap", action="store_true", help="Utiliser Glomap au lieu du mapper COLMAP")
    # Feature extraction
    p.add_argument("--no_single_camera",  action="store_true", help="Désactiver le mode caméra unique")
    p.add_argument("--max_image_size",    type=int,   default=3200, help="Résolution max des images (défaut: 3200)")
    p.add_argument("--max_num_features",  type=int,   default=8192, help="Nb max de features par image (défaut: 8192)")
    p.add_argument("--estimate_affine_shape", action="store_true", help="Estimer la forme affine des features")
    p.add_argument("--no_domain_size_pooling", action="store_true", help="Désactiver le domain size pooling")
    # Feature matching
    p.add_argument("--matcher_type", choices=["exhaustive","sequential","vocab_tree"], default="exhaustive",
                   help="Stratégie de matching (défaut: exhaustive)")
    p.add_argument("--max_ratio",    type=float, default=0.8,  help="Ratio max Lowe (défaut: 0.8)")
    p.add_argument("--max_distance", type=float, default=0.7,  help="Distance max (défaut: 0.7)")
    p.add_argument("--no_cross_check", action="store_true", help="Désactiver le cross-check")
    # Mapper
    p.add_argument("--min_model_size",    type=int, default=10, help="Taille min du modèle (défaut: 10)")
    p.add_argument("--min_num_matches",   type=int, default=15, help="Nb min de matches (défaut: 15)")
    p.add_argument("--multiple_models",   action="store_true",  help="Autoriser plusieurs modèles")
    p.add_argument("--no_refine_focal",   action="store_true",  help="Ne pas affiner la focale")
    p.add_argument("--refine_principal",  action="store_true",  help="Affiner le point principal")
    p.add_argument("--no_refine_extra",   action="store_true",  help="Ne pas affiner les params extra")

    # ── brush ─────────────────────────────────────────────────────────────────
    p = subs.add_parser("brush", help="Entraînement Gaussian Splat (Brush)")
    p.add_argument("--input",  "-i", required=True, help="Dossier dataset COLMAP")
    p.add_argument("--output", "-o", required=True, help="Dossier de sortie")
    p.add_argument("--preset", choices=["default","fast","std","dense"], default="default",
                   help="Preset de paramètres (défaut: default)")
    p.add_argument("--iterations", type=int,   default=None, metavar="N",
                   help="Nb total d'itérations (défaut preset: 30000)")
    p.add_argument("--sh_degree",  type=int,   default=None, choices=range(1,5),
                   help="Degré Spherical Harmonics 1-4 (défaut: 3)")
    p.add_argument("--device",     default="auto",
                   choices=["auto","mps","cuda","cpu"], help="Device (défaut: auto)")
    p.add_argument("--refine_mode", action="store_true", help="Mode Refine (reprend depuis dernier checkpoint)")
    p.add_argument("--with_viewer", action="store_true", help="Ouvrir le viewer interactif")
    p.add_argument("--ply_name",   default=None,      help="Nom du fichier PLY de sortie")
    p.add_argument("--custom_args", default=None,     help="Arguments supplémentaires passés à brush")
    # Paramètres avancés (None = utilise la valeur du preset ou du défaut)
    p.add_argument("--start_iter",              type=int,   default=None, help="Itération de départ (défaut: 0)")
    p.add_argument("--refine_every",            type=int,   default=None, help="Densification toutes les N iters (défaut: 200)")
    p.add_argument("--growth_grad_threshold",   type=float, default=None, help="Seuil gradient densification (défaut: 0.003)")
    p.add_argument("--growth_select_fraction",  type=float, default=None, help="Fraction sélection densification (défaut: 0.2)")
    p.add_argument("--growth_stop_iter",        type=int,   default=None, help="Arrêt de la densification (défaut: 15000)")
    p.add_argument("--max_splats",              type=int,   default=None, help="Nb max de gaussiennes (défaut: 10 000 000)")
    p.add_argument("--checkpoint_interval",     type=int,   default=None, help="Sauvegarder tous les N iters (défaut: 7000)")
    p.add_argument("--max_resolution",          type=int,   default=None, help="Résolution max entraînement 0=auto (défaut: 0)")

    # ── sharp ─────────────────────────────────────────────────────────────────
    p = subs.add_parser("sharp", help="Single Image/Vidéo → 3D Splat (ML-Sharp)")
    p.add_argument("--input",  "-i", required=True, help="Image, dossier d'images ou vidéo")
    p.add_argument("--output", "-o", required=True, help="Dossier de sortie")
    p.add_argument("--mode",   choices=["image","video"], default="image",
                   help="Mode : image unique ou vidéo (défaut: image)")
    p.add_argument("--checkpoint", "-c", default=None, help="Chemin vers un checkpoint .pt")
    p.add_argument("--device", default="default",
                   choices=["default","mps","cpu","cuda"], help="Device (défaut: default)")
    p.add_argument("--skip_frames", type=int, default=1,
                   help="[mode vidéo] Traiter 1 frame sur N (défaut: 1)")
    p.add_argument("--upscale", action="store_true",
                   help="Upscaler les images avant prédiction (requiert upscayl-bin)")
    p.add_argument("--verbose", action="store_true", help="Afficher la sortie détaillée de Sharp")

    # ── view ──────────────────────────────────────────────────────────────────
    p = subs.add_parser("view", help="Visualiser un .ply dans SuperSplat")
    p.add_argument("--input",     "-i", required=True, help="Fichier .ply ou dossier")
    p.add_argument("--port",      type=int, default=3000, help="Port SuperSplat (défaut: 3000)")
    p.add_argument("--data_port", type=int, default=8000, help="Port serveur données (défaut: 8000)")
    p.add_argument("--no_ui",     action="store_true", help="Masquer l'interface SuperSplat")
    p.add_argument("--cam_pos",   default=None, metavar="X,Y,Z", help="Position initiale caméra")
    p.add_argument("--cam_rot",   default=None, metavar="X,Y,Z", help="Rotation initiale caméra (degrés)")

    # ── upscale ───────────────────────────────────────────────────────────────
    p = subs.add_parser("upscale", help="Upscale d'images via upscayl-bin (NCNN)")
    p.add_argument("--input",  "-i", required=True, help="Image ou dossier d'images")
    p.add_argument("--output", "-o", required=True, help="Dossier de sortie")
    p.add_argument("--model",  default="realesrgan-x4plus",
                   help="ID du modèle upscayl (défaut: realesrgan-x4plus)")
    p.add_argument("--scale",  type=int, choices=[2, 3, 4], default=4,
                   help="Facteur d'upscale (défaut: 4)")
    p.add_argument("--format", choices=["png","jpg","webp"], default="png",
                   help="Format de sortie (défaut: png)")
    p.add_argument("--tile",        type=int, default=0,
                   help="Taille des tuiles VRAM en px, 0=auto (défaut: 0)")
    p.add_argument("--tta",         action="store_true", help="Activer le Test-Time Augmentation")
    p.add_argument("--compression", type=int, default=0,
                   help="Niveau de compression sortie 0-9 (défaut: 0)")

    # ── 4dgs ──────────────────────────────────────────────────────────────────
    p = subs.add_parser("4dgs", help="Préparation dataset 4D Gaussian Splatting (Nerfstudio)")
    p.add_argument("--input",  "-i", required=True,
                   help="Dossier contenant les vidéos multi-caméras")
    p.add_argument("--output", "-o", required=True, help="Dossier de sortie")
    p.add_argument("--fps",    type=int, default=5,  help="FPS d'extraction vidéo (défaut: 5)")
    p.add_argument("--colmap_only", action="store_true",
                   help="Lancer uniquement COLMAP sur un dataset déjà extrait")

    # ── extract360 ────────────────────────────────────────────────────────────
    p = subs.add_parser("extract360", help="Extraction vidéo 360° en multi-caméras COLMAP-ready")
    p.add_argument("--input",  "-i", required=True, help="Fichier vidéo 360°")
    p.add_argument("--output", "-o", required=True, help="Dossier de sortie")
    p.add_argument("--interval",        type=float, default=1.0,
                   help="Intervalle entre frames en secondes (défaut: 1.0)")
    p.add_argument("--format",          default="jpg",
                   help="Format image de sortie (défaut: jpg)")
    p.add_argument("--resolution",      type=int,   default=2048,
                   help="Résolution des images extraites (défaut: 2048)")
    p.add_argument("--camera_count",    type=int,   default=6,
                   help="Nombre de caméras virtuelles (défaut: 6)")
    p.add_argument("--quality",         type=int,   default=95,
                   help="Qualité JPEG 0-100 (défaut: 95)")
    p.add_argument("--layout",          default="equirectangular",
                   help="Layout de projection (défaut: equirectangular)")
    p.add_argument("--ai_mask",         action="store_true", help="Activer le masquage IA")
    p.add_argument("--ai_skip",         action="store_true", help="Activer le saut IA")
    p.add_argument("--adaptive",        action="store_true", help="Extraction adaptative au mouvement")
    p.add_argument("--motion_threshold", type=float, default=0.3,
                   help="Seuil de mouvement pour l'extraction adaptative (défaut: 0.3)")

    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Run functions
# ─────────────────────────────────────────────────────────────────────────────

def run_colmap(args):
    params = ColmapParams(
        camera_model=args.camera_model,
        single_camera=not args.no_single_camera,
        max_image_size=args.max_image_size,
        max_num_features=args.max_num_features,
        estimate_affine_shape=args.estimate_affine_shape,
        domain_size_pooling=not args.no_domain_size_pooling,
        max_ratio=args.max_ratio,
        max_distance=args.max_distance,
        cross_check=not args.no_cross_check,
        min_model_size=args.min_model_size,
        multiple_models=args.multiple_models,
        ba_refine_focal_length=not args.no_refine_focal,
        ba_refine_principal_point=args.refine_principal,
        ba_refine_extra_params=not args.no_refine_extra,
        min_num_matches=args.min_num_matches,
        matcher_type=args.matcher_type,
        undistort_images=args.undistort,
        use_glomap=args.use_glomap,
    )

    print(tr("cli_start_colmap"))
    print(tr("cli_input", args.input))
    print(tr("cli_output", args.output))

    engine = ColmapEngine(
        params, args.input, args.output, args.type, args.fps,
        project_name=args.project_name,
        logger_callback=print,
        progress_callback=lambda x: print(tr("cli_progression", x)),
    )

    success, msg = engine.run()
    if success:
        print(tr("cli_success", msg))
    else:
        print(tr("cli_error", msg))
        sys.exit(1)


def run_brush(args):
    params = dict(BRUSH_DEFAULTS)

    if args.preset != "default":
        params.update(BRUSH_PRESETS[args.preset])

    # Explicit args override preset (only when provided by user)
    if args.iterations is not None:           params["total_steps"] = args.iterations
    if args.sh_degree is not None:            params["sh_degree"] = args.sh_degree
    if args.start_iter is not None:           params["start_iter"] = args.start_iter
    if args.refine_every is not None:         params["refine_every"] = args.refine_every
    if args.growth_grad_threshold is not None: params["growth_grad_threshold"] = args.growth_grad_threshold
    if args.growth_select_fraction is not None: params["growth_select_fraction"] = args.growth_select_fraction
    if args.growth_stop_iter is not None:     params["growth_stop_iter"] = args.growth_stop_iter
    if args.max_splats is not None:           params["max_splats"] = args.max_splats
    if args.checkpoint_interval is not None:  params["checkpoint_interval"] = args.checkpoint_interval
    if args.max_resolution is not None:       params["max_resolution"] = args.max_resolution

    params["device"] = args.device
    params["refine_mode"] = args.refine_mode
    params["with_viewer"] = args.with_viewer
    if args.custom_args: params["custom_args"] = args.custom_args
    if args.ply_name:    params["ply_name"] = args.ply_name

    print(tr("cli_start_brush"))
    print(tr("cli_input", args.input))
    print(tr("cli_output", args.output))
    print(f"  Preset     : {args.preset}")
    print(f"  Steps      : {params['total_steps']}")
    print(f"  SH degree  : {params['sh_degree']}")
    print(f"  Device     : {params['device']}")

    engine = BrushEngine(logger_callback=print)

    try:
        returncode = engine.train(args.input, args.output, params=params)
        if returncode == 0:
            print(tr("msg_success"))
        else:
            print(tr("msg_error"))
            sys.exit(1)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()


def run_sharp(args):
    engine = SharpEngine(logger_callback=print)

    params = {
        "checkpoint": args.checkpoint,
        "device": args.device,
        "verbose": args.verbose,
    }

    if args.mode == "image":
        print(tr("cli_start_sharp"))
        print(tr("cli_input", args.input))
        print(tr("cli_output", args.output))

        try:
            returncode = engine.predict(args.input, args.output, params=params)
            if returncode == 0:
                print(tr("msg_success"))
            else:
                print(tr("msg_error"))
                sys.exit(1)
        except KeyboardInterrupt:
            print(tr("cli_stopping"))
            engine.stop()

    else:  # video mode
        _run_sharp_video(args, engine, params)


def _run_sharp_video(args, engine, params):
    import tempfile

    video_path = _Path(args.input)
    output_dir = _Path(args.output)
    skip = max(1, args.skip_frames)

    print(f"Sharp vidéo : {video_path.name} (1 frame / {skip})")
    print(tr("cli_output", args.output))

    frames_dir = output_dir / "temp_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Extraire les frames
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg_bin, "-y", "-i", str(video_path),
        "-vf", f"select=not(mod(n\\,{skip}))",
        "-vsync", "vfr", "-q:v", "1",
        str(frames_dir / "frame_%04d.png"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Erreur FFmpeg : {result.stderr}")
        sys.exit(1)

    frames = sorted(frames_dir.glob("*.png"))
    total = len(frames)
    if total == 0:
        print("Aucune frame extraite.")
        sys.exit(1)

    print(f"{total} frames extraites.")
    success_count = 0

    try:
        for idx, frame_path in enumerate(frames, 1):
            print(f"  Frame {idx}/{total}: {frame_path.name}")
            frame_out = output_dir / frame_path.stem
            returncode = engine.predict(str(frame_path), str(frame_out), params)
            if returncode == 0:
                ply_files = list(frame_out.rglob("*.ply"))
                if ply_files:
                    shutil.copy2(ply_files[0], output_dir / f"{frame_path.stem}.ply")
                    success_count += 1
            if frame_out.exists():
                shutil.rmtree(frame_out)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
    finally:
        if frames_dir.exists():
            shutil.rmtree(frames_dir)

    print(f"Terminé : {success_count}/{total} frames converties.")
    if success_count == 0:
        sys.exit(1)


def run_supersplat(args):
    engine = SuperSplatEngine()

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

    # Build URL with optional params
    url = f"http://localhost:{args.port}"
    url_params = []
    if filename:
        data_url = f"http://localhost:{args.data_port}/{filename}"
        url_params.append(f"load={data_url}")
    if args.no_ui:
        url_params.append("noui")
    if args.cam_pos:
        url_params.append(f"cameraPosition={args.cam_pos.strip()}")
    if args.cam_rot:
        url_params.append(f"cameraRotation={args.cam_rot.strip()}")
    if url_params:
        url += "?" + "&".join(url_params)

    print(f"\nAccédez à : {url}\n")
    print("Appuyez sur Ctrl+C pour arrêter les serveurs.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(tr("cli_server_stop"))
        engine.stop_all()


def run_upscale(args):
    from app.core.upscale_engine import UpscaleEngine

    engine = UpscaleEngine(logger_callback=print)

    if not engine.is_installed():
        print("Erreur : upscayl-bin introuvable. Installez-le depuis l'onglet Upscale de l'interface graphique.")
        sys.exit(1)

    upsampler = engine.load_model(
        model_id=args.model,
        scale=args.scale,
        output_format=args.format,
        tile=args.tile,
        tta=args.tta,
        compression=args.compression,
    )
    if not upsampler:
        print("Erreur : impossible de charger le modèle.")
        sys.exit(1)

    import os
    input_path = _Path(args.input)
    output_path = _Path(args.output)

    print(f"Upscale x{args.scale} — modèle : {args.model}")
    print(f"  Input  : {args.input}")
    print(f"  Output : {args.output}")

    try:
        if input_path.is_dir():
            success, msg = engine.upscale_folder(
                str(input_path), str(output_path),
                cancel_check=None, **upsampler,
            )
        else:
            success = engine.upscale_image(str(input_path), str(output_path / input_path.name), upsampler)
            msg = "Upscale terminé." if success else "Upscale échoué."
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        sys.exit(0)

    print(f"{'Succès' if success else 'Erreur'} : {msg}")
    if not success:
        sys.exit(1)


def run_4dgs(args):
    from app.core.four_dgs_engine import FourDGSEngine

    engine = FourDGSEngine(logger_callback=print)

    if not args.colmap_only and not _Path(args.input).exists():
        print(f"Erreur : dossier source introuvable : {args.input}")
        sys.exit(1)

    print("Préparation dataset 4DGS")
    print(f"  Input  : {args.input}")
    print(f"  Output : {args.output}")

    try:
        if args.colmap_only:
            print("Mode COLMAP uniquement.")
            success = engine.run_colmap(args.output)
        else:
            print(f"  FPS    : {args.fps}")
            success = engine.process_dataset(args.input, args.output, fps=args.fps)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(0)

    print("Terminé avec succès." if success else "Erreur lors du traitement.")
    if not success:
        sys.exit(1)


def run_extract360(args):
    from app.core.extractor_360_engine import Extractor360Engine

    engine = Extractor360Engine(logger_callback=print)

    if not engine.is_installed():
        print("Erreur : Extracteur 360° non installé. Activez-le depuis l'onglet 360° de l'interface graphique.")
        sys.exit(1)

    params = {
        "interval":         args.interval,
        "format":           args.format,
        "resolution":       args.resolution,
        "camera_count":     args.camera_count,
        "quality":          args.quality,
        "layout":           args.layout,
        "ai_mask":          args.ai_mask,
        "ai_skip":          args.ai_skip,
        "adaptive":         args.adaptive,
        "motion_threshold": args.motion_threshold,
    }

    print("Extraction vidéo 360°")
    print(f"  Input       : {args.input}")
    print(f"  Output      : {args.output}")
    print(f"  Interval    : {args.interval}s")
    print(f"  Résolution  : {args.resolution}px")
    print(f"  Caméras     : {args.camera_count}")

    try:
        success = engine.run_extraction(
            args.input, args.output, params,
            log_callback=print,
            progress_callback=lambda x: print(f"  Progression : {x}%"),
        )
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        engine.stop()
        sys.exit(0)

    print("Terminé avec succès." if success else "Erreur lors de l'extraction.")
    if not success:
        sys.exit(1)


def run_pipeline(args):
    """Pipeline complet COLMAP → Brush."""

    _sep = lambda title: print(f"\n{'─' * 50}\n  {title}\n{'─' * 50}")

    # ── Étape 1 : COLMAP ──────────────────────────────────────────────────────
    _sep("Étape 1/2 — Reconstruction COLMAP")
    print(f"  Input       : {args.input}")
    print(f"  Output      : {args.output}")
    print(f"  Projet      : {args.project_name}")
    print(f"  Type        : {args.type}")
    if args.type == "video":
        print(f"  FPS         : {args.fps}")

    colmap_params = ColmapParams(
        camera_model=args.camera_model,
        matcher_type=args.matcher_type,
        max_image_size=args.max_image_size,
        undistort_images=args.undistort,
        use_glomap=args.use_glomap,
    )

    colmap_engine = ColmapEngine(
        colmap_params, args.input, args.output, args.type, args.fps,
        project_name=args.project_name,
        logger_callback=print,
        progress_callback=lambda x: print(f"  Progression : {x}%"),
    )

    try:
        success, msg = colmap_engine.run()
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        colmap_engine.stop()
        sys.exit(0)

    if not success:
        print(f"\nErreur COLMAP : {msg}")
        sys.exit(1)

    dataset_path = _Path(args.output) / args.project_name
    print(f"\nDataset prêt : {dataset_path}")

    # ── Étape 2 : Brush ───────────────────────────────────────────────────────
    _sep("Étape 2/2 — Entraînement Brush")

    brush_params = dict(BRUSH_DEFAULTS)

    if args.preset != "default":
        brush_params.update(BRUSH_PRESETS[args.preset])

    if args.iterations is not None: brush_params["total_steps"] = args.iterations
    if args.sh_degree is not None:  brush_params["sh_degree"] = args.sh_degree
    brush_params["device"] = args.device
    brush_params["with_viewer"] = args.with_viewer
    if args.ply_name: brush_params["ply_name"] = args.ply_name

    print(f"  Dataset     : {dataset_path}")
    print(f"  Preset      : {args.preset}")
    print(f"  Steps       : {brush_params['total_steps']}")
    print(f"  SH degree   : {brush_params['sh_degree']}")
    print(f"  Device      : {brush_params['device']}")

    brush_engine = BrushEngine(logger_callback=print)

    try:
        returncode = brush_engine.train(str(dataset_path), str(dataset_path), params=brush_params)
    except KeyboardInterrupt:
        print(tr("cli_stopping"))
        brush_engine.stop()
        sys.exit(0)

    if returncode == 0:
        print(f"\nPipeline terminé. Splat disponible dans : {dataset_path}")
    else:
        print(f"\nBrush a retourné une erreur (code {returncode}).")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

DISPATCH = {
    "pipeline":    run_pipeline,
    "colmap":      run_colmap,
    "brush":       run_brush,
    "sharp":       run_sharp,
    "view":        run_supersplat,
    "upscale":     run_upscale,
    "4dgs":        run_4dgs,
    "extract360":  run_extract360,
}


def main():
    parser = get_parser()
    args = parser.parse_args()

    # No subcommand + no --gui → GUI par défaut
    if not args.command and not args.gui:
        _launch_gui()
        return

    if args.gui:
        _launch_gui()
        return

    missing_deps = check_dependencies()
    if missing_deps:
        print(f"Attention : dépendances manquantes : {', '.join(missing_deps)}")

    handler = DISPATCH.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
