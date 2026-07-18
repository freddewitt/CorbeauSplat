# Refonte UI — Suivi d'avancement (reprendre ici)

> Tracker du chantier `PROMPT_CLAUDE_CODE_REFONTE_UI.md` (spec : `REFONTE_UI_SPEC.md`).
> **En cas de reprise (`/reprise`), lire CE fichier en premier.** 1 commit par lot, journal mis à jour en fin de lot.

## ⏯️ Reprendre ici
- **Lot courant** : Lot 2 — Squelette PySide6 4 zones (top bar / rail / centre / logbar)
- **Prochaine action** : orienter via graphify sur `main_window.py`/`styles.py`/`LogsTab`, créer `app/gui/studio_window.py` (sans supprimer `main_window.py`). ⚠️ Lot 2 exige vérif visuelle Apple Silicon.
- **Acquis Lot 1 réutilisable** : `app/core/run_state.py` (RunState + StepStatus, Observer), `app/core/config_io.py` (ChainConfig save/load nommé), `app/core/brush_params.py` (surface structurée, `to_engine_params()`), `app/core/brush_presets.py` (presets user, `merge_presets(builtins)`).

## État des lots
| Lot | Titre | Statut | Commit |
|---|---|---|---|
| 0 | Audit état réel (pas de code) | ✅ fait | (rapport, pas de commit) |
| 1 | État partagé & plomberie backend | ✅ fait | (voir git log — lot 1) |
| 2 | Squelette PySide6 4 zones | 🔄 à démarrer | — |
| 3 | Pipeline Gsplat : Source / Reconstruction / Entraînement | ☐ | — |
| 4 | Nettoyage / Export / Visualiser | ☐ | — |
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

## Vérifications Apple Silicon en attente (par lot)
- Lot 2 : rendu réel 4 zones, densité top bar, hauteur rail 13 items sur MacBook Air 13".
- Lot 3 : pipeline COLMAP→Brush complet, non-régression temps/résultats.
- Lot 4 : Visualiser (serveur local + navigateur).
- Lot 5 : chaque module à binaire externe réel.
- Lot 6 : notifications macOS réelles (permissions système).
- Lot 7 : passe complète 3 pipelines (Gsplat/Sharp/4DGS) + 7 modules OUTILS.
</content>
</invoke>
