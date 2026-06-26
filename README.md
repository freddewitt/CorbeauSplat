# CorbeauSplat — Windows / CUDA Edition

**CorbeauSplat** is an all-in-one Gaussian Splatting automation tool for **Windows with NVIDIA CUDA GPUs**. It streamlines the whole workflow from raw video/images to a fully trained and viewable 3D scene (Gaussian Splat).

> 🪟 **Windows/CUDA fork** of the original macOS project. The pipeline is focused on
> **video → frames → COLMAP → Brush splat training → view**, accelerated by your NVIDIA GPU.

![CorbeauSplat Interface](assets/interface.webp)

## 🚀 What it does

A unified GUI (and CLI) to orchestrate:
1.  **Project Management**: Organises outputs into structured project folders (images, sparse data, checkpoints).
2.  **Frame Extraction**: Pulls frames from a video with **FFmpeg**, using **NVIDIA NVDEC (`-hwaccel cuda`)** when a GPU is present.
3.  **Sparse Reconstruction**: Automates **COLMAP** feature extraction, matching and mapping with **GPU-accelerated SIFT** (`--SiftExtraction.use_gpu` / `--SiftMatching.use_gpu`). Supports **Glomap** as an alternative mapper.
4.  **Undistortion**: Optionally undistorts images for optimal training quality.
5.  **AI Upscaling** *(optional)*: Enhances input images with **upscayl-ncnn** before reconstruction.
6.  **Training**: Integrates **Brush** (Rust/wgpu, DirectX 12 / Vulkan) to train Gaussian Splats on your GPU.
7.  **Visualization**: Built-in **SuperSplat** tab for immediate local viewing/editing of `.ply` files.
8.  **4DGS Preparation (Experimental)**: Prepares 4D Gaussian Splatting datasets (multi-camera video → Nerfstudio format).
9.  **360 Extractor (Experimental)**: Converts equirectangular 360° videos into planar image sets.

It is designed to be "click-and-run", with dependency checks, process management and session persistence.
Includes full localization for **French, English, German, Italian, Spanish, Arabic, Russian, Chinese and Japanese**.

## 🛠 Prerequisites & Installation

### Requirements
- **Windows 10/11 (x64)**
- **NVIDIA GPU** with up-to-date drivers (for CUDA acceleration; CPU fallback works but is slow)
- **Python 3.11+** ([python.org](https://www.python.org/downloads/) — tick *"Add Python to PATH"*)
- **Git** (optional, for updates and source builds)

That's it — **COLMAP (CUDA) and FFmpeg are installed automatically** on first launch (see below). No manual download/PATH setup required.

### Installation
1.  Clone or download this repository.
2.  Double-click **`run.bat`** (or run it from a terminal).

    On first launch it automatically:
    - creates a Python virtual environment and installs the Python dependencies;
    - **downloads the CUDA COLMAP build** (`colmap-x64-windows-cuda.zip`) from GitHub releases into `engines\colmap\`;
    - **installs FFmpeg** (via `winget` if available, otherwise a static build into `engines\ffmpeg\`);
    - downloads/builds the other engines (Brush, SuperSplat, upscayl);
    - launches the app.

> All auto-downloaded engines live under `engines\` (git-ignored). To re-download everything cleanly, run `run.bat --clean`.
>
> If you already have COLMAP installed system-wide, CorbeauSplat will use that instead (it checks PATH and `C:\COLMAP`). No GPU? It falls back to the non-CUDA COLMAP build and CPU execution automatically.

Optional flags:
```bat
run.bat --clean      :: wipe venvs + engines + config and start fresh
```

## 📖 How to Use

1.  **Configuration Tab**: choose your input (a video or a folder of images), set a **Project Name**, then click **"Create COLMAP Dataset"**.
2.  **Params Tab**: *(optional)* tweak COLMAP settings or enable **Glomap**.
3.  **Upscale Tab**: *(optional)* enable upscaling and pick a model.
4.  **Brush Tab**: choose a preset (e.g. "Aggressive Densification"), set **Device** to `cuda`, then **"Start Brush Training"**.
5.  **SuperSplat Tab**: load your `.ply` and **"Start Servers"** to view it locally.

### ⌨️ Command Line Interface (CLI)

```bat
python main.py pipeline -i video.mp4 -o C:\projects --type video --preset dense
python main.py colmap   -i C:\photos  -o C:\projects
python main.py brush    -i C:\projects\scene -o C:\projects\scene --device cuda --preset dense
python main.py view     -i scene.ply
python main.py upscale  -i image.png -o C:\out --scale 4
```

Run `python main.py <command> --help` for per-command options. No arguments launches the GUI.

## 👏 Acknowledgments & Credits

*   **COLMAP**: Structure-from-Motion and Multi-View Stereo. [GitHub](https://github.com/colmap/colmap)
*   **Brush**: An efficient cross-platform Gaussian Splatting trainer (Rust/wgpu). [GitHub](https://github.com/ArthurBrussee/brush)
*   **SuperSplat**: Web-based Splat editor by PlayCanvas. [GitHub](https://github.com/playcanvas/supersplat)
*   **Glomap**: Global Structure-from-Motion. [GitHub](https://github.com/colmap/glomap)
*   **Nerfstudio**: NeRF and Splatting framework (used for 4DGS data prep). [GitHub](https://github.com/nerfstudio-project/nerfstudio)
*   **upscayl-ncnn**: High-performance AI image upscaling (NCNN). [GitHub](https://github.com/upscayl/upscayl-ncnn)

## 📄 License

MIT — see [LICENSE](LICENSE). Originally created for the documentary *"Le Corbeau"*; ported to Windows/CUDA.
