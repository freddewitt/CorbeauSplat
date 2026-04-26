# Command Line Interface (CLI)

CorbeauSplat exposes all its features via the command line, making it easy to integrate into automated pipelines or run on headless machines.

Without arguments, the graphical interface launches automatically. Each subcommand has its own `--help`.

## Quick Usage

```bash
python3 main.py <command> --help    # Help for a specific command
python3 main.py --help              # List all commands
```

---

## Commands

### `pipeline` — Full training in one command

Runs COLMAP reconstruction then Brush training back-to-back. The dataset is created at `<output>/<project_name>/` and passed directly to Brush.

```bash
# From a video
python3 main.py pipeline -i video.mp4 -o ~/projects --type video

# From photos, high-quality preset
python3 main.py pipeline -i ~/photos -o ~/projects --preset dense

# Named project with Glomap
python3 main.py pipeline -i ~/photos -o ~/projects --project_name my_scene --use_glomap

# Fast preview from video
python3 main.py pipeline -i video.mp4 -o ~/projects --type video --fps 3 --preset fast
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Source video or images folder |
| `--output`, `-o` | *(required)* | Parent output folder |
| `--project_name` | `Untitled` | Project subfolder name |
| `--type` | `images` | Input type: `images` or `video` |
| `--fps` | `5` | Frame extraction rate for video |
| `--camera_model` | `SIMPLE_RADIAL` | COLMAP camera model |
| `--undistort` | — | Run undistortion after reconstruction |
| `--use_glomap` | — | Use Glomap mapper |
| `--matcher_type` | `exhaustive` | Matching strategy: `exhaustive`, `sequential`, `vocab_tree` |
| `--max_image_size` | `3200` | Max image resolution for COLMAP |
| `--preset` | `default` | Brush preset: `default`, `fast`, `std`, `dense` |
| `--iterations` | *(preset)* | Override Brush iteration count |
| `--sh_degree` | `3` | Spherical Harmonics degree (1–4) |
| `--device` | `auto` | Brush device: `auto`, `mps`, `cuda`, `cpu` |
| `--with_viewer` | — | Open interactive Brush viewer after training |
| `--ply_name` | — | Output PLY filename |

For fine-grained control over either step, run `colmap` and `brush` separately.

---

### `colmap` — Build a COLMAP dataset

Runs the full pipeline: frame extraction → feature extraction → matching → reconstruction.

```bash
# From a video
python3 main.py colmap -i video.mp4 -o ~/projects --type video --fps 5

# From images
python3 main.py colmap -i ~/photos -o ~/projects --project_name my_scene

# With Glomap mapper
python3 main.py colmap -i ~/photos -o ~/projects --use_glomap

# Undistort after reconstruction
python3 main.py colmap -i ~/photos -o ~/projects --undistort
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Source video or images folder |
| `--output`, `-o` | *(required)* | Output folder |
| `--type` | `images` | Input type: `images` or `video` |
| `--fps` | `5` | Frame extraction rate for video |
| `--project_name` | `Untitled` | Project subfolder name |
| `--camera_model` | `SIMPLE_RADIAL` | COLMAP camera model (`SIMPLE_PINHOLE`, `PINHOLE`, `SIMPLE_RADIAL`, `RADIAL`, `OPENCV`, `OPENCV_FISHEYE`) |
| `--undistort` | — | Run undistortion after reconstruction |
| `--use_glomap` | — | Use [Glomap](https://github.com/colmap/glomap) instead of the standard COLMAP mapper |

**Advanced COLMAP flags**

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--no_single_camera` | — | Disable single-camera mode |
| `--max_image_size` | `3200` | Max image resolution |
| `--max_num_features` | `8192` | Max features per image |
| `--matcher_type` | `exhaustive` | Matching strategy: `exhaustive`, `sequential`, `vocab_tree` |
| `--max_ratio` | `0.8` | Lowe ratio threshold |
| `--max_distance` | `0.7` | Max feature distance |
| `--no_cross_check` | — | Disable cross-check |
| `--min_model_size` | `10` | Min reconstruction model size |
| `--min_num_matches` | `15` | Min number of matches |
| `--multiple_models` | — | Allow multiple reconstruction models |
| `--estimate_affine_shape` | — | Estimate affine shape of features |
| `--no_domain_size_pooling` | — | Disable domain size pooling |
| `--no_refine_focal` | — | Skip focal length refinement |
| `--refine_principal` | — | Refine principal point |
| `--no_refine_extra` | — | Skip extra params refinement |

---

### `brush` — Train a Gaussian Splat

Train a 3DGS model from a COLMAP dataset.

```bash
# Basic training
python3 main.py brush -i ~/projects/my_scene -o ~/projects/my_scene

# With a preset
python3 main.py brush -i ~/projects/my_scene -o ~/projects/my_scene --preset dense

# Refine from last checkpoint
python3 main.py brush -i ~/projects/my_scene -o ~/projects/my_scene --refine_mode

# Override preset with individual params
python3 main.py brush -i ~/projects/my_scene -o ~/projects/my_scene --preset fast --iterations 10000
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | COLMAP dataset folder |
| `--output`, `-o` | *(required)* | Output folder |
| `--preset` | `default` | Parameter preset: `default`, `fast`, `std`, `dense` |
| `--iterations` | `30000` | Total training steps |
| `--sh_degree` | `3` | Spherical Harmonics degree (1–4) |
| `--device` | `auto` | Device: `auto`, `mps`, `cuda`, `cpu` |
| `--refine_mode` | — | Resume from the latest checkpoint |
| `--with_viewer` | — | Open the interactive Brush viewer |
| `--ply_name` | — | Output PLY filename |
| `--custom_args` | — | Extra flags passed directly to brush |

**Preset values**

| Preset | Steps | Refine every | Grad threshold | Fraction | Growth stop |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `default` / `std` | 30 000 | 200 | 0.003 | 0.2 | 15 000 |
| `fast` | 7 000 | 100 | 0.01 | 0.2 | 6 000 |
| `dense` | 50 000 | 100 | 0.0005 | 0.6 | 40 000 |

**Advanced Brush flags** *(override preset values)*

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--start_iter` | `0` | Starting iteration |
| `--refine_every` | `200` | Densification interval |
| `--growth_grad_threshold` | `0.003` | Gradient threshold for densification |
| `--growth_select_fraction` | `0.2` | Densification selection fraction |
| `--growth_stop_iter` | `15000` | Stop densification at this iteration |
| `--max_splats` | `10000000` | Max number of Gaussians |
| `--checkpoint_interval` | `7000` | Save a checkpoint every N iterations |
| `--max_resolution` | `0` (auto) | Max training image resolution |

---

### `sharp` — Single Image / Video → 3D Splat

Use Apple's ML-Sharp model to generate a `.ply` from an image or a video.

```bash
# Single image
python3 main.py sharp -i photo.jpg -o ~/output

# Video (processes every frame)
python3 main.py sharp -i clip.mp4 -o ~/output --mode video

# Video with frame skip (1 out of 3 frames)
python3 main.py sharp -i clip.mp4 -o ~/output --mode video --skip_frames 3
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Image, image folder, or video file |
| `--output`, `-o` | *(required)* | Output folder |
| `--mode` | `image` | Processing mode: `image` or `video` |
| `--checkpoint`, `-c` | — | Path to a custom `.pt` checkpoint |
| `--device` | `default` | Device: `default`, `mps`, `cpu`, `cuda` |
| `--skip_frames` | `1` | `[video]` Process 1 frame every N |
| `--upscale` | — | Upscale images before prediction (requires upscayl-bin) |
| `--verbose` | — | Show detailed Sharp output |

---

### `view` — Visualise a Splat (SuperSplat)

Launch a local SuperSplat web viewer for a `.ply` file.

```bash
python3 main.py view -i splat.ply

# Custom ports
python3 main.py view -i splat.ply --port 4000 --data_port 9000

# Open with no UI and a preset camera position
python3 main.py view -i splat.ply --no_ui --cam_pos 0,1,-5 --cam_rot 10,0,0
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | `.ply` file or folder |
| `--port` | `3000` | SuperSplat web server port |
| `--data_port` | `8000` | Data server port |
| `--no_ui` | — | Hide the SuperSplat interface |
| `--cam_pos` | — | Initial camera position `X,Y,Z` |
| `--cam_rot` | — | Initial camera rotation `X,Y,Z` (degrees) |

---

### `upscale` — Upscale Images (upscayl-bin)

Upscale images using NCNN-based super-resolution models. Requires upscayl-bin (installable from the GUI).

```bash
# Upscale a single image x4
python3 main.py upscale -i photo.png -o ~/output

# Upscale a folder x2 with a specific model
python3 main.py upscale -i ~/images -o ~/output --scale 2 --model realesrgan-x4plus
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Image or folder of images |
| `--output`, `-o` | *(required)* | Output folder |
| `--model` | `realesrgan-x4plus` | Upscayl model ID |
| `--scale` | `4` | Upscale factor: `2`, `3`, or `4` |
| `--format` | `png` | Output format: `png`, `jpg`, `webp` |
| `--tile` | `0` (auto) | Tile size in pixels (for low VRAM) |
| `--tta` | — | Enable Test-Time Augmentation |
| `--compression` | `0` | Output compression level (0–9) |

---

### `4dgs` — Prepare a 4D Gaussian Splatting Dataset

Extract frames from multi-camera videos and run COLMAP or Nerfstudio processing.

```bash
# Full pipeline: extract frames + Nerfstudio (or COLMAP fallback)
python3 main.py 4dgs -i ~/videos -o ~/output --fps 5

# Run only COLMAP on an already-extracted dataset
python3 main.py 4dgs -i ~/videos -o ~/output --colmap_only
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Folder containing multi-camera `.mp4`/`.mov` videos |
| `--output`, `-o` | *(required)* | Output folder |
| `--fps` | `5` | Frame extraction rate |
| `--colmap_only` | — | Skip extraction, run COLMAP only on `--output` |

---

### `extract360` — Extract 360° Video to Multi-Camera Images

Convert an equirectangular 360° video into a set of perspective images ready for COLMAP.

```bash
# Basic extraction
python3 main.py extract360 -i 360video.mp4 -o ~/output

# Higher density with 8 cameras and adaptive extraction
python3 main.py extract360 -i 360video.mp4 -o ~/output \
  --camera_count 8 --resolution 2048 --adaptive
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | 360° video file |
| `--output`, `-o` | *(required)* | Output folder |
| `--interval` | `1.0` | Seconds between extracted frames |
| `--format` | `jpg` | Output image format |
| `--resolution` | `2048` | Output image resolution (px) |
| `--camera_count` | `6` | Number of virtual cameras |
| `--quality` | `95` | JPEG quality (0–100) |
| `--layout` | `equirectangular` | Projection layout |
| `--ai_mask` | — | Enable AI masking |
| `--ai_skip` | — | Enable AI-based frame skipping |
| `--adaptive` | — | Motion-adaptive extraction |
| `--motion_threshold` | `0.3` | Motion threshold for adaptive extraction |

---

## Typical Pipelines

**Standard 3DGS from video**
```bash
python3 main.py colmap -i video.mp4 -o ~/projects --type video --fps 5
python3 main.py brush  -i ~/projects/Untitled -o ~/projects/Untitled --preset std
python3 main.py view   -i ~/projects/Untitled/output.ply
```

**High-quality scan from photos**
```bash
python3 main.py colmap -i ~/photos -o ~/projects --matcher_type exhaustive --max_num_features 16384
python3 main.py brush  -i ~/projects/Untitled -o ~/projects/Untitled --preset dense
```

**Quick preview**
```bash
python3 main.py colmap -i ~/photos -o ~/projects
python3 main.py brush  -i ~/projects/Untitled -o ~/projects/Untitled --preset fast
python3 main.py view   -i ~/projects/Untitled/output.ply --no_ui
```

**Single photo to 3D**
```bash
python3 main.py sharp -i photo.jpg -o ~/output
python3 main.py view  -i ~/output/photo.ply
```
