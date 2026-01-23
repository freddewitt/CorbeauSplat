
import os
import shutil
import sys
import subprocess
import glob
from .system import is_apple_silicon, get_optimal_threads

class UpscaleEngine:
    """
    Engine for Real-ESRGAN upscaling.
    Handles dynamic installation of dependencies and execution of upscaling.
    """

    def __init__(self, logger_callback=None):
        self.logger = logger_callback if logger_callback else print
        self.device = "mps" if is_apple_silicon() else "cpu"
        # On Mac, sometimes 'cpu' is safer for some ops, but 'mps' is preferred for speed if supported.
        # RealESRGAN supports mps.

    def log(self, msg):
        self.logger(msg)

    def _apply_patches(self):
        """
        Hotfix for basicsr/realesrgan compatibility with newer torchvision.
        Populates torchvision.transforms.functional_tensor with functional.
        """
        import sys
        try:
             import torchvision.transforms.functional_tensor
        except ImportError:
            try:
                import torchvision.transforms.functional as F
                sys.modules["torchvision.transforms.functional_tensor"] = F
            except Exception as e:
                # If this fails, we can't do much, but we print it
                print(f"DEBUG: Patching failed: {e}")

    def is_installed(self):
        """Checks if realesrgan and torch are importable."""
        try:
            import torch
            self._apply_patches()
            import realesrgan
            return True
        except ImportError as e:
            print(f"DEBUG: Upscale import failed: {e}")
            return False

    def get_version(self):
        """Returns installed version of realesrgan"""
        try:
            import realesrgan
            return getattr(realesrgan, "__version__", "Unknown")
        except ImportError:
            return None

    def get_models_path(self):
        """Returns the directory where weights are stored"""
        # We store weights in app/weights for persistence
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        weights_dir = os.path.join(root, "weights")
        os.makedirs(weights_dir, exist_ok=True)
        return weights_dir

    def check_model_availability(self, model_name):
        """Checks if model weights are present locally"""
        weights_dir = self.get_models_path()
        # Mapping model names to filenames usually used by RealESRGAN
        file_map = {
            "RealESRGAN_x4plus": "RealESRGAN_x4plus.pth",
            "RealESRNet_x4plus": "RealESRNet_x4plus.pth", 
            "RealESRGAN_x4plus_anime_6B": "RealESRGAN_x4plus_anime_6B.pth"
        }
        filename = file_map.get(model_name)
        if not filename: return False
        
        path = os.path.join(weights_dir, filename)
        return os.path.exists(path)

    # install/uninstall methods deprecated, handled by setup_dependencies.py

    def load_model(self, model_name='RealESRGAN_x4plus', tile=0, target_scale=4):
        """
        Loads the RealESRGANer model. 
        Returns the model object or None.
        """
        if not self.is_installed():
            self.log("Dependencies not installed.")
            return None

            return None

        try:
            self._apply_patches()
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer
            
            model = None
            netscale = 4
            
            if model_name == 'RealESRGAN_x4plus':
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
                netscale = 4
            elif model_name == 'RealESRNet_x4plus':
                model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
                netscale = 4
            # Add more models if needed
            
            # Auto-download if missing
            file_path = os.path.join(self.get_models_path(), f"{model_name}.pth")
            if not os.path.exists(file_path):
                self.log(f"Model {model_name} missing. Attempting auto-download...")
                if not self.download_model(model_name):
                    self.log(f"Failed to auto-download {model_name}.")
                    return None
            
            # Let's rely on standard usage:
            upsampler = RealESRGANer(
                scale=netscale,
                # If we need auto-download, we might need a helper.
                # 'realesrgan' package typically fetches weights if using their CLI, 
                # but as library we often need to provide path or URL.
                model=model,
                tile=tile,
                tile_pad=10,
                pre_pad=0,
                half=False, # mps/cpu might not like half
                device=self.device,
                model_path=os.path.join(self.get_models_path(), f"{model_name}.pth")
            )
            # Inject target scale into upsampler object for later retrieval if needed
            upsampler.target_scale = target_scale
            return upsampler
            
        except Exception as e:
            self.log(f"Failed to load model: {e}")
            return None
            
            self.log(f"Failed to load model: {e}")
            return None

    def download_model(self, model_name):
        """Downloads the specific model weights"""
        # Urls from realesrgan repo
        urls = {
            "RealESRGAN_x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            "RealESRNet_x4plus": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth",
            "RealESRGAN_x4plus_anime_6B": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"
        }
        
        url = urls.get(model_name)
        if not url:
            self.log(f"No URL found for {model_name}")
            return False
            
        save_path = os.path.join(self.get_models_path(), f"{model_name}.pth")
        
        if os.path.exists(save_path):
            # Check size (sanity check, arbitrary min size 1MB)
            if os.path.getsize(save_path) > 1024 * 1024: 
                self.log(f"Model {model_name} already exists and valid.")
                return True
            else:
                self.log(f"Model {model_name} exists but seems empty/corrupt. Redownloading.")
                os.remove(save_path)
            
        self.log(f"Downloading {model_name}...")
        try:
            # Basic download using requests or curl
            # We can use subprocess curl for simplicity and progress bar in log?
            # Or urllib
            import urllib.request
            
            def progress(count, block_size, total_size):
                if total_size > 0:
                    percent = int(count * block_size * 100 / total_size)
                    if percent % 10 == 0:
                         # Hacky progress log, maybe too verbose
                         pass

            # Wait, signature is (url, filename, reporthook)
            urllib.request.urlretrieve(url, save_path)
            
            self.log(f"Download complete: {save_path}")
            
            # Verify size post download
            if not os.path.exists(save_path) or os.path.getsize(save_path) < 1024 * 1024:
                 self.log("Download failed (file too small or missing).")
                 return False
                 
            return True
        except Exception as e:
            self.log(f"Download failed: {e}")
            return False

    def upscale_image(self, input_path, output_path, upsampler, face_enhance=False):
        """
        Upscales a single image.
        """
        try:
            import cv2
            img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                self.log(f"Failed to read {input_path}")
                return False
                
            # Upscale
            # Determine outscale. 
            # If using RealESRGAN, 'outscale' parameter in enhance() handles resizing.
            
            # Default to 4 if not specified
            final_scale = 4
            if hasattr(upsampler, 'target_scale') and upsampler.target_scale:
                final_scale = upsampler.target_scale
                
            output, _ = upsampler.enhance(img, outscale=final_scale)
            
            # Face Enhance (GFPGAN) - Optional, implementation complex without helper wrapper.
            if face_enhance:
                # Placeholder: Face enhancement logic usually requires loading GFPGANer
                # For this iteration, we acknowledge the flag but might not implement full GFPGAN unless requested heavily
                # or if we implement a FaceEnhancer helper.
                # Given dependencies list had 'gfpgan', we could try using it if installed.
                pass
            
            cv2.imwrite(output_path, output)
            return True
        except Exception as e:
            self.log(f"Error upscaling {input_path}: {e}")
            return False

    def upscale_folder(self, input_dir, output_dir, extension='jpg', model_name='RealESRGAN_x4plus', tile=0, target_scale=4, face_enhance=False):
        """
        Upscales all images in input_dir to output_dir.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Get images
        files = sorted(glob.glob(os.path.join(input_dir, f"*.{extension}")))
        if not files:
             files = sorted(glob.glob(os.path.join(input_dir, f"*.png"))) # fallback
             
        self.log(f"Found {len(files)} images to upscale.")
        
        # Load Model
        upsampler = self.load_model(model_name=model_name, tile=tile, target_scale=target_scale)
        if not upsampler:
            return False, "Failed to load model"
            
        success_count = 0
        for idx, img_path in enumerate(files):
            basename = os.path.basename(img_path)
            out_path = os.path.join(output_dir, basename)
            
            self.log(f"Upscaling [{idx+1}/{len(files)}]: {basename} (x{target_scale})")
            if self.upscale_image(img_path, out_path, upsampler, face_enhance=face_enhance):
                success_count += 1
                
        self.log(f"Upscaling complete. {success_count}/{len(files)} processed.")
        return True, "Success"
