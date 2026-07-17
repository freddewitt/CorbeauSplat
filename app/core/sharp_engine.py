import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Callable
from .base_engine import BaseEngine
from .system import resolve_project_root, is_apple_silicon

class SharpEngine(BaseEngine):
    """Moteur d'execution pour Apple ML Sharp"""
    
    def __init__(self, logger_callback=None):
        super().__init__("Sharp", logger_callback)
        self.process = None
        
    def _get_sharp_cmd(self):
        # 1. Look for .venv_sharp dedicated environment
        root_dir = resolve_project_root()
        sharp_venv_bin = root_dir / ".venv_sharp" / "bin"
        
        # Check binary in venv_sharp
        sharp_bin = sharp_venv_bin / "sharp"
        if sharp_bin.exists() and os.access(sharp_bin, os.X_OK):
            return [str(sharp_bin)]
            
        # Check python in venv_sharp -> run module
        sharp_python = sharp_venv_bin / "python3"
        if sharp_python.exists():
             return [str(sharp_python), "-m", "sharp.cli"]
 
        # 2. Try to find 'sharp' in the same bin dir as python executable (venv main)
        # Fallback if dedicated venv failed
        venv_bin = Path(sys.executable).parent
        sharp_bin = venv_bin / "sharp"
        if sharp_bin.exists() and os.access(sharp_bin, os.X_OK):
            return [str(sharp_bin)]
 
        # 3. Check global PATH
        from shutil import which
        if which("sharp"):
            return ["sharp"]
            
        # 4. Fallback: Run module
        return [sys.executable, "-m", "sharp.cli"]
    def is_installed(self):
        """Vérifie si Sharp est disponible (venv_sharp ou local)"""
        # Check venv_sharp binary
        root_dir = resolve_project_root()
        sharp_venv_bin = root_dir / ".venv_sharp" / "bin" / "sharp"
        if sharp_venv_bin.exists(): return True
        
        from shutil import which
        import importlib.util
        
        # 1. Check binary
        if which("sharp"): return True
        
        # 2. Check module
        if importlib.util.find_spec("sharp") is not None:
            return True
            
        return False

    def predict(self, input_path, output_path, params=None):
        """
        Lance la prediction Sharp.
        params: dict of prediction parameters
        """
        params = params or {}
        cmd = self._get_sharp_cmd()
        
        cmd.extend(["predict"])
        # Validate and resolve paths
        safe_input = self.validate_path(input_path)
        safe_output = self.validate_path(output_path)
        if safe_input is None:
            self.log(f"SECURITY: Invalid input path: {input_path}")
            return -1
        if safe_output is None:
            # Output may not exist yet — check parent
            out_parent = Path(output_path).parent
            if self.validate_path(str(out_parent)) is None:
                self.log(f"SECURITY: Invalid output path: {output_path}")
                return -1
            safe_output = Path(output_path).resolve()
        
        cmd.extend(["-i", str(safe_input)])
        cmd.extend(["-o", str(safe_output)])
        
        checkpoint = params.get("checkpoint")
        if checkpoint:
            safe_ckpt = self.validate_path(checkpoint)
            if safe_ckpt:
                cmd.extend(["-c", str(safe_ckpt)])
            else:
                self.log(f"SECURITY: Invalid checkpoint path: {checkpoint}")
            
        device = params.get("device", self.device)
        if device and device != "default":
            cmd.extend(["--device", device])
            
        if params.get("verbose"):
            cmd.append("--verbose")
            
        # Environnement
        env = os.environ.copy()
        
        # Ensure all args are strings for Popen
        cmd = [str(arg) for arg in cmd]
        
        self.log(f"Lancement Sharp: {' '.join(cmd)}")
        
        # GoF-Template Method : Délégation au runner 
        return self._execute_command(cmd, env=env)

    def process_video_frames(self, video_path: str, output_dir: str,
                             params: Optional[dict] = None,
                             log_callback: Optional[Callable] = None,
                             status_callback: Optional[Callable] = None,
                             progress_callback: Optional[Callable] = None,
                             cancel_check: Optional[Callable] = None) -> int:
        """Shared video frame extraction + Sharp prediction pipeline.
        
        Extracts frames from a video via ffmpeg, runs Sharp on each frame,
        collects resulting PLY files, and cleans up temporary data.
        
        Parameters
        ----------
        video_path: str
            Path to the input video file.
        output_dir: str
            Directory where output PLY files will be placed.
        params: dict, optional
            Sharp parameters (skip_frames, etc.).
        log_callback: callable, optional
            Called with each log message.
        status_callback: callable, optional
            Called with status updates.
        progress_callback: callable, optional
            Called with integer percentage (0-100).
        cancel_check: callable, optional
            Called before each frame; if returns True, processing stops.
            
        Returns
        -------
        int
            Number of successfully processed frames.
        """
        params = params or {}
        skip = max(1, int(params.get("skip_frames", 1)))
        
        vp = Path(video_path)
        out = Path(output_dir)
        
        frames_dir = out / "temp_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean previous frames
        for f in frames_dir.glob("*.png"):
            f.unlink()
        
        # Extract frames via ffmpeg
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        ffmpeg_cmd = [ffmpeg_bin]
        if is_apple_silicon():
            ffmpeg_cmd.extend(["-hwaccel", "videotoolbox"])
        ffmpeg_cmd.extend([
            "-y", "-i", str(vp),
            "-vf", f"select=not(mod(n\\,{skip}))",
            "-vsync", "vfr", "-q:v", "1",
            str(frames_dir / "frame_%04d.png"),
        ])
        
        if log_callback:
            log_callback(f"Running: {' '.join(ffmpeg_cmd)}")

        # Délégation au runner standard (Template Method) : rend l'extraction
        # annulable via self.stop() / self.runner.terminate(), contrairement à
        # un subprocess.run() bloquant.
        extraction_log = []

        def _ffmpeg_line(line_str):
            extraction_log.append(line_str)
            if log_callback:
                log_callback(line_str)

        returncode = self._execute_command(ffmpeg_cmd, line_callback=_ffmpeg_line, timeout=3600)

        if self.stop_requested:
            if log_callback:
                log_callback("--- Arrêté par l'utilisateur ---")
            shutil.rmtree(frames_dir, ignore_errors=True)
            return 0

        if returncode != 0:
            if log_callback:
                log_callback(f"FFmpeg error (code {returncode}): {' | '.join(extraction_log[-5:])}")
            shutil.rmtree(frames_dir, ignore_errors=True)
            return 0
        
        frames = sorted(frames_dir.glob("*.png"))
        total_frames = len(frames)
        
        if total_frames == 0:
            if log_callback:
                log_callback("Aucune frame extraite.")
            shutil.rmtree(frames_dir, ignore_errors=True)
            return 0
        
        if log_callback:
            log_callback(f"Total frames extraites: {total_frames}")
        
        success_count = 0
        for idx, frame_path in enumerate(frames):
            if cancel_check and cancel_check():
                if log_callback:
                    log_callback("--- Arrêté par l'utilisateur ---")
                break
            
            display_idx = idx + 1
            if status_callback:
                status_callback(f"Processing frame {display_idx}/{total_frames}")
            if log_callback:
                log_callback(f"Processing frame {display_idx}/{total_frames}: {frame_path.name}")
            
            frame_out_dir = out / frame_path.stem
            returncode = self.predict(str(frame_path), str(frame_out_dir), params)
            
            if returncode == 0:
                ply_files = list(frame_out_dir.rglob("*.ply"))
                if ply_files:
                    dest_ply = out / f"{frame_path.stem}.ply"
                    shutil.copy2(ply_files[0], dest_ply)
                    if log_callback:
                        log_callback(f"Saved: {dest_ply.name}")
                    success_count += 1
            
            if progress_callback:
                progress_callback(int((display_idx / total_frames) * 100))
            
            if frame_out_dir.exists():
                shutil.rmtree(frame_out_dir)
        
        # Cleanup temp frames
        if frames_dir.exists():
            shutil.rmtree(frames_dir, ignore_errors=True)
        
        return success_count
