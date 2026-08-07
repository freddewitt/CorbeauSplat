"""Brush engine dependency installer."""
import contextlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from app.scripts.checksum_verifier import load_expected_checksums, verify_download_strict
from app.scripts.installers.base import EngineDependency
from app.scripts.installers.tools import install_rust_toolchain

BRUSH_REPO = "https://github.com/ArthurBrussee/brush.git"


class BrushEngineDep(EngineDependency):
    ask_before_update = True

    def __init__(self):
        super().__init__("brush", BRUSH_REPO)

    def is_enabled_in_config(self, config: dict) -> bool:
        return config.get("brush_params", {}).get("enabled", False) or config.get("brush_enabled", False)

    def get_remote_version(self) -> str:
        """Version cible : HEAD en mode source, version **épinglée** en mode release.

        En mode release, on ne suit délibérément pas la dernière release amont.
        L'archive est vérifiée contre une empreinte figée dans ce dépôt
        (``darwin_brush``/``linux_brush``) : suivre « latest » garantissait qu'au
        premier tag publié en amont, l'empreinte ne corresponde plus et que
        l'installation soit refusée — la panne constatée le 2026-08-07. Pire,
        ``base.py`` comparant cette valeur à la version locale, il aurait proposé
        la mise à jour à *chaque* démarrage, vers un échec certain.

        Version et empreinte vivent donc côte à côte dans ``checksums.json`` et
        se bumpent ensemble, en une seule modification relue. Adopter une
        nouvelle release reste un geste délibéré, pas un effet de bord du
        calendrier de publication d'un tiers.
        """
        config = {}
        with contextlib.suppress(OSError, json.JSONDecodeError):
            config = json.loads((self.root / "config.json").read_text())
        build_mode = config.get("brush_params", {}).get("build_mode", "release")

        if build_mode == "source":
            return self._get_head_commit()

        pinned = load_expected_checksums().get("brush_release", "")
        if not pinned:
            print("⚠️ Aucune version Brush épinglée (clé 'brush_release' de checksums.json).")
            return ""

        latest = self._fetch_latest_release_tag()
        if latest and latest != pinned:
            print(
                f"ℹ️  Brush {latest} est disponible en amont ; ce dépôt épingle {pinned}.\n"
                f"   Pour l'adopter : mettre à jour 'brush_release' ET l'empreinte "
                f"'darwin_brush'/'linux_brush' dans app/scripts/checksums.json.\n"
                f"   Empreintes publiées par le projet : "
                f"https://github.com/ArthurBrussee/brush/releases/download/{latest}/sha256.sum"
            )
        return pinned

    def _fetch_latest_release_tag(self) -> str:
        """Dernier tag publié en amont — purement informatif.

        Ne sert **pas** à choisir ce qui est installé (cf. ``get_remote_version``) :
        uniquement à signaler qu'un bump de l'épinglage est possible.
        """
        import json as _json
        import urllib.request
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/ArthurBrussee/brush/releases/latest",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "CorbeauSplat"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:  # nosec B310 - URL https littérale (API GitHub releases), pas de schéma file:
                return _json.loads(resp.read()).get("tag_name", "")
        except Exception as e:
            print(f"⚠️ Could not fetch latest Brush version: {e}")
            return ""

    def _get_head_commit(self) -> str:
        """Returns the short HEAD commit hash of the remote repo."""
        try:
            out = subprocess.check_output(
                ["git", "ls-remote", self.repo_url, "HEAD"], text=True, timeout=10
            ).strip()
            return out.split()[0][:12] if out else ""
        except Exception as e:
            print(f"⚠️ Could not fetch HEAD commit: {e}")
            return ""

    def install(self):
        config = {}
        with contextlib.suppress(OSError, json.JSONDecodeError):
            config = json.loads((self.root / "config.json").read_text())
        build_mode = config.get("brush_params", {}).get("build_mode", "release")

        if build_mode == "source":
            # Source mode tracks the HEAD commit, not a release tag
            remote_ref = self._get_head_commit()
            release_version = None
        else:
            # Pas de repli en dur ici : ce serait un troisième endroit où la
            # version vivrait, donc une troisième occasion de diverger de
            # l'empreinte. checksums.json est la seule source.
            remote_ref = self.get_remote_version()
            if not remote_ref:
                print("❌ Version Brush épinglée introuvable — installation annulée.")
                return
            release_version = remote_ref

        if self.bin_path.exists():
            local_ver = self.get_local_version()
            installed_as_source = "-source" in local_ver
            requested_source = (build_mode == "source")

            if installed_as_source != requested_source:
                print(f"Build mode changed ({'release → source' if requested_source else 'source → release'}). Replacing existing binary...")
                self.bin_path.unlink()
                if self.version_file.exists():
                    self.version_file.unlink()
            else:
                # Same mode — compare versions
                local_ref = local_ver.replace("-source", "")
                if remote_ref and local_ref == remote_ref:
                    print(f"Brush {local_ver} is already up to date.")
                    return
                elif remote_ref:
                    print(f"Brush update: {local_ref} → {remote_ref}. Updating...")
                    self.bin_path.unlink()
                    if self.version_file.exists():
                        self.version_file.unlink()
                else:
                    print("Brush installed, could not check for updates.")
                    return

        if build_mode == "source":
            head = remote_ref or "HEAD"
            print(f"Mode source sélectionné — compilation depuis HEAD ({head[:7]})...")
            if not self._install_from_source(head):
                print("❌ Compilation source échouée. Relancez après avoir vérifié votre installation Rust/cargo.")
        else:
            print(f"Mode release sélectionné ({release_version}). Téléchargement...")
            if not self._install_from_release(release_version):
                print("❌ Téléchargement release échoué. Vérifiez votre connexion.")

    def _install_from_release(self, version: str) -> bool:
        import platform
        import tarfile
        import urllib.request
        import zipfile

        system = platform.system()
        machine = platform.machine()

        platform_suffix = None
        if system == "Darwin" and machine == "arm64":
            platform_suffix = "aarch64-apple-darwin.tar.xz"
        elif system == "Windows" and machine == "AMD64":
            platform_suffix = "x86_64-pc-windows-msvc.zip"
        elif system == "Linux" and machine == "x86_64":
            platform_suffix = "x86_64-unknown-linux-gnu.tar.xz"

        if not platform_suffix:
            print(f"⚠️ No pre-built release for {system}/{machine}.")
            return False

        release_url = f"https://github.com/ArthurBrussee/brush/releases/download/{version}/brush-app-{platform_suffix}"
        print(f"Downloading Brush {version} from {release_url}...")

        archive_path = self.engines_dir / f"brush-app-{platform_suffix}"
        try:
            req = urllib.request.Request(release_url)
            with urllib.request.urlopen(req, timeout=120) as resp, open(str(archive_path), "wb") as out_f:  # nosec B310 - URL https littérale construite depuis le tag de release
                out_f.write(resp.read())
        except Exception as e:
            print(f"⚠️ Download failed: {e}")
            if archive_path.exists():
                archive_path.unlink()
            return False

        checksums = load_expected_checksums()
        checksum_key = "darwin_brush" if system == "Darwin" else "linux_brush"
        # Fail-closed: an unknown or mismatching hash aborts the install rather
        # than extracting and running an unverified binary.
        if not verify_download_strict(archive_path, checksums.get(checksum_key, "")):
            archive_path.unlink(missing_ok=True)
            print(
                f"❌ Brush archive SHA256 mismatch or missing reference hash "
                f"(checksum key: {checksum_key}) — installation refusée."
            )
            return False

        def _is_safe_member(name: str, dest: Path) -> bool:
            # Reject absolute paths and ``..`` traversal without resolving through
            # symlinks that a previous member may already have created.
            if os.path.isabs(name) or ".." in Path(name).parts:
                return False
            return (dest / name).is_relative_to(dest)

        print("Extracting Brush...")
        extract_dir = self.engines_dir / f"brush-extract-{version}"
        extract_dir.mkdir(exist_ok=True)
        dest_resolved = extract_dir.resolve()
        try:
            if archive_path.name.endswith(".zip"):
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    for member in zf.infolist():
                        if not _is_safe_member(member.filename, dest_resolved):
                            print(f"⚠️ Rejected unsafe archive member: {member.filename}")
                            continue
                        # Upper 16 bits of external_attr hold the Unix mode; 0xA000
                        # marks a symlink, which could redirect later members.
                        if (member.external_attr >> 16) & 0xF000 == 0xA000:
                            print(f"⚠️ Rejected symlink archive member: {member.filename}")
                            continue
                        zf.extract(member, extract_dir)
            else:
                with tarfile.open(archive_path, 'r:xz') as tf:
                    for tar_member in tf.getmembers():
                        if not _is_safe_member(tar_member.name, dest_resolved):
                            print(f"⚠️ Rejected unsafe archive member: {tar_member.name}")
                            continue
                        if tar_member.issym() or tar_member.islnk():
                            print(f"⚠️ Rejected link archive member: {tar_member.name}")
                            continue
                        tf.extract(tar_member, extract_dir)
        except Exception as e:
            print(f"⚠️ Extraction failed: {e}")
            archive_path.unlink(missing_ok=True)
            shutil.rmtree(str(extract_dir), ignore_errors=True)
            return False
        finally:
            archive_path.unlink(missing_ok=True)

        # Find the executable anywhere in the extracted tree
        extracted_bin = None
        bin_names = {"brush-app", "brush_app", "brush-app.exe", "brush_app.exe"}
        for root_dir, _dirs, files in os.walk(str(extract_dir)):
            for f in files:
                if f in bin_names:
                    extracted_bin = Path(root_dir) / f
                    break
            if extracted_bin:
                break

        if not extracted_bin:
            print("⚠️ Could not find brush executable in archive.")
            shutil.rmtree(str(extract_dir), ignore_errors=True)
            return False

        dest = self.engines_dir / "brush"
        shutil.move(str(extracted_bin), str(dest))
        shutil.rmtree(str(extract_dir), ignore_errors=True)

        if system != "Windows":
            os.chmod(str(dest), 0o755)  # nosec B103 - binaire moteur : doit être exécutable, hash vérifié en amont

        self.save_local_version(version)
        print(f"✅ Brush {version} installed successfully from release binary.")
        return True

    def _install_from_source(self, head_ref: str) -> bool:
        """Compiles Brush from the latest commit on the default branch (HEAD)."""
        print(f"Compiling Brush from source (HEAD: {head_ref[:7] if head_ref else '?'})...")
        cargo = shutil.which("cargo")
        if not cargo:
            if not install_rust_toolchain():
                return False
            cargo = shutil.which("cargo")
            if not cargo:
                print("❌ cargo still not found after Rust install.")
                return False

        # Ensure rustc is recent enough (brush deps require ≥ 1.95)
        rustup = shutil.which("rustup")
        try:
            rustc_out = subprocess.check_output(["rustc", "--version"], text=True).strip()
            # e.g. "rustc 1.94.0 (4a4ef493e 2026-03-02)"
            parts = rustc_out.split()
            if len(parts) >= 2:
                ver_parts = parts[1].split(".")
                major, minor = int(ver_parts[0]), int(ver_parts[1])
                if (major, minor) < (1, 95):
                    print(f"⚠️  {rustc_out} — Brush requires rustc ≥ 1.95. Mise à jour via rustup...")
                    if rustup:
                        subprocess.check_call([rustup, "update", "stable"])
                    else:
                        print("❌ rustup introuvable. Mettez à jour Rust manuellement : https://rustup.rs")
                        return False
        except (subprocess.CalledProcessError, OSError, IndexError, ValueError) as e:
            print(f"⚠️ Could not check rustc version: {e}. Letting cargo surface errors if needed.")

        # Build from HEAD (no --tag), try --locked first then without
        base_cmd = [cargo, "install", "--git", self.repo_url, "brush-app", "--root", str(self.engines_dir)]
        env = os.environ.copy()
        # Ensure cargo home bin is in PATH after potential rustup install
        cargo_bin = Path.home() / ".cargo" / "bin"
        if cargo_bin.exists():
            env["PATH"] = str(cargo_bin) + os.pathsep + env.get("PATH", "")

        success = False
        for extra in [["--locked"], []]:
            cmd = base_cmd + extra
            flag_str = " --locked" if extra else " (no lockfile)"
            print(f"cargo install{flag_str}...")
            try:
                subprocess.check_call(cmd, env=env)
                success = True
                break
            except subprocess.CalledProcessError as e:
                print(f"⚠️ Attempt failed{flag_str}: {e}")

        if not success:
            print("❌ Brush source compilation failed.")
            return False

        bin_dir = self.engines_dir / "bin"
        moved = False
        for name in ["brush-app", "brush_app", "brush", "brush-app.exe", "brush_app.exe"]:
            src = bin_dir / name
            if src.exists():
                shutil.move(str(src), str(self.engines_dir / "brush"))
                moved = True
                break
        shutil.rmtree(str(bin_dir), ignore_errors=True)

        if not moved:
            print("❌ Binary not found after compilation.")
            return False

        # Save HEAD commit as version identifier
        version_str = f"{head_ref[:12]}-source" if head_ref else "HEAD-source"
        self.save_local_version(version_str)
        print(f"✅ Brush compiled from HEAD ({head_ref[:7] if head_ref else '?'}) and installed.")
        return True
