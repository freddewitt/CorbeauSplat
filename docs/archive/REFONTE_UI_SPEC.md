# CorbeauSplat — Refonte UI, spec vivante

> Document de travail, mis à jour au fil de la conversation. Repart de zéro par rapport à une éventuelle tentative précédente (non retrouvée dans le dépôt à `HEAD=b4e88db`, v1.5.0). Base factuelle : `ETAT_DES_LIEUX.md` du 2026-07-18 + captures des 11 onglets actuels.

---

## 1. Dette technique (préalable à la refonte)

Discutée et partiellement décidée en conversation, puis **traitée intégralement par l'utilisateur directement dans Claude Code** — le détail exact de l'implémentation n'est pas connu de cette conversation, à vérifier dans `manifest.md`/`CHANGELOG.md`/le code au prochain contact avec le dépôt.

Décisions actées en conversation avant le passage à Claude Code :

- **`guided_matching`** (orphelin d'écriture, widget désactivé en permanence) → **réactivé** : retirer `setEnabled(False)`, l'écrire dans `set_params()`.
- **`sequential_overlap`** (orphelin complet, `matcher_type='sequential'` sélectionnable mais non fonctionnel) → **widget ajouté** (spinbox, actif si `matcher_type == 'sequential'`).
- **`undistort_images`/`filter_blurry`/`blur_factor`** (éclatés entre `ConfigTab`/`ParamsTab`, mapping `blur_factor` dupliqué GUI/CLI) → recommandation formulée : **tout rapatrier dans `ColmapParams`** (coût jugé faible : seul `config.json` de session GUI est affecté, pas les projets sur disque). **Non confirmée explicitement par l'utilisateur avant le passage à Claude Code — à vérifier.**
- **Cluster C** (double chemin Brush `trainRequested` vs `run_standalone()` fire-and-forget ; workers dupliqués FourDGS/Extractor360 tab-local vs main_window) : options présentées, **pas de choix explicite acté en conversation**.
- **Cluster D** (`ExportTab` orpheline, import privé `_apply_robust` depuis le CLI) : options présentées, **pas de choix explicite acté en conversation**.
- **Cluster E** (CORS SuperSplat) : pas de dette tant qu'il n'y a pas de mode réseau local prévu — à revérifier si la refonte en introduit un.

**À faire au prochain contact avec le dépôt** : relire `manifest.md`/`CHANGELOG.md`/le code pour aligner ce document sur ce qui a été réellement implémenté.

---

## 2. Principes structurants de l'interface

Interface en **4 zones** :

### Top bar
- Nom du projet (miroir du champ éditable dans Source — clic = renommage rapide ; **pas** un vrai sélecteur de projets, cohérent avec l'absence d'objet `Project` persistant)
- Pastille de statut "X moteurs prêts" (vérification dépendances installées)
- Dropdown **mode de pipeline** : **Gsplat / Sharp / 4DGS** — 3 pipelines complets, chacun avec son propre déroulé Source→...→Visualiser, **et** chacun accessible aussi en usage rapide via un module du rail (voir §2.3) — confirmé pour 4DGS aussi : préparation de dataset autonome nécessaire, donc accès dual comme les autres
- Bouton **"Lancer"** unique (remplace les boutons colorés multiples actuels)
- Icône **réglages généraux** (roue crantée, tout à droite) : ouvre une **fenêtre indépendante** regroupant Thème, Langue, **Charger**/**Sauvegarder** la configuration complète de la chaîne (Source y compris chemins dossier/fichier d'entrée et dossier de sortie, Reconstruction, Entraînement, Nettoyage/Export, tous les toggles — distinct des Presets locaux par étape comme `BRUSH_PRESETS`, plus étroits/engine-only), `build_mode` Brush (binaire release vs compilé source), `thermal_throttling`, notifications de fin d'exécution (voir plus bas), reset factory, relancer, quitter — un seul point d'entrée pour tout ce qui n'est pas au cœur du flux de travail

**Résolu** : le modèle `Project` reste un label cosmétique dérivé des champs de Source (nom + dossier de sortie) — pas d'objet persistant avec chemin propre.

### Rail gauche — section PIPELINE (étapes)
Étapes communes : **Source → Reconstruction → Entraînement → Nettoyage → Export → Visualiser**

- Chaque élément du rail a une icône dédiée **toujours affichée avec son libellé** (jamais icône seule, y compris quand la section OUTILS est repliée — repliée = section masquée/affichée dans son ensemble, pas un mode icône-only par item), une coche ✓ si l'étape est terminée, une surbrillance + indicateur d'activité si en cours, et une **icône d'erreur distincte** (rouge) si l'étape a échoué — cliquable, déplie la barre de logs repliée par défaut et scrolle jusqu'à l'entrée concernée.
- Nettoyage / Export / Visualiser sont **optionnels/skippables** (toggle, pas séquence forcée) — cohérent avec les checkboxes `post_clean`/`post_export` déjà existantes.
- **Gsplat** (incl. mode 360, toggle dans Source) : les 6 étapes s'appliquent. Reconstruction = COLMAP seul ; Entraînement = Brush seul (accordéons séparés, pas fusionnés).
- **Sharp** (Photo→3D) : Reconstruction = l'inférence Sharp elle-même (une seule étape moteur, pas d'étape Entraînement séparée) ; Nettoyage/Export/Visualiser s'appliquent.
- **4DGS** : rail **tronqué à 2 étapes** (Source, Reconstruction) — le moteur actuel (`FourDGSEngine`) s'arrête à la préparation du dataset pour Nerfstudio, aucune sortie `.ply` exploitable aujourd'hui dans l'app.

### Rail gauche — section OUTILS (modules indépendants)
**Brush, ML Sharp, SuperSplat, Upscale, SplatTransform, 4DGS, 360 Extractor** (ordre du rail) — **section repliable, repliée par défaut** (13 items PIPELINE+OUTILS cumulés, risque de dépassement vertical sur petit écran type MacBook Air 13" déjà géré ailleurs dans l'app via `QScrollArea`)

- Chaque module = écran autonome à un seul niveau (pas de stepper), utilisable sans passer par le concept de projet/pipeline complet.
- Icône dédiée par module ; statut d'installation affiché inline si pertinent (ex. "4DGS · non installé").
- **Pas de case "Activer le module"** distincte (contrairement à Sharp/4DGS/360 Extractor aujourd'hui) — la sélection du module dans le rail suffit à y accéder.
- **360 Extractor** : reste une variante du pipeline Gsplat (mode 360, toggle dans Source) **et** un module standalone.
- **Brush** : ajouté en module indépendant — reprend `run_standalone()` existant, à rebrancher sur le chemin orchestré (cf. cluster C dette technique) plutôt que fire-and-forget.
- **SuperSplat** : ajouté en module indépendant — écran identique à l'étape Visualiser, accessible sans navigation pipeline.
- **4DGS** : accès dual confirmé — pipeline complet top-bar (préparation dataset dans le contexte d'un projet) **et** module OUTILS (préparation de dataset autonome, sans navigation pipeline).

### Centre + Barre de droite
- **Breadcrumb de flux** en haut du centre (toutes étapes PIPELINE) : résume uniquement les étapes incluses dans le run courant, avec stats live compactes par étape (ex. "Source · 412 img → COLMAP · 398 posées → Brush · 12400/30000 → Export SPZ") — reflète l'état terminé/en cours/en attente de chaque étape active.
- **Centre** : contenu contextuel à l'étape/module sélectionné — instructions, aperçu, et pour les étapes avec exécution longue (Reconstruction, Entraînement), bascule vers une vue de suivi d'exécution (aperçu/courbe de loss en zone centrale + rangée de stats compactes sous l'aperçu, ex. pour Entraînement : splats, it/s, temps restant, état thermique — à adapter par étape).
- **Barre de logs repliable** en bas de fenêtre, **repliée par défaut**, persistante à travers les écrans, avec recherche, **Effacer**, **Copier**, **Sauvegarder logs** (repris tels quels de l'onglet Logs actuel), et auto-scroll lock (déjà existant, préservé littéralement — pas juste une métaphore pour la navigation du rail).
- **Barre de droite** : tous les paramètres de l'élément sélectionné, avec hiérarchie **Preset (si pertinent) → champs essentiels visibles directement → sections avancées repliables**, toggle "Avancé" dans l'en-tête du panneau pour révéler les groupes secondaires. Répond directement au pain point initial (densité, absence de hiérarchie essentiel/avancé). **Appliqué partout où c'est dense** (Source inclus, pas seulement Entraînement).
- **Convention de nommage "X après"** : les toggles de chaînage automatique utilisent tous la même forme — **Entraînement après**, **Nettoyer après**, **Exporter après**, **Visualiser après** — repris à l'identique dans Source, Reconstruction, Entraînement et tous les modules OUTILS concernés. Remplace les formulations variables actuelles ("Lancer Brush à la suite", "Nettoyer le résultat", "Lancer la visualisation après entraînement", etc.).
- **Lancer/Arrêter local par écran** : en plus du bouton "Lancer" global du top bar, chaque étape optionnelle (Nettoyage, Export, Visualiser) et chaque module OUTILS a son propre Lancer/Arrêter local dans le centre — permet d'exécuter cet élément seul sans dépendre du contexte du run global. Les deux mécanismes coexistent (comme déjà noté pour Visualiser).
- **Principe général params inline vs partagés** : question posée explicitement, **réponse jamais formellement tranchée** comme principe général. Résolu au cas par cas dans les étapes déjà définies : les params pertinents apparaissent directement où ils sont utilisés (Source, Reconstruction), y compris en **duplication assumée** entre deux endroits quand ça sert un vrai cas d'usage (ex. `undistort_images` présent à la fois dans Source et dans Reconstruction).

### Progression (3 niveaux, hérités d'une réflexion antérieure, non re-questionnés en conversation)
1. Barre globale segmentée pondérée + ETA
2. Micro-barre par étape dans le rail
3. Vue détaillée par phase nommée au centre (mode indéterminé pour les phases non-progressables type mapper COLMAP)

### Notifications système
Notification macOS native (via `pyobjc-framework-Cocoa`, déjà une dépendance du projet — pas de nouvelle dépendance) à la fin d'un run complet (succès) ou en cas d'échec d'une étape. Utile pour les étapes longues (Reconstruction/Entraînement, jusqu'à 4h de timeout Brush) quand l'utilisateur n'a pas l'app au premier plan. Clic sur la notification ramène l'app au premier plan (comportement standard macOS). Toggle d'activation dans la fenêtre de réglages généraux.

### Navigation pendant l'exécution
Le rail **suit automatiquement l'étape active** par défaut (bascule seul de Reconstruction à Entraînement, etc.). Se **désaccouple dès qu'on clique manuellement** sur un autre élément du rail — même logique que le lock auto-scroll des logs déjà existant. Le suivi auto ne reprend pas tout seul après désaccouplement (à confirmer à l'implémentation : reprise manuelle via un bouton "revenir au live" ?).

---

## 3. Détail par élément du rail

### ✅ Source (étape PIPELINE)

**Correspondance avec les onglets actuels** :
- **Entraînement** (`ConfigTab`) → éclaté : la majorité (input, dossier sortie, delete dataset, filter_blurry/upscale/undistort/mode stabilisé, post_clean/post_export) va dans **Source** ; "Reprise COLMAP" va dans **Reconstruction** (déjà couvert par le sélecteur de dossier en entrée directe) ; la case "lancer Brush automatiquement" devient le toggle d'activation de l'étape **Entraînement**
- **Paramètres COLMAP** (`ParamsTab`) → entièrement absorbé dans **Reconstruction**
- **Brush** (`BrushTab`) → entièrement absorbé dans **Entraînement** (étape séparée, pas fusionnée avec Reconstruction)

**Centre**
- Nom du projet (auto-rempli depuis le dossier/fichier source, éditable)
- Zone de dépôt/sélection (`DropLineEdit`, glisser-déposer dossier/fichier/vidéo)
- Détection auto image/vidéo au drag&drop (**existe déjà dans le code**, CHANGELOG v0.22 — réutilisée telle quelle, radio manuel gardé en override)
- Type de sélection : Dossier/Fichier(s) (pertinent pour Images)
- Aperçu contextuel : vignette (image unique) / nombre de fichiers (dossier) / durée+résolution (vidéo)
- Texte d'instruction contextuel selon le mode détecté
- Si vidéo détectée : options d'extraction (FPS)
- Dossier de sortie + Destination des checkpoints (optionnel)
- **Pas de champ "mode d'entraînement" local** — lecture seule sur le mode top-bar (Gsplat/Sharp/4DGS) + toggle 360 séparé, pas de duplication du sélecteur

**Barre de droite** (hiérarchie essentiel/avancé, même pattern qu'Entraînement)
- Champs essentiels visibles directement : **Entraînement après** (auto-chaîne l'étape Entraînement), **Visualiser après**
- Toggle "Avancé" → révèle : Upscaler les images, Générer images non-distordues (`undistort_images` — dupliqué avec Reconstruction, voir note), Supprimer les images floues avant reconstruction (`filter_blurry`/`blur_factor`), Mode stabilisé
- **Nettoyer après** (révèle rien de plus, PlyCleaner utilise ses réglages par défaut ici — l'intensité se règle dans l'étape Nettoyage elle-même)
- **Exporter après** (révèle Dossier d'export des PLY, Format de conversion du PLY de sortie)
- *(séparé visuellement, action destructive)* Supprimer le dataset existant (règles actuelles conservées)

### ✅ Reconstruction (étape PIPELINE)

**Centre — état repos**
- Bannière "Apple Silicon détecté — N threads optimisés" (reprise telle quelle de l'onglet Paramètres COLMAP actuel)
- Si dataset déjà défini via Source : résumé prêt à lancer (nb images, chemin, modèle caméra)
- Si entrée directe (sans passer par Source) : sélecteur de dossier **"Reprise de COLMAP"**, **deux cas gérés par le même sélecteur** :
  - Dossier = projet CorbeauSplat existant → resume classique (comportement actuel : réutilise `images/`, écrase `sparse/`+`database.db`)
  - Dossier externe libre contenant des images → **nouveau projet créé à la volée** (nom/dossier de sortie déduits ou demandés)
- Nom du projet / dossier de sortie (si pas déjà connus du contexte)
- **Entraînement après** (contrôle si l'étape Entraînement s'enchaîne automatiquement dans ce run — équivalent de la case "Lancer entrainement Brush automatiquement" existant aujourd'hui dans ConfigTab)
- **Visualiser après** (même flag que Source, exposé ici aussi)

**Centre — état exécution**
- Vue par phase nommée : Feature Extraction → Matching → Mapper → Undistortion
- Progression détaillée (3ᵉ niveau des 3 niveaux de progression), logs de la phase en cours

**Barre de droite** (accordéons)
- **Feature Extraction** : `camera_model`, `single_camera`, `max_image_size`, `feature_type`, `estimate_affine_shape`, `domain_size_pooling`, `max_num_features`
- **Matching** : `matching_type`, `matcher_type`, `sequential_overlap`, `max_ratio`, `max_distance`, `cross_check`, `guided_matching`, `min_num_matches`
- **Mapper** : `ba_refine_focal_length`, `ba_refine_principal_point`, `ba_refine_extra_params`, `use_view_graph_calibration`, `ignore_watermarks`, `thermal_throttling`, `undistort_images` (exécution réelle ici, dupliqué en raccourci dans Source)

### ✅ Entraînement (étape PIPELINE) — nouveau, équivalent de l'onglet Brush actuel

**Centre — état repos**
- Si chaîné automatiquement depuis Reconstruction (toggle actif) : résumé du dataset issu de la reconstruction précédente, prêt à lancer
- Si **Mode Manuel/Indépendant** (équivalent du toggle actuel dans `BrushTab`) : sélecteurs Dossier Dataset (sparse+images), Dossier Export, Nom du fichier PLY (optionnel) — permet de lancer un entraînement Brush sur un dataset externe sans passer par Source/Reconstruction
- **Visualiser après** (sa vraie place — dupliqué en raccourci dans Source et Reconstruction)

**Centre — état exécution**
- Progression de l'entraînement (steps courants/total), logs
- Aperçu live si "Activer le visualiseur pendant l'entraînement" est coché

**Barre de droite**
- Preset (dropdown, en tête de panneau) — inclut les presets existants (`BRUSH_PRESETS`, Strategy pattern déjà en place) **et** des presets personnalisés sauvegardés par l'utilisateur
- **Enregistrer la configuration actuelle comme preset** (nomme et persiste l'ensemble des réglages de l'étape — steps, SH degree, max splats, densification, checkpoints — réutilisable via le dropdown Preset)
- Champs essentiels visibles directement : Steps Total, SH Degree, Max Splats (`--max-splats`, actuellement noyé dans `custom_args`/`ALLOWED_FLAGS` — candidat à promouvoir en champ structuré), Device
- Toggle "Avancé" (**mémorisé** entre sessions, comme le thème) dans l'en-tête → révèle : Résolution Maximum, Arguments supplémentaires (reliquat non couvert par les champs structurés), Activer le visualiseur pendant l'entraînement
- Section repliable **Densification** : les flags `ALLOWED_FLAGS` correspondants (`--growth-grad-threshold`, `--growth-select-fraction`, `--growth-stop-iter`, `--start-iter`, `--refine-every`, `--refine-pose`) — mêmes candidats à structurer plutôt que texte libre
- Section repliable **Checkpoints** : destination, `--checkpoint-interval`, `--save-iterations`, `--eval-every`, `--export-every`, mode (Nouveau/Refine)
- Mode Manuel/Indépendant (bascule chaîné ↔ manuel)
- Afficher les détails avancés (si distinct du toggle "Avancé" — à clarifier à l'implémentation, risque de redondance)

**Note structuration** : le mockup suggère de promouvoir certains flags de `ALLOWED_FLAGS` (aujourd'hui dans `custom_args` texte libre splitté) en champs structurés (Max Splats, groupe Densification, groupe Checkpoints). C'est un changement de surface (UI) au-dessus de l'allowlist existante côté `BrushEngine`, pas un changement de sécurité — l'allowlist continue de filtrer côté moteur quelle que soit la façon dont l'UI construit la chaîne.

**Sauvegarde de configuration** : le mécanisme global (icônes Charger/Sauvegarder en top bar, voir §2) couvre déjà toute la chaîne, Entraînement inclus — le "Enregistrer la configuration actuelle comme preset" ci-dessus reste utile comme raccourci **local et plus étroit** (juste les params Brush, sans les chemins ni le reste de la chaîne), similaire à `BRUSH_PRESETS` existant.

**Note** : le module OUTILS "Brush" (§2.3) reste distinct — accès rapide sans passer par la navigation pipeline (Source/Reconstruction/Entraînement) du tout, même logique que 360 Extractor/Upscale qui existent aussi en variante de pipeline et en module autonome. Le mode manuel d'Entraînement et le module Brush partagent probablement le même écran sous-jacent, à vérifier à l'implémentation.

### ✅ Nettoyage (étape PIPELINE, optionnelle)

**Centre**
- Zone de dépôt/sélection PLY (fichier unique ou dossier pour mode batch)
- Si chaîné automatiquement post-Entraînement (`post_clean`) : fichier pré-rempli depuis la sortie Brush
- Liste des fichiers détectés si batch
- Statut d'exécution simple (pas de vue par phase — `ply_cleaner` en process, NumPy/plyfile, pas de subprocess externe)

**Barre de droite**
- Mode (Fichier unique / Batch)
- Intensité (Léger / Moyen / Fort)
- Réglages avancés (`opacity_min`, `scale_pct`, `outlier_pct`)
- Dossier/fichier de sortie nettoyé

### ✅ Export (étape PIPELINE, optionnelle)

**Centre**
- Zone de dépôt/sélection PLY (fichier unique ou multiple)
- Si chaîné auto post-Nettoyage (`post_export`) : fichier(s) pré-remplis depuis la sortie précédente (Nettoyage si actif, sinon Reconstruction)
- Liste des fichiers à exporter si multi
- Dossier de sortie
- Progression par fichier (`ExportWorker` a des signaux `log/progress/status/finished`)

**Barre de droite**
- Format cible (`spz`/`glb`/`obj`/`ply`/`xyz`)
- Échelle (`scale`, défaut 1.0)
- Options spécifiques au format (détail à vérifier dans `export_engine.py` à l'implémentation)
- Avertissement si dépendance manquante pour le format choisi (GLB → `trimesh`/`open3d`/repli `assimp`/`blender`)

### ✅ Visualiser (étape PIPELINE, optionnelle)

**Centre**
- Zone de dépôt/sélection du fichier à visualiser (.ply/.spz), pré-rempli si chaîné depuis Export/Nettoyage/Reconstruction
- **Bouton Démarrer/Arrêter local**, indépendant du bouton "Lancer" du top bar — permet de lancer le viewer seul, avec ou sans PLY déjà sélectionné
- Statut serveur (Arrêté/En cours)
- Rappel URL locale une fois lancé + bouton "Rouvrir dans le navigateur" (SuperSplat reste web-based, pas de viewer embarqué)

**Barre de droite**
- Port SuperSplat
- Port Données
- Masquer l'interface (No UI)
- Position Caméra (X,Y,Z)
- Rotation Caméra (X,Y,Z, degrés)

**Note** : deux façons de démarrer SuperSplat coexistent — bouton local (Visualiser) pour un lancement ponctuel/manuel, et toggle **Visualiser après** (Source) pour un chaînage automatique via le bouton "Lancer" global. Les deux pilotent le même `SuperSplatEngine`.

### ✅ Module Brush (standalone)

**Centre**
- Statut moteur Brush (version release/compilé source, réinstaller)
- Sélecteurs Dossier Dataset (sparse+images), Dossier Export, Nom du fichier PLY (optionnel) — identique au mode manuel d'Entraînement
- Suivi d'exécution : progression steps, aperçu live si viewer actif
- **Nettoyer après** / **Exporter après** / **Visualiser après**

**Barre de droite**
Identique à Entraînement (Preset, Steps Total, SH Degree, Max Splats, Device, toggle Avancé, sections Densification/Checkpoints, mode Nouveau/Refine) — même écran sous-jacent, confirmé.

### ✅ Module ML Sharp

**Centre**
- Statut moteur (installé et prêt / non installé + lien réinstaller — même logique que la pastille "moteurs prêts" du top bar)
- Toggle Image → PLY / Vidéo → PLY
- Zone de dépôt/sélection entrée (`DropLineEdit`, détection auto image/vidéo comme Source)
- Dossier de sortie
- Suivi d'exécution : simple running/done pour une image (un seul appel d'inférence) ; barre de progression par frame pour une vidéo (`SharpVideoWorker` a un vrai signal `progress`)

**Barre de droite**
- Device
- Checkpoint (.pt) optionnel + Parcourir (auto-résolu par défaut sinon)
- Mode Verbose
- Upscaler avant traitement (toggle, réutilise le module Upscale)
- **Nettoyer après** / **Exporter après** / **Visualiser après** (mêmes toggles que Source — le module produit un `.ply`)

**Pattern général OUTILS** : les toggles **Nettoyer après** / **Exporter après** / **Visualiser après** s'appliquent aux modules qui produisent un `.ply` (ML Sharp, Brush standalone, SplatTransform). 360 Extractor et Upscale produisent des images, pas concernés.

### ✅ Module SuperSplat (standalone)

**Centre**
- Zone de dépôt/sélection du fichier à visualiser (.ply/.spz)
- Bouton Démarrer/Arrêter (même mécanisme que l'étape Visualiser)
- Statut serveur (Arrêté/En cours)
- Rappel URL locale une fois lancé + bouton "Rouvrir dans le navigateur"

**Barre de droite**
- Port SuperSplat, Port Données, Masquer l'interface (No UI), Position Caméra (X,Y,Z), Rotation Caméra (X,Y,Z, degrés)

**Note** : écran identique à l'étape PIPELINE Visualiser, accessible ici sans navigation pipeline — même pattern que Brush/Entraînement.

### ✅ Module Upscale

**Centre**
- Statut moteur (installé/prêt, réinstaller — même pattern)
- Catalogue des modèles (cards : nom, description, échelle, taille, statut installé, Télécharger/Supprimer) — contenu riche, sa place naturelle est ici plutôt qu'en barre de droite
- Zone dépôt/sélection : Source (fichier ou dossier), Destination
- Suivi d'exécution (progress par fichier si dossier)

**Barre de droite**
- Modèle actif (dropdown, reflète le catalogue du centre)
- Échelle de sortie, Format de sortie, Compression, Taille des tuiles, Mode TTA

Pas de **Nettoyer après** / **Exporter après** / **Visualiser après** (sortie image, pas `.ply`).

### ✅ Module SplatTransform

**Centre**
- Statut moteur (détecté/non détecté, comme aujourd'hui)
- Zone dépôt/sélection : Entrée (.ply/.spz/.splat), Dossier de sortie
- Suivi d'exécution simple (transformation en process, pas de progress granulaire connu)
- **Nettoyer après** / **Exporter après** / **Visualiser après** (produit un `.ply`/`.spz`/`.splat`)

**Barre de droite**
- Format de sortie
- Filtres : Supprimer splats dégénérés (`--filter-nan`), Optimiser l'ordre spatial (`--morton-order`), Réduire harmoniques sphériques (`--filter-harmonics`, avec choix de bande)
- Décimer (`--decimate`, % à conserver)

### ✅ Module 4DGS (standalone)

**Centre**
- Texte descriptif du module (repris tel quel de l'onglet actuel : "Ce module extrait des frames de vidéos synchronisées...")
- Statut installation (souvent "non installé" comme dans le mockup — Nerfstudio ~4Go, install à la demande)
- Zone dépôt/sélection : Source Vidéos (dossier multi-caméras), Destination Dataset
- Bouton "Reconstruction COLMAP seulement" séparé (existe déjà aujourd'hui — utile pour relancer juste cette sous-partie)
- Suivi d'exécution : statut simple (pas de signal `progress` structuré aujourd'hui, juste `log/status/finished`)

**Barre de droite**
- Extraction FPS
- Pas de **Nettoyer après** / **Exporter après** / **Visualiser après** — pas de sortie `.ply`, s'arrête à un dataset préparé pour Nerfstudio

### ✅ Module 360 Extractor

**Centre**
- Texte descriptif du module (repris tel quel de l'onglet actuel : "Convertit des vidéos/images 360° équirectangulaires...")
- Statut moteur (installé/prêt, comme ML Sharp)
- Zone de dépôt/sélection : Vidéo source, Dossier de sortie
- Suivi d'exécution : progress bar (`Extractor360Worker` a `log/progress/status/finished`)
- Pas de **Nettoyer après** / **Exporter après** / **Visualiser après** — sortie en images planaires, pas de `.ply`

**Barre de droite**
- Intervalle (sec), Résolution (px), Disposition Caméras, Nb Caméras, Qualité JPEG, Format
- Section repliable **IA Avancé** : Masquer Opérateur (YOLO), Sauter images avec Opérateur, Intervalle Adaptatif, Seuil Mouvement

---

## 4. Points ouverts (non tranchés)

1. ~~Modèle `Project`~~ — **résolu** : label cosmétique dérivé des champs de Source, comme aujourd'hui. Pas d'objet `Project` persistant avec chemin propre.
2. **Principe général params inline vs partagés** entre étape pipeline et module OUTILS — jamais formellement tranché, résolu au cas par cas jusqu'ici (duplication assumée quand utile).
3. **Cluster C dette technique** (chemins Brush dupliqués, workers FourDGS/Extractor360) — résolu dans Claude Code, détail exact inconnu ici.
4. **Cluster D dette technique** (`ExportTab` orpheline, import privé) — résolu dans Claude Code, détail exact inconnu ici — impacte directement la définition de l'étape Export à venir.
5. ~~Un projet = un pipeline figé ou changeable~~ — **résolu** : changeable en cours de route. Nuance d'implémentation à traiter plus tard : basculer de mode ne supprime pas les sorties déjà produites par l'ancien mode (ex. reconstruction COLMAP déjà lancée puis bascule vers Sharp) — elles restent sur disque, potentiellement réutilisables si on rebascule, notamment via le sélecteur "Reprise de COLMAP" de Reconstruction.
6. ~~Répartition Source/Reconstruction à reprendre~~ — **résolu** : split en 3 étapes distinctes Source/Reconstruction (COLMAP seul)/Entraînement (Brush seul, nouveau). Table de correspondance mise à jour en §3.
7. ~~Sauvegarde de configuration en preset personnalisé~~ — **résolu** : mécanisme global via icônes Charger/Sauvegarder en top bar, couvre toute la chaîne (Source y compris chemins, Reconstruction, Entraînement, Nettoyage/Export, toggles). Coexiste avec les presets locaux par étape (plus étroits, engine-only). Stockage à définir à l'implémentation.

---

## 5. Prochaine étape

Toutes les étapes PIPELINE et tous les modules OUTILS sont définis (Source, Reconstruction, Entraînement, Nettoyage, Export, Visualiser + Brush, ML Sharp, SuperSplat, Upscale, SplatTransform, 4DGS, 360 Extractor). Tous les points ouverts du §4 sont résolus. Audit de complétude effectué contre les 11 onglets actuels (captures + `ETAT_DES_LIEUX.md`) — aucune option perdue, gaps identifiés corrigés (logs Effacer/Copier/Sauvegarder, bannière Apple Silicon, textes descriptifs 4DGS/360 Extractor, Lancer/Arrêter local par écran, suppression des cases "Activer le module").

---

## 6. Notes pour le prompt d'implémentation final

- **Single source of truth sur les toggles dupliqués** : `Entraînement après`, `Nettoyer après`, `Exporter après`, `Visualiser après`, `undistort_images` apparaissent à plusieurs endroits de l'UI (Source/Reconstruction/Entraînement/modules OUTILS). Chaque duplication doit être **bindée au même état source** (une seule propriété/variable par flag, plusieurs widgets qui la reflètent), jamais des widgets indépendants avec leur propre état — c'est exactement le pattern qui a causé l'éclatement `undistort_images`/`filter_blurry`/`blur_factor` corrigé en dette technique (cluster B). À rappeler explicitement dans le prompt Claude Code au moment de l'implémentation.
