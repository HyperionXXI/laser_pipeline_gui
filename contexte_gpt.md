# Contexte GPT – Projet *Laser Pipeline GUI*

Ce document sert de **mémoire stable** pour les futures conversations avec ChatGPT
autour du projet `laser_pipeline_gui`.  
Il décrit l’architecture actuelle, les invariants à respecter et les pistes
d’évolution déjà identifiées.

---

## A. Vue d’ensemble et objectifs

### A.1 But du projet

Le projet **Laser Pipeline GUI** est une application expérimentale en Python qui
sert de **banc d’essai** pour transformer une vidéo classique en **animation
laser au format ILDA** (`.ild`).

La chaîne de traitement est découpée en **quatre étapes indépendantes et
réutilisables** :

1. **FFmpeg → PNG**  
   Extraction de frames PNG à partir d’un fichier vidéo (MP4, MOV, AVI…).

2. **ImageMagick → BMP**  
   Prétraitement des PNG en BMP noir/blanc (binarisation, éventuellement
   *thinning*) pour obtenir un trait exploitable par la vectorisation.

3. **Potrace → SVG**  
   Vectorisation des BMP en fichiers SVG (chemins vectoriels).

4. **Export ILDA → .ild**  
   Conversion de la séquence de SVG en un fichier ILDA destiné à des
   logiciels/show laser (LaserOS, LaserCube, etc.).

Objectifs principaux :

- disposer d’un **pipeline modulaire** réutilisable en ligne de commande ;
- offrir une **interface graphique PySide6** pour piloter ce pipeline ;
- gérer :
  - la journalisation (logs),
  - la progression,
  - l’annulation propre d’étapes longues,
  - des **prévisualisations** aux différents stades (PNG, BMP, SVG, ILDA).

Cas d’usage visés :

- animations filaires / vectorielles (ex. *La Linea*),
- générique pour d’autres vidéos stylisées (jeux d’arcade, etc.),
- à terme : gestion d’épaisseur de trait, stabilité, plein écran, couleurs,
  et éventuellement synchronisation approximative avec le son.

---

## B. Architecture globale

L’architecture est organisée en deux couches principales : **core** (métier) et
**GUI** (Qt).

### B.1 Couche core (`core/`)

Logique métier indépendante de Qt :

- `config.py`  
  Résolution des chemins vers les exécutables externes :
  - `FFMPEG_PATH`
  - `POTRACE_PATH`
  - `MAGICK_PATH`
  - `PROJECTS_ROOT`

  Priorité de résolution :

  1. variables d’environnement `LPIP_FFMPEG`, `LPIP_POTRACE`,
     `LPIP_MAGICK`, `LPIP_PROJECTS_ROOT` (si définies) ;
  2. binaire trouvé dans le `PATH` via `shutil.which` ;
  3. chemins par défaut (Windows / Unix) pour garder la compatibilité
     avec la machine de développement actuelle.

  Les outils restent conceptuellement **externes**, mais peuvent
  être fournis dans le repo et référencés par ces variables.

- `step_ffmpeg.py`  
  Extraction des frames PNG à partir de la vidéo.

- `step_bitmap.py`  
  Conversion des PNG en BMP noir/blanc avec paramètres :
  - `threshold` (%),
  - `use_thinning` (bool),
  - `max_frames` (int ou `None` pour toutes les frames).

- `step_potrace.py`  
  Vectorisation des BMP en SVG via Potrace, plus post-traitement des SVG
  (par ex. forcer `stroke` blanc, `fill="none"`, etc.).

- `step_ilda.py`  
  Conversion de la séquence de SVG en frames ILDA :
  - calcul d’une **bounding box globale** sur tous les SVG ;
  - normalisation dans l’espace ILDA `[-32768 .. +32767]` avec un
    `fill_ratio` (< 1 pour éviter le clipping) ;
  - filtrage des petits chemins (anti “poussière”) via `min_rel_size` ;
  - gestion du **blanking** :
    - premier point de chaque sous-chemin en `blanked=True`,
    - points suivants en `blanked=False`.

- `ilda_writer.py`  
  Écriture bas niveau des fichiers `.ild` (entêtes ILDA, frames, points).

- `ilda_preview.py`  
  Outils pour générer des images (PNG) à partir d’un fichier ILDA.
  Utilisé comme base pour une future prévisualisation ILDA plus fidèle.

#### B.1.1 Pipeline générique (`core/pipeline/`)

- `base.py`  
  Définit les types génériques utilisés par toutes les étapes :

  - `FrameProgress`  
    Représente l’avancement d’une frame individuelle pendant un step.

    Champs stables à conserver :
    - `frame_index: int | None`
    - `total_frames: int | None`
    - `frame_path: str | None` (chemin vers le fichier généré, utilisé pour
      les prévisualisations)
    - (optionnel) `step_percent: int | None` si besoin.

  - `StepResult`  
    Résultat global d’un step.

    Champs stables :
    - `success: bool`
    - `message: str`
    - `output_dir: str | None`
    - éventuellement des infos spécifiques (dernier PNG/BMP/SVG, etc.).

  - `StepCallbacks` (ou équivalent)  
    Ensemble de callbacks fournis par la couche supérieure
    (GUI ou CLI) :

    - `log: Callable[[str], None] | None`
    - `progress: Callable[[int], None] | None` (0–100 global)
    - `frame_progress: Callable[[FrameProgress], None] | None`
    - `check_cancel: Callable[[], bool] | None`  
      (permet l’annulation propre).

  **Important :**  
  Le code de `core/pipeline/*.py` ne dépend pas de Qt. Il ne voit
  que ces callbacks Python.

- `ffmpeg_step.py`, `bitmap_step.py`, `potrace_step.py`, `ilda_step.py`  
  Wrappers de haut niveau qui :
  - appellent les fonctions de `step_*.py` correspondantes ;
  - traduisent leur progression en `FrameProgress` ;
  - retournent un `StepResult` cohérent.

### B.2 Couche GUI (`gui/`)

Interface utilisateur basée sur PySide6 :

- `main_window.py`  
  Fenêtre principale avec trois zones :

  1. **Paramètres généraux**  
     - chemin vidéo,
     - nom du projet (ex. `projet_demo`),
     - FPS,
     - bouton « Tester les paramètres » (log des valeurs).

  2. **Pipeline vidéo → vecteur**  
     - contrôle commun “Frame” (`QSpinBox`) + bouton “Prévisualiser frame”
       qui affiche la frame sélectionnée dans les quatre previews (si les
       fichiers existent) ;
     - barre de progression globale + bouton “Annuler la tâche en cours” ;
     - quatre colonnes, chacune avec :
       - un groupe “step”,
       - un groupe “prévisualisation”.

     Colonnes :

     1. **FFmpeg → PNG (frames)**  
        Bouton « Lancer FFmpeg » + preview PNG (`RasterPreview`).

     2. **Bitmap (ImageMagick)**  
        Paramètres :
        - seuil (%),
        - *thinning* (bool),
        - max frames (0 = toutes).  
        Bouton « Lancer Bitmap » + preview BMP (`RasterPreview`).

     3. **Vectorisation (Potrace)**  
        Bouton « Lancer Potrace » + preview SVG (`SvgPreview`).

     4. **ILDA (export)**  
        Bouton « Exporter ILDA » + preview ILDA (actuellement approximation
        basée sur les SVG).

  3. **Zone de log** (`QTextEdit` read-only)  
     - les logs sont timestampés ;
     - auto-scroll sur la dernière ligne à chaque nouveau message.

- `pipeline_controller.py`  
  Objet central qui encapsule les threads et communique avec la couche core.

  - crée un `QThread` par step ;
  - y place un worker qui appelle `run_ffmpeg_step`, `run_bitmap_step`,
    `run_potrace_step` ou `run_ilda_step` ;
  - relaye les callbacks core → signaux Qt :

    - `step_started(step_name: str)`
    - `step_finished(step_name: str, result: StepResult)`
    - `step_error(step_name: str, message: str)`
    - `step_progress(step_name: str, payload: FrameProgress)`

  - détruit proprement le thread après exécution ou annulation.

  L’API publique exposée à `MainWindow` :

  - `start_ffmpeg(video_path, project, fps)`
  - `start_bitmap(project, threshold, use_thinning, max_frames)`
  - `start_potrace(project)`
  - `start_ilda(project)`
  - `cancel_current_step()`.

  **Invariant :** `MainWindow` ne manipule plus directement les `QThread`,
  seulement `PipelineController` et ses signaux.

- `preview_widgets.py`  

  - `RasterPreview`  
    - widget Qt pour images raster (PNG/BMP, etc.) ;
    - fond noir ;
    - image centrée en conservant le ratio (`Qt.KeepAspectRatio`).

  - `SvgPreview`  
    - widget Qt pour SVG (via `QSvgRenderer`) ;
    - fond noir ;
    - calcul d’un `target_rect` ayant le **même ratio** que le `viewBox`,
      centré dans le widget → pas de distorsion même en plein écran.

- `gui_main.py`  
  Point d’entrée minimal qui crée l’application Qt, instancie `MainWindow`,
  et lance la boucle d’événements.

---

## C. Organisation des données de projet

Tous les outputs sont regroupés par **nom de projet** sous `PROJECTS_ROOT`
(par défaut `projects/` à la racine du repo ; surcharge possible via
`LPIP_PROJECTS_ROOT`).

Pour un projet `mon_projet` :

- `projects/mon_projet/frames/`  
  PNG extraits par FFmpeg  
  (`frame_0001.png`, `frame_0002.png`, …).

- `projects/mon_projet/bmp/`  
  BMP générés par ImageMagick.

- `projects/mon_projet/svg/`  
  SVG vectorisés par Potrace.

- `projects/mon_projet/ilda/`  
  fichiers `.ild` exportés.

Cette arborescence est **contractuelle** pour le pipeline, la GUI
et les tests.

---

## D. État fonctionnel actuel

### D.1 Fonctionnel

À la date de ce contexte :

- Le pipeline complet **FFmpeg → BMP → SVG → ILDA** fonctionne sur des
  cas réels (ex. vidéo *La Linea*) et produit des `.ild` lisibles dans
  LaserOS.
- L’animation est reconnaissable et dans le bon sens.
- Les étapes sont pilotables séparément via la GUI.
- La progression et l’annulation sont gérées pour les quatre steps.
- Les prévisualisations fonctionnent :

  - Step 1 : affichage en direct des PNG extraits.  
  - Step 2 : affichage des BMP binarisés.  
  - Step 3 : affichage des SVG vectorisés, sans distorsion quelle que
    soit la taille de la fenêtre.  
  - Step 4 : preview ILDA approximative basée sur les SVG (pas encore un
    rendu ILDA “physique”).

- `MainWindow` ne manipule plus directement de threads, tout passe par
  `PipelineController`.

### D.2 Limitations connues / travaux futurs

Ces points sont **connus et assumés** comme travail futur :

1. **Prévisualisation ILDA plus fidèle / animée**

   - Aujourd’hui, la preview ILDA est basée sur les SVG (approximation).
   - Piste : utiliser `core/ilda_preview.py` pour rendre réellement
     une frame ILDA (ou une mini animation) vers un `QImage`
     puis `RasterPreview`.

2. **Qualité ILDA (stabilité, plein écran, lignes parasites)**

   - L’image ne remplit pas toujours parfaitement la fenêtre du
     projecteur (compromis via `fill_ratio` et la bounding box).
   - Des traits parasites peuvent apparaître entre deux formes (blanking,
     ordre des points).
   - L’animation est encore un peu plus “tremblante” que certaines
     séquences SVG faites à la main.

   Pistes :

   - exposer dans la GUI des paramètres ILDA :
     - `fill_ratio` (0.0–1.0),
     - `min_rel_size` (filtre d’objets),
     - options de simplification de trajectoire ;
   - revoir l’ordre des points dans certains paths et la gestion des
     points `blanked`.

3. **Performance**

   - Les steps Bitmap et Potrace peuvent devenir **lents** sur de longues
     vidéos (quelques minutes de traitement).  
   - Pistes :
     - mode “rapide” (sous-échantillonnage de frames, réduction
       temporaire de résolution) pour la prévisualisation ;
     - conserver un mode “qualité max” pour le rendu final.

4. **UX / ergonomie**

   - À ajouter / améliorer :
     - menus (File, Help, Settings…) ;
     - boutons pour ouvrir directement les dossiers
       `frames/`, `bmp/`, `svg/`, `ilda/` ;
     - outils de nettoyage d’un projet ;
     - paramètres Potrace avancés (échantillonnage, courbure, etc.) ;
     - paramètres ILDA (voir ci-dessus) ;
     - prévisualisation plus interactive (scrub fluide, etc.).

---

## E. Invariants et règles pour les futures modifications

Pour éviter de retomber dans du “bricolage” et garder le projet cohérent,
les règles suivantes sont considérées comme **inviolables**, sauf décision
consciente de refonte :

1. **Pas de QThread direct dans `MainWindow`**  
   Toute gestion de thread passe par `PipelineController`.

2. **Code métier dans `core/` uniquement**  
   - Aucun import Qt dans `core/`.
   - Communication uniquement via `StepCallbacks` et `StepResult`.

3. **Prévisualisation = responsabilité de la GUI**  
   - Le core signale uniquement :
     - la progression globale,
     - les `FrameProgress` (index, total, `frame_path`).
   - La GUI décide quel widget mettre à jour
     (`RasterPreview`, `SvgPreview`, futur preview ILDA).

4. **Types stables dans le pipeline**

   - `FrameProgress` doit au minimum conserver :
     - `frame_index`,
     - `total_frames`,
     - `frame_path`.
   - `StepResult` doit rester lisible et extensible sans casser la
     compatibilité (ajout de champs OK, changements destructifs à éviter).

5. **Nouveaux steps**

   Pour ajouter une nouvelle étape :

   1. créer `core/pipeline/<step_name>_step.py` avec une fonction
      `run_<step_name>_step(callbacks, ...)` qui respecte le modèle
      `StepCallbacks` / `StepResult` ;
   2. enregistrer cette étape dans `PipelineController` via une méthode
      `start_<step_name>(...)` et les signaux existants ;
   3. n’ajouter dans `MainWindow` que :
      - un bouton / groupe de paramètres,
      - la gestion des signaux `step_started`, `step_progress`,
        `step_finished`, `step_error` pour cette étape.

6. **Gestion des outils externes**

   - Toujours passer par `core.config` pour connaître les chemins
     de FFmpeg, ImageMagick et Potrace.
   - Ne jamais re-hardcoder ces chemins ailleurs dans le code.
   - Encourager l’utilisation des variables d’environnement `LPIP_*`
     ou d’outils installés dans le `PATH`. Des binaires peuvent être
     fournis dans le repo, mais restent configurés via ces mécanismes.

---

## F. Liens

- Dépôt GitHub :  
  <https://github.com/HyperionXXI/laser_pipeline_gui>
