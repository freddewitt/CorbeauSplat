# Prompt Claude Code — Implémentation de la refonte UI CorbeauSplat

> À copier-coller dans Claude Code, lot par lot (jamais tout d'un coup). Suppose que `REFONTE_UI_SPEC.md` a été placé à la racine du dépôt avant de commencer.

---

## 0. Contexte

CorbeauSplat (macOS Apple Silicon, PySide6, MIT) passe d'une interface à 11 onglets `QTabWidget` à une interface en 4 zones (top bar / rail gauche / centre / barre de droite) organisée autour de 6 étapes PIPELINE (Source, Reconstruction, Entraînement, Nettoyage, Export, Visualiser) et 7 modules OUTILS indépendants (Brush, ML Sharp, SuperSplat, Upscale, SplatTransform, 4DGS, 360 Extractor).

La spec complète et canonique est `REFONTE_UI_SPEC.md` (racine du dépôt). Ce prompt n'en est que le plan d'exécution — **en cas de divergence entre ce prompt et `REFONTE_UI_SPEC.md`, `REFONTE_UI_SPEC.md` fait foi.**

C'est un chantier massif. Il **doit** être traité lot par lot, avec un commit distinct par lot, jamais en un seul passage. Chaque lot ci-dessous est une session Claude Code séparée.

---

## 1. Lecture obligatoire avant tout code

Dans l'ordre, avant d'écrire une seule ligne :

1. `REFONTE_UI_SPEC.md` — intégralement, c'est le cahier des charges
2. `manifest.md` et `CHANGELOG.md` — état réel actuel du dépôt
3. `ETAT_DES_LIEUX.md` s'il est encore présent — inventaire factuel de référence (état au moment où la spec a été écrite)
4. **Vérification de la dette technique préalable** (§1 de `REFONTE_UI_SPEC.md`) : confirmer dans le code que `guided_matching` est bien réactivé (`set_params()` l'écrit, plus de `setEnabled(False)` permanent), que `sequential_overlap` a bien un widget, et vérifier l'état réel de `undistort_images`/`filter_blurry`/`blur_factor` (rapatriés dans `ColmapParams` ou toujours éclatés `ConfigTab`/`ParamsTab` ?). **Si l'état réel diverge de ce que `REFONTE_UI_SPEC.md` suppose, arrête-toi et rapporte l'écart avant de continuer** — ne code pas sur une hypothèse fausse.
5. Fichiers sources actuels à connaître avant de migrer quoi que ce soit : `app/core/base_engine.py`, `app/core/params.py`, `app/core/brush_engine.py`, `app/core/engine.py`, `app/gui/main_window.py`, `app/gui/managers.py`, `app/gui/workers.py`, `app/gui/base_worker.py`, `app/gui/widgets/dialog_utils.py`, `app/gui/widgets/drop_line_edit.py`, `app/core/i18n.py`, tous les fichiers de `app/gui/tabs/`.

---

## 2. Principes non-négociables

**Sécurité — aucune régression tolérée :**
- `BaseEngine.validate_path()`/`is_safe_path()` : réutilisés tels quels partout où un chemin est saisi dans la nouvelle UI. Ne pas réimplémenter une validation parallèle.
- Aucun `subprocess` avec `shell=True`, nulle part, jamais.
- Allowlist `ALLOWED_FLAGS` de `BrushEngine` (13 flags) : **inchangée côté moteur**. Si des champs structurés (Max Splats, Densification, Checkpoints — voir §3 lot 3) sont ajoutés dans l'UI, ils doivent générer les mêmes tokens `--flag valeur` déjà filtrés par `build_command()`. C'est un changement de surface UI au-dessus de l'allowlist existante, pas un changement de l'allowlist elle-même.
- CORS SuperSplat (bind `127.0.0.1`, reflet d'`Origin` restreint) : inchangé, sauf si un lot futur introduit explicitement un mode réseau (non prévu ici).
- Sanitisation nom de projet (blacklist `..`, `/`, `\`) : reprise telle quelle.

**i18n :** toute nouvelle chaîne visible doit être ajoutée aux **9 locales** (`ar, de, en, es, fr, it, ja, ru, zh` — `fr` = source de vérité pour ce projet). Réutiliser `LanguageManager`/`tr()`/`add_language_observer()`/`retranslate_ui()` tels qu'ils existent déjà — ne pas créer un second mécanisme d'i18n.

**Single source of truth (critique) :** `Entraînement après`, `Nettoyer après`, `Exporter après`, `Visualiser après`, `undistort_images` apparaissent à plusieurs endroits de l'UI (Source, Reconstruction, Entraînement, modules OUTILS). **Chaque duplication doit être bindée au même état source** (une seule propriété par flag, plusieurs widgets qui la reflètent et la modifient) — jamais des widgets indépendants avec leur propre état interne qui se resynchronisent tant bien que mal. C'est exactement le pattern qui a produit l'éclatement `undistort_images`/`filter_blurry`/`blur_factor` entre `ConfigTab` et `ParamsTab` corrigé en amont de ce chantier (dette technique cluster B). Voir lot 1 pour le mécanisme central proposé.

**Diff minimal par lot :** ne pas refactorer au-delà du périmètre du lot en cours, même si une amélioration adjacente est tentante. Note-la plutôt pour un lot ultérieur.

**Ambiguïté :** si un point n'est explicitement tranché ni dans `REFONTE_UI_SPEC.md` ni dans ce prompt, arrête-toi et demande — ne devine pas un comportement UI ou une valeur par défaut.

**Vérification Apple Silicon :** GUI PySide6 et binaires macOS (COLMAP, Brush, Sharp, upscayl…) non exécutables dans l'environnement Claude Code. Chaque lot liste explicitement ce qui nécessite une vérification manuelle sur Mac Apple Silicon avant d'être considéré terminé.

**Tests :** toute nouvelle logique non-GUI (state management, sérialisation config, promotion des flags Brush, sérialisation presets) doit avoir des tests unitaires. La GUI reste testée via le mock PySide6 existant (`tests/conftest.py`, `PYTEST_QT_API=pyside6`) — pas de nouveau test end-to-end GUI réel possible hors Apple Silicon.

---

## 3. Note technique — notifications macOS (à trancher avant le lot 6)

Recherche effectuée : `UNUserNotificationCenter` (API moderne) **exige un exécutable signé** pour autoriser l'envoi de notifications — une signature ad-hoc suffit (pas besoin d'un compte développeur Apple payant), mais un Python installé via Homebrew n'est **pas** signé par défaut (celui de python.org l'est). `NSUserNotificationCenter` (API historique, dépréciée) fonctionne sans signature mais peut disparaître dans une future version de macOS.

Deux options réalistes pour un outil solo distribué via `run.command`/Homebrew (pas un `.app` packagé signé) :
1. Bibliothèque [`desktop-notifier`](https://github.com/samschott/desktop-notifier) (maintenue, cross-platform) avec l'option `macos_legacy=True` pour forcer `NSUserNotificationCenter` et éviter le problème de signature.
2. Appel direct à `NSUserNotificationCenter` via `pyobjc-framework-Cocoa` (déjà une dépendance du projet, donc **zéro nouvelle dépendance**) — plus simple mais dépréciée par Apple.

**Ne pas trancher seul** : présenter ces deux options à l'utilisateur en début de lot 6 et implémenter celle qu'il choisit.

---

## 4. Découpage en lots

### Lot 0 — Audit de l'état réel (pas de code)
**Objectif** : confirmer que les hypothèses de `REFONTE_UI_SPEC.md` §1 sont vraies dans le code actuel.
**Sortie attendue** : rapport texte (pas de commit) listant les écarts trouvés, si il y en a.
**Critère de fin** : accord explicite de l'utilisateur pour procéder au lot 1, avec les écarts corrigés dans la compréhension du chantier si besoin.

---

### Lot 1 — État partagé & plomberie backend (aucun changement GUI visible)

**Objectif** : poser les fondations non-GUI avant de toucher à un seul widget.

**Fichiers à créer** (noms indicatifs, adapte-toi aux conventions déjà en place dans `app/core/`) :
- `app/core/run_state.py` — objet d'état partagé central (ex. `PipelineRunConfig` ou nom cohérent avec le reste du code) portant les flags dupliqués (`entrainement_apres`, `nettoyer_apres`, `exporter_apres`, `visualiser_apres`, `undistort_images`) en propriétés uniques, avec un mécanisme d'observation (réutiliser le pattern Observer déjà en place pour `LanguageManager` plutôt qu'en inventer un nouveau) pour que tous les widgets qui reflètent un même flag restent synchronisés.
- `app/core/config_io.py` — sérialisation/désérialisation de la configuration complète de la chaîne (Source y compris chemins, `ColmapParams`, params Brush, réglages Nettoyage/Export, tous les flags de `run_state.py`) vers un fichier nommé, pour les icônes Charger/Sauvegarder du top bar. Distinct de `SessionManager` (qui gère la session GUI courante) — `config_io.py` gère des configurations **nommées et réutilisables**, potentiellement plusieurs. Vérifier s'il est pertinent de faire reposer `config_io.py` sur le même mécanisme `to_dict()`/`from_dict()` que `ColmapParams` plutôt que de dupliquer la sérialisation.
- Extension de `app/core/brush_engine.py` (ou nouveau module dédié) : promotion de certains flags `ALLOWED_FLAGS` en champs structurés — `max_splats` en champ de premier niveau, groupe `densification` (`growth_grad_threshold`, `growth_select_fraction`, `growth_stop_iter`, `start_iter`, `refine_every`, `refine_pose`), groupe `checkpoints` (`checkpoint_interval`, `save_iterations`, `eval_every`, `export_every`). **Doit continuer à produire exactement les mêmes tokens `--flag valeur` déjà filtrés par `build_command()`** — n'ajoute aucun flag hors de l'allowlist existante.
- Presets personnalisés Brush : extension du système `BRUSH_PRESETS` (Strategy pattern déjà en place) pour accepter des presets sauvegardés par l'utilisateur, nommés, persistés (probablement dans `config.json` ou un fichier dédié à définir selon ce qui est le plus cohérent avec `SessionManager` existant).
- État d'erreur par étape : mécanisme simple (enum `idle`/`running`/`done`/`error`) pour piloter l'icône rouge du rail — peut vivre dans `run_state.py`.

**Tests** : couverture unitaire complète de `run_state.py` et `config_io.py` (sérialisation round-trip, synchronisation multi-observateurs, gestion des valeurs manquantes/anciennes versions de config sauvegardée). Tests de non-régression sur `build_command()` de `BrushEngine` : les tokens générés avant/après la promotion des flags structurés doivent être strictement identiques pour les mêmes valeurs.

**Vérification Apple Silicon** : aucune (lot purement backend, testable en CI headless).

---

### Lot 2 — Squelette PySide6 4 zones (pas de câblage moteur)

**Objectif** : structure visuelle vide, sans logique métier.

**Fichiers à créer** (suggestion de structure, à adapter) :
- `app/gui/studio_window.py` — nouvelle fenêtre principale, remplace progressivement `ColmapGUI` de `main_window.py` (ne pas supprimer `main_window.py` tant que la migration n'est pas complète — bascule finale au lot 7)
- `app/gui/topbar.py` — nom projet éditable, pastille statut, dropdown mode pipeline (Gsplat/Sharp/4DGS), bouton Lancer, icône réglages généraux
- `app/gui/settings_window.py` — fenêtre indépendante : Thème, Langue, Charger/Sauvegarder, `build_mode` Brush, `thermal_throttling`, toggle notifications, reset factory, relancer, quitter
- `app/gui/rail.py` — colonne gauche, section PIPELINE (6 items, coche/spinner/erreur) + section OUTILS (7 items, repliable/repliée par défaut), icône+libellé toujours ensemble (jamais icône seule)
- `app/gui/logbar.py` — barre de logs repliable en bas, repliée par défaut, Effacer/Copier/Sauvegarder/Rechercher, auto-scroll lock (reprendre le comportement déjà existant de `LogsTab`, pas le réinventer)
- Zone centre + barre de droite : `QStackedWidget` (ou équivalent) piloté par la sélection du rail, vide à ce stade (panneaux réels ajoutés lots 3-5)

**Réutilisation explicite** : `app/gui/styles.py` (thèmes existants, juste retirer les dropdowns Thème/Langue du styling top-bar pour les déplacer dans `settings_window.py`), `app/core/i18n.py` tel quel.

**Tests** : tests unitaires sur le câblage des signaux rail→zone centre (sélection change bien le panneau affiché), sur le repli/dépli de la section OUTILS et de la barre de logs. Pas de test visuel automatisé (PySide6 mocké).

**Vérification Apple Silicon** : **obligatoire** — rendu visuel réel, aucune capture d'écran/mock ne peut valider la mise en page (densité top bar, hauteur du rail à 13 items sur MacBook Air 13", cf. `REFONTE_UI_SPEC.md` §2 point de vigilance densité).

---

### Lot 3 — Pipeline Gsplat : Source, Reconstruction, Entraînement

**Objectif** : les 3 premières étapes PIPELINE, fonctionnelles, branchées sur les moteurs existants.

**Correspondance avec l'existant** (reprendre la logique, pas la réécrire) :
- Source ← `ConfigTab` (`app/gui/tabs/config_tab.py`) : input, dossier sortie, delete dataset, `filter_blurry`/upscale/undistort/mode stabilisé, toggles `entrainement_apres`/`nettoyer_apres`/`exporter_apres`/`visualiser_apres` (bindés sur `run_state.py`, lot 1)
- Reconstruction ← `ParamsTab` (`app/gui/tabs/params_tab.py`) pour les accordéons Feature Extraction/Matching/Mapper, + logique "Reprise COLMAP" actuelle (aujourd'hui dans `ConfigTab`, à migrer ici) étendue au cas "dossier externe → nouveau projet à la volée" (nouveau comportement, pas dans l'existant — implémente en réutilisant `ColmapEngine`/`delete_project_content` existants)
- Entraînement ← `BrushTab` (`app/gui/tabs/brush_tab.py`) intégralement, y compris son mode Manuel/Indépendant

**Moteurs et workers réutilisés sans modification** : `ColmapEngine`, `BrushEngine`, `ColmapWorker`, `BrushWorker`, `PostTrainingWorker` (`app/gui/workers.py`). Le câblage des signaux (`log_signal`/`progress_signal`/`status_signal`/`finished_signal`) pointe vers les nouveaux widgets (breadcrumb, logbar, rail) au lieu des anciens `LogsTab`/`ConfigTab.progress_bar`.

**Nouveaux comportements à implémenter** (pas dans l'existant) :
- Breadcrumb de flux en haut du centre (stats live compactes par étape)
- 3 niveaux de progression (barre globale segmentée + ETA, micro-barre rail, vue par phase centre)
- Navigation auto-follow du rail pendant l'exécution, désaccouplement au clic manuel (comportement à documenter dans le code par analogie explicite avec l'auto-scroll lock des logs déjà existant)
- Hiérarchie Preset→essentiel→avancé sur la barre de droite de Source et Entraînement (toggle "Avancé" mémorisé entre sessions)
- Bannière "Apple Silicon détecté — N threads" (reprise de `ParamsTab` actuel) dans Reconstruction

**Tests** : tests d'intégration mockés pour le dispatch Source→Reconstruction→Entraînement (chaînage conditionnel selon les toggles), tests sur la logique "dossier externe → nouveau projet à la volée".

**Vérification Apple Silicon** : **obligatoire** — lancement réel d'un pipeline COLMAP→Brush complet, vérifier que rien ne régresse par rapport au comportement actuel (temps d'exécution, résultats identiques).

---

### Lot 4 — Nettoyage, Export, Visualiser

**Correspondance avec l'existant** :
- Nettoyage ← `CleanerTab`/`CleanerExportTab` (`app/gui/tabs/cleaner_tab.py`, `cleaner_export_tab.py`), moteur `ply_cleaner.py` inchangé
- Export ← **résurrection de `ExportTab`** (`app/gui/tabs/export_tab.py`, aujourd'hui orpheline) et câblage réel via `ExportEngine`/`ExportWorker` (déjà utilisés indirectement via `PostTrainingWorker`, à exposer maintenant comme étape à part entière avec progression par fichier)
- Visualiser ← `SuperSplatTab` (`app/gui/tabs/superplat_tab.py`), moteur `SuperSplatEngine` inchangé, y compris `start_data_server()`/`stop_all()`

**Nouveau** : bouton Lancer/Arrêter local par écran (en plus du bouton Lancer global du top bar) — vérifier que `stop_all()` de `SuperSplatEngine` est bien appelé proprement à la fermeture de l'app (`closeEvent`/`AppLifecycle`), point de vigilance renforcé maintenant que le viewer peut démarrer automatiquement en tâche de fond via le toggle `visualiser_apres`.

**Tests** : tests sur le déclenchement conditionnel Nettoyage→Export selon `nettoyer_apres`/`exporter_apres` (dépendance séquentielle déjà existante dans `PostTrainingWorker`, à confirmer préservée).

**Vérification Apple Silicon** : **obligatoire** pour Visualiser (serveur local réel, navigateur).

---

### Lot 5 — Modules OUTILS (7 modules)

Un module par sous-lot si besoin (le découpage ci-dessous peut être scindé en 7 sessions Claude Code distinctes si un seul lot est trop gros) :

| Module | Réutilise | Nouveau |
|---|---|---|
| Brush (standalone) | `BrushEngine`, écran quasi identique à Entraînement (mode manuel) | rebranchement sur le chemin orchestré (`BrushWorker`), remplace `run_standalone()` fire-and-forget actuel — **changement de comportement volontaire**, plus de logs/finished signal manquants |
| ML Sharp | `SharpEngine`, `SharpWorker`/`SharpVideoWorker` | toggles nettoyer/exporter/visualiser après |
| SuperSplat (standalone) | `SuperSplatEngine`, écran identique à Visualiser | aucun (juste un point d'entrée rail supplémentaire vers le même écran) |
| Upscale | `UpscaleEngine`, `upscayl_manager.py`, `ModelCard` (`upscale_widgets.py`) | aucun changement fonctionnel, juste replacement dans le nouveau layout |
| SplatTransform | `SplatTransformEngine` | toggles nettoyer/exporter/visualiser après (nouveau) |
| 4DGS (standalone) | `FourDGSEngine`, `FourDGSWorker` | aucun changement fonctionnel |
| 360 Extractor | `Extractor360Engine`, `Extractor360Worker` | aucun changement fonctionnel |

**Point de vigilance transverse** : `FourDGSTab`/`Extractor360Tab` instanciaient jusqu'ici leurs propres workers indépendants de ceux de `main_window` — vérifier si ce chantier est l'occasion de fusionner en un seul point d'orchestration (dette technique cluster C, non tranchée explicitement dans `REFONTE_UI_SPEC.md` — **demander à l'utilisateur** si la fusion doit être faite ici ou reportée).

**Tests** : un test d'intégration par module confirmant le bon déclenchement du worker associé.

**Vérification Apple Silicon** : **obligatoire** pour chaque module impliquant un binaire externe réel.

---

### Lot 6 — Sauvegarde/Chargement global, presets, notifications, finitions

- Câblage réel des icônes Charger/Sauvegarder du top bar sur `config_io.py` (lot 1)
- UI de sauvegarde de preset personnalisé dans Entraînement (bouton "Enregistrer la configuration actuelle comme preset")
- **Notifications macOS** : trancher avec l'utilisateur entre les deux options du §3 de ce prompt avant de coder ; toggle d'activation dans `settings_window.py` ; déclenchement en fin de run (succès) et en cas d'échec d'étape
- Icône d'erreur rouge sur le rail + clic → déplie la logbar et scrolle jusqu'à l'entrée concernée
- Passe i18n complète : toutes les nouvelles chaînes introduites lots 2-6 ajoutées aux 9 locales

**Tests** : tests sur le déclenchement des notifications (mock de la couche notification, ne pas déclencher de vraies notifications en CI), test d'exhaustivité i18n (clés identiques dans les 9 fichiers — un script de ce type existe probablement déjà vu `ETAT_DES_LIEUX.md` §7, réutilise-le).

**Vérification Apple Silicon** : notifications réelles, uniquement testables sur machine réelle avec permissions système.

---

### Lot 7 — Nettoyage final

- Suppression des anciens fichiers `app/gui/tabs/*.py` et `app/gui/main_window.py` (`ColmapGUI`) une fois `studio_window.py` confirmé comme remplaçant complet et validé par l'utilisateur sur Apple Silicon
- Suppression de l'import privé `_apply_robust` cross-couche (`main_window.py` → `app/cli/commands.py`) si encore présent — migration vers `app/core/` (dette technique cluster D, à confirmer non déjà traitée en amont du chantier)
- Mise à jour `manifest.md`, `CHANGELOG.md`, `journal.md`/`journal.jsonl` — obligatoire, c'est ce qui permet de repartir avec un contexte à jour la prochaine fois
- Suite de tests complète : confirmer le nombre de tests passés/skippés cohérent avec la baseline d'avant chantier (292 pass, 1 skip, 15 deselected au dernier état connu — à réajuster si des tests ont été ajoutés en cours de route)

**Vérification Apple Silicon** : passe complète manuelle de bout en bout sur les 3 pipelines (Gsplat, Sharp, 4DGS) et les 7 modules OUTILS avant de considérer le chantier terminé.

---

## 5. Format de restitution attendu par lot

Pour chaque lot : un commit Git ciblé (pas un commit géant multi-lots), message de commit clair référençant le numéro de lot, mise à jour des tests concernés, et un résumé de fin de lot listant explicitement ce qui reste à vérifier manuellement sur Apple Silicon avant de passer au lot suivant.
