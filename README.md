# CorbeauSplat

**CorbeauSplat** is an all-in-one Gaussian Splatting automation tool designed specifically for **macOS Silicon** . It streamlines the entire workflow from raw video/images to a fully trained and viewable 3D scene (Gaussian Splat).

![CorbeauSplat Interface](assets/interface.webp)

## 🚀 What it does

This application provides a unified Graphical User Interface (GUI) to orchestrate the following steps:
1.  **Project Management**: Automatically organizes your outputs into structured project folders with images, sparse data, and checkpoints.
2.  **Sparse Reconstruction**: Automates **COLMAP** feature extraction, matching, and mapping. Supports **Glomap** as a modern alternative mapper.
3.  **Undistortion**: Automatically undistorts images for optimal training quality.
4.  **Training**: Integrates **Brush** to train Gaussian Splats directly on your Mac.
    -   **Densification Control**: Includes presets (Fast, Standard, Aggressive) and advanced parameters.
    -   **Auto-Refine**: Resume training seamlessly from your last checkpoint.
5.  **Visualization**: Includes a built-in tab running **SuperSplat** for immediate local viewing and editing of your PLY files.
6.  **Single Image to 3D**: (Bonus) Uses **Apple ML Sharp** to generate a 3D model from a single 2D image.
7.  **4DGS Preparation (Experimental)**: A new module to prepare 4D Gaussian Splatting datasets (Multi-camera video -> Nerfstudio format).
8.  **Factory Reset**: Integrated tools to fix dependency issues by rebuilding the environment from scratch.

It is designed to be "click-and-run", handling dependency checks, process management, and **session persistence** for you.

## ✍️ A Note from the Author

> This program was realized through **"vibecoding"** with the help of **Gemini 3 Pro**.
>
> It was originally created to facilitate the technical workflow for a documentary film titled **"Le Corbeau"**. I am not a professional developer; I simply needed to automate a complex process by gathering the tools I use daily: COLMAP, the Brush app, and SuperSplat. 
>
> I share this code in all humility. I didn't originally plan to release it, but I thought that perhaps someone, somewhere on this earth, might find it useful.
>
> As this software was built via "vibecoding" (AI-assisted coding), it is provided "as is" with no guarantees.

## 🛠 Prerequisites & Installation

### Requirements
- **macOS** (Silicon recommended - M1/M2/M3)
- **Python 3.13+** (Recommended for JIT/Performance) or Python 3.11 (Supported)
- **Xcode Command Line Tools** (Required for compiling custom engines like Glomap or Brush)
- **Homebrew** (for installing system dependencies like COLMAP and FFmpeg)
- **Git**

### Installation
1.  Clone this repository:
    ```bash
    git clone https://github.com/freddewitt/CorbeauSplat.git
    cd CorbeauSplat
    ```

2.  Run the launcher:
    ```bash
    ./run.command
    ```
    *The script will automatically detect missing dependencies (Python packages, Brush, SuperSplat, Rust, Node.js, etc.) and attempt to install them for you.*

## 📖 How to Use

1.  **Configuration Tab**: 
    -   Select your input (Video or Folder of images).
    -   Define a **Project Name** (your files will be saved in `[Output Folder]/[Project Name]`).
    -   Click **"Create COLMAP Dataset"**.
2.  **Params Tab**: (Optional) Tweak advanced COLMAP settings or enable **Glomap**.
3.  **Upscale Tab**: (Optional)
    -   Check **"Activate Upscale Module"** to install dependencies.
    -   Select a model (e.g., RealESRGAN_x4plus) and a scale factor (x2, x4).
    -   These settings will be applied during the "Create COLMAP Dataset" phase.
4.  **Brush Tab**: 
    -   **Auto-Refine**: Choose "Refine" mode to resume training from the latest checkpoint.
    -   **Presets**: Use specific densification strategies (e.g., "Aggressive Densification").
    -   Click **"Start Brush Training"**.
4.  **SuperSplat Tab**: 
    -   Load your trained `.ply` file.
    -   Click **"Start Servers"** to launch the viewer locally.
5.  **4DGS Tab (Experimental)**:
    -   Check **"Activate"** to install the required dependencies (Nerfstudio).
    -   Select a folder containing your synced camera videos.
    -   Click **"Start Process"** to generate a dataset ready for 4DGS training.
6.  **Apple Sharp Tab (Bonus)**:
    -   Select a single source image.
    -   Click **"Predict 3D Model"** to generate a mesh using machine learning.

### ⌨️ Command Line Interface (CLI)

CorbeauSplat exposes all its features via the command line.

� **[See CLI.md for full command line documentation](CLI.md)**

## 👏 Acknowledgments & Credits

This project stands on the shoulders of giants. A huge thank you to the creators of the core technologies used here:

*   **COLMAP**: Structure-from-Motion and Multi-View Stereo. [GitHub](https://github.com/colmap/colmap)
*   **Brush**: An efficient Gaussian Splatting trainer for macOS. [GitHub](https://github.com/ArthurBrussee/brush)
*   **SuperSplat**: An amazing web-based Splat editor by PlayCanvas. [GitHub](https://github.com/playcanvas/supersplat)
*   **Apple ML Sharp**: Machine Learning tools for Swift. [GitHub](https://github.com/apple/ml-sharp)
*   **Nerfstudio**: The modular NeRF and Splatting framework (used for 4DGS data prep). [GitHub](https://github.com/nerfstudio-project/nerfstudio)
*   **Real-ESRGAN**: AI algorithms for image restoration and enhancement. [GitHub](https://github.com/xinntao/Real-ESRGAN)

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details. This is the most permissive open-source license, allowing you to use, modify, and distribute this software freely.
