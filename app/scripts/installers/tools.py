"""Utility functions for dependency management — installers, checkers, helpers."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.scripts.checksum_verifier import load_expected_checksums, verify_download

# ─────────────────────────────────────────────────────────────────────────────
# Config and requirements helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_config():
    """Loads config.json from project root/cwd"""
    p = Path("config.json")
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load config.json: {e}")
    return {}


def relax_requirements(src, dst):
    """Refactor utils: Relax strict torch deps"""
    with open(src) as f_in, open(dst, 'w') as f_out:
        for line in f_in:
            if line.strip().startswith('torch==') or line.strip().startswith('torchvision=='):
                line = line.replace('==', '>=')
            f_out.write(line)


# ─────────────────────────────────────────────────────────────────────────────
# Version helpers (standalone functions)
# ─────────────────────────────────────────────────────────────────────────────

def get_remote_version(repo_url):
    """Gets the latest commit hash from the remote git repository"""
    try:
        output = subprocess.check_output(["git", "ls-remote", repo_url, "HEAD"], text=True).strip()
        if output:
            return output.split()[0]
    except Exception as e:
        print(f"Attention: Impossible de verifier la version distante pour {repo_url}: {e}")
    return None


def get_local_version(version_file: Path):
    if version_file.exists():
        try:
            return version_file.read_text().strip()
        except OSError:
            pass
    return None


def save_local_version(version_file: Path, version):
    if version:
        try:
            version_file.parent.mkdir(parents=True, exist_ok=True)
            version_file.write_text(version)
        except Exception as e:
            print(f"Attention: Impossible d'enregistrer la version locale: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Checkers
# ─────────────────────────────────────────────────────────────────────────────

def check_cargo():
    return shutil.which("cargo") is not None


def check_brew():
    return shutil.which("brew") is not None


def check_node():
    return shutil.which("node") is not None and shutil.which("npm") is not None


def check_cmake_ninja():
    return shutil.which("cmake") is not None and shutil.which("ninja") is not None


def check_xcode_tools():
    """Checks if Xcode Command Line Tools are installed (macOS only)"""
    if sys.platform != "darwin":
        return True
    try:
        # xcode-select -p prints the path if installed, or exits with error
        subprocess.check_call(["xcode-select", "-p"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Installers helpers
# ─────────────────────────────────────────────────────────────────────────────

def install_node_js():
    print("Installing Node.js via Homebrew...")
    try:
        subprocess.check_call(["brew", "install", "node"])
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"Error installing Node.js: {e}")
        return False


def install_build_tools():
    print("Installing CMake & Ninja via Homebrew...")
    try:
        subprocess.check_call(["brew", "install", "cmake", "ninja"])
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"Error installing build tools: {e}")
        return False


def install_rust_toolchain():
    print("Installing Rust (cargo)...")
    import tempfile
    import urllib.request
    try:
        rustup_path = Path(tempfile.mkstemp(suffix=".sh")[1])
        req = urllib.request.Request("https://sh.rustup.rs")
        with urllib.request.urlopen(req, timeout=30) as resp:
            rustup_path.write_bytes(resp.read())

        checksums = load_expected_checksums()
        checksum_key = "darwin_rustup" if sys.platform == "darwin" else "linux_rustup"
        if not verify_download(rustup_path, checksums.get(checksum_key, "")):
            print(f"⚠️ rustup installer SHA256 mismatch (checksum key: {checksum_key}). Continuing anyway.")

        rustup_path.chmod(0o755)
        subprocess.check_call([str(rustup_path), "-y"])
        rustup_path.unlink()

        # Add to current path for this session
        cargo_bin = Path.home() / ".cargo" / "bin"
        if cargo_bin.exists():
            os.environ["PATH"] = str(cargo_bin) + os.pathsep + os.environ["PATH"]
            print("Rust installed and added to PATH.")
            return True
    except Exception as e:
        print(f"Error installing Rust: {e}")
    return False


def install_system_dependencies(check_only=False):
    print("--- System Dependency Check (Homebrew) ---")
    missing = []
    for cmd in ["colmap", "ffmpeg"]:
        if shutil.which(cmd) is None:
            missing.append(cmd)

    if sys.platform == "darwin":
        try:
             # Check for libomp and freeimage
             if subprocess.run(["brew", "list", "libomp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                 missing.append("libomp")
             if subprocess.run(["brew", "list", "freeimage"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                 missing.append("freeimage")
        except (subprocess.CalledProcessError, OSError):
            print("⚠️ Could not check brew packages (libomp/freeimage).")

    if not missing:
        print("✅ System dependencies present.")
        return True

    print(f"Missing: {', '.join(missing)}")
    if check_only:
        print("ℹ️ Audit mode: automatic installation skipped.")
        return False

    if shutil.which("brew") is None:
        print("ERROR: Homebrew required.")
        return False

    print("Installing via Homebrew...")
    try:
        if "colmap" in missing:
            subprocess.check_call(["brew", "install", "colmap"])
        if "ffmpeg" in missing:
            subprocess.check_call(["brew", "install", "ffmpeg"])
        if "libomp" in missing:
            subprocess.check_call(["brew", "install", "libomp"])
        if "freeimage" in missing:
            subprocess.check_call(["brew", "install", "freeimage"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"System installation failed: {e}")
        return False
