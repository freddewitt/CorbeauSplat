# Command Line Interface (CLI)

CorbeauSplat exposes its features via the command line, making it easy to integrate into automated pipelines or run on headless machines.

Without arguments, the graphical interface launches automatically (`--gui` forces it). Each subcommand has its own `--help`.

## Quick Usage

```bash
python3 main.py <command> --help    # Help for a specific command
python3 main.py --help              # List all commands
```

Commands: `pipeline`, `colmap`, `brush`, `sharp`, `view`, `upscale`, `4dgs`, `clean`, `splattransform`, `extract360`.

---

## Commands

### `pipeline` — Full run in one command

Runs COLMAP reconstruction then Brush training back-to-back. The dataset is created at `<output>/<project_name>/` and passed directly to Brush. Cleaning and export are opt-in extra steps (`--clean`, `--export`).

```bash
# From a video
python3 main.py pipeline -i video.mp4 -o ~/projects --type video

# From photos, high-quality preset
python3 main.py pipeline -i ~/photos -o ~/projects --preset dense

# Train, clean (strong) and export to SPZ
python3 main.py pipeline -i ~/photos -o ~/projects --clean strong --export spz

# Video range only (seconds 10 to 40), fast preview
python3 main.py pipeline -i video.mp4 -o ~/projects --type video --trim_start 10 --trim_end 40 --preset fast
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Source video or images folder |
| `--output`, `-o` | *(required)* | Parent output folder |
| `--project_name` | `Untitled` | Project subfolder name |
| `--type` | `images` | Input type: `images` or `video` |
| `--fps` | `5` | Frame extraction rate for video |
| `--trim_start` / `--trim_end` | *(whole video)* | Video range to extract, in seconds |
| `--convert` | `png` | Convert non-JPEG/PNG images (HEIC, TIFF, BMP, WebP…) before processing: `png`, `jpeg`, `off` |
| `--filter_blur` | — | Drop blurry images before COLMAP |
| `--blur_strength` | `medium` | Blur filter strength: `light`, `medium`, `strong` |
| `--camera_model` | `SIMPLE_RADIAL` | COLMAP camera model |
| `--undistort` | — | Run undistortion after reconstruction |
| `--feature_type` | `SIFT` | Feature extractor: `SIFT`, `ALIKED_N16ROT`, `ALIKED_N32` |
| `--matching_type` | *(auto)* | `SIFT_BRUTEFORCE`, `ALIKED_BRUTEFORCE`, `SIFT_LIGHTGLUE`, `ALIKED_LIGHTGLUE` |
| `--matcher_type` | `exhaustive` | Matching strategy: `exhaustive`, `sequential`, `vocab_tree` |
| `--sequential_overlap` | `30` | Neighbouring images compared by the sequential matcher |
| `--guided_matching` | — | Epipolar-guided matching (slower, more robust) |
| `--max_image_size` | `3200` | Max image resolution for COLMAP |
| `--robust` | — | Robust mode for large scenes (anti-crash COLMAP) |
| `--thermal-throttling` | — | Enable thermal throttling |
| `--view-graph-calibration` / `--no-view-graph-calibration` | on | View-graph calibration (recommended for AI-generated video) |
| `--ignore-watermarks` / `--no-ignore-watermarks` | on | Ignore watermarks (recommended for AI-generated video) |
| `--preset` | `default` | Brush preset: `default`, `fast`, `std`, `dense` |
| `--iterations` | *(preset)* | Override Brush iteration count |
| `--sh_degree` | `3` | Spherical Harmonics degree (1–4) |
| `--device` | `auto` | Brush device: `auto`, `mps`, `cuda`, `cpu` |
| `--max_resolution` | `0` (auto) | Max training image resolution |
| `--with_viewer` | — | Open the interactive viewer after training |
| `--ply_name` | — | Output PLY filename |
| `--clean [STRENGTH]` | *(off)* | Clean the splat after training: `light`, `medium` (default if flag given), `strong` |
| `--export FORMAT` | *(off)* | Export after training (and after cleaning): `spz`, `glb`, `obj`, `ply`, `xyz` |
| `--export_output` | *(next to the splat)* | Export destination folder |

For fine-grained control over either step, run `colmap` and `brush` separately.

---

### `colmap` — Build a COLMAP dataset

Runs the full pipeline: frame extraction → feature extraction → matching → reconstruction.

```bash
# From a video
python3 main.py colmap -i video.mp4 -o ~/projects --type video --fps 5

# From images
python3 main.py colmap -i ~/photos -o ~/projects --project_name my_scene

# Neural features and matching
python3 main.py colmap -i ~/photos -o ~/projects --feature_type ALIKED_N32 --matching_type ALIKED_LIGHTGLUE

# Undistort after reconstruction
python3 main.py colmap -i ~/photos -o ~/projects --undistort
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Source video or images folder |
| `--output`, `-o` | *(required)* | Output folder |
| `--type` | `images` | Input type: `images` or `video` |
| `--fps` | `5` | Frame extraction rate for video |
| `--trim_start` / `--trim_end` | *(whole video)* | Video range to extract, in seconds |
| `--project_name` | `Untitled` | Project subfolder name |
| `--camera_model` | `SIMPLE_RADIAL` | `SIMPLE_PINHOLE`, `PINHOLE`, `SIMPLE_RADIAL`, `RADIAL`, `OPENCV`, `OPENCV_FISHEYE` |
| `--undistort` | — | Run undistortion after reconstruction |
| `--convert` | `png` | Convert non-JPEG/PNG images before processing: `png`, `jpeg`, `off` |
| `--filter_blur` | — | Drop blurry images before COLMAP |
| `--blur_strength` | `medium` | `light`, `medium`, `strong` |
| `--robust` | — | Robust mode for large scenes (anti-crash COLMAP) |
| `--thermal-throttling` | — | Enable thermal throttling |
| `--view-graph-calibration` / `--no-view-graph-calibration` | on | View-graph calibration (recommended for AI-generated video) |
| `--ignore-watermarks` / `--no-ignore-watermarks` | on | Ignore watermarks (recommended for AI-generated video) |

**Features**

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--feature_type` | `SIFT` | `SIFT`, `ALIKED_N16ROT`, `ALIKED_N32` (ALIKED needs ONNX, bundled in the Homebrew COLMAP) |
| `--max_image_size` | `3200` | Max image resolution |
| `--max_num_features` | `8192` | Max features per image |
| `--estimate_affine_shape` | — | Estimate affine shape of features |
| `--no_domain_size_pooling` | — | Disable domain size pooling |
| `--no_single_camera` | — | Disable single-camera mode |

**Matching**

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--matching_type` | *(auto from feature type)* | `SIFT_BRUTEFORCE`, `ALIKED_BRUTEFORCE`, `SIFT_LIGHTGLUE`, `ALIKED_LIGHTGLUE` |
| `--matcher_type` | `exhaustive` | `exhaustive`, `sequential`, `vocab_tree` |
| `--sequential_overlap` | `30` | Neighbouring images compared by the sequential matcher |
| `--guided_matching` | — | Epipolar-guided matching (slower, more robust) |
| `--max_ratio` | `0.8` | Lowe ratio threshold |
| `--max_distance` | `0.7` | Max feature distance |
| `--no_cross_check` | — | Disable cross-check |
| `--min_num_matches` | `15` | Min number of matches |

**Reconstruction**

| Flag | Default | Description |
| :--- | :--- | :--- |
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
| `--with_viewer` | — | Open the interactive viewer |
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

Launch a local SuperSplat web viewer for a `.ply` file. The servers only listen on `127.0.0.1`.

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
| `--scale` | `4` | Upscale factor: `1`, `2`, `3`, or `4` |
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
| `--colmap_only` | — | Skip extraction, run COLMAP only on the already-extracted dataset |

---

### `clean` — Clean a Gaussian Splat `.ply`

Remove noise and floaters from a `.ply` file, or from every `.ply` in a folder.

```bash
# One file
python3 main.py clean -i scene.ply -o scene_clean.ply

# A folder, recursively, strong preset
python3 main.py clean -i ~/splats -o ~/splats_clean --strength strong -r

# Clean then export to SPZ
python3 main.py clean -i scene.ply -o ~/out --then-export spz
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Input `.ply` file or folder of `.ply` |
| `--output`, `-o` | *(required)* | Output `.ply` file or destination folder |
| `--strength` | `medium` | Cleaning severity: `light`, `medium`, `strong` |
| `--recursive`, `-r` | — | Walk sub-folders (folder mode only) |
| `--opacity_min` | *(preset)* | Minimum opacity, 0–1 (overrides the preset) |
| `--scale_pct` | *(preset)* | Max scale percentile, 90–100 (overrides the preset) |
| `--outlier_pct` | *(preset)* | Max distance percentile, 90–100 (overrides the preset) |
| `--then-export FORMAT` | — | Chain an export after cleaning: `spz`, `glb`, `obj`, `ply`, `xyz` |
| `--export-output` | *(clean output folder)* | Export destination folder |

---

### `splattransform` — Convert / filter splats (PlayCanvas splat-transform)

Convert between splat formats and apply filters with [splat-transform](https://github.com/playcanvas/splat-transform).

```bash
python3 main.py splattransform -i scene.ply -o ~/out --format spz

# Drop NaN splats and keep half of the points
python3 main.py splattransform -i scene.ply -o ~/out --format ply --filter-nan --decimate 50%

# Strip spherical harmonics above band 1
python3 main.py splattransform -i scene.spz -o ~/out --format glb --filter-harmonics 1
```

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--input`, `-i` | *(required)* | Input file (`.ply`, `.spz`, `.splat`, …) |
| `--output`, `-o` | *(required)* | Output folder |
| `--format`, `-f` | `ply` | Output format: `ply`, `spz`, `glb`, `csv` |
| `--filter-nan` | — | Remove degenerate / NaN splats |
| `--filter-harmonics` | — | Strip spherical harmonics above the given band (`0`–`3`, `0` = DC only) |
| `--decimate` | — | Reduce point count, e.g. `50%` keeps half the splats |
| `--morton-order` | — | Reorder splats along a Morton curve (GPU cache efficiency) |

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

**One command, video to cleaned SPZ**
```bash
python3 main.py pipeline -i video.mp4 -o ~/projects --type video --clean --export spz
```

**Standard 3DGS from video, step by step**
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

**Single photo to 3D**
```bash
python3 main.py sharp -i photo.jpg -o ~/output
python3 main.py view  -i ~/output/photo.ply
```
