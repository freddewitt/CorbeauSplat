# Plan de correction — CorbeauSplat v0.99.1

Analyse réalisée le 28/04/2026 par DeepSeek.

## Batch 1 : Bugs critiques

### C1 — FourDGSWorker.stop() appelle super().stop() deux fois
- Fichier : app/gui/workers.py:597-598
- Supprimer la seconde ligne super().stop()

### C2 — sqlite3.connect() sans context manager
- Fichier : app/core/engine.py:310-313
- Passer à with sqlite3.connect(...) as con:

### C3 — ffmpeg en dur dans SharpVideoWorker
- Fichier : app/gui/workers.py:483
- Remplacer "ffmpeg" par self.ffmpeg_bin ou shutil.which("ffmpeg") or "ffmpeg"

### C4 — frames_dir cleanup pas dans finally
- Fichier : app/gui/workers.py:548-550
- Déplacer le rmtree(frames_dir) dans un bloc try/finally

## Batch 2 : Bugs majeurs

### M1 — ColmapWorker mute self.engine.input_path après construction
- Fichier : app/gui/workers.py:115-116
- Supprimer les mutations

### M2 — SuperSplat.start_supersplat() contourne le Template Method
- Fichier : app/core/superplat_engine.py:71-78
- Utiliser self.runner.start() et itérer sur self.runner.stdout_iter()

### M3 — Collision de noms dans _prepare_images (mode images)
- Fichier : app/core/engine.py:284-286
- Générer un nom unique avec incrément

### M4 — Commentaire # 3. en double dans sharp_engine.py
- Fichier : app/core/sharp_engine.py:38,42
- # 3. → # 4.

### M5 — Messages d'erreur techniques exposés
- Fichier : app/core/engine.py:86-87
- Logger l'exception complète, retourner message générique

### M6 — shell=True pour install Rust
- Fichier : app/scripts/setup_dependencies.py:727
- Remplacer par urllib.request.urlretrieve + exécution directe

## Batch 3 : Bugs mineurs + Legacy

### m1 — universal_newlines → text
- Fichiers : base_engine.py, extractor_360_engine.py, upscayl_manager.py, base_worker.py

### m2 — bufsize=1 redondant
- Fichier : base_engine.py:43

### m3 — import shutil dans une boucle Sharp video
- Fichier : main.py:463-468,474

### m4 — Image lue 2x dans _check_and_normalize_resolution
- Fichier : engine.py:398+424

### m5 — __annotations__ → dataclasses.fields
- Fichier : params.py:33

### Legacy — Supprimer app/weights/ (2 .pth)
### Legacy — Nettoyer les tags [AUDIT]

## Batch 4 : Optimisations

### P2 — Timeout sur downloads GitHub
- Fichier : upscayl_manager.py, setup_dependencies.py

### Q4 — # noqa: F401 → find_spec
- Fichier : system.py:94

### Q7 — unlink(missing_ok=True)
- Fichier : engine.py:161
