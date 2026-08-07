# ETAT_DES_LIEUX — CorbeauSplat

Instantané factuel du dépôt à `HEAD=a4453d3` (2026-08-07), **arbre de travail inclus** (nombreuses modifications non committées, cf. §0.3). Généré en lecture seule : aucun fichier de code n'a été modifié pour produire ce document. Document autosuffisant — pas d'accès au dépôt requis pour l'exploiter.

Remplace `docs/archive/ETAT_DES_LIEUX.md` (état à `HEAD=b4e88db`, 2026-07-18, v1.5.0), devenu obsolète : l'interface à onglets qu'il décrit n'existe plus.

---

## 0. Changements majeurs depuis le dernier état des lieux

### 0.1 Résumé du diff `b4e88db..HEAD` par thème

43 commits (`git log --oneline b4e88db..HEAD | wc -l` → 43). `git diff b4e88db HEAD --name-status -M` → 82 fichiers : **41 ajouts, 13 suppressions, 27 modifications, 1 renommage**.

**Thème 1 — Disparition complète de l'UI à onglets (13 suppressions).**
`app/gui/main_window.py` (classe `ColmapGUI`) et les 12 onglets de `app/gui/tabs/` (`brush_tab.py`, `cleaner_export_tab.py`, `cleaner_tab.py`, `config_tab.py`, `export_tab.py`, `extractor_360_tab.py`, `four_dgs_tab.py`, `params_tab.py`, `sharp_tab.py`, `splat_transform_tab.py`, `superplat_tab.py`, `upscale_tab.py`) sont supprimés. Vérifié : `ls app/gui/main_window.py` → *No such file or directory* ; `ls -1 app/gui/tabs/` ne contient plus que `__init__.py` et `logs_tab.py`.

**Thème 2 — Nouvelle couche GUI « Studio » (26 fichiers ajoutés dans `app/gui/`).**
- Coquille : `studio_window.py` (`StudioWindow`, 770 lignes), `topbar.py`, `rail.py`, `logbar.py`, `settings_window.py`, `studio_nav.py`, `run_state_binding.py`, `pipeline_planner.py`.
- 12 panneaux dans le nouveau paquet `app/gui/panels/` + 1 module de logique pure `reconstruction_logic.py`.

**Thème 3 — Nouveaux modules `app/core/` (5 fichiers).**
`run_state.py` (état partagé observable), `config_io.py` (configurations nommées), `notifications.py` (notifications macOS), `brush_params.py` (dataclass `BrushParams`), `brush_presets.py` (presets Brush utilisateur persistés).

**Thème 4 — Renommage du lanceur.**
`run.command` → `CorbeauSplat.command` (détecté par `git diff -M`, similarité ~74 %). Ajout de `app/scripts/set_launcher_icon.py`.

**Thème 5 — Suppressions de fichiers morts (arbre de travail).**
`app/core/ply_utils.py` (fichier vide), `verify_imports.py`, `requirements.lock.bak` — les trois sont supprimés mais **non encore committés** (`git status --short` → `D app/core/ply_utils.py`, `D verify_imports.py`, `D requirements.lock.bak`). Vérifié absents du disque.

**Thème 6 — Tests (13 fichiers ajoutés).**
`tests/test_brush_params.py`, `test_brush_presets.py`, `test_config_io.py`, `test_notifications.py`, `test_pipeline_planner.py`, `test_reconstruction_logic.py`, `test_run_state.py`, `test_run_state_binding.py`, `test_studio_nav.py`, `tests/integration/test_tool_launch_integration.py` (committés) ; `tests/test_locales.py`, `tests/test_panel_contracts.py`, `tests/integration/test_e2e_4dgs.py`, `tests/integration/test_e2e_extractor_360.py`, `tests/integration/_synthetic_video.py` (non committés).

**Thème 7 — i18n : purge massive.**
Les 9 locales passent de 516 clés (ancien état des lieux) à **265 clés** chacune. Le diff non committé retire ~390 lignes par fichier (`git diff HEAD --stat` : `assets/locales/fr.json | 383 +-`, `ar.json | 401 +-`, etc.).

**Thème 8 — Archivage documentaire.**
`ETAT_DES_LIEUX.md`, `PROMPT_CLAUDE_CODE_REFONTE_UI.md`, `REFONTE_UI_PROGRESS.md`, `REFONTE_UI_SPEC.md` déplacés vers `docs/archive/` (renommages `R` dans `git status`), + `docs/archive/README.md` (non suivi).

### 0.2 Écart entre la spec de refonte et l'état réel du code

Source : `docs/archive/REFONTE_UI_SPEC.md` (spec cible) et `docs/archive/REFONTE_UI_PROGRESS.md` (tracker par lot).

| Lot | Objet | Statut déclaré dans PROGRESS | Constat dans le code |
|---|---|---|---|
| 0 | Audit état réel | ✅ fait | — |
| 1 | État partagé & plomberie backend | ✅ fait | **Confirmé** : `app/core/run_state.py`, `config_io.py`, `brush_params.py`, `brush_presets.py` existent. |
| 2 | Squelette 4 zones | ✅ fait | **Confirmé** : `StudioWindow.init_ui()` (`studio_window.py:110-231`) monte TopBar / Rail / `center_stack`+`right_stack` / LogBar. |
| 3 | Source / Reconstruction / Entraînement | ✅ UI+plan, « reste câblage moteurs » | **Dépassé** : le câblage moteur est fait (`_build_colmap_worker` L383, `_build_brush_worker` L403, `_start_pipeline_worker` L424). |
| 4 | Nettoyage / Export / Visualiser | ✅ UI, « reste câblage moteurs » | **Partiellement dépassé** : les trois panneaux ont un bouton Lancer local câblé (`_launch_cleaner` L532, `_launch_export` L541, `VisualiserPanel.toggle_server` L136) — mais **pas de chaînage automatique** (voir écart ci-dessous). |
| 5 | 7 modules OUTILS | ✅ UI, « reste câblage moteurs » | **Dépassé** : 7 lanceurs câblés (`_launch_extractor360`, `_launch_fourdgs`, `_launch_fourdgs_colmap_only`, `_launch_sharp`, `_launch_splat_transform`, `_launch_upscale`, `_launch_brush`, L554-628). |
| 6 | Sauvegarde/chargement, presets, notifications, i18n | ✅ | **Confirmé** : `collect_config`/`apply_config`/`save_config_dialog`/`load_config_dialog` (L669-724), `app/core/notifications.py`, `brush_presets.py`. |
| 7 | Nettoyage final + bascule `main.py` | ☐ non fait | **En réalité fait** : `app/cli/launcher.py:22` importe `StudioWindow`, `launcher.py:37` l'instancie. `main_window.py` supprimé. `PROGRESS.md` n'a pas été mis à jour. |

**Écarts spec ↔ code encore ouverts** (chacun vérifié par grep) :

1. **Le mode de pipeline (Gsplat / Sharp / 4DGS) ne change pas le moteur exécuté.**
   `grep -n "current_mode" app/gui/studio_window.py` → **une seule occurrence**, ligne 323, dans `launch()`, où le mode ne sert qu'à `plan_pipeline(mode, self.run_state)`. `_run_pipeline_step()` (L338-381) construit **toujours** un `ColmapWorker` pour l'étape `"reconstruction"` (L360-364), quel que soit le mode. Conséquence : en mode **Sharp**, cliquer « Lancer » exécute COLMAP, pas l'inférence Sharp ; en mode **4DGS**, idem au lieu de `FourDGSEngine`. La spec §2.1 prévoyait 3 pipelines complets. Les moteurs Sharp et 4DGS ne sont atteignables que par les boutons Lancer locaux des modules OUTILS.

2. **Le signal `TopBar.modeChanged` est orphelin.**
   `grep -rn "modeChanged" app/` → défini `topbar.py:34`, émis `topbar.py:80`, **jamais connecté**. Le rail n'est donc jamais tronqué selon le mode (spec §2.2 : « 4DGS : rail tronqué à 2 étapes », « Sharp : pas d'étape Entraînement »). Les 13 items du rail restent tous visibles et cliquables dans les 3 modes.

3. **Le chaînage automatique s'arrête après Entraînement.**
   `_run_pipeline_step` (`studio_window.py:373-381`) : après `source`/`reconstruction`/`entrainement`, toute étape suivante (`nettoyage`, `export`, `visualiser`) déclenche `_finish_pipeline_chain(True, tr("run_chain_manual_continue").format(step))` — la chaîne s'arrête proprement et l'utilisateur doit continuer manuellement. Les drapeaux « Nettoyer après » / « Exporter après » / « Visualiser après » n'ont donc d'effet que sur le *plan affiché* (breadcrumb), pas sur l'exécution. La spec §2.4 et §3 les décrivaient comme des chaînages réels. L'ancien `PostTrainingWorker` qui assurait ce chaînage a été supprimé (`grep -rn "PostTrainingWorker" app/ tests/` → 0 résultat).

4. **« Reprise de COLMAP » est décorative.**
   `ReconstructionPanel` crée `self.resume_path` (`reconstruction_panel.py:82`) et classe le dossier via `classify_resume_folder` (L273) pour afficher un statut. Mais `resume_path` **n'apparaît ni dans `get_params()` (L294-319) ni dans `get_state()` (L350-351)**, et `grep -n "resume" app/gui/studio_window.py` → 0 résultat. Aucun lancement ne consomme ce champ.

5. **Le mode 360 en variante de pipeline a disparu.**
   Spec §2.3 : « 360 Extractor reste une variante du pipeline Gsplat (mode 360, toggle dans Source) **et** un module standalone ». `SourcePanel.get_state()` (`source_panel.py:222-233`) ne contient aucune clé 360, et `_build_colmap_worker` (`studio_window.py:398-401`) appelle `ColmapWorker(params, input_path, output_path, input_type, fps, project_name=...)` **sans** `extractor_360_params` ni `upscale_params`. Seul le module OUTILS 360 subsiste.

6. **L'upscale avant COLMAP a disparu du pipeline** — même cause que le point 5 : `ColmapWorker.__init__` accepte toujours `upscale_params` (`workers.py:67`) mais le seul site de construction (`studio_window.py:398`) ne le passe jamais.

### 0.3 État de l'arbre de travail (non committé)

`git status --short` : **57 fichiers modifiés/supprimés + 5 non suivis + 4 renommages indexés**. `git diff HEAD --stat` → *57 files changed, 805 insertions(+), 4187 deletions(-)*.

Ces modifications correspondent aux **sessions 12 (2026-08-06) et 13 (2026-08-07)** documentées dans `journal.md` : deux audits complets suivis de 23 + 23 corrections. Regroupées par thème :

| Groupe | Fichiers | Apport (lecture rapide du diff) |
|---|---|---|
| **Sécurité** | `app/scripts/checksum_verifier.py` (+13) | Ajout de `verify_download_strict()` **fail-closed** (empreinte absente ⇒ échec) à côté de `verify_download()` fail-open, avec docstrings expliquant lequel utiliser pour bloquer une installation. |
| **Correction fonctionnelle GUI** | `app/gui/panels/reconstruction_logic.py` (+17), `app/gui/studio_window.py` (+10/-9) | Ajout de `apply_source_blur_settings()` : le filtre flou réglé dans Source (`filter_blur`/`blur_strength`) n'atteignait jamais `ColmapParams`. Désormais appliqué dans `_build_colmap_worker`. |
| **Performance export** | `app/core/export_engine.py` (-203 net) | Remplacement de boucles Python par des écritures vectorisées (`np.savetxt`). |
| **Simplification moteurs** | `app/core/engine.py` (212 lignes touchées) | `ColmapEngine.run()` éclaté en 5 méthodes privées (`_validate_and_setup_paths` L197, `_process_input` L241, `_filter_blurry_images` L261, `_run_reconstruction_pipeline` L304, `_prepare_images` L385) — complexité cyclomatique 40 → 19 d'après `journal.md`. |
| **Code mort** | `app/gui/workers.py` (-84), `app/core/system.py` (-33), `app/upscayl_models.py` (-24), `app/core/ply_utils.py` (supprimé), `verify_imports.py` (supprimé) | Suppression de `PostTrainingWorker` et de divers helpers sans appelant. |
| **i18n** | 9 fichiers `assets/locales/*.json` (-390 lignes chacun), `app/core/i18n.py` (+35) | Purge de 375 clés orphelines (633 → 257 → 265 après réajout), `DEFAULT_LANG = "en"` (`i18n.py:5`), garde `is_known_lang()` (`i18n.py:15-23`) qui bloque une valeur de config du type `"../../secrets"`. |
| **Bugs post-refonte** | `app/gui/panels/upscale_panel.py` (+84), `app/gui/widgets/upscale_widgets.py` (-147), `app/gui/panels/extractor360_panel.py` (+11) | `combo_model` (Upscale) et `combo_layout` (360) restaient vides : peuplement + `refresh_models()` (`upscale_panel.py:124`) + `ModelDownloadWorker`. |
| **Outillage CI** | `.github/workflows/ci.yml` (+6), `pyproject.toml` (+31) | Ajout d'un job **Bandit** (`bandit -r app/ -ll`, MEDIUM+HIGH seulement) ; déclaration de `[project.dependencies]` et d'une table `[tool.deptry]` pour supprimer ~40 faux positifs DEP001. |
| **Divers** | `app/scripts/installers/brush.py`, `tools.py`, `upscayl.py`, `app/upscayl_manager.py`, `app/cli/commands.py`, `app/cli/parser.py`, `app/core/{base_engine,brush_engine,brush_params,sharp_engine,superplat_engine,upscale_engine}.py` | Ajustements ponctuels issus des deux audits. |
| **Docs/journal** | `manifest.md`, `journal.md`, `journal.jsonl`, `journal_archive.md` | Consignation des sessions 12 et 13. |

**Fichiers non suivis** (`??`) : `docs/archive/README.md`, `tests/integration/_synthetic_video.py`, `tests/integration/test_e2e_4dgs.py`, `tests/integration/test_e2e_extractor_360.py`, `tests/test_locales.py`, `tests/test_panel_contracts.py`.

**Note** : `audit-report-2026-08-07.md` et `feature-proposal.md` sont présents à la racine mais **exclus du suivi git** (`git check-ignore -v` → `.gitignore:52: audit-report*.md`). De même `config.json` (`.gitignore:30`).

---

## 1. Métadonnées

- **Version** : `1.5.1`. Trois sources concordantes : `pyproject.toml:3` (`version = "1.5.1"`), `app/__init__.py:1` (`VERSION = "1.5.1"`), `CHANGELOG.md:3` (`## [1.5.1] - 2026-07-18`).
  ⚠️ **Le CHANGELOG n'a reçu aucune entrée depuis le 2026-07-18** : toute la refonte Studio (43 commits) et les deux audits de sessions 12/13 n'y figurent pas. `grep -n '^## \[' CHANGELOG.md | head` → `[1.5.1]`, `[1.5.0]`, `[1.2.3]`, `[1.2.2]`, `[1.2.1]`, `[1.2.0]`.
- **Binding Qt** : PySide6. `requirements.txt:1` → `PySide6>=6.6,<7`. Version installée dans `.venv` : **6.11.1** (`.venv/bin/python -c "import PySide6; print(PySide6.__version__)"`).
- **Python** :
  - `.venv` (app principale) : **3.13.12**
  - `.venv_sharp` (Apple ML Sharp) : **3.11.15** (imposé par le fork Apple)
  - `.venv_360` (extracteur 360) : **3.13.12**
  - `.venv_4dgs` (Nerfstudio) : **absent du disque** (`ls -d .venv_4dgs` → No such file or directory) — cohérent avec `manifest.md` qui note la phase B 4DGS comme restante.
- **Dépendances majeures** (`requirements.txt`, 9 lignes) :
  ```
  PySide6>=6.6,<7
  requests>=2.32,<3
  urllib3>=2.0,<3
  numpy>=1.26,<3
  send2trash>=1.8,<2
  pyobjc-framework-Cocoa>=10.0,<11; sys_platform == "darwin"
  Pillow>=12.3,<13
  plyfile>=0.7,<1
  opencv-python-headless>=4.8,<5
  ```
  `requirements.lock` épingle PySide6 6.11.1, numpy 2.4.4, opencv-python-headless 4.13.0.92, Pillow 12.3.0, plyfile 0.9, requests 2.33.1, urllib3 **2.7.0** (relevé de 2.6.3 en session 12 pour une CVE), Send2Trash 1.8.3, pyobjc-core 12.1, pyobjc-framework-Cocoa 10.3.2.
  Depuis l'arbre de travail, `pyproject.toml` déclare aussi ces 9 dépendances dans `[project.dependencies]` (bloc dupliqué volontairement, commentaire : « Doit rester synchronisé avec requirements.txt »).
- **Nombre de fichiers `.py`** : **114** dans `app/` + `tests/` (`find app tests -name '*.py' | wc -l`), **115** dans tout le dépôt hors `.venv*`/`engines/`/`.git`/`target` (le 115ᵉ est `main.py`).
  ⚠️ `manifest.md:11` indique encore « ~74 Python files » — chiffre périmé.
- **Total de lignes Python dans `app/`** : 13 072 (`find app -name '*.py' | xargs wc -l`).
- **`pytest --collect-only`** : **419 tests collectés sur 443, 24 désélectionnés**, en 0,32 s.
  Commande exacte : `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --collect-only -q`.
  Les 24 désélectionnés sont les tests e2e : `pyproject.toml:76` → `addopts = "-m 'not e2e'"`.
- **Marqueurs pytest déclarés** (`pyproject.toml:77-83`) : `e2e`, `e2e_sharp`, `e2e_upscale`, `e2e_4dgs`, `e2e_360`.

---

## 2. Arborescence commentée

### app/ (racine)
- `app/__init__.py` — définit `VERSION = "1.5.1"`.
- `app/upscayl_manager.py` (394 l.) — recherche, téléchargement et gestion du binaire `upscayl-bin` ; `download_model_files()` (L327).
- `app/upscayl_models.py` — catalogue des modèles upscayl compatibles ncnn.

### app/cli/
- `__init__.py` — point d'entrée `main()` (L41) : sans sous-commande ni `--gui`, appelle `_launch_gui()`.
- `commands.py` (673 l.) — implémentations des sous-commandes, `BRUSH_PRESETS`, `BRUSH_DEFAULTS`, `DISPATCH`, `run_pipeline()` (L576).
- `launcher.py` — lance l'application Qt ; **`launcher.py:22` importe `StudioWindow`**, instancié `launcher.py:37`.
- `parser.py` (286 l.) — `argparse` et sous-commandes.

### app/core/ (20 fichiers)
- `base_engine.py` (344 l.) — `IProcessRunner` (L16), `SubprocessRunner` (L44), `BaseEngine` (L123) ; `_execute_command()` (L209), `validate_path()` (L313), `validate_path_standalone()` (L337).
- `brush_engine.py` (167 l.) — moteur Brush ; **`ALLOWED_FLAGS`** (L15-20, 13 flags), filtrage en L97.
- **`brush_params.py`** *(nouveau)* — dataclass `BrushParams` (L29) : surface structurée au-dessus de l'allowlist. 17 champs (`total_steps`, `sh_degree`, `max_splats`, `device`, `max_resolution`, `with_viewer`, `build_mode`, `custom_args`, `start_iter`, `refine_every`, `growth_grad_threshold`, `growth_select_fraction`, `growth_stop_iter`, `refine_pose`, `checkpoint_interval`, `save_iterations`, `refine_mode`). `_CUSTOM_ARG_FLAGS` (L22-26) replie 3 flags non gérés nativement dans `custom_args`, où l'allowlist du moteur les filtre. Expose `to_engine_params()` (dict plat consommé par `BrushEngine.build_command`).
- **`brush_presets.py`** *(nouveau)* — presets Brush **utilisateur**, persistés dans `brush_presets.json` à la racine (`_store_path()` L22). `load_user_presets()` L26, `save_user_preset()` L46, `delete_user_preset()` L55, `merge_presets(builtins)` L65 (l'utilisateur l'emporte sur l'intégré).
- `colmap_commands.py` (178 l.) — fonctions pures de construction des lignes de commande COLMAP.
- **`config_io.py`** *(nouveau)* — configurations **nommées** de la chaîne complète, une par fichier dans `configs/`. Dataclass `ChainConfig` (L44 : `version`, `source`, `colmap`, `brush`, `cleaning`, `export`, `flags`), `is_safe_config_name()` (L35, même règle que la sanitisation du nom de projet), `save_config()` (L83), `load_config()` (L95), `list_configs()` (L104), `delete_config()`. `CONFIG_VERSION = 1` avec point d'extension `_migrate()`.
- `engine.py` (936 l., le plus gros fichier du dépôt) — `ColmapEngine` (L112). `run()` (L164) délègue désormais à 5 méthodes privées : `_validate_and_setup_paths` (L197), `_process_input` (L241), `_filter_blurry_images` (L261), `_run_reconstruction_pipeline` (L304), `_prepare_images` (L385).
- `export_engine.py` (416 l.) — export PLY → spz/glb/obj/xyz.
- `extractor_360_engine.py` (140 l.) — extraction de vues depuis vidéos 360°.
- `four_dgs_engine.py` (175 l.) — préparation de dataset 4DGS pour Nerfstudio.
- `i18n.py` (154 l.) — `LanguageManager` singleton (L26), `DEFAULT_LANG = "en"` (L5), `is_known_lang()` (L15), `tr()` module-level (L144).
- **`notifications.py`** *(nouveau, 47 l.)* — notifications macOS via `NSUserNotificationCenter` (pyobjc, dépendance déjà présente). `is_available()` (L18), `notify(title, message)` (L30). Entièrement défensif : retourne `False` si pyobjc absent.
- `params.py` — dataclass `ColmapParams` (L24, 24 champs) + `blur_factor_from_strength()` (L18).
- `ply_cleaner.py` (203 l.) — nettoyage des artefacts PLY (NumPy/plyfile), presets `light`/`medium`/`strong`.
- **`run_state.py`** *(nouveau, 199 l.)* — voir §3.2.
- `sharp_engine.py` (248 l.) — Apple ML Sharp.
- `splat_transform_engine.py` — wrapper du CLI PlayCanvas ; `ALLOWED_FLAGS_BOOLEAN` (L27), `ALLOWED_FLAGS_VALUE` (L36).
- `superplat_engine.py` (164 l.) — serveur local + viewer SuperSplat.
- `system.py` (374 l.) — détection matériel, `resolve_project_root()`, `get_optimal_threads()`.
- `upscale_engine.py` (151 l.) — wrapper `upscayl-bin`.

*(`app/core/ply_utils.py` n'existe plus — vérifié : `ls app/core/ply_utils.py` → No such file or directory.)*

### app/gui/ (coquille Studio)
- **`studio_window.py`** (770 l.) — `StudioWindow(QMainWindow)` (L87). Voir §5.
- **`topbar.py`** — `TopBar(QWidget)` (L30). Contient : champ nom de projet, label de statut, combo mode (`PIPELINE_MODES` L23 : `gsplat`/`sharp`/`4dgs`), bouton Lancer/Annuler, bouton ⚙. Signaux : `projectNameChanged`, `modeChanged`, `launchRequested`, `settingsRequested`.
- **`rail.py`** (190 l.) — `Rail(QWidget)` (L76). `TOOL_KEYS` (L29) = `("brush", "sharp", "supersplat", "upscale", "splattransform", "4dgs", "360")`. Section PIPELINE (6 étapes issues de `run_state.PIPELINE_STEPS`) + section OUTILS repliable (`CollapseState`). Icônes monochromes (`_STEP_ICONS`, `_TOOL_ICONS`). `set_step_status()` (L166) pose la coche/spinner/icône d'erreur.
- **`logbar.py`** — `LogBar(QWidget)` (L16) : barre de logs repliable en bas de fenêtre, persistante entre écrans. `set_collapsed()` (L44), `append_log()` (L54), `expand_and_search()` (L60).
- **`settings_window.py`** (213 l.) — `SettingsWindow(QDialog)` (L113), fenêtre indépendante ouverte par l'icône ⚙. Signaux : `loadRequested`, `saveRequested`, `resetRequested(bool)`, `notificationsToggled(bool)`. Contient aussi `ResetDialog` (L68) et `_NoScrollComboBox` (L49, empêche la molette de changer une valeur par accident).
- **`studio_nav.py`** — `PageRegistry` (L11, mapping clé ↔ index du `QStackedWidget`) et `CollapseState` (L40). Logique pure, sans Qt.
- **`run_state_binding.py`** — `bind_flag_checkbox()` (L20) et `bind_text_field()` (L42) : liaison bidirectionnelle widget ↔ `RunState`, avec anti-boucle.
- **`pipeline_planner.py`** — `plan_pipeline(mode, run_state)` (L19). Logique pure, sans Qt. Voir §3.3.
- `managers.py` (205 l.) — `SessionManager` (L15) et `AppLifecycle` (L98). Voir §3.1.
- `base_worker.py` — `BaseWorker(QThread)`, signaux standardisés.
- `workers.py` (754 l.) — 9 workers : `Extractor360Worker` (L18), `ColmapWorker` (L64), `BrushWorker` (L139), `SharpWorker` (L417), `SharpVideoWorker` (L496), `CleanerWorker` (L538), `SplatTransformWorker` (L626), `FourDGSWorker` (L664), `ExportWorker` (L703). *(`PostTrainingWorker` supprimé.)*
- `styles.py` (167 l.) — 3 thèmes (`slate`, `graphite`, `blue`), QPalette + QSS ; `get_saved_theme()` L106, `save_theme()` L120 (clé `"theme"` de `config.json`).
- `tabs/logs_tab.py` (136 l.) — **seul vestige de l'ancienne UI à onglets** encore présent ; `LogsTab` (L17) est réutilisé par `LogBar`.

### app/gui/panels/ (13 fichiers, tous nouveaux)
Convention commune (`app/gui/panels/__init__.py`) : **chaque panneau est une classe Python simple (pas un `QWidget`) exposant deux attributs `center` et `right`**, chacun un `QWidget`, insérés respectivement dans `center_stack` et `right_stack` de `StudioWindow`.

| Fichier | Classe | Clé rail | Rôle | `get_params` | `set_params` | `get_state` | `set_state` | `retranslate_ui` |
|---|---|---|---|---|---|---|---|---|
| `source_panel.py` (272 l.) | `SourcePanel` (L40) | `source` | Étape Source : chemins d'entrée/sortie, nom de projet, FPS vidéo, destination checkpoints, toggles d'automatisation, filtre flou, undistort, options d'export | ❌ | ❌ | ✅ L222 | ✅ L235 | ✅ L256 |
| `reconstruction_panel.py` (390 l.) | `ReconstructionPanel` (L55) | `reconstruction` | Étape Reconstruction (COLMAP) : accordéons Feature Extraction / Matching / Mapper + champ « Reprise de COLMAP » | ✅ L294 | ✅ L321 | ✅ L350 | ✅ L353 | ✅ L358 |
| `reconstruction_logic.py` | *(module)* | — | Logique pure hors Qt : `classify_resume_folder()` (L22), `apply_source_blur_settings()` (L49) | — | — | — | — | — |
| `entrainement_panel.py` (395 l.) | `EntrainementPanel` (L54) | `entrainement` **et** `brush` | Étape Entraînement (Brush). Paramètre `standalone=False` (L57) : la même classe sert de module OUTILS Brush | ✅ L300 (→ `BrushParams`) | ✅ L319 | ✅ L353 | ✅ L356 | ✅ L361 |
| `cleaner_panel.py` (208 l.) | `CleanerPanel` (L35) | `nettoyage` | Étape Nettoyage : fichier unique ou batch, intensité | ✅ L143 | ❌ | ✅ L155 | ✅ L165 | ✅ L197 |
| `export_panel.py` (157 l.) | `ExportPanel` (L34) | `export` | Étape Export : construit directement sur `ExportEngine`/`ExportWorker` | ❌ (`get_format`/`get_scale`) | ❌ | ✅ L119 | ✅ L122 | ✅ L151 |
| `visualiser_panel.py` (233 l.) | `VisualiserPanel` (L40) | `visualiser` **et** `supersplat` | Étape Visualiser / module SuperSplat : démarrage-arrêt serveur, ports, position/rotation caméra, No-UI | ❌ | ❌ | ❌ | ❌ | ✅ L224 |
| `sharp_panel.py` (181 l.) | `SharpPanel` (L31) | `sharp` | Module OUTILS Apple ML Sharp (Photo/Vidéo → PLY) | ✅ L138 | ❌ | ❌ | ❌ | ✅ L167 |
| `upscale_panel.py` (210 l.) | `UpscalePanel` (L23) | `upscale` | Module OUTILS Upscale (upscayl-ncnn) : sélection modèle, échelle, tile, TTA, compression. `refresh_models()` L124 | ✅ L188 | ❌ | ❌ | ❌ | ✅ L199 |
| `splat_transform_panel.py` (159 l.) | `SplatTransformPanel` (L25) | `splattransform` | Module OUTILS SplatTransform : format cible, filtres, décimation | ✅ L136 | ❌ | ❌ | ❌ | ✅ L146 |
| `four_dgs_panel.py` | `FourDGSPanel` (L23) | `4dgs` | Module OUTILS 4DGS : dossier vidéos multi-caméras, destination, FPS, bouton « COLMAP seulement » | ✅ L100 | ❌ | ❌ | ❌ | ✅ L108 |
| `extractor360_panel.py` (190 l.) | `Extractor360Panel` (L28) | `360` | Module OUTILS 360 Extractor : vidéo source, dossier de sortie, layout, format | ✅ L154 | ❌ | ❌ | ❌ | ✅ L170 |

### app/gui/widgets/
- `dialog_utils.py` — wrappers autour de `QFileDialog`. **`grep -rln "QFileDialog" app/gui/` → un seul fichier : `dialog_utils.py`.** Les 12 fichiers appelants (11 panneaux + `logs_tab.py`) passent tous par lui. *(Dette de l'ancien audit résolue.)*
- `drop_line_edit.py` — `DropLineEdit(QLineEdit)`, glisser-déposer avec validation de chemin (`_validate_path` L44).
- `upscale_widgets.py` (128 l.) — `BinaryInstallWorker`, `ModelDownloadWorker`, `TestWorker`.

### app/scripts/
- `checksum_verifier.py` — `compute_file_sha256()`, `verify_download()` (fail-open, documenté comme tel), **`verify_download_strict()` (fail-closed)**.
- `checksums.json` — empreintes SHA-256 attendues.
- `set_launcher_icon.py` *(nouveau)* — pose l'icône du lanceur macOS.
- `setup_dependencies.py` (137 l.) — réexporte les installers.
- `installers/` — `base.py` (242 l.), `brush.py` (301 l.), `extractor_360.py`, `mapping.py`, `sharp.py`, `splat_transform.py`, `spz.py`, `supersplat.py`, `tools.py` (204 l.), `upscayl.py`.

### assets/locales/
9 fichiers `{ar,de,en,es,fr,it,ja,ru,zh}.json`, **265 clés chacun**.

### Racine
- `main.py` — 13 lignes ; ajoute la racine au `sys.path` puis appelle `app.cli.main()`.
- `CorbeauSplat.command` — lanceur macOS double-cliquable (ex-`run.command`).
- `config.json` — état de session utilisateur (non versionné, `.gitignore:30`).
- `config.example.json` — **périmé** (voir §8).
- `Makefile`, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `requirements.lock`, `uv.lock`.
- `manifest.md`, `CHANGELOG.md`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `journal.md`, `journal.jsonl`, `journal_archive.md`.
- `graphify-out/` — graphe de connaissance (`graph.json`, `GRAPH_REPORT.md`, `manifest.json`).
- `docs/archive/` — 7 documents obsolètes archivés en session 13.

---

## 3. Nouvelle plomberie d'état

### 3.1 `SessionManager` — ce qu'il persiste maintenant

`app/gui/managers.py:15-92`. **Sa portée a été fortement réduite** par la refonte.

```python
CONFIG_KEY = "last_project"                       # managers.py:26
def get_session_file(self) -> Path                # L34 → resolve_project_root() / "config.json"
def save(self, immediate=False)                   # L37 — debounce 1500 ms via QTimer
def _source_panel(self)                           # L44 → self.mw.panels.get("source")
def _do_save(self)                                # L48
def _write_merged(self, project_state)            # L54 — lit le fichier, ne touche QUE sa clé, réécrit
def load(self)                                    # L74
```

**Il ne persiste plus que l'état du panneau Source**, sous la clé `"last_project"` (auparavant : 9 blocs `tab_mapping` couvrant tous les onglets). Le contenu est exactement le dict retourné par `SourcePanel.get_state()` : `project_name`, `input_path`, `output_path`, `checkpoint_dest`, `fps`, `filter_blur`, `blur_strength`, `export_dir`, `export_format`.

Déclenchement : `StudioWindow._wire_session_autosave()` (`studio_window.py:233-241`) connecte le `textChanged` de trois champs Source (`input_project_name`, `input_path`, `output_path`) à `save()` ; `closeEvent` (L757) appelle `save(immediate=True)`.

`config.json` reste **partagé** entre trois écrivains indépendants, chacun en fusion prudente : `SessionManager` (clé `last_project`), `LanguageManager` (clé `language`, `i18n.py:97-110`), `styles.py` (clé `theme`, L120-131).

### 3.2 `RunState` — source de vérité unique des drapeaux dupliqués

`app/core/run_state.py`. **Ne remplace pas** `SessionManager` : il n'est pas persisté par lui-même (seulement sérialisé dans une `ChainConfig`, cf. §3.4).

```python
class StepStatus(str, Enum): IDLE / RUNNING / DONE / ERROR       # L23
PIPELINE_STEPS = ("source","reconstruction","entrainement",
                  "nettoyage","export","visualiser")             # L34
_FLAG_DEFAULTS = {"entrainement_apres": False, "nettoyer_apres": False,
                  "exporter_apres": False, "visualiser_apres": False,
                  "undistort_images": False}                     # L45
_FIELD_DEFAULTS = {"project_name": ""}                           # L56

class RunState:                                                  # L61
    add_observer / remove_observer / _notify                     # L77 / L82 / L86
    get_flag / set_flag                                          # L94 / L97
    get_field / set_field                                        # L106 / L109
    get_status / set_status / reset_status                       # L166 / L169 / L177
    to_dict / load_dict / from_dict                              # L183 / L186 / L195
```

Deux garanties explicitées dans le code : (a) `set_flag`/`set_field`/`set_status` ne notifient **que si la valeur change réellement** (L101, L113, L173) — anti-boucle de rétroaction ; (b) les observateurs reçoivent la clé modifiée, et chaque exception est journalisée sans interrompre les autres (L88-91). Même idiome que `LanguageManager`.

**Consommateurs** : `SourcePanel._bind` et `ReconstructionPanel._bind` (via `run_state_binding.bind_flag_checkbox`), `pipeline_planner.plan_pipeline`, `Rail.set_step_status`, `StudioWindow` (statuts + nom de projet, `studio_window.py:92, 133-136, 327`).

**`undistort_images` — dette résolue** : le champ vit désormais une seule fois dans `RunState`. La case existe dans les deux panneaux (`source_panel.py:141-143` et `reconstruction_panel.py:245-246`), toutes deux bindées sur le même drapeau. `ReconstructionPanel.get_params()` (L315) le lit depuis `self.run_state.undistort_images`.

### 3.3 `plan_pipeline` — le plan de run

`app/gui/pipeline_planner.py:19-41`. Logique pure, testable sans Qt.

| Mode | Plan retourné |
|---|---|
| `4dgs` | `["source", "reconstruction"]` (tronqué, L24-25) |
| `sharp` | `["source", "reconstruction"]` + post-étapes selon drapeaux (pas d'`entrainement`, L30) |
| `gsplat` | `["source", "reconstruction"]` + `entrainement` si `entrainement_apres` + `nettoyage`/`export`/`visualiser` selon leurs drapeaux |

Un mode inconnu est ramené à `gsplat` (L21-22).

### 3.4 `config_io` — configurations nommées

`app/core/config_io.py`. **Complète** `SessionManager` sans le remplacer : là où `SessionManager` persiste *la* session courante (une seule, dans `config.json`), `config_io` gère *plusieurs configurations nommées et réutilisables*, une par fichier JSON dans `configs/` (créé à la demande, `configs_dir()` L28).

`ChainConfig` (L44) agrège 6 sections : `source`, `colmap`, `brush`, `cleaning`, `export`, `flags`. La sérialisation réutilise les contrats `to_dict`/`from_dict` existants (`ColmapParams`, `BrushParams`, `RunState`), tous tolérants aux clés manquantes/inconnues — une config sauvegardée par une version antérieure se recharge sans casser.

Côté UI : `StudioWindow.collect_config()` (L670) et `apply_config()` (L683) font le pont ; `save_config_dialog()` (L697) et `load_config_dialog()` (L708) sont branchés sur les signaux `saveRequested`/`loadRequested` de `SettingsWindow` (`studio_window.py:736-737`).

---

## 4. Paramètres et dataclasses

Il y a maintenant **trois** dataclasses de paramètres (contre une seule à `b4e88db`).

### `ColmapParams` (`app/core/params.py:24`) — 24 champs, inchangés

`camera_model` `SIMPLE_RADIAL`, `single_camera` `True`, `max_image_size` `3200`, `max_num_features` `8192`, `feature_type` `SIFT`, `matching_type` `SIFT_BRUTEFORCE`, `estimate_affine_shape` `True`, `domain_size_pooling` `True`, `max_ratio` `0.8`, `max_distance` `0.7`, `cross_check` `True`, `guided_matching` `False`, `ba_refine_focal_length` `True`, `ba_refine_principal_point` `False`, `ba_refine_extra_params` `True`, `min_num_matches` `15`, `matcher_type` `exhaustive`, `sequential_overlap` `30`, `undistort_images` `False`, `filter_blurry` `False`, `blur_factor` `0.7`, `thermal_throttling` `False`, `use_view_graph_calibration` `True`, `ignore_watermarks` `True`.

**Nouveauté : `blur_factor_from_strength()` (`params.py:18`)** — le mapping `{"light":0.5,"medium":0.7,"strong":0.9}` vit désormais dans **un seul endroit**. `grep -rn "blur_factor_from_strength" app/` → 3 appelants : `app/cli/commands.py:11` (import) et `:105`, `app/gui/panels/reconstruction_logic.py:12` et `:60`. *(La duplication GUI/CLI signalée dans l'ancien audit est résolue.)*

### `BrushParams` (`app/core/brush_params.py:29`) — nouvelle

17 champs, tous optionnels (`None` = « non défini » ⇒ flag omis). Documenté explicitement comme **ne modifiant pas le contrat de sécurité** : le module ne produit que le dict plat déjà consommé par `BrushEngine.build_command()`, l'allowlist reste seule maîtresse côté moteur.

### `ChainConfig` (`app/core/config_io.py:44`) — nouvelle

Voir §3.4.

### Cross-référence champ ↔ panneau

| Champ | Panneau | Lu par | Remarque |
|---|---|---|---|
| Les 23 champs COLMAP hors `undistort_images` | `reconstruction_panel.py` | `get_params()` L294-319 / `set_params()` L321-348 | OK, aller-retour complet |
| `undistort_images` | **`source_panel.py:141` ET `reconstruction_panel.py:245`** | `run_state.undistort_images` (`reconstruction_panel.py:315`) | Deux widgets, **une** source de vérité |
| `filter_blurry` / `blur_factor` | `source_panel.py` (`chk_filter_blur`, `combo_blur`) | `apply_source_blur_settings()` appelé dans `studio_window.py:392` | Reporté sur `ColmapParams` juste avant le lancement |
| `guided_matching` | `reconstruction_panel.py` (`guided_match_check`) | `get_params()` L308 **et** `set_params()` L337 | Aller-retour complet, widget actif *(dette résolue)* |
| `sequential_overlap` | `reconstruction_panel.py` (`sequential_overlap_spin`) | `get_params()` L314, `set_params()` L338, activation conditionnelle `_update_sequential_enabled()` L348 | Widget présent *(dette résolue)* |
| `checkpoint_dest`, `export_dir`, `export_format` | `source_panel.py:96, 177, 180` | **personne** | Voir §8, anomalie A3 |

---

## 5. Couche GUI — `StudioWindow`

`app/gui/studio_window.py:87-770`. 25 méthodes ; aucune ne dépasse 150 lignes (la plus longue est `init_ui()`, L110-231, soit 122 lignes).

### Structure en 4 zones (`init_ui`, L110-231)
1. **TopBar** (haut) — L128-137.
2. **Rail** (gauche, largeur fixe 220 px) — L143-146.
3. **Centre** (breadcrumb + `center_stack`, stretch 3) et **barre de droite** (`right_stack`, largeur fixe 400 px) — L152-168, séparés par des filets fins `_vline()`.
4. **LogBar** (bas, repliable) — L219-220, puis **barre inférieure permanente** (`_build_bottom_bar()`, L243-264) : label `v{VERSION}` + boutons Relancer / Quitter.

Fenêtre : `setMinimumSize(820, 560)` (L115), taille initiale = 90 % de l'écran disponible (L119).

### Dictionnaire des panneaux (`studio_window.py:172-188`)

```python
self.panels = {
    "source": SourcePanel(self.run_state),
    "reconstruction": ReconstructionPanel(self.run_state),
    "entrainement": EntrainementPanel(self.run_state),
    "nettoyage": CleanerPanel(self.run_state),
    "export": ExportPanel(self.run_state),
    "visualiser": VisualiserPanel(self.run_state),
    "brush": EntrainementPanel(self.run_state, standalone=True),   # même classe
    "sharp": SharpPanel(self.run_state),
    "supersplat": VisualiserPanel(self.run_state),                 # même classe
    "upscale": UpscalePanel(self.run_state),
    "splattransform": SplatTransformPanel(self.run_state),
    "4dgs": FourDGSPanel(self.run_state),
    "360": Extractor360Panel(self.run_state),
}
```

13 clés = `_PAGE_KEYS` (L69) = `PIPELINE_STEPS` (6) + `TOOL_KEYS` (7). **Deux classes sont instanciées deux fois** — `EntrainementPanel` (étape Entraînement + module Brush) et `VisualiserPanel` (étape Visualiser + module SuperSplat) — conformément à la spec §3, avec un `run_state` partagé mais des widgets distincts.

### Navigation et auto-follow
- `on_rail_selected(key)` (L291-298) : un clic manuel **désaccouple** l'auto-follow (`self._auto_follow = False`) — même logique que le lock d'auto-scroll des logs. Si l'étape sélectionnée est en `ERROR`, la barre de logs se déplie automatiquement (L297-298).
- `follow_step(key)` (L307-312) : ne bascule le rail que si `_auto_follow` est encore vrai.
- `launch()` (L318) remet `_auto_follow = True` (L326). **Aucun mécanisme de « revenir au live »** n'existe (question ouverte de la spec §2.4, toujours ouverte).

---

## 6. Couplages et flux — le tableau « Lancer »

Deux chemins de lancement coexistent, tous deux passant par `StudioWindow` (plus aucun lancement tab-local fire-and-forget : `grep -rn "run_standalone" app/` → **0 résultat**, l'ancien `BrushTab.run_standalone()` a disparu).

### 6.1 Chemin A — bouton « Lancer » du top bar (chaîne pipeline)

`TopBar.launchRequested` → `StudioWindow.on_topbar_launch()` (L483) → si un worker tourne, il est annulé (`_cancel_active_worker`, L492) ; sinon `launch()` (L318).

`launch()` : lit le mode (L323), calcule le plan (`plan_pipeline`, L324), réinitialise les statuts (L327), met à jour le breadcrumb (L328), journalise le plan (L329), puis `_run_pipeline_step(0)` (L331).

| Étape du plan | Traitement dans `_run_pipeline_step` (L338-381) | Worker | Moteur |
|---|---|---|---|
| `source` | L352-357 : marquée `DONE` immédiatement (pas de worker propre — elle ne fait que fournir les chemins), enchaîne | aucun | — |
| `reconstruction` | L359-363 → `_build_colmap_worker()` (L383-401) | `ColmapWorker` | `ColmapEngine.run()` |
| `entrainement` | L365-369 → `_build_brush_worker()` (L403-422) | `BrushWorker` | `BrushEngine.train()` |
| `nettoyage` / `export` / `visualiser` | L373-381 : **chaîne arrêtée** avec message `run_chain_manual_continue` | aucun | — |

`_build_colmap_worker` compose : chemins et FPS depuis `SourcePanel.get_state()`, `ColmapParams` depuis `ReconstructionPanel.get_params()`, puis `apply_source_blur_settings()` (L392-394) pour reporter le filtre flou, `_detect_input_type()` (L77-84, distingue `"video"`/`"images"` par extension).

`_build_brush_worker` compose : `project_dir = Path(output_path) / project_name` (L416), paramètres via `EntrainementPanel.get_params().to_engine_params()` (L418), `ply_name` optionnel (L419-421).

`_start_pipeline_worker(step, worker)` (L424-439) : pose `RUNNING` sur `run_state` **et** sur le rail, relie `log_signal`/`status_signal` à `logbar.append_log`, connecte `finished_signal` à `_on_pipeline_step_finished`, bascule le top bar en « Annuler », déplie la barre de logs, démarre le thread.

`_on_pipeline_step_finished(success, message)` (L441-460) : succès ⇒ `DONE` + étape suivante ; échec ⇒ `ERROR`, arrêt de la chaîne, notification + `QMessageBox` **sauf si l'arrêt a été demandé par l'utilisateur** (`stopped_by_user`, L455).

### 6.2 Chemin B — boutons « Lancer » locaux (modules OUTILS et post-étapes)

Câblés dans `init_ui` (`studio_window.py:194-203`) :

| Bouton | Slot | Worker | Moteur |
|---|---|---|---|
| `panels["nettoyage"].btn_run` | `_launch_cleaner` L532 | `CleanerWorker` | `ply_cleaner.clean_ply` |
| `panels["export"].btn_run` | `_launch_export` L541 | `ExportWorker` | `ExportEngine.export()` |
| `panels["360"].btn_run` | `_launch_extractor360` L554 | `Extractor360Worker` | `Extractor360Engine.run_extraction()` |
| `panels["4dgs"].btn_run` | `_launch_fourdgs` L563 | `FourDGSWorker(input, output, fps)` | `FourDGSEngine.process_dataset()` |
| `panels["4dgs"].btn_colmap_only` | `_launch_fourdgs_colmap_only` L571 | `FourDGSWorker(None, output, fps)` | `FourDGSEngine.run_colmap()` |
| `panels["sharp"].btn_run` | `_launch_sharp` L581 | `SharpWorker` ou `SharpVideoWorker` selon `params["mode"]` | `SharpEngine.predict` / `process_video_frames` |
| `panels["splattransform"].btn_run` | `_launch_splat_transform` L596 | `SplatTransformWorker` | `SplatTransformEngine.transform()` |
| `panels["upscale"].btn_run` | `_launch_upscale` L616 | `TestWorker` (`upscale_widgets.py`) | `upscayl_manager` / `UpscaleEngine` |
| `panels["brush"].btn_run` | `_launch_brush` L624 | `BrushWorker` | `BrushEngine.train()` |
| `panels["source"].btn_delete_dataset` | `_delete_dataset` L639 | aucun | `ColmapEngine.delete_project_content()` (statique, mise à la corbeille, confirmation `QMessageBox`) |
| `VisualiserPanel.btn_*` (interne au panneau) | `toggle_server` L136 | aucun (threads internes) | `SuperSplatEngine.start_supersplat` / `start_data_server` |

Tous passent par `_start_tool_worker(worker, finished_signal=None)` (L502-513), puis `_on_tool_finished` (L515-525). Une seule variable `self._active_worker` — donc **un seul worker à la fois**, chemin A et chemin B confondus.

`_check_paths(*paths)` (L527-530) : garde commune, affiche `err_no_paths` si un chemin est vide.

### 6.3 Fermeture

`closeEvent` (L755-769) : sauvegarde immédiate de la session, annulation du worker actif, puis `engine.stop_all()` sur les panneaux `"visualiser"` et `"supersplat"` — pas de serveur SuperSplat orphelin.

### 6.4 Réglages, notifications, cycle de vie

`open_settings()` (L732-742) instancie `SettingsWindow` à la demande (singleton paresseux) et connecte 4 signaux : `saveRequested` → `save_config_dialog`, `loadRequested` → `load_config_dialog`, `notificationsToggled` → `set_notifications_enabled`, `resetRequested` → `reset_factory`.

`notify(title, message)` (L728-731) ne fait rien tant que `_notifications_enabled` est faux — **et il est initialisé à `False`** (`studio_window.py:98`) sans être relu depuis `config.json` au démarrage. Le réglage n'est donc pas persistant entre deux lancements.

`restart_application()` (L744) et `reset_factory(deep=False)` (L747) délèguent à `AppLifecycle`.

---

## 7. i18n

**Mécanisme** — `LanguageManager` (`app/core/i18n.py:26`), singleton via `__new__` (L29), pattern Observer. Instance module-level `_lm` (L142) derrière des wrappers libres `tr()` (L144), `get_current_lang()` (L147), `set_language()` (L150), `add_language_observer()` (L153).

Changements depuis `b4e88db` :
- **`DEFAULT_LANG = "en"`** (L5) — l'anglais est la langue par défaut au premier lancement (auparavant : français).
- **`is_known_lang(lang_code)`** (L15-23) — garde de sécurité : refuse toute valeur qui n'est pas alphanumérique, ce qui empêche une valeur de `config.json` du type `"../../secrets"` de sortir du dossier des locales.
- Chaîne de repli inchangée : langue choisie → `en.json` → `fr.json` → dict vide (L48-58).

**Locales** — `assets/locales/{ar,de,en,es,fr,it,ja,ru,zh}.json`.
Comptage plat (clés imbriquées jointes par `.`) : **265 clés par fichier, pour les 9 fichiers**.
Diff exhaustif (union des 9 fichiers, comparée fichier par fichier) : union = 265, **0 clé manquante nulle part** → **les 9 locales sont parfaitement alignées**.

**Verrouillage par tests** — `tests/test_locales.py` (4 tests, non committé) impose trois invariants :
1. `test_all_nine_locales_present` — exactement les 9 codes attendus ;
2. `test_locales_share_the_exact_same_keys` — aucune clé en trop ni manquante par rapport à `fr.json` ;
3. `test_no_orphan_locale_keys` — **aucune clé ne doit être absente du code de `app/`** (c'est ce test qui a fait tomber le compte de 633 à 257 clés en session 13) ;
4. `test_every_tr_literal_has_a_translation` — tout littéral passé à `tr()` doit exister dans les 9 langues.

**Re-traduction** — chaque panneau, la TopBar, le Rail, la LogBar, la SettingsWindow et `StudioWindow` s'enregistrent via `add_language_observer(self.retranslate_ui)` dans leur `__init__`. `StudioWindow.retranslate_ui()` (L751-754) ne retraduit que le titre de fenêtre et les deux boutons de la barre inférieure — le reste est pris en charge par les composants eux-mêmes.

**Point de vigilance documenté dans le code** (`studio_window.py:373-379`, commentaire de 7 lignes) : `LanguageManager.tr()` applique `.format(*args)` en interne dès que des arguments supplémentaires sont fournis **et** que la clé est trouvée. Passer à la fois un texte de repli et faire son propre `.format()` ensuite ferait consommer le texte de repli comme substitution `{0}`. D'où l'appel `tr("run_chain_manual_continue").format(step)` sans repli.

---

## 8. Sécurité

Tous les greps ci-dessous ont été réexécutés sur le code actuel.

### `validate_path()` — 37 sites d'appel

`grep -rn "validate_path" app/ | grep '\.py:'` → **37 lignes**. Définition : `BaseEngine.validate_path()` (`base_engine.py:313`), plus une variante libre `validate_path_standalone(path, project_root=None)` (`base_engine.py:337`) pour les appelants hors moteur.

Répartition par fichier :
- `app/core/sharp_engine.py` : 75, 76, 83, 93
- `app/core/export_engine.py` : 47, 51  ← **nouveaux depuis l'ancien audit** (finding A2-I2)
- `app/core/splat_transform_engine.py` : 92, 93, 98
- `app/core/extractor_360_engine.py` : 48, 49
- `app/core/brush_engine.py` : 127, 128
- `app/core/engine.py` : 199, 223, 232, 900, 903
- `app/core/upscale_engine.py` : 95, 99, 102, 125, 126, 132
- `app/core/four_dgs_engine.py` : 120, 121
- `app/core/ply_cleaner.py` : 105, 108, 157, 158
- `app/gui/widgets/drop_line_edit.py` : 30, 44 (validation GUI au drop)
- `app/core/base_engine.py` : 313, 325, 337

### `shell=True` — aucune occurrence réelle

`grep -rn "shell=True" app/ | grep '\.py:'` → **1 seul hit, un commentaire** : `app/core/splat_transform_engine.py:7` (« All arguments are passed as a list; shell=True is never used »). Toutes les commandes sont passées en liste à `subprocess.Popen`.

### Allowlist Brush — toujours dans `brush_engine.py`

Contrairement à ce qu'on pouvait craindre avec l'arrivée de `brush_params.py`/`brush_presets.py`, **l'allowlist n'a pas bougé** : elle reste `BrushEngine.ALLOWED_FLAGS` (`app/core/brush_engine.py:15-20`), 13 flags :

```python
ALLOWED_FLAGS = {
    "--save-iterations", "--log-level", "--test-split",
    "--start-iter", "--refine-every", "--growth-grad-threshold",
    "--growth-select-fraction", "--growth-stop-iter", "--max-splats",
    "--eval-every", "--export-every", "--max-resolution", "--refine-pose"
}
```

Appliquée en `brush_engine.py:97` (`if arg in self.ALLOWED_FLAGS`). `brush_params.py` le documente explicitement (docstring L8-14) : le module « ne touche ni à `ALLOWED_FLAGS` ni à `build_command` », il ne fait que produire le dict plat déjà consommé, et replie 3 flags dans `custom_args` où l'allowlist les filtre comme avant. **Le contrat de sécurité est inchangé.**

Allowlist SplatTransform inchangée : `ALLOWED_FLAGS_BOOLEAN` (`splat_transform_engine.py:27`) et `ALLOWED_FLAGS_VALUE` (L36), appliquées L119 et L122.

### CORS SuperSplat — inchangé, toujours strict

`app/core/superplat_engine.py:91-148`. Bind exclusif sur `127.0.0.1` (L127). Le handler CORS (L103-111) reflète l'`Origin` de la requête **uniquement si son hostname est `localhost` ou `127.0.0.1`** (L107, via `urlparse`), sinon replie sur `http://localhost:{port}` (L108). Ajout d'un en-tête `Vary: Origin` (L111) avec le commentaire expliquant qu'un cache partagé servirait sinon une réponse à la mauvaise origine.

### Sanitisation du nom de projet — inchangée, toujours en liste noire

`grep -rni "sanitiz" app/ | grep '\.py:'` → **1 seul hit, un commentaire** (`app/gui/workers.py:318`).

La vérification réelle reste inline, en liste noire, dans `ColmapEngine._validate_and_setup_paths()` (`app/core/engine.py:205`) :

```python
if ".." in self.project_name or "/" in self.project_name or "\\" in self.project_name:
    self.log("Nom de projet invalide")
    return None
```

`config_io.is_safe_config_name()` (`config_io.py:35-40`) applique **exactement la même règle** aux noms de configuration (commentaire explicite « Même règle que la sanitisation du nom de projet »), et `brush_presets.save_user_preset()` (L46-49) l'applique aux noms de presets.

### Checksums — fail-closed disponible (arbre de travail)

`app/scripts/checksum_verifier.py` expose désormais deux fonctions clairement documentées :
- `verify_download(path, expected_hash)` — **fail-open** : empreinte absente ⇒ `True`. Docstring : « Do NOT use to gate installation ».
- `verify_download_strict(path, expected_hash)` — **fail-closed** : empreinte absente ⇒ `False`. Docstring : « the variant installers must use before extracting or executing a downloaded artifact ».

D'après `journal.md`, les 3 appelants installeurs ont été basculés sur la variante stricte (finding A2-C1).

### Analyse statique de sécurité en CI

Ajout non committé dans `.github/workflows/ci.yml` : job **Bandit** (`bandit -r app/ -ll`), limité aux findings MEDIUM et HIGH — le commentaire précise que les 109 findings LOW (assert, `try/except/pass`, `subprocess` sans shell) ont été arbitrés comme du bruit.

---

## 9. Tests

`find tests -name '*.py' | wc -l` → 41 fichiers, dont **30 contiennent des tests collectés**.

`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --collect-only -q` → **419 tests collectés / 443, 24 désélectionnés** (marqueur `e2e`).

### Répartition exacte (tests collectés par fichier)

| Fichier | Tests | | Fichier | Tests |
|---|---:|---|---|---:|
| `tests/test_colmap_engine.py` | 37 | | `tests/test_studio_nav.py` **†** | 9 |
| `tests/test_setup_dependencies.py` | 31 | | `tests/test_sharp_engine.py` | 9 |
| `tests/test_cli.py` | 30 | | `tests/test_reconstruction_logic.py` **†** | 9 |
| `tests/test_panel_contracts.py` **‡** | 27 | | `tests/test_export_engine.py` | 9 |
| `tests/test_upscayl_manager.py` | 25 | | `tests/test_brush_presets.py` **†** | 9 |
| `tests/test_extractor_360_engine.py` | 25 | | `tests/integration/test_tool_launch_integration.py` **†** | 9 |
| `tests/test_workers.py` | 22 | | `tests/integration/test_engine_params_integration.py` | 9 |
| `tests/test_managers.py` | 18 | | `tests/test_ply_cleaner.py` | 7 |
| `tests/test_config_io.py` **†** | 18 | | `tests/test_pipeline_planner.py` **†** | 7 |
| `tests/test_brush_engine.py` | 17 | | `tests/integration/test_colmap_pipeline.py` | 7 |
| `tests/test_four_dgs_engine.py` | 15 | | `tests/integration/test_cleaner_export_integration.py` | 7 |
| `tests/test_run_state.py` **†** | 13 | | `tests/test_run_state_binding.py` **†** | 5 |
| `tests/test_base_engine.py` | 13 | | `tests/test_locales.py` **‡** | 4 |
| `tests/test_brush_params.py` **†** | 12 | | `tests/integration/test_e2e_extractor_360.py` **‡** | 4 |
| `tests/integration/test_security_i18n_integration.py` | 10 | | `tests/test_notifications.py` **†** | 2 |

**†** ajouté et committé depuis `b4e88db` — **‡** ajouté mais **non committé**.

Fichiers sans test collecté (helpers ou entièrement désélectionnés) : `conftest.py` ×2, `__init__.py` ×2, `_synthetic_image.py`, `_synthetic_scene.py`, `_synthetic_video.py`, `test_e2e_pipeline.py`, `test_e2e_sharp.py`, `test_e2e_upscale.py`, `test_e2e_4dgs.py` (les 4 derniers étant désélectionnés par `addopts`).

### Les deux nouveaux garde-fous structurels

**`tests/test_panel_contracts.py` (27 tests, non committé)** — analyse **AST** de `app/gui/panels/`, sans instancier Qt ni display. Motivation citée dans la docstring : « la couche `app/gui/panels/` concentre l'orchestration mais n'avait aucun test. La classe de bug récurrente y est *widget créé, jamais relu* — quatre findings d'affilée (`chk_upscale`, `chk_stabilized`, `tta`/`compression`, `chk_filter_blur`/`combo_blur`) ». Le test parcourt les `INPUT_WIDGETS` (`QCheckBox`, `QComboBox`, `QSpinBox`, `QDoubleSpinBox`, `QLineEdit`, `QSlider`, `QRadioButton`, `QPlainTextEdit`) et vérifie que la valeur de chacun est lue quelque part.

**`tests/test_locales.py` (4 tests, non committé)** — voir §7.

### Couverture — ce qui reste non testé

- **`StudioWindow` lui-même** n'a pas de fichier de test dédié (`ls tests/test_studio_window.py` → absent). Son orchestration (`launch`, `_run_pipeline_step`, `_on_pipeline_step_finished`) n'est couverte qu'indirectement par `tests/integration/test_tool_launch_integration.py` (9 tests).
- Aucun test n'instancie réellement les panneaux Qt : la couverture panneaux est **statique** (AST) via `test_panel_contracts.py`.
- Le mock PySide6 de `tests/conftest.py` reste le mécanisme central pour les tests headless.

---

## 10. Dette technique — reprise point par point de l'ancien §10

| # | Point de l'ancien audit (`docs/archive/ETAT_DES_LIEUX.md` §10) | Statut | Preuve |
|---|---|---|---|
| 1 | `ColmapParams.guided_matching` : lu mais jamais écrit, widget `setEnabled(False)` permanent | ✅ **Résolu** | `reconstruction_panel.py:308` (lu) **et** `:337` (écrit) ; aucun `setEnabled(False)` sur `guided_match_check` |
| 2 | `ColmapParams.sequential_overlap` : aucune UI, aucun flag CLI | ✅ **Résolu** | `reconstruction_panel.py` : widget `sequential_overlap_spin`, lu L314, écrit L338, activé conditionnellement L348 |
| 3 | `matching_type` : `set_params()` peut ignorer silencieusement une valeur incompatible | ⚠️ **Toujours présent** | `reconstruction_panel.py:331-333` : `if match_type in COMPATIBLE_MATCHING.get(feat_type, [])` — sinon la valeur est ignorée sans avertissement |
| 4 | `undistort_images`/`filter_blurry`/`blur_factor` éclatés entre `ParamsTab` et `ConfigTab` | ✅ **Résolu** | `undistort_images` centralisé dans `RunState` ; `blur_factor_from_strength()` factorisé dans `app/core/params.py:18`, 2 appelants ; report explicite via `apply_source_blur_settings()` |
| 5 | `ExportTab` orpheline, jamais instanciée | ✅ **Obsolète** — le fichier a été supprimé | `export_tab.py` absent ; remplacé par `ExportPanel`, câblé `studio_window.py:195` |
| 6 | `BrushTab.run_standalone()` fire-and-forget, hors workers | ✅ **Résolu** | `grep -rn "run_standalone" app/` → 0 résultat. Le module Brush passe par `_launch_brush` → `BrushWorker` (`studio_window.py:624-637`) |
| 7 | `FourDGSTab`/`Extractor360Tab` instancient leurs propres workers | ✅ **Résolu** | Les deux passent par `StudioWindow._launch_fourdgs` (L563) / `_launch_extractor360` (L554) → `_start_tool_worker` |
| 8 | Mode encodé en chaîne, re-dérivé à plusieurs endroits | ⚠️ **Déplacé, pas résolu** | Le mode n'est plus re-dérivé (une seule lecture, L323) — mais il n'est **plus utilisé du tout** pour choisir le moteur (voir anomalie A1 ci-dessous). Sharp conserve son second niveau de mode interne (`params["mode"]` image/vidéo, `studio_window.py:585`) |
| 9 | 29 `setEnabled(False)` dispersés dans `app/gui/` | ✅ **Fortement réduit** | `grep -rn "setEnabled(False)" app/gui/ \| wc -l` → **4** |
| 10 | `QFileDialog` appelé directement hors `dialog_utils.py` | ✅ **Résolu** | `grep -rln "QFileDialog" app/gui/` → **un seul fichier : `dialog_utils.py`** |
| 11 | Import inter-couches GUI → CLI (`main_window.py:200` importait un helper privé de `app/cli/commands.py`) | ⚠️ **Toujours présent, déplacé** | `app/gui/panels/entrainement_panel.py:37` → `from app.cli.commands import BRUSH_PRESETS`. La GUI dépend toujours du CLI plutôt que d'un module `core` partagé. `app/cli/launcher.py:22` importe `StudioWindow` — sens attendu |
| 12 | Allowlist Brush / CORS / liste noire du nom de projet absentes du CHANGELOG | ⚠️ **Aggravé** | Le CHANGELOG n'a plus aucune entrée depuis `[1.5.1] - 2026-07-18` : ni la refonte, ni les correctifs de sécurité de sessions 12/13 (checksum fail-closed, urllib3 CVE) n'y figurent |
| 13 | Bug de scroll horizontal (barre de droite) | ✅ **Résolu** | `.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)` présent dans 11 fichiers (18 occurrences au total : `cleaner_panel` 2, `entrainement_panel` 4, `export_panel` 1, `extractor360_panel` 2, `four_dgs_panel` 1, `reconstruction_panel` 3, `sharp_panel` 1, `splat_transform_panel` 1, `upscale_panel` 1, `visualiser_panel` 1, `settings_window` 1) |

### Anomalies **nouvelles**, introduites ou révélées par la refonte

**A1 — Les modes Sharp et 4DGS n'exécutent pas leur moteur depuis le bouton « Lancer ».** *(Critique fonctionnel)*
`_run_pipeline_step` construit toujours un `ColmapWorker` pour l'étape `reconstruction` (`studio_window.py:360-364`), sans consulter le mode. Vérifié : `grep -n "current_mode" app/gui/studio_window.py` → une seule occurrence (L323), passée uniquement à `plan_pipeline`. Un utilisateur qui choisit « Sharp » dans le top bar et clique « Lancer » déclenche COLMAP.

**A2 — `TopBar.modeChanged` est un signal orphelin.**
`grep -rn "modeChanged" app/` → défini `topbar.py:34`, émis `topbar.py:80`, jamais connecté. Le rail n'est donc jamais adapté au mode (spec §2.2).

**A3 — Trois réglages de `SourcePanel` sont écrits mais jamais lus.**
`checkpoint_dest` (`source_panel.py:96`), `export_dir` (L177), `combo_export_format` (L180) figurent dans `get_state()`/`set_state()` et sont donc persistés dans `config.json`, mais `grep -rn "checkpoint_dest\|export_dir\|export_format" app/` ne montre **aucun consommateur** en dehors du panneau lui-même. Note : `test_panel_contracts.py` ne les détecte pas, car il considère `get_state()` comme une lecture valide.

**A4 — `resume_path` (« Reprise de COLMAP ») n'est jamais consommé.**
Créé `reconstruction_panel.py:82`, classé pour affichage L273, mais absent de `get_params()` (L294-319) et de `get_state()` (L350-351), et jamais lu par `StudioWindow`.

**A5 — `ColmapWorker.upscale_params` et `extractor_360_params` sont devenus inatteignables.**
`grep -rn "ColmapWorker(" app/ tests/` → un seul site de construction (`studio_window.py:398`), qui ne passe aucun des deux. Le code des lignes 89-135 de `workers.py` (chaînage 360 → COLMAP, activation de l'upscale) n'est donc plus exécutable depuis la GUI.

**A6 — Le réglage « notifications » n'est pas persistant.**
`self._notifications_enabled = False` (`studio_window.py:98`) n'est jamais réhydraté depuis `config.json` ni depuis une `ChainConfig`. Il faut le réactiver à chaque lancement.

**A7 — `config.example.json` est périmé.**
Ses clés (`language`, `config`, `colmap_params`, `brush_params`, `sharp_params`, `upscale_params`, `extractor_360_params`, `four_dgs_params`, `superplat_params`) décrivent l'ancien schéma par onglet. Le `config.json` réellement produit contient `last_project` et `theme`, absents de l'exemple. Le `config.json` de développement présent sur la machine contient d'ailleurs **les deux schémas** cohabitant (12 clés), dont 9 désormais mortes.

**A8 — Trois fonctions publiques n'ont que des tests pour appelants.**
- `brush_presets.delete_user_preset()` (L55) : `grep -rn "delete_user_preset" app/ tests/` → seulement `tests/test_brush_presets.py`.
- `config_io.delete_config()` : seulement `tests/test_config_io.py`.
- `notifications.is_available()` (L18) : seulement `tests/test_notifications.py:19`.
Ces trois-là correspondent au finding **A2-M8** listé comme arbitrage ouvert dans `manifest.md`.

**A9 — `requests` et `urllib3` déclarées mais jamais importées.**
Signalé comme finding **A2-M14** dans `manifest.md` : tout le réseau passe par `urllib.request` de la stdlib. Les retirer imposerait de régénérer `requirements.lock`.

**A10 — `manifest.md` contient des chiffres périmés.**
`manifest.md:11` annonce « ~74 Python files » (réel : 114). Sa table « Changelog Highlights » s'arrête à 1.2.0.

**A11 — `PROGRESS.md` déclare le Lot 7 non fait alors qu'il l'est.**
`docs/archive/REFONTE_UI_PROGRESS.md:27` → `| 7 | Nettoyage final + bascule studio_window | ☐ | — |`, alors que `app/cli/launcher.py:22` importe déjà `StudioWindow` et que `main_window.py` est supprimé. Document archivé, donc sans conséquence — mais il ne doit pas être pris pour un état courant.

---

## 11. Questions ouvertes

Les questions 2, 3, 4, 5, 6, 7, 8 de l'ancien document sont **tranchées** (voir §10 : `guided_matching`, `sequential_overlap`, éclatement `undistort/blur`, `ExportTab`, `run_standalone`, workers tab-local, `QFileDialog`). Restent ouvertes ou nouvelles :

1. **Modes Sharp / 4DGS depuis le bouton « Lancer »** (anomalie A1) — faut-il (a) brancher `_run_pipeline_step` sur le mode pour construire `SharpWorker`/`FourDGSWorker`, (b) désactiver le combo de mode et n'assumer que Gsplat en pipeline, ou (c) retirer le combo au profit des seuls modules OUTILS ? C'est le plus gros écart spec ↔ code restant.

2. **Chaînage automatique des post-étapes** (Nettoyage / Export / Visualiser) — l'ancien `PostTrainingWorker` a été supprimé comme code mort. Faut-il le réintroduire sous une forme adaptée aux panneaux, ou assumer que ces trois toggles ne servent qu'à *afficher* le plan et que l'utilisateur enchaîne à la main ?

3. **« Reprise de COLMAP »** (anomalie A4) — brancher `resume_path` sur `_build_colmap_worker` (et sur `ColmapEngine.resume_colmap`), ou retirer le champ ?

4. **`checkpoint_dest`, `export_dir`, `export_format` de Source** (anomalie A3) — les câbler (respectivement sur la destination des checkpoints Brush et sur l'`ExportWorker` du chaînage), ou les retirer du panneau ?

5. **Mode 360 et upscale en variante de pipeline** (écart 5/6 de §0.2) — la spec les prévoyait comme toggles dans Source. Décision à acter : les rétablir, ou entériner qu'ils ne sont plus que des modules OUTILS autonomes (auquel cas les paramètres `upscale_params`/`extractor_360_params` de `ColmapWorker` sont à supprimer).

6. **`matching_type` incompatible ignoré silencieusement** (dette n°3) — ajouter un avertissement utilisateur, ou assumer le repli silencieux ?

7. **Import inter-couches `app/gui/panels/entrainement_panel.py:37` → `app/cli/commands.py`** (dette n°11) — `BRUSH_PRESETS` devrait-il descendre dans `app/core/` (à côté de `brush_presets.py`, qui gère déjà les presets *utilisateur*) pour que GUI et CLI en dépendent symétriquement ?

8. **Reprise du suivi automatique après désaccouplement** — la spec §2.4 laissait la question ouverte (« bouton *revenir au live* ? »). Le code n'en propose aucun : `_auto_follow` ne redevient vrai qu'au prochain `launch()`.

9. **Persistance du réglage de notifications** (anomalie A6) — le stocker dans `config.json` comme `theme`/`language`, ou le laisser volontairement éphémère ?

10. **Fonctions sans appelant applicatif** (anomalie A8) — câbler `delete_user_preset`/`delete_config` dans la fenêtre Réglages, ou supprimer code + tests ? Arbitrage déjà listé comme ouvert dans `manifest.md` (A2-M8).

11. **`requests`/`urllib3` déclarées mais inutilisées** (anomalie A9, A2-M14) — les retirer et régénérer le lock, ou les garder en prévision ?

12. **Documentation** — le CHANGELOG doit-il rattraper 43 commits d'un coup (entrée `[1.6.0]` couvrant la refonte Studio), et `manifest.md` être remis à jour (nombre de fichiers, architecture) ?

13. **Défaut `feature_type = SIFT`** (question 1 de l'ancien document) — toujours non tranchée ; `ALIKED_N16ROT`/`ALIKED_N32` restent disponibles mais non par défaut.

---

## Annexe — commandes de vérification utilisées

```bash
# Métadonnées
grep -n 'version' pyproject.toml            # → ligne 3 : 1.5.1
cat app/__init__.py                          # → VERSION = "1.5.1"
grep -n '^## \[' CHANGELOG.md | head         # → [1.5.1] en tête, 2026-07-18
find app tests -name '*.py' | wc -l          # → 114

# Diff depuis l'ancien état des lieux
git log --oneline b4e88db..HEAD | wc -l      # → 43
git diff b4e88db HEAD --name-status -M       # → 82 fichiers (41 A, 13 D, 27 M, 1 R)
git diff HEAD --stat                         # → 57 fichiers, +805 / -4187
git status --short

# Absence des fichiers supprimés
ls app/gui/main_window.py app/core/ply_utils.py verify_imports.py
ls -1 app/gui/tabs/                          # → __init__.py, logs_tab.py

# Tests
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --collect-only -q
                                             # → 419/443 collectés, 24 désélectionnés

# i18n
# comptage plat + diff exhaustif des 9 locales → 265 clés, union 265, 0 manquante

# Sécurité
grep -rn "validate_path" app/ | grep '\.py:' | wc -l   # → 37
grep -rn "shell=True" app/ | grep '\.py:'              # → 1 (commentaire)
grep -rni "sanitiz" app/ | grep '\.py:'                # → 1 (commentaire)
sed -n '14,20p' app/core/brush_engine.py               # → ALLOWED_FLAGS, 13 flags
grep -n "Origin\|127.0.0.1" app/core/superplat_engine.py

# Anomalies
grep -n "current_mode" app/gui/studio_window.py        # → 1 seule occurrence (L323)
grep -rn "modeChanged" app/                            # → défini/émis, jamais connecté
grep -rn "ColmapWorker(" app/ tests/                   # → 1 seul site de construction
grep -rn "PostTrainingWorker" app/ tests/              # → 0
grep -rn "run_standalone" app/                         # → 0
grep -rn "from app.cli" app/gui/ app/core/             # → entrainement_panel.py:37
grep -rln "QFileDialog" app/gui/                       # → dialog_utils.py seul
grep -rn "setEnabled(False)" app/gui/ | wc -l          # → 4
```
