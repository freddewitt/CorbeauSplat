"""
upscayl_manager.py — Finds, installs and manages the upscayl-bin binary (Windows).

Priority order for binary discovery:
  1. ./bin/upscayl-bin.exe     (embedded, downloaded at runtime)
  2. which upscayl-bin         (on PATH)
"""
import json
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from app.core.system import resolve_project_root
from app.scripts.checksum_verifier import load_expected_checksums, verify_download

GITHUB_API = "https://api.github.com/repos/upscayl/upscayl-ncnn/releases/latest"


def _is_windows() -> bool:
    return os.name == "nt" or platform.system() == "Windows"


def bin_filename() -> str:
    """Executable file name for the current platform."""
    return "upscayl-bin.exe" if _is_windows() else "upscayl-bin"


def get_bin_dir() -> Path:
    return resolve_project_root() / "bin"


def get_models_dir() -> Path:
    """Returns our local models directory (for downloads)."""
    p = resolve_project_root() / "models" / "upscayl"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_effective_models_dir() -> Path | None:
    """
    Returns the models directory to pass to upscayl-bin via -m, or None
    if the binary should use its own bundled/default model location.

    Priority:
      1. Our local ./models/upscayl/ if it contains model files → pass -m
      2. Models folder next to the binary (app bundle) → pass -m
      3. Otherwise → return None (let upscayl-bin find its own models)
    """
    local = get_models_dir()
    if any(local.glob("*.bin")):
        return local

    binary = find_binary()
    if binary:
        candidates = [
            binary.parent / "models",
            binary.parent.parent / "models",
            binary.parent.parent / "Resources" / "models",
            binary.parent.parent.parent / "Resources" / "models",
        ]
        for c in candidates:
            if c.exists() and any(c.glob("*.bin")):
                return c

    return None  # let upscayl-bin use its default model path


def is_using_local_binary() -> bool:
    """True if we downloaded our own binary (not using system/app install)."""
    local = get_bin_dir() / bin_filename()
    return local.exists() and os.access(local, os.X_OK)


def find_binary() -> Path | None:
    """Returns the first usable upscayl-bin, or None."""
    local = get_bin_dir() / bin_filename()
    if local.exists() and os.access(local, os.X_OK):
        return local

    which = shutil.which("upscayl-bin")
    if which:
        return Path(which)

    return None


def get_version(binary: Path) -> str:
    """Returns a short version/info string from the binary."""
    try:
        result = subprocess.run(
            [str(binary)], capture_output=True, text=True, timeout=5
        )
        output = result.stdout + result.stderr
        for line in output.splitlines():
            line = line.strip()
            if line and ("upscayl" in line.lower() or "version" in line.lower() or "ncnn" in line.lower()):
                return line[:80]
        return "upscayl-bin"
    except Exception:
        return "upscayl-bin"


def _fetch_release() -> dict:
    req = urllib.request.Request(GITHUB_API, headers={"User-Agent": "CorbeauSplat"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _find_windows_asset(assets: list) -> dict | None:
    """Finds the Windows release asset."""
    for a in assets:
        name = a["name"].lower()
        if ("windows" in name or "win64" in name or "win32" in name or "win" in name) and \
                name.endswith((".zip", ".7z")):
            return a
    # Fallback: any windows-named asset
    for a in assets:
        name = a["name"].lower()
        if "windows" in name or "win" in name:
            return a
    return None


def download_binary(log_callback=None) -> Path:
    """
    Downloads the latest upscayl-bin release for Windows.
    Extracts binary to ./bin/ and bundled models to ./models/upscayl/.
    Returns the installed binary path.
    Raises RuntimeError on failure.
    """
    def log(msg: str):
        if log_callback:
            log_callback(msg)
        print(msg)

    log("Fetching latest upscayl-ncnn release info...")
    release = _fetch_release()
    asset = _find_windows_asset(release.get("assets", []))
    if not asset:
        raise RuntimeError("No Windows release asset found on GitHub.")

    size_mb = asset["size"] // 1024 // 1024
    log(f"Downloading {asset['name']} ({size_mb} MB)...")

    bin_dir = get_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    archive_path = bin_dir / asset["name"]

    req = urllib.request.Request(asset["browser_download_url"])
    with urllib.request.urlopen(req, timeout=120) as resp, open(str(archive_path), "wb") as f:
        f.write(resp.read())

    checksums = load_expected_checksums()
    checksum_key = "windows_upscayl" if _is_windows() else "linux_upscayl"
    if not verify_download(archive_path, checksums.get(checksum_key, "")):
        log(f"⚠️ upscayl archive SHA256 mismatch (checksum key: {checksum_key}). Continuing anyway.")

    log("Extracting...")

    models_dir = get_models_dir()
    _extract_archive(archive_path, bin_dir, models_dir, log)
    archive_path.unlink(missing_ok=True)

    dest = bin_dir / bin_filename()
    if not dest.exists():
        raise RuntimeError(f"{bin_filename()} not found after extraction.")

    if not _is_windows():
        os.chmod(dest, 0o755)
    log(f"✅ {bin_filename()} installed: {dest}")
    return dest


def _extract_archive(archive: Path, bin_dest: Path, models_dest: Path, log):
    """Extracts upscayl-bin and *.bin/*.param model files from an archive."""
    bin_dest_resolved = bin_dest.resolve()
    models_dest_resolved = models_dest.resolve()

    def is_safe_extraction(name: str, allowed_dirs: list) -> bool:
        for allowed in allowed_dirs:
            resolved = (allowed / Path(name).name).resolve()
            try:
                resolved.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False

    target_bin = bin_filename()

    def handle_member(name: str, read_fn):
        fname = Path(name).name
        if fname in ("upscayl-bin", "upscayl-bin.exe"):
            if not is_safe_extraction(name, [bin_dest_resolved]):
                log(f"  ⚠️ Rejected unsafe member: {name}")
                return
            out = bin_dest / target_bin
            out.write_bytes(read_fn())
            log(f"  → {out}")
        elif fname.endswith(".bin") or fname.endswith(".param"):
            if not is_safe_extraction(name, [models_dest_resolved]):
                log(f"  ⚠️ Rejected unsafe member: {name}")
                return
            out = models_dest / fname
            if not out.exists():
                out.write_bytes(read_fn())
                log(f"  → models/{fname}")

    name_lower = archive.name.lower()
    if name_lower.endswith(".zip"):
        with zipfile.ZipFile(archive, "r") as zf:
            for info in zf.infolist():
                handle_member(info.filename, lambda i=info: zf.read(i.filename))
    elif name_lower.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive, "r:gz") as tf:
            for member in tf.getmembers():
                if member.isfile():
                    handle_member(member.name, lambda m=member: tf.extractfile(m).read())
    else:
        log(f"Unknown archive format: {archive.name}")


def run_upscayl(input_path, output_path, params,
                log_callback=None, progress_callback=None, done_callback=None,
                cancel_check=None):
    """
    Runs upscayl-bin as a blocking subprocess (call from a worker thread).

    params keys:
      bin_path    — path to upscayl-bin (auto-detected if absent)
      model_id    — model name without extension
      models_dir  — path to models folder (auto-detected if absent)
      scale       — int: 2, 3 or 4 (native scale used with -s)
      format      — 'png', 'jpg' or 'webp'
      tile        — int tile size, 0 = auto
      tta         — bool
      compression — int 0-100 (ignored for png)

    Calls done_callback(success: bool) when finished.
    """
    def _log(msg):
        if log_callback:
            log_callback(msg)

    binary = params.get("bin_path") or find_binary()
    if not binary or not os.access(str(binary), os.X_OK):
        _log("❌ upscayl-bin introuvable ou non exécutable.")
        if done_callback:
            done_callback(False)
        return

    model_id = params.get("model_id", "")
    if not model_id:
        _log("❌ Aucun modèle upscayl sélectionné.")
        if done_callback:
            done_callback(False)
        return

    models_dir = params.get("models_dir") or get_effective_models_dir()
    if models_dir:
        models_dir = Path(models_dir)
        if not (models_dir / f"{model_id}.bin").exists() or \
                not (models_dir / f"{model_id}.param").exists():
            _log(f"❌ Modèle introuvable : {model_id} (.bin/.param manquant dans {models_dir})")
            if done_callback:
                done_callback(False)
            return

    Path(output_path).mkdir(parents=True, exist_ok=True)

    scale       = params.get("scale", 4)
    fmt         = params.get("format", "png")
    tile        = params.get("tile", 0)
    tta         = params.get("tta", False)
    compression = params.get("compression", 0)

    cmd = [
        str(binary),
        "-i", str(input_path),
        "-o", str(output_path),
        "-n", model_id,
        "-s", str(scale),
        "-f", fmt,
        "-t", str(tile),
    ]
    if models_dir:
        models_arg = os.path.relpath(str(models_dir), str(Path(binary).parent))
        cmd += ["-m", models_arg]
    if tta:
        cmd.append("-x")
    if compression > 0 and fmt in ("jpg", "webp"):
        cmd += ["-c", str(compression)]

    _log(f"upscayl-bin: {' '.join(cmd)}")
    success = False
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in proc.stdout:
            if cancel_check and cancel_check():
                proc.terminate()
                _log("⚠ Upscale interrompu par l'utilisateur.")
                break
            _log(line.rstrip())
        proc.wait()
        success = (proc.returncode == 0) and not (cancel_check and cancel_check())
        if proc.returncode != 0 and not (cancel_check and cancel_check()):
            _log(f"❌ upscayl-bin a retourné le code {proc.returncode}")
    except Exception as e:
        _log(f"❌ Exception upscayl : {e}")

    if done_callback:
        done_callback(success)


def resize_to_original(upscaled_dir, original_sizes_dict):
    """
    Resize each image in upscaled_dir back to its original (pre-upscale) size.
    original_sizes_dict = { 'filename.png': (width, height), ... }
    Uses Pillow LANCZOS resampling.
    """
    from PIL import Image
    upscaled_dir = Path(upscaled_dir)
    for filename, (orig_w, orig_h) in original_sizes_dict.items():
        src = upscaled_dir / filename
        if not src.exists():
            continue
        with Image.open(src) as img:
            resized = img.resize((orig_w, orig_h), Image.LANCZOS)
            resized.save(src)


def download_model_files(url_bin: str, url_param: str,
                         model_id: str, log_callback=None) -> bool:
    """Downloads a single model's .bin and .param files."""
    import hashlib
    def log(msg):
        if log_callback:
            log_callback(msg)

    from app.upscayl_models import get_model
    model = get_model(model_id)

    models_dir = get_models_dir()
    ok = True
    for url, ext, sha_attr in [(url_bin, ".bin", "sha256_bin"), (url_param, ".param", "sha256_param")]:
        dest = models_dir / f"{model_id}{ext}"
        if dest.exists() and dest.stat().st_size > 1024:
            # Verify existing file integrity if SHA256 is configured
            if model:
                expected = getattr(model, sha_attr, "")
                if expected:
                    actual = hashlib.sha256(dest.read_bytes()).hexdigest()
                    if actual == expected:
                        log(f"  ✅ {dest.name} (already present, checksum OK)")
                        continue
                    else:
                        log(f"  ⚠️ {dest.name} checksum mismatch, re-downloading...")
                        dest.unlink()
                else:
                    log(f"  Already present: {dest.name}")
                    continue
            else:
                log(f"  Already present: {dest.name}")
                continue
        try:
            log(f"Downloading {model_id}{ext}...")
            req = urllib.request.Request(url, headers={"User-Agent": "CorbeauSplat"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()

            if len(data) < 512:
                log(f"  ❌ {dest.name}: unexpected response ({len(data)} bytes). URL: {url}")
                dest.unlink(missing_ok=True)
                ok = False
                continue

            dest.write_bytes(data)

            # Verify integrity after download
            if model:
                expected = getattr(model, sha_attr, "")
                if expected:
                    actual = hashlib.sha256(data).hexdigest()
                    if actual == expected:
                        log(f"  ✅ {dest.name} ({len(data) // 1024 // 1024} MB, checksum OK)")
                    else:
                        log(f"  ❌ {dest.name}: SHA256 mismatch (expected {expected[:16]}..., got {actual[:16]}...)")
                        dest.unlink(missing_ok=True)
                        ok = False
                        continue
                else:
                    log(f"  ✅ {dest.name} ({len(data) // 1024 // 1024} MB)")
            else:
                log(f"  ✅ {dest.name} ({len(data) // 1024 // 1024} MB)")
        except Exception as e:
            log(f"  ❌ {dest.name}: {e}")
            dest.unlink(missing_ok=True)
            ok = False
    return ok
