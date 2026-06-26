#!/usr/bin/env python3
"""CLI argument parser for CorbeauSplat."""
import argparse


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
                   choices=["auto","cuda","cpu"], help="Device Brush (défaut: auto)")
    p.add_argument("--with_viewer", action="store_true", help="Ouvrir le viewer interactif après entraînement")
    p.add_argument("--max_resolution", type=int, default=None,
                   help="Résolution max entraînement 0=auto (défaut: 0)")
    p.add_argument("--ply_name",    default=None,        help="Nom du fichier PLY de sortie")
    p.add_argument("--filter_blur", action="store_true", help="Écarter les images floues avant COLMAP")
    p.add_argument("--blur_strength", choices=["light", "medium", "strong"], default="medium",
                   help="Sévérité du filtre de flou (défaut: medium)")
    p.add_argument("--robust", action="store_true",
                   help="Mode robuste grandes scènes (PINHOLE, anti-crash BA, filtre flou)")

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
    p.add_argument("--domain_size_pooling", action="store_true",
                   help="Activer le domain size pooling (force le SIFT sur CPU — désactivé par défaut)")
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
    # Blur filtering
    p.add_argument("--filter_blur", action="store_true", help="Écarter les images floues avant COLMAP")
    p.add_argument("--blur_strength", choices=["light", "medium", "strong"], default="medium",
                   help="Sévérité du filtre de flou (défaut: medium)")
    p.add_argument("--robust", action="store_true",
                   help="Mode robuste grandes scènes (PINHOLE, anti-crash BA, filtre flou)")

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
                   choices=["auto","cuda","cpu"], help="Device (défaut: auto)")
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

    # ── clean ─────────────────────────────────────────────────────────────────
    p = subs.add_parser("clean", help="Nettoyer un splat .ply (ciel/floaters/bruit)")
    p.add_argument("--input",  "-i", required=True, help="Fichier .ply à nettoyer")
    p.add_argument("--output", "-o", required=True, help="Fichier .ply de sortie")
    p.add_argument("--strength", choices=["light", "medium", "strong"], default="medium",
                   help="Sévérité du nettoyage (défaut: medium)")

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
