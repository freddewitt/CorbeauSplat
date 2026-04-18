#!/usr/bin/env python3
"""
Upscale runner — exécuté dans .venv_upscale (Python 3.11).
Appelé par upscale_engine.py via subprocess.
"""
import argparse
import sys
from pathlib import Path


def apply_patches():
    try:
        import torchvision.transforms.functional_tensor  # noqa: F401
    except ImportError:
        try:
            import torchvision.transforms.functional as F
            sys.modules["torchvision.transforms.functional_tensor"] = F
        except Exception:
            pass


def load_upsampler(model_name, weights_dir, tile, scale, half):
    apply_patches()
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer

    if model_name in ("RealESRGAN_x4plus", "RealESRNet_x4plus"):
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    elif model_name == "RealESRGAN_x4plus_anime_6B":
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
    else:
        print(f"ERROR: Modèle inconnu: {model_name}", file=sys.stderr)
        sys.exit(1)

    file_path = Path(weights_dir) / f"{model_name}.pth"
    if not file_path.exists():
        print(f"ERROR: Modèle introuvable: {file_path}", file=sys.stderr)
        sys.exit(1)

    upsampler = RealESRGANer(
        scale=4,
        model=model,
        tile=tile,
        tile_pad=10,
        pre_pad=0,
        half=half,
        model_path=str(file_path),
    )
    return upsampler


def mode_image(args):
    import cv2
    upsampler = load_upsampler(args.model, args.weights_dir, args.tile, args.scale, args.half)
    img = cv2.imread(args.input, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"ERROR: Impossible de lire {args.input}", file=sys.stderr)
        sys.exit(1)
    output, _ = upsampler.enhance(img, outscale=args.scale)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(args.output, output)
    print(f"OK:{args.output}")


def mode_folder(args):
    import cv2
    upsampler = load_upsampler(args.model, args.weights_dir, args.tile, args.scale, args.half)
    in_p = Path(args.input)
    out_p = Path(args.output)
    out_p.mkdir(parents=True, exist_ok=True)

    exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    files = sorted(f for f in in_p.iterdir() if f.is_file() and f.suffix.lower() in exts)
    total = len(files)
    success = 0

    for idx, img_path in enumerate(files):
        print(f"PROGRESS:{idx + 1}/{total}:{img_path.name}", flush=True)
        img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            print(f"SKIP:{img_path.name}", flush=True)
            continue
        output, _ = upsampler.enhance(img, outscale=args.scale)
        cv2.imwrite(str(out_p / img_path.name), output)
        success += 1

    print(f"DONE:{success}/{total}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CorbeauSplat Upscale Runner")
    parser.add_argument("--mode", choices=["image", "folder"], required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="RealESRGAN_x4plus")
    parser.add_argument("--weights-dir", required=True)
    parser.add_argument("--tile", type=int, default=512)
    parser.add_argument("--scale", type=int, default=4)
    parser.add_argument("--half", action="store_true")
    args = parser.parse_args()

    if args.mode == "image":
        mode_image(args)
    else:
        mode_folder(args)
