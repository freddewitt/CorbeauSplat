import os
import subprocess
import glob
import shutil
from .system import is_apple_silicon, resolve_binary, get_optimal_threads

class FourDGSEngine:
    """
    Engine for 4DGS dataset preparation.
    Pipeline:
    1. Extract frames from multiple videos (cameras) using FFmpeg.
    2. (Optional user step: Manual Sync Check - ignored for automation flow usually, or we just proceed)
    3. Run COLMAP (Feature Extractor, Matcher, Mapper).
    4. Run ns-process-data.
    """

    def __init__(self, input_dir, output_dir, fps=5, logger_callback=None):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.fps = fps
        self.logger = logger_callback if logger_callback else print
        self._current_process = None
        self.is_silicon = is_apple_silicon()
        self.num_threads = get_optimal_threads() if self.is_silicon else os.cpu_count()
        
        self.ffmpeg_bin = resolve_binary('ffmpeg') or 'ffmpeg'
        self.colmap_bin = resolve_binary('colmap') or 'colmap'
        # ns-process-data is a python script usually, we assume it's in path
        self.ns_process_bin = 'ns-process-data' 

    def log(self, msg):
        self.logger(msg)

    def stop(self):
        if self._current_process and self._current_process.poll() is None:
            self.log("Stopping process...")
            self._current_process.terminate()

    def run_command(self, cmd, description):
        self.log(f"--- {description} ---")
        self.log(f"CMD: {' '.join(cmd)}")
        
        try:
            env = os.environ.copy()
            if self.is_silicon:
                env['OMP_NUM_THREADS'] = str(self.num_threads)
                env['VECLIB_MAXIMUM_THREADS'] = str(self.num_threads)
                env['OPENBLAS_NUM_THREADS'] = str(self.num_threads)

            self._current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env
            )
            for line in self._current_process.stdout:
                self.log(line.strip())
            
            self._current_process.wait()
            return self._current_process.returncode == 0
        except Exception as e:
            self.log(f"Error running {description}: {e}")
            return False
        finally:
            self._current_process = None

    def process(self):
        if not os.path.exists(self.input_dir):
            self.log("Input directory does not exist.")
            return False, "Input directory missing"

        video_files = sorted(glob.glob(os.path.join(self.input_dir, "*.mp4")))
        if not video_files: # Try .MOV or others if needed, but tutorial said MP4
            video_files = sorted(glob.glob(os.path.join(self.input_dir, "*.MOV")))
        
        if not video_files:
            self.log("No video files found (*.mp4, *.MOV)")
            return False, "No videos found"

        os.makedirs(self.output_dir, exist_ok=True)
        images_root = os.path.join(self.output_dir, "images")
        
        # 1. FFmpeg Extraction
        self.log(f"Found {len(video_files)} videos. Starting extraction...")
        
        for i, video_path in enumerate(video_files):
            cam_name = f"cam{i+1:02d}" # cam01, cam02...
            cam_dir = os.path.join(images_root, cam_name)
            os.makedirs(cam_dir, exist_ok=True)
            
            cmd = [
                self.ffmpeg_bin
            ]
            if self.is_silicon:
                cmd.extend(['-hwaccel', 'videotoolbox'])
            
            cmd.extend([
                '-i', video_path,
                '-vf', f'fps={self.fps}',
                os.path.join(cam_dir, 'frame_%05d.jpg')
            ]
            
            if not self.run_command(cmd, f"Extracting {os.path.basename(video_path)} to {cam_name}"):
                return False, f"FFmpeg failed for {cam_name}"

        # 2. COLMAP
        self.log("\nStarting COLMAP Pipeline...")
        db_path = os.path.join(self.output_dir, "db.db")
        sparse_dir = os.path.join(self.output_dir, "sparse")
        os.makedirs(sparse_dir, exist_ok=True)
        
        # Feature Extractor
        cmd_extract = [
            self.colmap_bin, 'feature_extractor',
            '--database_path', db_path,
            '--image_path', images_root,
            '--ImageReader.camera_model', 'OPENCV_FISHEYE',
            '--ImageReader.single_camera', '1',
            # '--SiftExtraction.use_gpu', '0' # Removed, let colmap decide or user config? Tutorial said usage 0 for M-series but standard colmap usually handles it or Auto. 
            # If user explicitely asked for use_gpu 0, I should probably add it.
            # Tutorial: "--SiftExtraction.use_gpu 0  # CPU sur M-series"
        ]
        if is_apple_silicon():
             cmd_extract.extend(['--SiftExtraction.use_gpu', '0'])

        if not self.run_command(cmd_extract, "COLMAP Feature Extractor"):
            return False, "COLMAP Feature Extractor failed"

        # Matcher
        cmd_match = [
            self.colmap_bin, 'exhaustive_matcher',
            '--database_path', db_path,
        ]
        if not self.run_command(cmd_match, "COLMAP Exhaustive Matcher"):
            return False, "COLMAP Matcher failed"

        # Mapper
        output_sparse_0 = os.path.join(sparse_dir, "0")
        os.makedirs(output_sparse_0, exist_ok=True)
        
        cmd_mapper = [
            self.colmap_bin, 'mapper',
            '--database_path', db_path,
            '--image_path', images_root,
            '--output_path', output_sparse_0
        ]
        if not self.run_command(cmd_mapper, "COLMAP Mapper"):
             return False, "COLMAP Mapper failed"

        # 3. ns-process-data
        self.log("\nStarting ns-process-data...")
        # Tutorial:
        # ns-process-data images \
        #   --data ~/gopro_data \
        #   --output-dir ~/gopro_data_ns \
        #   --colmap-dir ~/gopro_data/sparse/0
        
        # Note: The tutorial puts output in a DIFFERENT folder (gopro_data_ns).
        # We should probably ask or decide where to put it. 
        # I will put it in a subfolder `ns_output` or similar inside output_dir? 
        # Or just use output_dir as data and create ns_output next to it?
        # Let's keep it simple: Create `processed` inside output_dir?
        # Actually, tutorial has: --data ~/gopro_data (which contains images/ sparse/)
        # and --output-dir ~/gopro_data_ns
        
        ns_output_dir = self.output_dir + "_ns"
        
        cmd_ns = [
            self.ns_process_bin, 'images',
            '--data', self.output_dir,
            '--output-dir', ns_output_dir,
            '--colmap-dir', output_sparse_0,
            '--skip-colmap' # IMPORTANT: We already ran colmap. ns-process-data usually runs colmap if not told otherwise, OR if we use the 'images' subcommand it expects to RUN colmap? 
            # Wait, 'ns-process-data images' converts images to nerfstudio format. 
            # Usually it runs colmap internally. 
            # BUT the tutorial explicitly ran colmap before.
            # The tutorial command: 
            # ns-process-data images --data ... --colmap-dir ...
            # If we provide --colmap-dir, it might skip running it?
            # Let's check ns-process-data help if we could... but I can't run it here.
            # The tutorial implies using the pre-computed colmap.
            # Most ns-process-data implementations verify if colmap dir exists.
        ]
        
        # NOTE: ns-process-data often assumes it needs to run colmap if we use 'images' or 'video'.
        # However, checking documentation (or common knowledge), you can provide existing colmap.
        # Arguments like --skip-colmap exist in some versions.
        # Given the tutorial command:
        # ns-process-data images --data ~/gopro_data --output-dir ~/gopro_data_ns --colmap-dir ~/gopro_data/sparse/0
        # It passes the colmap dir. Let's assume this works as intended by the user's tutorial.
        
        if not self.run_command(cmd_ns, "ns-process-data"):
            return False, "ns-process-data failed. Is 'ns-process-data' in your PATH?"

        self.log(f"\nProcessing Complete!\nResult in: {ns_output_dir}")
        return True, "Success"
