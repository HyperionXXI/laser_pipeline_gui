# Laser Pipeline GUI

Interface graphique expérimentale pour transformer une vidéo en animation laser au format ILDA, via un pipeline en plusieurs étapes :

1. **FFmpeg** : extraction de frames PNG à partir d’une vidéo.
2. **ImageMagick** : prétraitement des frames en BMP (binarisation + thinning optionnel).
3. **Potrace** : vectorisation des BMP en SVG.
4. **Export ILDA** : génération d’un fichier `.ild` à partir des SVG.

Le projet est pensé comme un banc d’essai pour automatiser la préparation de contenus laser (par exemple pour LaserOS / LaserCubes), avec une approche modulaire et des étapes bien séparées.

Le format ILDA est un format de fichier standardisé (.ild) défini par l’International Laser Display Association pour stocker et échanger des images et animations vectorielles destinées aux projecteurs laser (positions des points et couleurs).
---

## Fonctionnalités

### Pipeline complet vidéo → ILDA

- **Sélection de la vidéo source**
  - Chemin de la vidéo (MP4, MOV, AVI, …).
  - Choix du nom de projet (création de `projects/<nom_projet>/`).

- **Étape 1 – FFmpeg → PNG**
  - Extraction des frames dans `projects/<projet>/frames/frame_XXXX.png`.
  - Paramètre **FPS** réglable.
  - Bouton : `Lancer FFmpeg`.

- **Étape 2 – Bitmap (ImageMagick)**
  - Conversion PNG → BMP dans `projects/<projet>/bmp/frame_XXXX.bmp`.
  - Paramètres :
    - **Seuil (%)** pour la binarisation.
    - **Thinning** (optionnel) pour affiner les traits.
    - **Max frames (0 = toutes)** pour limiter le nombre d’images traitées.
  - Bouton : `Lancer Bitmap`.

- **Étape 3 – Vectorisation (Potrace)**
  - Conversion BMP → SVG dans `projects/<projet>/svg/frame_XXXX.svg`.
  - Post-traitement des SVG pour les adapter au rendu laser.
  - Bouton : `Lancer Potrace`.

- **Étape 4 – Export ILDA**
  - Parcours des SVG du projet et génération d’un fichier :
    - `projects/<projet>/ilda/<projet>.ild`
  - Utilise un writer ILDA dédié (`core/ilda_writer.py` / `core/step_ilda.py`).
  - Bouton : `Exporter ILDA`.

> ⚠️ **Remarque** : la partie conversion SVG → points ILDA est encore expérimentale.
> Le pipeline ILDA fonctionne déjà pour des tests simples (ex. carré de test), mais
> la conversion des SVG complexes (La Linea, etc.) reste à affiner (colorisation, filtrage,
> simplification des paths…).

---

## Interface graphique

L’UI est construite avec **PySide6** :

- En haut : **Paramètres généraux**
  - Vidéo source
  - Nom du projet
  - FPS
  - Bouton « Tester les paramètres » (log des valeurs courantes).

- Au centre : **Pipeline vidéo → vecteur**
  - Sélecteur de **frame** + bouton « Prévisualiser frame ».
  - **Barre de progression** + bouton « Annuler la tâche en cours » (structure en place, annulation à raffiner).
  - **4 colonnes** alignées :
    1. **FFmpeg** + prévisualisation PNG.
    2. **Bitmap** + prévisualisation BMP.
    3. **Vectorisation** + prévisualisation SVG rasterisée.
    4. **ILDA** + prévisualisation (placeholder pour l’instant).

- En bas : **Zone de log**
  - Affiche la trace des étapes, erreurs, chemins de fichiers, etc.

Les prévisualisations sont gérées via `gui/preview_widgets.py` :

- `RasterPreview` pour PNG/BMP/ILDA (pixmaps).
- `SvgPreview` qui rasterise le SVG pour l’afficher dans un QLabel
  avec un comportement cohérent avec les previews raster (respect du ratio, redimensionnement, message « aucune image »…).

---

## Architecture du code

```text
core/
  config.py          # chemins vers FFMPEG, MAGICK, POTRACE, PROJECTS_ROOT, etc.
  step_ffmpeg.py     # extract_frames(...)
  step_bitmap.py     # png_frames_to_bmp_folder(...) / convert_project_frames_to_bmp(...)
  step_potrace.py    # bitmap_to_svg_folder(...) + post-traitement des SVG
  step_ilda.py       # structures ILDA, export_project_to_ilda(...), parsing SVG (en développement)
  ilda_writer.py     # writer ILDA bas niveau (headers, points, démo carré, etc.)

gui/
  main_window.py     # classe MainWindow, layout 4 colonnes, gestion des QThread et Worker
  preview_widgets.py # widgets de prévisualisation PNG/BMP/SVG/ILDA

tests/
  test_ilda_square.py  # script de test pour générer un carré ILDA (validation LaserOS)
