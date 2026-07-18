# Refonte UI — Suivi d'avancement (reprendre ici)

> Tracker du chantier `PROMPT_CLAUDE_CODE_REFONTE_UI.md` (spec : `REFONTE_UI_SPEC.md`).
> **En cas de reprise (`/reprise`), lire CE fichier en premier.** 1 commit par lot, journal mis à jour en fin de lot.

## ⏯️ Reprendre ici
- **Lot courant** : Lots 3 & 4 **terminés côté UI**. Prochain : **Lot 5** (modules OUTILS) ou **câblage moteurs réels** (dispatch + boutons locaux) = phase Apple Silicon.
- **⚠️ RESTE : câblage moteurs réels (phase Apple Silicon)** — commun aux Lots 3 et 4. Les panneaux + `launch()` pilotent l'UI (plan, breadcrumb, rail, statuts) mais **n'exécutent pas les moteurs**. À brancher : `ColmapWorker`/`BrushWorker`/`PostTrainingWorker` dans `launch()` (réutiliser logique `main_window.py`), boutons locaux Nettoyage(`CleanerWorker`)/Export(`ExportWorker`)/Visualiser(`SuperSplatEngine.start_data_server`/`stop_all` + `stop_all()` au `closeEvent`). Signaux → `logbar`/`rail.set_step_status`/breadcrumb.
- **Prochaine action (Lot 5)** : modules OUTILS (Brush, ML Sharp, SuperSplat, Upscale, SplatTransform, 4DGS, 360) — panneaux plain dans `StudioWindow.panels` sur les clés TOOL_KEYS (déjà des placeholders). Réutiliser panneaux existants où identiques (Brush≈Entraînement mode manuel, SuperSplat≈Visualiser).
- **Pattern panneau établi (3a)** : classe plain exposant `.center`/`.right` (QWidget), insérée dans `StudioWindow.panels[key]`. Toggles de chaînage via `bind_flag_checkbox(chk, run_state, flag)` (`app/gui/run_state_binding.py`) = source de vérité unique. Persistance via `get_state()`.
- **Acquis Lot 1** : `run_state.py`, `config_io.py`, `brush_params.py` (`to_engine_params()`), `brush_presets.py` (`merge_presets`).
- **Acquis Lot 2** : `studio_window.py` (StudioWindow, 4 zones, QStackedWidget centre+droite), `topbar.py`, `rail.py` (13 items, OUTILS repliée par défaut, statut par étape), `logbar.py` (encapsule LogsTab, repliée), `settings_window.py` (thème/langue fonctionnels, reste en signaux), `studio_nav.py` (PageRegistry/CollapseState — logique testable hors Qt). **Placeholders centre/droite** = `StudioWindow._placeholder()`, à remplacer par les vrais panneaux.
- **Note test GUI** : les classes héritant d'un widget Qt ne sont PAS instanciables sous le mock PySide6 (elles deviennent MagicMock). Tester la logique via des helpers plain (cf. `studio_nav.py`) ; valider le rendu via smoke `QT_QPA_PLATFORM=offscreen .venv/bin/python -c "..."` et sur Apple Silicon.
- **`main.py` inchangé** : `ColmapGUI` reste l'UI active, bascule vers `StudioWindow` au Lot 7.

## État des lots
| Lot | Titre | Statut | Commit |
|---|---|---|---|
| 0 | Audit état réel (pas de code) | ✅ fait | (rapport, pas de commit) |
| 1 | État partagé & plomberie backend | ✅ fait | (voir git log — lot 1) |
| 2 | Squelette PySide6 4 zones | ✅ fait | (voir git log — lot 2) |
| 3 | Pipeline Gsplat : Source / Reconstruction / Entraînement | ✅ UI+plan (reste câblage moteurs) | — |
| 4 | Nettoyage / Export / Visualiser | ✅ UI (reste câblage moteurs) | — |
| 5 | Modules OUTILS (7) | ☐ | — |
| 6 | Sauvegarde/chargement, presets, notifications, i18n | ☐ | — |
| 7 | Nettoyage final + bascule studio_window | ☐ | — |

## Résultat audit Lot 0 (écarts spec/prompt vs code réel à HEAD=d3352d6, v1.5.1)
Spec écrite à `b4e88db` (v1.5.0), avant les correctifs dette technique de la session 9.

**Déjà fait (le prompt les liste à tort comme à faire) :**
- `guided_matching` réactivé (écrit dans `set_params`, `params_tab.py:221`, émis `colmap_commands.py:65`).
- `sequential_overlap` widget présent (`params_tab.py:110`, câblé set_params 227 / read-back 252).
- `undistort_images`/`filter_blurry`/`blur_factor` **déjà rapatriés dans `ColmapParams`** (`params.py:46/49/50`). → Lot 1 allégé.
- Brush `run_standalone` **déjà recâblé** (émet `standaloneRunRequested`, `brush_tab.py:598`). → Lot 5 Brush « changement de comportement » déjà fait.
- FourDGS/360 orchestration centralisée (journal session 9). → « demander à l'utilisateur » du Lot 5 sans objet.

**Écarts changeant le plan :**
- ⚠️ **ExportTab supprimée** (pas orpheline). `export_tab.py` absent ; export actuel délégué à SplatTransform. **Mais `ExportEngine`/`ExportWorker` intacts** (`app/core/export_engine.py`, via `PostTrainingWorker`). → Lot 4 : construire le panneau Export **directement sur `ExportEngine`/`ExportWorker`** (comme spec §3), ne rien « ressusciter ».

**Confirmé à faire :**
- `_apply_robust` cross-couche encore présent (`main_window.py:209` ← `app/cli/commands.py`). → nettoyage Lot 7.

## 🐞 Bugs connus (à corriger plus tard)
- **Scroll horizontal barre de droite / fenêtre** (signalé Apple Silicon) : persiste indépendamment de la largeur du `right_stack` (testé 300/340/380/400 → sans effet). Donc PAS un problème de largeur de la barre : probablement la fenêtre dont la largeur minimale (rail 220 + right fixe + largeur mini du centre) dépasse l'écran, OU un widget large non-wrappé dans le centre. Pistes : rendre le centre réellement rétrécissable (scroll area centre, ou min-width forcée basse), vérifier `QFormLayout` des accordéons (labels longs → passer libellés au-dessus des champs), envisager `right_stack` non-fixe (min+max). À investiguer sur Mac avec la taille réelle d'écran.

## Vérifications Apple Silicon en attente (par lot)
- Lot 2 : rendu réel 4 zones, densité top bar, hauteur rail 13 items sur MacBook Air 13".
- Lot 3 : pipeline COLMAP→Brush complet, non-régression temps/résultats.
- Lot 4 : Visualiser (serveur local + navigateur).
- Lot 5 : chaque module à binaire externe réel.
- Lot 6 : notifications macOS réelles (permissions système).
- Lot 7 : passe complète 3 pipelines (Gsplat/Sharp/4DGS) + 7 modules OUTILS.
</content>
</invoke>
