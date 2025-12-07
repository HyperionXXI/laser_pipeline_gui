# Laser Pipeline GUI  
_Interface graphique de traitement laser / Laser processing GUI_

---

## Aperçu / Overview

Interface graphique expérimentale pour transformer une vidéo en animation laser au format ILDA, via un pipeline en plusieurs étapes :  
*Experimental graphical interface to convert a video into a laser animation in ILDA format, using a multi-step pipeline:*

1. **FFmpeg** : extraction de frames PNG à partir d’une vidéo.  
   *FFmpeg: extract PNG frames from a video.*  

2. **ImageMagick** : prétraitement des frames en BMP (binarisation + thinning optionnel).  
   *ImageMagick: pre-process frames to BMP (binarization + optional thinning).*  

3. **Potrace** : vectorisation des BMP en SVG.  
   *Potrace: vectorize BMP images to SVG.*  

4. **Export ILDA** : génération d’un fichier `.ild` à partir des SVG.  
   *ILDA export: generate a `.ild` file from the SVG frames.*  

Le projet est pensé comme un banc d’essai pour automatiser la préparation de contenus laser (par exemple pour LaserOS / LaserCubes), avec une approche modulaire et des étapes bien séparées.  
*The project is designed as a test bench to automate the preparation of laser content (for example for LaserOS / LaserCubes), with a modular approach and clearly separated steps.*

Le format ILDA est un format de fichier standardisé (`.ild`) défini par l’International Laser Display Association pour stocker et échanger des images et animations vectorielles destinées aux projecteurs laser (positions des points et couleurs).  
*The ILDA format is a standardized file format (`.ild`) defined by the International Laser Display Association to store and exchange vector images and animations for laser projectors (point positions and colors).*

---

## Fonctionnalités / Features

### Pipeline complet vidéo → ILDA  
### Full video → ILDA pipeline

- **Sélection de la vidéo source**  
  *Source video selection*
  - Chemin de la vidéo (MP4, MOV, AVI, …).  
    *Video file path (MP4, MOV, AVI, …).*  
  - Choix du nom de projet (création de `projects/<nom_projet>/`).  
    *Project name (creates `projects/<project_name>/`).*

- **Étape 1 – FFmpeg → PNG**  
  *Step 1 – FFmpeg → PNG*
  - Extraction des frames dans `projects/<projet>/frames/frame_XXXX.png`.  
    *Extract frames to `projects/<project>/frames/frame_XXXX.png`.*  
  - Paramètre **FPS** réglable.  
    *Configurable **FPS** parameter.*  
  - Bouton : `Lancer FFmpeg`.  
    *Button: `Run FFmpeg`.*

- **Étape 2 – Bitmap (ImageMagick)**  
  *Step 2 – Bitmap (ImageMagick)*
  - Conversion PNG → BMP dans `projects/<projet>/bmp/frame_XXXX.bmp`.  
    *Convert PNG → BMP in `projects/<project>/bmp/frame_XXXX.bmp`.*  
  - Paramètres :  
    *Parameters:*
    - **Seuil (%)** pour la binarisation.  
      ***Threshold (%)** for binarization.*  
    - **Thinning** (optionnel) pour affiner les traits.  
      ***Thinning** (optional) to thin the strokes.*  
    - **Max frames (0 = toutes)** pour limiter le nombre d’images traitées.  
      ***Max frames (0 = all)** to limit the number of processed frames.*  
  - Bouton : `Lancer Bitmap`.  
    *Button: `Run Bitmap`.*

- **Étape 3 – Vectorisation (Potrace)**  
  *Step 3 – Vectorization (Potrace)*
  - Conversion BMP → SVG dans `projects/<projet>/svg/frame_XXXX.svg`.  
    *Convert BMP → SVG in `projects/<project>/svg/frame_XXXX.svg`.*  
  - Post-traitement des SVG pour les adapter au rendu laser.  
    *SVG post-processing to adapt them for laser rendering.*  
  - Bouton : `Lancer Potrace`.  
    *Button: `Run Potrace`.*

- **Étape 4 – Export ILDA**  
  *Step 4 – ILDA export*
  - Parcours des SVG du projet et génération d’un fichier :  
    *Iterate through the project’s SVG files and generate:*
    - `projects/<projet>/ilda/<projet>.ild`  
      *`projects/<project>/ilda/<project>.ild`*
  - Utilise un writer ILDA dédié (`core/ilda_writer.py` / `core/step_ilda.py`).  
    *Uses a dedicated ILDA writer (`core/ilda_writer.py` / `core/step_ilda.py`).*  
  - Bouton : `Exporter ILDA`.  
    *Button: `Export ILDA`.*

> ⚠️ **Remarque** : la partie conversion SVG → points ILDA est encore expérimentale.  
> ⚠️ *Note: the conversion from SVG → ILDA points is still experimental.*  
>
> Le pipeline ILDA fonctionne déjà pour des tests simples (ex. carré de test), mais  
> la conversion des SVG complexes (La Linea, etc.) reste à affiner (colorisation, filtrage,  
> simplification des paths…).  
> *The ILDA pipeline already works for simple tests (e.g. a test square), but  
> the conversion of complex SVGs (La Linea, etc.) still needs tuning (colorization, filtering,  
> path simplification…).*

---

## Interface graphique / Graphical user interface

L’UI est construite avec **PySide6** :  
*The UI is built with **PySide6**:*

- En haut : **Paramètres généraux**  
  *Top: **General settings***
  - Vidéo source  
    *Source video*  
  - Nom du projet  
    *Project name*  
  - FPS  
    *FPS*  
  - Bouton « Tester les paramètres » (log des valeurs courantes).  
    *“Test settings” button (logs current values).*

- Au centre : **Pipeline vidéo → vecteur**  
  *Center: **Video → vector pipeline***
  - Sélecteur de **frame** + bouton « Prévisualiser frame ».  
    ***Frame** selector + “Preview frame” button.*  
  - **Barre de progression** + bouton « Annuler la tâche en cours »  
    (structure en place, annulation à raffiner).  
    ***Progress bar** + “Cancel current task” button  
    (structure implemented, cancellation still to be refined).*  
  - **4 colonnes** alignées :  
    ***4 aligned columns:***
    1. **FFmpeg** + prévisualisation PNG.  
       ***FFmpeg** + PNG preview.*  
    2. **Bitmap** + prévisualisation BMP.  
       ***Bitmap** + BMP preview.*  
    3. **Vectorisation** + prévisualisation SVG rasterisée.  
       ***Vectorization** + rasterized SVG preview.*  
    4. **ILDA** + prévisualisation (placeholder pour l’instant).  
       ***ILDA** + preview (placeholder for now).*

- En bas : **Zone de log**  
  *Bottom: **Log area***
  - Affiche la trace des étapes, erreurs, chemins de fichiers, etc.  
    *Displays the trace of steps, errors, file paths, etc.*

Les prévisualisations sont gérées via `gui/preview_widgets.py` :  
*Previews are handled via `gui/preview_widgets.py`:*

- `RasterPreview` pour PNG/BMP/ILDA (pixmaps).  
  *`RasterPreview` for PNG/BMP/ILDA (pixmaps).*  
- `SvgPreview` qui rasterise le SVG pour l’afficher dans un `QLabel`  
  avec un comportement cohérent avec les previews raster (respect du ratio, redimensionnement, message « aucune image »…).  
  *`SvgPreview` rasterizes the SVG and displays it in a `QLabel`  
  with behavior consistent with raster previews (keep aspect ratio, resize, “no image” message, etc.).*

---

## Architecture du code / Code architecture

```text
core/
  config.py          # chemins vers FFMPEG, MAGICK, POTRACE, PROJECTS_ROOT, etc.
                    # paths to FFMPEG, MAGICK, POTRACE, PROJECTS_ROOT, etc.
  step_ffmpeg.py     # extract_frames(...)
                    # extract_frames(...)
  step_bitmap.py     # png_frames_to_bmp_folder(...) / convert_project_frames_to_bmp(...)
                    # png_frames_to_bmp_folder(...) / convert_project_frames_to_bmp(...)
  step_potrace.py    # bitmap_to_svg_folder(...) + post-traitement des SVG
                    # bitmap_to_svg_folder(...) + SVG post-processing
  step_ilda.py       # structures ILDA, export_project_to_ilda(...), parsing SVG (en développement)
                    # ILDA structures, export_project_to_ilda(...), SVG parsing (work in progress)
  ilda_writer.py     # writer ILDA bas niveau (headers, points, démo carré, etc.)
                    # low-level ILDA writer (headers, points, test square demo, etc.)

gui/
  main_window.py     # classe MainWindow, layout 4 colonnes, gestion des QThread et Worker
                    # MainWindow class, 4-column layout, QThread + Worker management
  preview_widgets.py # widgets de prévisualisation PNG/BMP/SVG/ILDA
                    # preview widgets for PNG/BMP/SVG/ILDA

tests/
  test_ilda_square.py  # script de test pour générer un carré ILDA (validation LaserOS)
                      # test script to generate an ILDA square (LaserOS validation)
