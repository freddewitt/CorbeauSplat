# Installation de mast3r-sfm sur Mac Silicon avec venv

> Tutoriel from scratch — testé sur Mac Silicon (M1/M2/M3/M4)  
> Génère un dataset COLMAP (`cameras.txt`, `images.txt`, `points3D.txt`) sans GUI

---

## Prérequis système

### Xcode Command Line Tools
```bash
xcode-select --install
```

### Homebrew (si pas déjà installé)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Python 3.11
```bash
brew install python@3.11
```

---

## Étape 1 — Cloner le dépôt

```bash
cd ~
git clone --recursive https://github.com/jwd222/mast3r-sfm
cd mast3r-sfm
```

> Le flag `--recursive` est indispensable — il clone aussi `dust3r` inclus en sous-module.

---

## Étape 2 — Créer le venv

```bash
python3.11 -m venv venv
source venv/bin/activate
```

> Ton prompt doit afficher `(venv)` — si ce n'est pas le cas, le venv n'est pas actif.

Mettre pip à jour :

```bash
pip install --upgrade pip
```

---

## Étape 3 — Installer PyTorch pour Mac Silicon

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

> On utilise la version CPU/MPS — ne pas utiliser `pytorch-cuda`, ça n'existe pas sur Mac.

Vérifier que MPS est disponible :

```bash
python -c "import torch; print('MPS:', torch.backends.mps.is_available())"
```

> Doit afficher `MPS: True`.

---

## Étape 4 — Installer les dépendances

```bash
pip install -r requirements.txt
pip install -r dust3r/requirements.txt
pip install -r dust3r/requirements_optional.txt
```

> `requirements_optional.txt` ajoute le support des images HEIC (photos iPhone).

Installer les dépendances spécifiques à mast3r-sfm :

```bash
pip install numpy opencv-python trimesh Pillow tqdm plyfile
```

---

## Étape 5 — Télécharger le modèle

```bash
mkdir -p checkpoints
curl -L https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth \
  -o checkpoints/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth
```

> Le modèle fait ~400 MB — patiente quelques minutes.  
> Si `curl` est lent, tu peux aussi utiliser `wget` :

```bash
wget https://download.europe.naverlabs.com/ComputerVision/MASt3R/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth \
  -P checkpoints/
```

---

## Étape 6 — Préparer les images

Le script accepte uniquement `.jpg`, `.JPG`, `.png`, `.PNG`.  
Place tes images dans un dossier **hors du Bureau** (le Bureau est protégé par macOS).

```bash
mkdir -p ~/reconstruction/images
```

Copier tes images :

```bash
# Si tes images sont en .jpg
cp /chemin/vers/tes/images/*.jpg ~/reconstruction/images/

# Si tes images sont en .png
cp /chemin/vers/tes/images/*.png ~/reconstruction/images/
```

Vérifier :

```bash
ls ~/reconstruction/images/ | head -10
echo "Total :" $(ls ~/reconstruction/images/ | wc -l) "images"
```

### Si tes images sont en .HEIC (photos iPhone)

```bash
# Installer sips (déjà présent sur macOS)
for f in ~/reconstruction/images/*.HEIC; do
  sips -s format jpeg "$f" --out "${f%.HEIC}.jpg"
done
# Supprimer les .HEIC
rm ~/reconstruction/images/*.HEIC
```

---

## Étape 7 — Lancer la reconstruction

```bash
# S'assurer d'être dans le bon dossier avec le venv actif
cd ~/mast3r-sfm
source venv/bin/activate

python colmap_from_mast3r.py \
  --image_dir ~/reconstruction/images \
  --save_dir ~/reconstruction/output \
  --model_path checkpoints/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth \
  --device mps \
  --shared_intrinsics
```

### Paramètres disponibles

| Paramètre | Défaut | Description |
|---|---|---|
| `--image_dir` | — | Dossier contenant les images |
| `--save_dir` | — | Dossier de sortie |
| `--model_path` | — | Chemin vers le .pth |
| `--device` | `cuda` | Utiliser `mps` sur Mac Silicon, `cpu` en fallback |
| `--shared_intrinsics` | off | Recommandé si toutes les images viennent du même appareil |
| `--niter` | 300 | Iterations globales — réduire à 150 pour aller plus vite |
| `--niter1` | 300 | Iterations coarse — réduire à 150 pour aller plus vite |
| `--niter2` | 300 | Iterations fine — réduire à 150 pour aller plus vite |
| `--min_conf_thr` | 1.5 | Seuil de confiance — augmenter pour filtrer plus |
| `--matching_conf_thr` | 2.0 | Seuil matching — augmenter pour filtrer plus |
| `--image_size` | 512 | Résolution d'entrée |

### Commande rapide (vitesse/qualité équilibré)

```bash
python colmap_from_mast3r.py \
  --image_dir ~/reconstruction/images \
  --save_dir ~/reconstruction/output \
  --model_path checkpoints/MASt3R_ViTLarge_BaseDecoder_512_catmlpdpt_metric.pth \
  --device mps \
  --shared_intrinsics \
  --niter1 150 \
  --niter2 150 \
  --matching_conf_thr 2.0
```

---

## Étape 8 — Vérifier le dataset COLMAP

```bash
find ~/reconstruction/output -name "*.txt" | sort
```

Structure attendue :

```
reconstruction/output/
└── sparse/
    └── 0/
        ├── cameras.txt      ← intrinsèques caméra
        ├── images.txt       ← poses caméra
        └── points3D.txt     ← point cloud sparse
```

---

## Utilisation dans Brush (Gaussian Splatting)

```bash
# Installer Brush (Rust requis)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

git clone https://github.com/ArthurBrussee/brush
cd brush

# Lancer avec le dataset COLMAP
cargo run --release -- \
  --data ~/reconstruction/output/sparse/0
```

---

## Erreurs connues et solutions

| Erreur | Solution |
|---|---|
| `no images found` | Vérifier que les images sont en `.jpg` ou `.png`, pas `.HEIC` ou `.jpeg` |
| `PermissionError: Desktop` | Utiliser un dossier hors du Bureau (`~/reconstruction/images`) |
| `MPS: False` | Vérifier que PyTorch est bien installé : `pip install torch torchvision` |
| `--model_path required` | Ne pas utiliser `--model_name`, utiliser `--model_path` avec le chemin du `.pth` |
| `Warning: RoPE2D` | Normal sur Mac — pas de CUDA, utilise la version PyTorch (plus lente) |
| `torchvision image.so` | Warning ignorable — n'affecte pas la reconstruction |

---

## Notes Mac Silicon

| Point | Détail |
|---|---|
| `--device mps` | GPU Metal — ~5-10 sec/it |
| `--device cpu` | Fallback si MPS pose problème |
| 20 images | ~10-20 minutes |
| 50 images | ~30-50 minutes |
| Kernels CUDA RoPE | Non compilables sur Mac — warning normal |

