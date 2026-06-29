import json
import logging
import os
import platform
import re
import shutil
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .base_engine import BaseEngine
from .i18n import tr
from .system import get_optimal_threads, has_cuda, resolve_binary

_IMAGE_EXTS = {'.jpg', '.jpeg', '.png'}
_VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv'}


def _imread_unicode(path, flags):
    """cv2.imread that tolerates non-ASCII paths on Windows (cv2 fails on them)."""
    import cv2
    import numpy as np
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, flags)
    except (OSError, ValueError):
        return None


def _imwrite_unicode(path, img) -> bool:
    """cv2.imwrite that tolerates non-ASCII paths on Windows. Returns success.

    Encodes to an in-memory buffer first, then unlinks the destination before
    writing a fresh file — this both breaks any hardlink (so a hardlinked
    original is never modified) and avoids leaving the file deleted if encoding
    fails.
    """
    import cv2
    p = Path(path)
    suffix = p.suffix or ".png"
    params = []
    if suffix.lower() in (".jpg", ".jpeg"):
        # JPEG can't store an alpha channel and defaults to lossy quality 95.
        # Drop alpha (IMREAD_UNCHANGED may return 4 channels) and re-encode at
        # max quality so an in-place resize doesn't silently degrade the frame
        # or fail outright on a 4-channel image.
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        params = [cv2.IMWRITE_JPEG_QUALITY, 100]
    ok, buf = cv2.imencode(suffix, img, params)
    if not ok:
        return False
    try:
        p.unlink(missing_ok=True)
        buf.tofile(str(p))
        return True
    except OSError:
        return False


def _first_available_model() -> str:
    try:
        from app.upscayl_manager import get_models_dir
        from app.upscayl_models import get_downloaded_models
        models = get_downloaded_models(get_models_dir())
        return models[0].id if models else ""
    except Exception:
        return ""


def select_blurry_files(scores: dict, factor: float, max_remove_frac: float = 0.2):
    """Selects which files to discard as too blurry.

    A file is blurry if its sharpness score (variance of Laplacian) is below
    ``factor × median(scores)``. To avoid gutting the dataset, never removes
    more than ``max_remove_frac`` of the files (only the blurriest are kept as
    candidates if the cap is exceeded). Default cap is 20% — on shaky video a
    lower-than-median threshold can otherwise flag a large fraction of frames.

    Returns (rejected_files: list, threshold: float).
    """
    import statistics
    if not scores or factor <= 0:
        return [], 0.0
    median = statistics.median(scores.values())
    threshold = median * factor
    rejected = [f for f, s in scores.items() if s < threshold]
    cap = int(len(scores) * max_remove_frac)
    if len(rejected) > cap:
        rejected = sorted(rejected, key=lambda f: scores[f])[:cap]
    return rejected, threshold


class ColmapEngine(BaseEngine):
    """Moteur d'exécution COLMAP indépendant de l'interface graphique"""

    def __init__(self, params: Any, input_path: str, output_path: str, input_type: str, fps: int, project_name: str = "Untitled", logger_callback: Callable | None = None, progress_callback: Callable | None = None, status_callback: Callable | None = None, check_cancel_callback: Callable | None = None):
        """Initialise le moteur COLMAP avec les paramètres de configuration."""
        super().__init__("COLMAP", logger_callback)
        self.params = params
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.input_type = input_type
        self.fps = fps
        self.project_name = project_name
        self.has_cuda = has_cuda()
        self.num_threads = get_optimal_threads()
        self._current_process = None
        self.progress = progress_callback if progress_callback else lambda x: None
        self.status = status_callback if status_callback else lambda x: None
        self.check_cancel = check_cancel_callback if check_cancel_callback else lambda: False
        self.logger = logging.getLogger(__name__)

        # Resolve binaries
        self.ffmpeg_bin = resolve_binary('ffmpeg') or 'ffmpeg'
        self.colmap_bin = resolve_binary('colmap') or 'colmap'
        self.glomap_bin = resolve_binary('glomap') or 'glomap'

        # Pre-load cv2 on the main thread to avoid Bus Error (SIGBUS)
        try:
            import cv2
            self._cv2_loaded = True
        except ImportError:
            self._cv2_loaded = False

        if self.has_cuda:
            self.log(f"GPU NVIDIA CUDA détecté - {self.num_threads} threads, accélération GPU activée")
        else:
            self.log(f"Aucun GPU CUDA détecté - exécution CPU ({self.num_threads} threads)")
        self.log(f"Binaires: {self.colmap_bin}, {self.ffmpeg_bin}, {self.glomap_bin}")

    @property
    def project_path(self) -> Path:
        """Alias pour le chemin de sortie utilisé par les Workers et l'UI."""
        return self.output_path

    def is_cancelled(self) -> bool:
        """Vérifie si l'utilisateur a demandé l'annulation."""
        return self.check_cancel()

    def run(self) -> tuple[bool, str]:
        """Exécute le pipeline complet de reconstruction."""
        try:
            setup_result = self._validate_and_setup_paths()
            if not setup_result: return False, "Erreur de validation des chemins"
            project_dir, images_dir, checkpoints_dir = setup_result

            if not self._process_input(project_dir, images_dir):
                if self.is_cancelled(): return False, tr("USER_CANCELLED")
                return False, "Erreur lors de la preparation de l'entree"

            pipeline_result, msg = self._run_reconstruction_pipeline(project_dir, images_dir)
            return pipeline_result, msg

        except Exception as e:
            self.log(f"Erreur lors de l'exécution du pipeline: {e}")
            self.logger.error("Exception in pipeline", exc_info=True)
            if self.is_cancelled(): return False, "Arrete par l'utilisateur"
            return False, "Une erreur est survenue lors du traitement."

    def _validate_and_setup_paths(self) -> tuple[Path, Path, Path] | None:
        """Valide les chemins d'entrée/sortie et prépare la structure des dossiers."""
        safe_output = self.validate_path(str(self.output_path))
        if not safe_output:
            self.log("Chemin de sortie non sécurisé")
            return None
        self.output_path = safe_output

        if ".." in self.project_name or "/" in self.project_name or "\\" in self.project_name:
            self.log("Nom de projet invalide")
            return None

        project_dir = self.output_path / self.project_name
        images_dir = project_dir / "images"
        checkpoints_dir = project_dir / "checkpoints"

        project_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir.mkdir(parents=True, exist_ok=True)

        self.log(f"Préparation du projet dans : {project_dir}")

        raw_input = str(self.input_path)
        if "|" in raw_input:
            self.log("Validation de multiples chemins d'entree...")
            for p in raw_input.split("|"):
                if not self.validate_path(p.strip()):
                    self.log(f"Chemin d'entrée non sécurisé : {p}")
                    return None

            first_path = Path(raw_input.split("|")[0].strip())
            if not first_path.exists():
                self.log(f"Entrée introuvable: {first_path}")
                return None
        else:
            if not self.validate_path(raw_input):
                 self.log(f"Chemin d'entrée non sécurisé: {raw_input}")
                 return None
            if not self.input_path.exists():
                 self.log(f"Entrée introuvable: {self.input_path}")
                 return None

        return project_dir, images_dir, checkpoints_dir

    def _process_input(self, project_dir: Path, images_dir: Path) -> bool:
        """Prépare les images sources (extraction vidéo ou copie)."""
        self.status(tr("status_prep_images", "Préparation des visuels..."))
        if not self._prepare_images(images_dir):
            return False

        # Discard blurry frames before reconstruction (best on the raw frames,
        # i.e. before upscaling). Optional and never fatal.
        if getattr(self.params, 'filter_blurry', False):
            self.status(tr("status_blur_filter", "Filtrage des images floues..."))
            self._filter_blurry_images(images_dir, getattr(self.params, 'blur_factor', 0.7))

        upscale_conf = getattr(self, 'upscale_config', None)
        if upscale_conf and upscale_conf.get("active", False):
            self.status(tr("status_upscaling", "Upscaling des images..."))
            if not self._run_upscale(project_dir, images_dir):
                return False

        if not self._check_and_normalize_resolution(images_dir):
            return False

        return True

    # Params that change the contents of database.db (features + matches). If any
    # differ from a previous run, the DB must NOT be reused.
    _DB_SIG_KEYS = (
        'camera_model', 'single_camera', 'max_image_size', 'max_num_features',
        'estimate_affine_shape', 'domain_size_pooling',
        'matcher_type', 'max_ratio', 'max_distance', 'cross_check',
        'guided_matching', 'sequential_overlap',
    )

    def _db_sig_path(self, database_path: Path) -> Path:
        return Path(str(database_path) + ".sig.json")

    def _db_signature(self, images_dir: Path) -> dict:
        sig = {k: getattr(self.params, k, None) for k in self._DB_SIG_KEYS}
        sig['image_count'] = len(self._current_image_names(images_dir))
        return sig

    def _current_image_names(self, images_dir: Path) -> set:
        """Relative posix names of the images COLMAP would ingest (matches the
        filter used by _write_sorted_image_list and stored in the DB)."""
        root = Path(images_dir)
        if not root.exists():
            return set()
        return {
            f.relative_to(root).as_posix()
            for f in root.rglob('*')
            if f.is_file()
            and f.suffix.lower() in _IMAGE_EXTS
            and not f.name.lower().endswith('.mask.png')
        }

    def _write_db_signature(self, database_path: Path, images_dir: Path) -> None:
        try:
            self._db_sig_path(database_path).write_text(
                json.dumps(self._db_signature(images_dir)), encoding='utf-8'
            )
        except OSError as e:
            self.log(f"(info) Impossible d'écrire la signature de reprise : {e}")

    def _database_is_reusable(self, database_path: Path, images_dir: Path) -> bool:
        """True only if database.db can be safely resumed from: it has features
        AND geometrically-verified matches for EXACTLY the current image set, and
        the extraction/matching params are unchanged since it was built.

        Conservative by design — any missing data, mismatch, or error returns
        False so the pipeline rebuilds from scratch (never reuse a stale DB).
        """
        if not database_path.exists():
            return False
        # 1. Params + image-count signature must match the stored one.
        try:
            stored = json.loads(self._db_sig_path(database_path).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return False
        if stored != self._db_signature(images_dir):
            return False
        current = self._current_image_names(images_dir)
        if not current:
            return False
        # 2. The DB must actually contain features + verified matches for exactly
        #    those images.
        try:
            con = sqlite3.connect(str(database_path))
            try:
                tables = {r[0] for r in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if not {'images', 'descriptors'} <= tables:
                    return False
                db_names = {r[0] for r in con.execute("SELECT name FROM images")}
                if db_names != current:
                    return False
                n_images = con.execute("SELECT COUNT(*) FROM images").fetchone()[0]
                n_desc = con.execute(
                    "SELECT COUNT(*) FROM descriptors WHERE rows > 0").fetchone()[0]
                if n_desc < n_images:
                    return False
                # verified matches (what the mapper consumes); fall back to raw
                if 'two_view_geometries' in tables:
                    verified = con.execute(
                        "SELECT COUNT(*) FROM two_view_geometries WHERE rows > 0").fetchone()[0]
                elif 'matches' in tables:
                    verified = con.execute(
                        "SELECT COUNT(*) FROM matches WHERE rows > 0").fetchone()[0]
                else:
                    return False
                return verified > 0
            finally:
                con.close()
        except sqlite3.Error:
            return False

    def _run_reconstruction_pipeline(self, project_dir: Path, images_dir: Path) -> tuple[bool, str]:
        """Exécute les étapes de reconstruction COLMAP."""
        database_path = project_dir / "database.db"
        sparse_dir = project_dir / "sparse"
        # The sparse model is the mapper's output — always rebuilt fresh.
        if sparse_dir.exists():
            shutil.rmtree(sparse_dir)
            self.log(f"Reconstruction sparse precedente supprimee : {sparse_dir.name}")
        sparse_dir.mkdir(exist_ok=True)

        # Resume: if a previous run already extracted features AND matched them for
        # EXACTLY these images with the SAME params, skip extraction + matching and
        # go straight to the mapper. Guarded conservatively — any mismatch redoes
        # everything, so a stale DB can never silently corrupt the result.
        if self._database_is_reusable(database_path, images_dir):
            self.log("♻️ Base COLMAP existante valide pour ces images (mêmes paramètres) "
                     "— extraction et matching ignorés, reprise directe au mapper.")
            self.status("Reprise : base COLMAP réutilisée")
            self.progress(75)
        else:
            # Start from a fresh database to avoid SQLite schema incompatibilities
            # (especially between COLMAP and GLOMAP's bundled SQLite versions) and
            # stale features.
            for db_file in [database_path,
                            database_path.with_suffix(".db-wal"),
                            database_path.with_suffix(".db-shm"),
                            self._db_sig_path(database_path)]:
                if db_file.exists():
                    db_file.unlink(missing_ok=True)
                    self.log(f"Base de données précédente supprimée : {db_file.name}")

            self.progress(25)

            if self.is_cancelled(): return False, tr("USER_CANCELLED")
            self.status(tr("status_feature_extraction", "Analyse des images en cours..."))
            if not self.feature_extraction(str(database_path), str(images_dir)):
                return False, "Échec extraction features"
            if self.params.matcher_type == 'sequential':
                self.log("Tri de la base de données COLMAP (ordre temporel des images)...")
                self.status("Préparation du matching séquentiel...")
                self._sort_colmap_database_images(database_path)
                self.log("Base triée. Démarrage du matching.")

            self.progress(50)

            if self.is_cancelled(): return False, tr("USER_CANCELLED")
            self.status(tr("status_feature_matching", "Recherche des points communs..."))
            # The matcher first loads every image's descriptors into RAM before it
            # prints anything — on a large dataset that can be several minutes with
            # no output. Warn so the run doesn't look frozen.
            self.log("⏳ Matching en cours — COLMAP charge les descripteurs en mémoire. "
                     "Cette première phase peut durer plusieurs minutes sans affichage, "
                     "c'est normal, ne fermez pas le programme.")
            if not self.feature_matching(str(database_path)):
                return False, "Échec matching"

            # Stamp the DB so a later run can safely resume from it.
            self._write_db_signature(database_path, images_dir)

        self.progress(75)

        if self.is_cancelled(): return False, tr("USER_CANCELLED")

        # GLOMAP's bundled SQLite does not support WAL journal mode created by
        # recent COLMAP versions. Convert the database to DELETE mode before
        # handing it off to GLOMAP.
        if self.params.use_glomap:
            self._convert_db_journal_mode(database_path)

        self.status(tr("status_reconstruction", "Création de la scène 3D..."))
        if not self.mapper(str(database_path), str(images_dir), str(sparse_dir)):
            return False, "Échec reconstruction"

        # With multiple_models on, COLMAP writes sub-models (sparse/0, sparse/1, …)
        # in no particular size order. Brush and the undistorter use sparse/0, so
        # make sure sparse/0 is the model with the MOST registered images —
        # otherwise training can land on a tiny fragment (e.g. 11 of 3000 images).
        self._promote_largest_sparse_model(sparse_dir)

        self.progress(90)

        if self.params.undistort_images:
            if self.is_cancelled(): return False, tr("USER_CANCELLED")
            dense_dir = project_dir / "dense"
            dense_dir.mkdir(exist_ok=True)
            self.status(tr("status_undistorting", "Correction optique des images..."))
            if not self.image_undistorter(str(images_dir), str(sparse_dir), str(dense_dir)):
                return False, "Echec undistortion"

        self.progress(95)

        if not self.is_cancelled():
            self.status(tr("status_ready", "Traitement terminé !"))
            self.create_brush_config(project_dir, images_dir, sparse_dir)
            self.progress(100)
            return True, f"Dataset cree: {project_dir}"

        return False, "Arrete par l'utilisateur"

    def _import_manifest_path(self, images_dir: Path) -> Path:
        return images_dir.parent / "import_manifest.json"

    def _load_import_manifest(self, images_dir: Path) -> dict:
        """Maps absolute source path → imported target filename (resize-proof)."""
        try:
            data = json.loads(self._import_manifest_path(images_dir).read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_import_manifest(self, images_dir: Path, manifest: dict) -> None:
        try:
            self._import_manifest_path(images_dir).write_text(
                json.dumps(manifest), encoding='utf-8')
        except OSError:
            pass

    def _prepare_images(self, images_dir: Path) -> bool:
        """Gère l'extraction vidéo ou la copie d'images."""
        if self.input_type == "video":
            if self.is_cancelled(): return False

            video_paths = []
            if self.input_path.is_dir():
                supported_exts = {'.mp4', '.mov', '.avi', '.mkv'}
                video_paths = [
                    f for f in self.input_path.rglob('*')
                    if f.is_file() and f.suffix.lower() in supported_exts
                ]
                video_paths.sort()
            else:
                video_paths = [Path(p.strip()) for p in str(self.input_path).split("|") if p.strip()]

            total_videos = len(video_paths)

            if total_videos == 0:
                self.log(f"Aucune vidéo trouvée dans: {self.input_path}")
                return False

            for i, video_path in enumerate(video_paths):
                if self.is_cancelled(): return False

                if not video_path.exists():
                    self.log(f"Attention: Video introuvable: {video_path}")
                    continue

                base_name = video_path.stem
                sanitized = "".join([c for c in base_name if c.isalnum() or c in ('_', '-')])
                # Prefix with the enumeration index so two videos whose stems
                # sanitize to the same string (or to an empty string) get distinct,
                # non-empty prefixes and never overwrite each other's frames.
                prefix = f"{i:03d}_{sanitized}" if sanitized else f"{i:03d}"

                self.log(f"Extraction video ({i+1}/{total_videos}): {base_name}")

                if not self.extract_frames_from_video(str(video_path), images_dir, prefix=prefix):
                     self.log(f"Echec extraction video: {base_name}")
                     return False
            return True
        else:
            self.log("Copie des images sources vers le dossier de travail...")
            try:
                raw_input = str(self.input_path)
                src_files = []

                if "|" in raw_input:
                    paths = [Path(p.strip()) for p in raw_input.split("|") if p.strip()]
                    for p in paths:
                        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS and not p.name.lower().endswith('.mask.png'):
                            src_files.append(p)
                elif self.input_path.is_file():
                    if self.input_path.suffix.lower() in _IMAGE_EXTS and not self.input_path.name.lower().endswith('.mask.png'):
                        src_files.append(self.input_path)
                elif self.input_path.is_dir():
                    if self.input_path.resolve() == images_dir.resolve():
                        self.log("Les images sont déjà dans le dossier de destination. Copie ignorée.")
                        return True
                    src_files = [
                        f for f in self.input_path.rglob('*')
                        if f.is_file()
                        and f.suffix.lower() in _IMAGE_EXTS
                        and not f.name.lower().endswith('.mask.png')
                    ]

                total_files = len(src_files)
                self.log(f"{total_files} images trouvées.")

                if total_files == 0:
                    # Allow re-runs where the working folder is already populated.
                    already_present = images_dir.exists() and any(
                        f.is_file() and f.suffix.lower() in _IMAGE_EXTS
                        for f in images_dir.iterdir()
                    )
                    if already_present:
                        self.log("Aucune nouvelle image à copier — images déjà présentes, on continue.")
                        return True
                    self.log(
                        f"❌ Aucune image trouvée dans l'entrée : {self.input_path}\n"
                        f"   Sélectionnez un dossier contenant des images (.jpg/.jpeg/.png), "
                        f"ou choisissez le mode Vidéo si l'entrée est une vidéo."
                    )
                    return False

                # Map each source to a deterministic target by its absolute path
                # (a manifest), so a source that was already imported — even after
                # it was resized in place — is recognised and never re-imported
                # under a "<folder>_1_<name>" alias. Source content is NOT compared
                # (the in-place resize changes it); provenance is the source path.
                manifest = self._load_import_manifest(images_dir)
                src_files = sorted(src_files, key=lambda p: (p.name.lower(), str(p)))
                new_manifest = {}
                used = set()          # target names claimed this run
                linked = skipped = 0
                logged_mode = False
                for i, file_path in enumerate(src_files):
                    if self.is_cancelled(): return False
                    key = str(file_path.resolve())
                    # Prefer the name a prior run gave this source; else its
                    # basename. Disambiguate only against names claimed THIS run
                    # (two genuinely different sources sharing a basename).
                    target_name = manifest.get(key) or file_path.name
                    if target_name in used:
                        counter = 1
                        while True:
                            cand = f"{file_path.parent.name}_{counter}_{file_path.name}"
                            if cand not in used:
                                target_name = cand
                                break
                            counter += 1
                    target = images_dir / target_name
                    if target.exists():
                        skipped += 1           # already imported (possibly resized) → adopt
                    else:
                        mode = self._link_or_copy(file_path, target)
                        linked += 1
                        if not logged_mode:
                            self.log(
                                "Images liées (hardlink — pas de duplication sur le disque)."
                                if mode == "link" else
                                "Images copiées (entrée sur un autre volume — duplication inévitable)."
                            )
                            logged_mode = True
                    new_manifest[key] = target_name
                    used.add(target_name)

                    if i % 10 == 0 or i == total_files - 1:
                        p = 5 + int((i / total_files) * 15)
                        self.progress(p)
                        self.status(f"Préparation des images : {i+1} / {total_files}")

                # Self-heal: drop stale top-level images no current source claims
                # (e.g. "<folder>_1_<name>" duplicates from earlier buggy runs, or
                # frames of a source that was removed). Subfolders (images_src,
                # blurry, …) and mask files are left untouched.
                removed = 0
                claimed = set(new_manifest.values())
                for f in images_dir.iterdir():
                    if (f.is_file() and f.suffix.lower() in _IMAGE_EXTS
                            and not f.name.lower().endswith('.mask.png')
                            and f.name not in claimed):
                        try:
                            f.unlink()
                            removed += 1
                        except OSError:
                            pass

                self._save_import_manifest(images_dir, new_manifest)

                msg = f"✅ {linked} images préparées"
                if skipped:
                    msg += f", {skipped} déjà présentes"
                if removed:
                    msg += f", {removed} doublons/obsolètes supprimés"
                self.log(msg + ".")
                return True
            except Exception as e:
                self.log(f"Erreur copie images: {e}")
                return False

    def _link_or_copy(self, src: Path, dst: Path) -> str:
        """Hardlink src→dst to avoid duplicating the dataset on disk; fall back to
        a copy when a hardlink can't be made (e.g. source on another volume).

        Hardlinks share the same data on disk, so the project's images/ folder
        costs no extra space. In-place writers (resolution resize) break the
        link first, so the user's originals are never modified.
        """
        try:
            os.link(str(src), str(dst))
            return "link"
        except (OSError, NotImplementedError):
            shutil.copy2(str(src), str(dst))
            return "copy"

    def _is_single_video_input(self) -> bool:
        """True when the input is exactly one video file (not a dir, not a
        '|'-joined list). Frames from one ffmpeg run share one resolution, so
        callers can take resolution/format fast paths. Conservative: a folder of
        videos returns False."""
        raw = str(self.input_path)
        if "|" in raw:
            return False
        try:
            return self.input_path.is_file() and self.input_path.suffix.lower() in _VIDEO_EXTS
        except OSError:
            return False

    def _convert_db_journal_mode(self, database_path: Path):
        """Switch the COLMAP database from WAL to DELETE journal mode.

        Recent COLMAP versions open the database in WAL mode, which GLOMAP's
        bundled SQLite cannot handle. This converts it back to the classic
        rollback-journal mode before GLOMAP reads the file.
        """
        try:
            with sqlite3.connect(str(database_path)) as con:
                con.execute("PRAGMA journal_mode=DELETE")
                con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            for wal_file in [database_path.parent / (database_path.name + "-wal"),
                             database_path.parent / (database_path.name + "-shm")]:
                if wal_file.exists():
                    wal_file.unlink()
            self.log("Base de données convertie (WAL → DELETE) pour compatibilité GLOMAP.")
        except Exception as e:
            self.log(f"Avertissement : conversion journal mode échouée : {e}")

    def _filter_blurry_images(self, images_dir: Path, factor: float) -> None:
        """Move blurry frames out of images_dir (sharpness = variance of Laplacian).

        Rejected frames are moved to a sibling ``images_blurry`` folder rather
        than deleted, so they can be inspected/restored. Never fatal.
        """
        self.log(f"\n{'='*60}\nFiltrage des images floues\n{'='*60}")
        try:
            import cv2
        except ImportError:
            self.log("⚠️ OpenCV non disponible — filtrage du flou ignoré "
                     "(installez opencv-python-headless pour l'activer).")
            return

        files = sorted(
            f for f in images_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
            and not f.name.lower().endswith('.mask.png')
        )
        if len(files) < 10:
            self.log(f"Trop peu d'images ({len(files)}) — filtrage du flou ignoré.")
            return

        total = len(files)
        self.log(f"Analyse de la netteté de {total} images sur {self.num_threads} threads...")

        def _score_one(f):
            # cv2 releases the GIL during imread/resize/Laplacian, so threading
            # scales well. Downscaling to ≤640px preserves the relative ranking.
            img = _imread_unicode(f, cv2.IMREAD_GRAYSCALE)
            if img is None:
                return f, None
            h, w = img.shape[:2]
            longest = max(h, w)
            if longest > 640:
                s = 640.0 / longest
                img = cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s))),
                                 interpolation=cv2.INTER_AREA)
            return f, float(cv2.Laplacian(img, cv2.CV_64F).var())

        scores = {}
        done = 0
        with ThreadPoolExecutor(max_workers=max(2, self.num_threads)) as ex:
            futures = [ex.submit(_score_one, f) for f in files]
            for fut in as_completed(futures):
                if self.is_cancelled():
                    ex.shutdown(cancel_futures=True)
                    return
                f, sc = fut.result()
                if sc is not None:
                    scores[f] = sc
                done += 1
                if done % 200 == 0 or done == total:
                    self.status(f"Analyse netteté : {done}/{total}")
                    self.progress(int(done / total * 100))
                    if done % 1000 == 0 or done == total:
                        self.log(f"  netteté analysée : {done}/{total}")

        rejected, threshold = select_blurry_files(scores, factor)
        if not rejected:
            self.log(f"Aucune image floue détectée (seuil de netteté ≈ {threshold:.0f}).")
            return

        rejected_dir = images_dir.parent / "images_blurry"
        rejected_dir.mkdir(parents=True, exist_ok=True)
        moved = 0
        for f in rejected:
            try:
                shutil.move(str(f), str(rejected_dir / f.name))
                moved += 1
            except OSError as e:
                self.log(f"⚠️ Impossible de déplacer {f.name}: {e}")
        self.log(
            f"🔪 Filtre flou : {moved}/{len(files)} images écartées vers "
            f"'images_blurry' (seuil ≈ {threshold:.0f}). Pour les réutiliser, "
            f"remettez-les dans 'images' (ou désactivez le filtre)."
        )

    def _run_upscale(self, project_dir: Path, images_dir: Path) -> bool:
        """Gère l'upscaling via upscayl-bin."""
        self.log(f"\n{'='*60}\nUpscaling (upscayl-ncnn)\n{'='*60}")
        if self.is_cancelled(): return False

        try:
            from app.core.upscale_engine import UpscaleEngine
            upscaler = UpscaleEngine(logger_callback=self.log)

            if not upscaler.is_installed():
                self.log("⚠️ upscayl-bin introuvable — upscale ignoré (les images originales sont conservées).")
                return True

            # Verify a model is actually available BEFORE touching the images.
            # Upscale is an optional enhancement; a missing model must never
            # abort dataset creation.
            from app.upscayl_manager import get_models_dir
            from app.upscayl_models import get_downloaded_models
            downloaded = {m.id for m in get_downloaded_models(get_models_dir())}
            model_id = self.upscale_config.get("model_id")
            if model_id not in downloaded:
                model_id = _first_available_model()  # first downloaded model, or ""
            if not model_id:
                self.log(
                    "⚠️ Aucun modèle upscayl téléchargé — upscale ignoré. "
                    "Ouvrez l'onglet Upscale pour télécharger un modèle "
                    "(l'upscale est optionnel et non requis pour le splatting)."
                )
                return True

            images_sources_dir = project_dir / "images_src"
            if images_sources_dir.exists():
                self.log("'images_src' already exists — upscale already done.")
                return True

            self.log(f"Moving originals to {images_sources_dir}...")
            shutil.move(str(images_dir), str(images_sources_dir))
            images_dir.mkdir(parents=True, exist_ok=True)

            scale       = self.upscale_config.get("scale", 4)
            out_format  = self.upscale_config.get("format", "png")
            tile        = self.upscale_config.get("tile", 0)
            tta         = self.upscale_config.get("tta", False)
            compression = self.upscale_config.get("compression", 0)

            self.log(f"Upscaling x{scale} with model '{model_id}'...")
            success, msg = upscaler.upscale_folder(
                input_dir=str(images_sources_dir),
                output_dir=str(images_dir),
                model_id=model_id,
                scale=scale,
                output_format=out_format,
                tile=tile,
                tta=tta,
                compression=compression,
                cancel_check=self.is_cancelled,
            )
            if not success:
                self.log(f"⚠️ Upscale échoué ({msg}) — restauration des images originales.")
                self._restore_originals(images_sources_dir, images_dir)
                return True
            self.log("Upscale complete.")
            return True

        except Exception as e:
            self.log(f"⚠️ Erreur Upscale ({e}) — tentative de restauration des images originales.")
            try:
                src = project_dir / "images_src"
                if src.exists() and not any(images_dir.iterdir()):
                    self._restore_originals(src, images_dir)
            except OSError:
                pass
            return True  # optional step: never abort the pipeline

    def _restore_originals(self, src_dir: Path, images_dir: Path) -> None:
        """Move original images back from src_dir to images_dir after a failed upscale."""
        images_dir.mkdir(parents=True, exist_ok=True)
        for f in src_dir.iterdir():
            if f.is_file():
                dest = images_dir / f.name
                if not dest.exists():
                    shutil.move(str(f), str(dest))
        shutil.rmtree(str(src_dir), ignore_errors=True)
        self.log("Images originales restaurées — la reconstruction continue sans upscale.")

    def _check_and_normalize_resolution(self, images_dir: Path) -> bool:
        """Vérifie et normalise la résolution des images.

        Reads only image dimensions from the file header (fast, no full decode)
        in parallel. Frames from a single video are all the same size, so this
        exits almost instantly.
        """
        self.log(f"\n{'='*60}\nVérification résolution images\n{'='*60}")

        if not images_dir.exists():
            return True

        files = sorted([
            f for f in images_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
        ])

        if len(files) < 2:
            return True

        from PIL import Image

        # Fast path: all frames from a single ffmpeg extraction share one
        # resolution by construction. Sampling the first frame turns an O(n)
        # header scan into O(1). Multi-video / image-folder inputs (which may mix
        # resolutions) keep the full scan below.
        if self._is_single_video_input():
            try:
                with Image.open(files[0]) as im:
                    w, h = im.size
                self.log(f"✅ Source vidéo unique — résolution uniforme {w}×{h} px (échantillon, scan complet ignoré)")
                return True
            except Exception:
                pass  # fall through to the full scan on any read error

        total = len(files)
        self.log(f"Lecture des dimensions de {total} images (en-tête seulement, {self.num_threads} threads)...")

        def _size_one(f):
            try:
                with Image.open(f) as im:
                    return f, im.size  # (w, h) read from the header, no decode
            except Exception:
                return f, None

        sizes = {}
        done = 0
        with ThreadPoolExecutor(max_workers=max(2, self.num_threads)) as ex:
            futures = [ex.submit(_size_one, f) for f in files]
            for fut in as_completed(futures):
                if self.is_cancelled():
                    ex.shutdown(cancel_futures=True)
                    return False
                f, sz = fut.result()
                if sz is not None:
                    sizes[f] = sz
                done += 1
                if done % 1000 == 0 or done == total:
                    self.status(f"Dimensions : {done}/{total}")
                    self.progress(int(done / total * 100))

        if not sizes:
            return True

        unique_sizes = set(sizes.values())
        if len(unique_sizes) == 1:
            w, h = next(iter(unique_sizes))
            self.log(f"✅ Résolution uniforme: {w}×{h} px")
            return True

        if not getattr(self, '_cv2_loaded', False):
            self.log("⚠️ Résolutions différentes mais OpenCV indisponible — redimensionnement ignoré.")
            return True
        import cv2

        min_w = min(s[0] for s in unique_sizes)
        min_h = min(s[1] for s in unique_sizes)
        to_resize = [f for f, s in sizes.items() if s != (min_w, min_h)]

        self.log(f"⚠️ {len(unique_sizes)} résolutions différentes détectées.")
        self.log(f"Redimensionnement de {len(to_resize)} images → {min_w}×{min_h} px")

        def _resize_one(f):
            img = _imread_unicode(f, cv2.IMREAD_UNCHANGED)
            if img is None:
                return f, None
            resized = cv2.resize(img, (min_w, min_h), interpolation=cv2.INTER_AREA)
            return f, _imwrite_unicode(f, resized)

        # cv2 decode/resize/encode release the GIL → resize in parallel.
        n = len(to_resize)
        done = 0
        with ThreadPoolExecutor(max_workers=max(2, self.num_threads)) as ex:
            futures = [ex.submit(_resize_one, f) for f in to_resize]
            for fut in as_completed(futures):
                if self.is_cancelled():
                    ex.shutdown(cancel_futures=True)
                    return False
                f, ok = fut.result()
                if ok is None:
                    self.log(f"⚠️ Re-lecture impossible: {f.name}")
                elif not ok:
                    self.log(f"⚠️ Écriture impossible: {f.name}")
                done += 1
                if done % 10 == 0 or done == n:
                    self.status(f"Ajustement taille : {done} / {n}")

        self.log(f"✅ {n} images redimensionnées vers {min_w}×{min_h} px")
        return True

    def extract_frames_from_video(self, video_path: str, images_dir: Path, prefix: str | None = None) -> bool | None:
        """Extrait les frames d'une vidéo via FFmpeg."""
        base_name = Path(video_path).stem
        self.log(f"\n{'='*60}\nExtraction frames: {Path(video_path).name}\n{'='*60}")
        images_dir.mkdir(parents=True, exist_ok=True)

        frame_stem = f'{prefix}_' if prefix else 'frame_'
        output_pattern = images_dir / f'{frame_stem}%04d.jpg'

        def _ffmpeg_parser(line_str: str):
            if 'frame=' in line_str or 'error' in line_str.lower():
                self.log(line_str)
                if 'frame=' in line_str:
                    try:
                        f_num = line_str.split('frame=')[1].strip().split()[0]
                        self.status(f"Extraction {base_name} : image {f_num}")
                    except (IndexError, ValueError) as e:
                        self.logger.debug("Failed to parse frame number: %s", e)

        def _build_cmd(decoder):
            c = [self.ffmpeg_bin]
            if self.has_cuda:
                c.extend(['-hwaccel', 'cuda'])
                if decoder:                       # NVDEC hardware decoder (cuvid)
                    c.extend(['-c:v', decoder])
            c.extend([
                '-i', video_path,
                '-an',                            # no audio → faster, cleaner
                '-vf', f'fps={self.fps}',
                '-qscale:v', '2',
                str(output_pattern),
            ])
            return c

        def _clear_frames():
            # Remove this prefix's frames before each attempt so a re-run (changed
            # fps/source) or a failed GPU attempt never leaves stale frames behind.
            for old in images_dir.glob(f'{frame_stem}*.jpg'):
                try:
                    old.unlink()
                except OSError:
                    pass

        def _count_frames():
            return len([
                f for f in images_dir.iterdir()
                if f.suffix == '.jpg' and f.name.startswith(frame_stem)
            ])

        # Try NVDEC GPU decode first when a matching cuvid decoder is available,
        # then fall back to standard decode. The CPU attempt is always present, so
        # a missing/incompatible GPU decoder can never break extraction.
        decoder = self._cuvid_decoder_for(video_path) if self.has_cuda else None
        attempts = ([decoder] if decoder else []) + [None]

        for idx, dec in enumerate(attempts):
            if self.is_cancelled():
                return None
            if dec:
                self.log(f"Décodage vidéo : NVDEC GPU ({dec})")
            elif idx > 0:
                self.log("⚠️ Décodage GPU indisponible/échoué — bascule en décodage CPU.")
            _clear_frames()
            try:
                returncode = self._execute_command(_build_cmd(dec), line_callback=_ffmpeg_parser)
            except Exception as e:
                self.log(f"Erreur: {str(e)}")
                returncode = -1
            if self.is_cancelled():
                return None
            num_frames = _count_frames()
            if returncode == 0 and num_frames > 0:
                self.log(f"{num_frames} frames extraites")
                return True
            # otherwise fall through to the next attempt (CPU)

        self.log("⚠️ Aucune frame extraite de cette vidéo.")
        return None

    def _cuvid_decoder_for(self, video_path: str) -> str | None:
        """Returns the NVDEC (cuvid) decoder name for the input video's codec, or
        None if it can't be determined or isn't available in this ffmpeg build."""
        codec = self._probe_video_codec(video_path)
        if not codec:
            return None
        cuvid_map = {
            'h264': 'h264_cuvid', 'hevc': 'hevc_cuvid', 'h265': 'hevc_cuvid',
            'mpeg1video': 'mpeg1_cuvid', 'mpeg2video': 'mpeg2_cuvid',
            'mpeg4': 'mpeg4_cuvid', 'vc1': 'vc1_cuvid', 'vp8': 'vp8_cuvid',
            'vp9': 'vp9_cuvid', 'av1': 'av1_cuvid', 'mjpeg': 'mjpeg_cuvid',
        }
        decoder = cuvid_map.get(codec.lower())
        if decoder and decoder in self._available_cuvid_decoders():
            return decoder
        return None

    def _probe_video_codec(self, video_path: str) -> str | None:
        """Reads the first video stream's codec name via ffprobe (best-effort)."""
        ffprobe = self._ffprobe_bin()
        if not ffprobe:
            return None
        try:
            import subprocess
            out = subprocess.run(
                [ffprobe, '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=codec_name',
                 '-of', 'default=nokey=1:noprint_wrappers=1', str(video_path)],
                capture_output=True, text=True, timeout=15,
            )
            name = out.stdout.strip().splitlines()
            return name[0].strip() if name else None
        except (OSError, subprocess.SubprocessError):
            return None

    def _ffprobe_bin(self) -> str | None:
        """ffprobe path, derived from ffmpeg's (they ship together)."""
        if not getattr(self, 'ffmpeg_bin', None):
            return None
        p = Path(self.ffmpeg_bin)
        cand = p.with_name(p.name.replace('ffmpeg', 'ffprobe'))
        if cand.exists():
            return str(cand)
        which = shutil.which('ffprobe')
        return which

    def _available_cuvid_decoders(self) -> set:
        """Set of cuvid decoders this ffmpeg build exposes (probed once, cached)."""
        cached = getattr(self, '_cuvid_decoders', None)
        if cached is not None:
            return cached
        decoders = set()
        try:
            import subprocess
            out = subprocess.run(
                [self.ffmpeg_bin, '-hide_banner', '-decoders'],
                capture_output=True, text=True, timeout=15,
            )
            for line in (out.stdout + out.stderr).splitlines():
                for tok in line.split():
                    if tok.endswith('_cuvid'):
                        decoders.add(tok)
        except (OSError, subprocess.SubprocessError):
            pass
        self._cuvid_decoders = decoders
        return decoders

    def run_command(self, cmd: list, description: str, status_prefix: str | None = None) -> bool:
        """Exécute une commande système avec logging et callback de statut."""
        self.log(f"\n{'='*60}\n{description}\n{'='*60}")

        env = os.environ.copy()
        # Pin the inner BLAS/OpenMP pools to 1 thread. COLMAP already parallelizes
        # at the task level via --*.num_threads (Ceres bundle-adjustment threads);
        # letting BLAS *also* spawn N threads gives N×N oversubscription, which
        # thrashes the CPU and worsens the "Linear solver failure" retries during
        # global BA on large scenes. One source of parallelism, not nested.
        env['OMP_NUM_THREADS'] = '1'
        env['OPENBLAS_NUM_THREADS'] = '1'
        env['MKL_NUM_THREADS'] = '1'

        # Windows: the bundled colmap.exe loads DLLs from its own folder and a
        # sibling lib/ directory. Make both discoverable on PATH so we can call
        # colmap.exe directly (instead of COLMAP.bat, which needs a shell).
        if os.name == 'nt' and self.colmap_bin:
            bin_dir = Path(self.colmap_bin).parent
            dll_dirs = [bin_dir, bin_dir.parent / 'lib', bin_dir / 'lib', bin_dir.parent / 'bin']
            existing = [str(d) for d in dll_dirs if d.exists()]
            if existing:
                env['PATH'] = os.pathsep.join(existing) + os.pathsep + env.get('PATH', '')

        def _colmap_parser(line_str: str):
            self.log(line_str)
            # "Linear solver failure" is a non-fatal bundle-adjustment warning:
            # one optimisation step failed, the solver retries and the mapper
            # keeps registering images. Annotate it once so it doesn't look like
            # a crash to the user.
            if "Linear solver failure" in line_str and not getattr(self, "_ba_warn_noted", False):
                self._ba_warn_noted = True
                self.log("ℹ️ (info) « Linear solver failure » est un avertissement NON bloquant : "
                         "une étape d'optimisation a échoué, COLMAP réessaie automatiquement et "
                         "continue. Tant que les images continuent de s'enregistrer, tout va bien.")
            # Some COLMAP builds advertise --Mapper.ba_use_gpu but ship a Ceres
            # compiled without CUDA/cuDSS, so BA silently runs on the CPU. Surface
            # this once — it's the real reason the mapper is slow.
            if (("compiled without CUDA support" in line_str
                 or "compiled without cuDSS support" in line_str)
                    and not getattr(self, "_ceres_cpu_noted", False)):
                self._ceres_cpu_noted = True
                self.log("⚠️ Important : ce build de COLMAP a Ceres SANS CUDA/cuDSS → le bundle "
                         "adjustment tourne en réalité sur le CPU (le flag GPU est sans effet ici). "
                         "C'est la principale cause de lenteur du mapper. Pour accélérer : utilisez "
                         "GLOMAP (qui évite le BA global répété) ou un COLMAP compilé avec "
                         "Ceres+CUDA+cuDSS.")
            if status_prefix:
                if "Processed file" in line_str:
                    parts = line_str.split("Processed file")
                    if len(parts) > 1:
                        self.status(f"{status_prefix} : image {parts[1].strip()}")
                elif "Matching block" in line_str:
                    parts = line_str.split("Matching block")
                    if len(parts) > 1:
                        self.status(f"{status_prefix} : bloc {parts[1].strip()}")
                elif "Registering image" in line_str:
                    # Show num_reg_frames (images successfully placed so far) —
                    # the real progress counter for the mapper — instead of the
                    # raw image id, so the user can see where they are.
                    m = re.search(r'num_reg_frames=(\d+)', line_str)
                    if m:
                        self.status(f"{status_prefix} : {m.group(1)} images placées")
                    else:
                        parts = line_str.split("Registering image")
                        if len(parts) > 1:
                            img_info = parts[1].split('(')[0].strip()
                            self.status(f"{status_prefix} : ajout image {img_info}")
                elif "Bundle adjustment report" in line_str:
                    self.status(f"{status_prefix} : optimisation globale...")
                elif "Undistorting image" in line_str:
                    parts = line_str.split("Undistorting image")
                    if len(parts) > 1:
                        self.status(f"{status_prefix} : image {parts[1].strip()}")

        try:
            returncode = self._execute_command(cmd, env=env, line_callback=_colmap_parser)
            if self.is_cancelled(): return False

            if returncode == 0:
                self.log(f"{description} termine")
                return True
            else:
                self.log(f"{description} echoue")
                return False

        except FileNotFoundError:
            self.log("COLMAP introuvable. Installez une build CUDA depuis "
                     "https://github.com/colmap/colmap/releases (ex. colmap-x64-windows-cuda.zip) "
                     "et ajoutez-le au PATH.")
            return False

    def feature_extraction(self, database_path: str, images_dir: str) -> bool:
        """Exécute l'extraction des features SIFT."""
        image_list_path = self._write_sorted_image_list(images_dir)

        # COLMAP's GPU SIFT is disabled when affine-shape or domain-size-pooling
        # is on (it falls back to slow CPU extraction). Tell the user which path
        # will run so a misconfiguration that loses the GPU is obvious.
        cpu_only_opts = self.params.estimate_affine_shape or self.params.domain_size_pooling
        if self.has_cuda and not cpu_only_opts:
            self.log("SIFT : GPU (CUDA) ✅")
        elif self.has_cuda and cpu_only_opts:
            self.log("⚠️ SIFT sur CPU : 'Affine Shape' ou 'Domain Pooling' est activé "
                     "→ désactivez-les pour utiliser le GPU.")
        else:
            self.log("SIFT : CPU (pas de GPU CUDA détecté)")

        if self.params.camera_model == 'EQUIRECTANGULAR':
            self.log("Mode 360 natif : modèle de caméra EQUIRECTANGULAR "
                     "(requiert COLMAP ≥ 4.1.0).")

        cmd = [
            self.colmap_bin, 'feature_extractor',
            '--database_path', database_path,
            '--image_path', images_dir,
            '--ImageReader.camera_model', self.params.camera_model,
            '--ImageReader.single_camera', '1' if self.params.single_camera else '0',
            '--FeatureExtraction.num_threads', str(self.num_threads),
            '--FeatureExtraction.max_image_size', str(self.params.max_image_size),
            '--SiftExtraction.max_num_features', str(self.params.max_num_features),
            '--SiftExtraction.estimate_affine_shape', '1' if self.params.estimate_affine_shape else '0',
            '--SiftExtraction.domain_size_pooling', '1' if self.params.domain_size_pooling else '0',
        ]
        # NOTE: a CUDA-enabled COLMAP uses the GPU for SIFT by default. We don't
        # pass --SiftExtraction.use_gpu because some COLMAP builds (e.g. 4.x)
        # reject that option name; the GPU is still used automatically.
        if image_list_path:
            cmd.extend(['--image_list_path', str(image_list_path)])
        return self.run_command(cmd, "Extraction des features", status_prefix="Analyse")

    def _write_sorted_image_list(self, images_dir: str) -> Path | None:
        """Write a deterministic COLMAP image list so sequential matching follows frame order."""
        image_root = Path(images_dir)
        files = sorted(
            f for f in image_root.rglob('*')
            if f.is_file()
            and f.suffix.lower() in _IMAGE_EXTS
            and not f.name.lower().endswith('.mask.png')
        )
        if not files:
            return None

        image_list_path = image_root.parent / "image_list.txt"
        with image_list_path.open("w", encoding="utf-8") as f:
            for image_file in files:
                f.write(f"{image_file.relative_to(image_root).as_posix()}\n")

        self.log(f"Liste d'images triee pour COLMAP: {len(files)} images")
        return image_list_path

    def _sort_colmap_database_images(self, database_path: Path) -> None:
        """Make image IDs follow filename order for COLMAP's sequential matcher."""
        ALLOWED_COLUMNS = {
            ("images", "image_id"),
            ("keypoints", "image_id"),
            ("descriptors", "image_id"),
            ("frames", "frame_id"),
            ("frame_data", "frame_id"),
            ("frame_data", "data_id"),
            ("pose_priors", "corr_data_id"),
        }

        try:
            with sqlite3.connect(str(database_path)) as con:
                rows = con.execute(
                    "SELECT image_id, name FROM images ORDER BY name"
                ).fetchall()
                id_map = {old_id: new_id for new_id, (old_id, _) in enumerate(rows, start=1)}
                if all(old_id == new_id for old_id, new_id in id_map.items()):
                    self.log("Ordre des images COLMAP deja trie.")
                    return

                con.execute("PRAGMA foreign_keys=OFF")
                con.execute("DELETE FROM matches")
                con.execute("DELETE FROM two_view_geometries")
                con.execute("CREATE TEMP TABLE image_id_map(old_id INTEGER PRIMARY KEY, new_id INTEGER NOT NULL)")
                con.executemany(
                    "INSERT INTO image_id_map(old_id, new_id) VALUES (?, ?)",
                    id_map.items(),
                )
                table_columns = {
                    table_name: {
                        column[1]
                        for column in con.execute(f"PRAGMA table_info({table_name})").fetchall()
                    }
                    for table_name, in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }

                offset = 1000000000
                for table, column in [
                    ("images", "image_id"),
                    ("keypoints", "image_id"),
                    ("descriptors", "image_id"),
                    ("frames", "frame_id"),
                    ("frame_data", "frame_id"),
                    ("frame_data", "data_id"),
                    ("pose_priors", "corr_data_id"),
                ]:
                    if (table, column) not in ALLOWED_COLUMNS:
                        continue
                    if column not in table_columns.get(table, set()):
                        continue
                    con.execute(
                        f"""
                        UPDATE {table}
                        SET {column} = (
                            SELECT new_id + ?
                            FROM image_id_map
                            WHERE old_id = {table}.{column}
                        )
                        WHERE {column} IN (SELECT old_id FROM image_id_map)
                        """,
                        (offset,),
                    )
                    con.execute(
                        f"""
                        UPDATE {table}
                        SET {column} = {column} - ?
                        WHERE {column} > ?
                        """,
                        (offset, offset),
                    )

                con.execute("DROP TABLE image_id_map")
                con.execute(
                    "UPDATE sqlite_sequence SET seq = (SELECT MAX(image_id) FROM images) WHERE name = 'images'"
                )
                con.execute(
                    "UPDATE sqlite_sequence SET seq = COALESCE((SELECT MAX(frame_id) FROM frames), 0) WHERE name = 'frames'"
                )
                con.commit()
                self.log(f"Base COLMAP retriee pour matching sequentiel: {len(rows)} images")
        except Exception as e:
            self.log(f"Avertissement: tri de la base COLMAP echoue: {e}")

    def feature_matching(self, database_path: str) -> bool:
        """Exécute le matching des features."""
        if self.params.matcher_type == 'sequential':
            cmd = [
                self.colmap_bin, 'sequential_matcher',
                '--database_path', database_path,
                '--FeatureMatching.num_threads', str(self.num_threads),
                '--SiftMatching.max_ratio', str(self.params.max_ratio),
                '--SiftMatching.max_distance', str(self.params.max_distance),
                '--SiftMatching.cross_check', '1' if self.params.cross_check else '0',
                '--FeatureMatching.guided_matching', '1' if self.params.guided_matching else '0',
                '--SequentialMatching.overlap', str(self.params.sequential_overlap),
                '--SequentialMatching.quadratic_overlap', '1',
            ]
            description = "Matching Sequentiel"
        else:
            cmd = [
                self.colmap_bin, 'exhaustive_matcher',
                '--database_path', database_path,
                '--FeatureMatching.num_threads', str(self.num_threads),
                '--SiftMatching.max_ratio', str(self.params.max_ratio),
                '--SiftMatching.max_distance', str(self.params.max_distance),
                '--SiftMatching.cross_check', '1' if self.params.cross_check else '0',
                '--FeatureMatching.guided_matching', '1' if self.params.guided_matching else '0',
            ]
            description = "Matching Exhaustif"

        return self.run_command(cmd, description, status_prefix="Comparaison")

    def _colmap_has_command(self, name: str) -> bool:
        """True if the installed colmap exposes the subcommand `name` (probed via
        `colmap help`, cached). Lets us use COLMAP 4.0+'s built-in global_mapper
        without assuming it exists on older builds."""
        cached = getattr(self, "_colmap_help_cmds", None)
        if cached is None:
            cached = ""
            try:
                import subprocess
                out = subprocess.run([self.colmap_bin, 'help'],
                                     capture_output=True, text=True, timeout=15)
                cached = out.stdout + out.stderr
            except (OSError, subprocess.SubprocessError):
                cached = ""
            self._colmap_help_cmds = cached
        return name in cached

    def _global_mapper(self, database_path: str, images_dir: str, sparse_dir: Path) -> bool:
        """Global SfM (a single global bundle adjustment instead of the repeated
        per-image one) — much faster on large scenes. Prefers COLMAP 4.0+'s
        built-in `global_mapper` (no extra install); falls back to a standalone
        glomap binary, then to the incremental mapper."""
        if self._colmap_has_command('global_mapper'):
            # Calibrating focal lengths from the view graph first markedly
            # improves global-mapper quality (it relies on decent intrinsics).
            if self._colmap_has_command('view_graph_calibrator'):
                self.status("Calibrage du view-graph...")
                self.run_command(
                    [self.colmap_bin, 'view_graph_calibrator', '--database_path', database_path],
                    "Calibrage des intrinsèques (view-graph)", status_prefix="Calibrage")
            self.log("Reconstruction GLOBALE (colmap global_mapper) : un seul bundle "
                     "adjustment global au lieu du BA incrémental répété → bien plus rapide.")
            cmd = [self.colmap_bin, 'global_mapper',
                   '--database_path', database_path,
                   '--image_path', images_dir,
                   '--output_path', str(sparse_dir)]
            return self.run_command(cmd, "Reconstruction 3D (globale)", status_prefix="Reconstruction globale")

        if resolve_binary('glomap'):
            self.log("Utilisation de GLOMAP (binaire séparé) pour la reconstruction globale...")
            cmd = [self.glomap_bin, 'mapper',
                   '--database_path', database_path,
                   '--image_path', images_dir,
                   '--output_path', str(sparse_dir)]
            return self.run_command(cmd, "Reconstruction 3D (GLOMAP)", status_prefix="Reconstruction GLOMAP")

        self.log("⚠️ Reconstruction globale demandée mais indisponible (ce COLMAP n'a pas "
                 "'global_mapper' et glomap n'est pas installé) → bascule sur le mapper "
                 "incrémental classique.")
        return self._incremental_mapper(database_path, images_dir, sparse_dir)

    def mapper(self, database_path: str, images_dir: str, sparse_dir: Path) -> bool:
        """Exécute la reconstruction 3D (Mapper)."""
        if self.params.use_glomap:
            return self._global_mapper(database_path, images_dir, sparse_dir)
        return self._incremental_mapper(database_path, images_dir, sparse_dir)

    def _incremental_mapper(self, database_path: str, images_dir: str, sparse_dir: Path) -> bool:
        """COLMAP incremental SfM."""
        cmd = [
            self.colmap_bin, 'mapper',
            '--database_path', database_path,
            '--image_path', images_dir,
            '--output_path', str(sparse_dir),
            '--Mapper.num_threads', str(self.num_threads),
            '--Mapper.min_model_size', str(self.params.min_model_size),
            '--Mapper.multiple_models', '1' if self.params.multiple_models else '0',
            '--Mapper.ba_refine_focal_length', '1' if self.params.ba_refine_focal_length else '0',
            '--Mapper.ba_refine_principal_point', '1' if self.params.ba_refine_principal_point else '0',
            '--Mapper.ba_refine_extra_params', '1' if self.params.ba_refine_extra_params else '0',
            '--Mapper.min_num_matches', str(self.params.min_num_matches),
        ]
        # Bound bundle-adjustment cost (the dominant mapper time on large
        # scenes) — faster than COLMAP defaults, safe for a 3DGS target. Each
        # flag is gated on the installed COLMAP actually advertising it: COLMAP
        # 4.1.0 renamed/removed some of these (e.g. ba_global_*_ratio), and an
        # unrecognized option makes the whole mapper abort.
        ba_bounds = [
            ('ba_global_max_num_iterations', self.params.ba_global_max_num_iterations),
            ('ba_global_function_tolerance', self.params.ba_global_function_tolerance),
            # Refinement caps — the biggest in-mapper lever on the global-BA step.
            ('ba_global_max_refinements', self.params.ba_global_max_refinements),
            ('ba_local_max_refinements', self.params.ba_local_max_refinements),
            # How often global BA runs. COLMAP 4.1.0 RENAMED images_ratio →
            # frames_ratio (rig/frame terminology); pass both — only the name
            # the build advertises is used, so frequency control works on both
            # 4.1.0 (frames) and 3.x (images). Without this it was silently
            # dropped on 4.1.0, leaving global BA at the slow default cadence.
            ('ba_global_frames_ratio', self.params.ba_global_images_ratio),
            ('ba_global_images_ratio', self.params.ba_global_images_ratio),
            ('ba_global_points_ratio', self.params.ba_global_points_ratio),
            ('ba_local_max_num_iterations', self.params.ba_local_max_num_iterations),
        ]
        skipped = []
        for name, val in ba_bounds:
            if self._mapper_supports(name):
                cmd += [f'--Mapper.{name}', str(val)]
            else:
                skipped.append(name)
        if skipped:
            self.log(f"(info) Options BA non disponibles sur ce COLMAP, ignorées : {', '.join(skipped)}")
        # GPU bundle adjustment (COLMAP 4.1.0 "Caspar"). Only add the flag if
        # the installed COLMAP actually supports it — otherwise an older
        # build would abort with "unrecognized option". This is exactly the
        # step that throws "Linear solver failure" on the CPU for big scenes.
        if self.params.ba_use_gpu:
            if self._mapper_supports_gpu_ba():
                cmd += ['--Mapper.ba_use_gpu', '1']
                if self.params.ba_gpu_index is not None and self.params.ba_gpu_index >= 0:
                    cmd += ['--Mapper.ba_gpu_index', str(self.params.ba_gpu_index)]
                self.log("Bundle adjustment GPU demandé (--ba_use_gpu) — effectif seulement "
                         "si ce build de COLMAP a Ceres compilé avec CUDA/cuDSS (vérifié au runtime).")
            else:
                self.log("⚠️ GPU bundle adjustment demandé mais ce COLMAP ne le "
                         "supporte pas (requiert COLMAP ≥ 4.1.0) → fallback CPU. "
                         "Supprimez engines\\colmap et relancez run.bat pour mettre à jour.")
        return self.run_command(cmd, "Reconstruction 3D (COLMAP)", status_prefix="Reconstruction 3D")

    def _mapper_help_text(self) -> str:
        """`colmap mapper -h` output, fetched once and cached (empty on failure).

        Used to gate every optional --Mapper.* flag so we never pass an option a
        given COLMAP build doesn't recognize (which aborts the whole mapper).
        """
        cached = getattr(self, "_mapper_help", None)
        if cached is not None:
            return cached
        text = ""
        try:
            import subprocess
            out = subprocess.run(
                [self.colmap_bin, 'mapper', '-h'],
                capture_output=True, text=True, timeout=15,
            )
            text = out.stdout + out.stderr
        except (OSError, subprocess.SubprocessError):
            text = ""
        self._mapper_help = text
        return text

    def _mapper_supports(self, option: str) -> bool:
        """True if `colmap mapper` advertises --Mapper.<option> for this build.

        If the help probe failed (empty text) we return False — better to skip a
        speed-tuning flag than risk aborting the mapper on an unrecognized option.
        """
        return option in self._mapper_help_text()

    def _mapper_supports_gpu_ba(self) -> bool:
        """True if `colmap mapper` accepts --Mapper.ba_use_gpu (COLMAP ≥ 4.1.0)."""
        return self._mapper_supports('ba_use_gpu')

    def image_undistorter(self, images_dir: str, sparse_dir: str, output_dir: str) -> bool:
        """Exécute l'undistortion des images."""
        input_path = Path(sparse_dir) / "0"
        cmd = [
            self.colmap_bin, 'image_undistorter',
            '--image_path', images_dir,
            '--input_path', str(input_path),
            '--output_path', output_dir,
            '--output_type', 'COLMAP',
            '--max_image_size', str(self.params.max_image_size),
        ]
        return self.run_command(cmd, "Undistortion des images", status_prefix="Correction optique")

    def _count_registered_images(self, model_dir: Path) -> int:
        """Number of registered images in a COLMAP sub-model. The binary
        images.bin begins with a uint64 count, so this reads just 8 bytes;
        falls back to counting images.txt entries."""
        import struct
        b = model_dir / "images.bin"
        if b.exists():
            try:
                with open(b, "rb") as f:
                    head = f.read(8)
                return struct.unpack("<Q", head)[0] if len(head) == 8 else 0
            except (OSError, struct.error):
                return 0
        t = model_dir / "images.txt"
        if t.exists():
            try:
                # images.txt: comment lines, then 2 lines per registered image.
                lines = [ln for ln in t.read_text().splitlines()
                         if ln.strip() and not ln.startswith("#")]
                return len(lines) // 2
            except OSError:
                return 0
        return 0

    def _promote_largest_sparse_model(self, sparse_dir: Path) -> None:
        """Ensure sparse/0 is the sub-model with the most registered images.

        COLMAP's multiple_models output ordering is not by size, so sparse/0 may
        be a small fragment. Downstream (Brush, undistorter) always uses sparse/0,
        so swap the largest model into that slot."""
        try:
            models = []
            for d in sorted(sparse_dir.iterdir()):
                if d.is_dir() and d.name.isdigit():
                    n = self._count_registered_images(d)
                    if n > 0:
                        models.append((n, d))
        except OSError:
            return
        if not models:
            return
        models.sort(key=lambda m: m[0], reverse=True)
        best_n, best = models[0]
        if len(models) > 1:
            self.log("Sous-modèles COLMAP (images enregistrées) : "
                     + ", ".join(f"sparse/{p.name}={n}" for n, p in models))
        if best.name == "0":
            self.log(f"Modèle principal : sparse/0 ({best_n} images).")
            return
        # Swap the largest model into sparse/0.
        zero = sparse_dir / "0"
        tmp = sparse_dir / "_swap_tmp"
        try:
            if tmp.exists():
                shutil.rmtree(tmp)
            best.rename(tmp)        # largest → _swap_tmp
            zero.rename(best)       # old 0   → largest's freed name
            tmp.rename(zero)        # _swap_tmp → 0
            self.log(f"⚠️ La reconstruction s'est fragmentée — modèle le plus complet "
                     f"(sparse/{best.name}, {best_n} images) promu en sparse/0 pour l'entraînement.")
        except OSError as e:
            self.log(f"(info) Impossible de réordonner les sous-modèles COLMAP : {e}")

    def create_brush_config(self, output_dir: Path, images_dir: Path, sparse_dir: Path):
        """Génère le fichier de configuration pour Brush."""
        if self.params.undistort_images:
            final_images_path = output_dir / "dense" / "images"
            final_sparse_path = output_dir / "dense" / "sparse"
            self.log("Utilisation des images et reconstruction non-distordues pour Brush")
        else:
            final_images_path = images_dir
            final_sparse_path = sparse_dir / "0"

        config = {
            "dataset_type": "colmap",
            "images_path": str(final_images_path),
            "sparse_path": str(final_sparse_path),
            "created_with": "CorbeauSplat Windows",
            "architecture": platform.machine(),
            "optimized_for": "CUDA" if self.has_cuda else "CPU",
            "parameters": self.params.to_dict()
        }
        config_path = output_dir / "brush_config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        self.log(f"Configuration Brush créée: {config_path}")

    def stop(self):
        """Arrête le processus en cours."""
        super().stop()

    @staticmethod
    def delete_project_content(target_path: Path) -> tuple[bool, str]:
        """Supprime le contenu d'un dossier de projet de manière sécurisée.
        
        Only allows deletion if target_path is contained within project_root
        or user home directory.
        """
        from .system import resolve_project_root

        safe_path = Path(target_path).resolve()
        project_root = resolve_project_root().resolve()

        # Validate containment: target must be inside project_root only
        allowed = False
        try:
            safe_path.relative_to(project_root)
            allowed = True
        except ValueError:
            pass

        if not allowed:
            logger = logging.getLogger(__name__)
            logger.warning("delete_project_content blocked: path outside allowed boundaries — %s", safe_path)
            return False, "Suppression bloquée : le chemin n'est pas dans les limites autorisées."

        if safe_path == project_root or safe_path == Path.home().resolve():
            return False, "Tentative de suppression critique bloquée par sécurité."

        if not target_path.exists():
            return False, "Le dossier n'existe pas"

        import send2trash  # lazy: only the trash-delete path needs it, never startup
        try:
            for item in target_path.iterdir():
                if item.name == "images":
                    continue
                try:
                    send2trash.send2trash(str(item))
                except Exception as e:
                    logging.getLogger(__name__).error("Failed to trash %s. Reason: %s", item, e)
            return True, "Contenu mis à la corbeille"
        except Exception as e:
            logging.getLogger(__name__).error("Error during project cleanup: %s", e)
            return False, str(e)
