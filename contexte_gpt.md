Voici une version entièrement mise à jour de `contexte_gpt.md`, qui remplace l’ancienne.



---

# Contexte GPT – Projet *Laser Pipeline GUI*

Ce document sert de **mémoire stable** pour les futures conversations avec ChatGPT
autour du projet `laser_pipeline_gui`.
Il décrit l’architecture actuelle, les invariants à respecter et les pistes
d’évolution déjà identifiées.

Ligne directrice demandée par Florian :

> code **générique**, **portable**, **robuste**, **orienté objets** et pensé **intelligemment**.

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
   logiciels de show laser (LaserOS, LaserCube, etc.).

Objectifs principaux :

* disposer d’un **pipeline modulaire** réutilisable en ligne de commande ;
* offrir une **interface graphique PySide6** pour piloter ce pipeline ;
* gérer :

  * la journalisation (logs horodatés),
  * la progression,
  * l’annulation propre d’étapes longues,
  * des **prévisualisations** aux différents stades (PNG, BMP, SVG, ILDA).

Cas d’usage visés :

* animations filaires / vectorielles (ex. *La Linea*) ;
* générique pour d’autres vidéos stylisées (jeux d’arcade, etc.) ;
* à terme : gestion d’épaisseur de trait, stabilité, plein écran, couleurs,
  et éventuellement synchronisation approximative avec le son.

---

## B. Architecture globale

L’architecture est organisée en deux couches principales : **core** (métier) et
**GUI** (Qt).

### B.1 Couche core (`core/`)

Logique métier **indépendante de Qt**.

#### B.1.1 Configuration des outils externes (`config.py`)

`config.py` résout les chemins vers les exécutables externes :

* `FFMPEG_PATH`
* `POTRACE_PATH`
* `MAGICK_PATH`
* `PROJECTS_ROOT`

Priorité de résolution :

1. variables d’environnement (si définies) :

   * `LPIP_FFMPEG`
   * `LPIP_POTRACE`
   * `LPIP_MAGICK`
   * `LPIP_PROJECTS_ROOT`
2. binaire trouvé dans le `PATH` via `shutil.which` ;
3. chemins par défaut raisonnables (Windows / Unix) pour rester compatible
   avec la machine de développement actuelle.

Les outils restent conceptuellement **externes** :
on peut les livrer avec le repo, mais leur utilisation passe toujours
par ces mécanismes (jamais de chemin “magique” en dur ailleurs).

#### B.1.2 Étapes métier unitaires (`step_*.py`)

* `step_ffmpeg.py`
  Extraction des frames PNG à partir de la vidéo source.

* `step_bitmap.py`
  Conversion des PNG en BMP noir/blanc avec paramètres :

  * `threshold` (%),
  * `use_thinning` (bool),
  * `max_frames` (`int` ou `None` pour toutes les frames).

* `step_potrace.py`
  Vectorisation des BMP en SVG via Potrace.
  Post-traitement typique :

  * forcer un `stroke` blanc,
  * `fill="none"`,
  * suppression éventuelle de styles parasites.

* `step_ilda.py`
  Conversion de la séquence de SVG en frames ILDA :

  * lecture des SVG et extraction des chemins (`paths`) ;
  * calcul d’une **bounding box globale** sur l’ensemble des SVG ;
  * normalisation dans l’espace ILDA `[-32768 .. +32767]` avec un
    `fill_ratio` (< 1 pour éviter le clipping) ;
  * possibilité de laisser une petite marge contrôlée par un paramètre
    de type `frame_margin_rel` (actuellement assez conservateur → marge
    visible ; objectif futur : permettre un remplissage plus agressif) ;
  * filtrage des petits chemins (anti “poussière”) via `min_rel_size` ;
  * gestion du **blanking** :

    * premier point de chaque sous-chemin en `blanked=True`,
    * points suivants en `blanked=False`.

  Des heuristiques sont en place (et encore perfectibles) pour tenter de
  supprimer le **cadre extérieur** généré par Potrace lorsque celui-ci
  englobe presque toute l’image.

* `ilda_writer.py`
  Écriture bas niveau des fichiers `.ild` :

  * en-têtes ILDA,
  * frames,
  * points (coordonnées X/Y, couleur, drapeau `blanked`, etc.).

* `ilda_preview.py`
  Outils pour convertir une frame ILDA en segments 2D, puis en image
  (via Pillow). Sert de base pour une future prévisualisation ILDA
  réellement basée sur le fichier `.ild` (et pas seulement sur les SVG).

#### B.1.3 Pipeline générique (`core/pipeline/`)

* `base.py`
  Définit les types génériques utilisés par toutes les étapes :

  * `FrameProgress`
    Représente l’avancement d’une frame individuelle pendant un step.

    Champs stables à conserver :

    * `frame_index: int | None`
    * `total_frames: int | None`
    * `frame_path: Path | None` (chemin vers le fichier généré, utilisé
      pour les prévisualisations)
    * éventuellement `step_percent: int | None`.

  * `StepResult`
    Résultat global d’un step.

    Champs stables :

    * `success: bool`
    * `message: str`
    * `output_dir: Path | None`
    * d’autres champs spécifiques peuvent être ajoutés sans casser l’API
      (par ex. `last_frame_path`).

  * `StepCallbacks`
    Ensemble de callbacks fournis par la couche supérieure (GUI ou CLI) :

    * `log: Callable[[str], None] | None`
    * `progress: Callable[[int], None] | None` (0–100 global)
    * `frame_progress: Callable[[FrameProgress], None] | None`
    * `check_cancel: Callable[[], bool] | None`
      (permet l’annulation propre au sein des boucles).

  👉 **Important :**
  Le code de `core/pipeline/*.py` ne dépend pas de Qt.
  Il ne voit que ces callbacks Python.

* `ffmpeg_step.py`, `bitmap_step.py`, `potrace_step.py`, `ilda_step.py`
  Wrappers de haut niveau qui :

  * appellent les fonctions de `step_*.py` correspondantes ;
  * traduisent leur progression en `FrameProgress` ;
  * gèrent l’annulation via `check_cancel` ;
  * retournent un `StepResult` cohérent.

---

### B.2 Couche GUI (`gui/`)

Interface utilisateur basée sur PySide6.

#### B.2.1 Fenêtre principale (`main_window.py`)

Structure en trois zones :

1. **Paramètres généraux**

   * chemin vidéo (ligne d’édition + bouton “Parcourir…”),
   * nom du projet (ex. `projet_demo`),
   * FPS (spin box),
   * bouton **“Tester les paramètres”** qui logue les valeurs courantes.

2. **Pipeline vidéo → vecteur**

   * contrôle commun “Frame” (`QSpinBox`) + bouton “Prévisualiser frame”
     qui affiche la frame demandée dans les quatre previews (si elle existe) ;

   * barre de progression globale + bouton “Annuler la tâche en cours” ;

   * quatre colonnes, chacune avec :

     1. **FFmpeg → PNG (frames)**

        * bouton « Lancer FFmpeg » ;
        * prévisualisation PNG (`RasterPreview`).

     2. **Bitmap (ImageMagick)**

        * paramètres :

          * seuil (%),
          * *thinning* (bool),
          * max frames (0 = toutes) ;
        * bouton « Lancer Bitmap » ;
        * prévisualisation BMP (`RasterPreview`).

     3. **Vectorisation (Potrace)**

        * bouton « Lancer Potrace » ;
        * prévisualisation SVG (`SvgPreview`), sans distorsion.

     4. **ILDA (export)**

        * bouton « Exporter ILDA » ;
        * prévisualisation ILDA actuellement basée sur un SVG
          (approximation visuelle de la première frame).

   * La **progress bar** :

     * passe en mode indéterminé quand `total_frames` est inconnu ;
     * sinon, quand `FrameProgress.total_frames` est renseigné,
       affiche un pourcentage calculé à partir de `frame_index`.

3. **Zone de log**

   * `QTextEdit` en lecture seule ;
   * chaque message est préfixé par un **timestamp** `[HH:MM:SS]` ;
   * auto-scroll vers la dernière ligne à chaque ajout ;
   * utilisé par la GUI et par les steps (via les callbacks `log`).

#### B.2.2 Contrôleur de pipeline (`pipeline_controller.py`)

Objet central qui encapsule les threads et fait le pont Qt ↔ core.

* crée un `QThread` par step ;

* y place un worker qui appelle `run_ffmpeg_step`, `run_bitmap_step`,
  `run_potrace_step` ou `run_ilda_step` ;

* relaye les callbacks core → signaux Qt :

  * `step_started(step_name: str)`
  * `step_finished(step_name: str, result: StepResult)`
  * `step_error(step_name: str, message: str)`
  * `step_progress(step_name: str, payload: FrameProgress)`

* détruit proprement le thread après exécution ou annulation.

API publique exposée à `MainWindow` :

* `start_ffmpeg(video_path, project, fps)`
* `start_bitmap(project, threshold, use_thinning, max_frames)`
* `start_potrace(project)`
* `start_ilda(project)`
* `cancel_current_step()`.

👉 **Invariant :** `MainWindow` ne manipule jamais directement des `QThread`,
seulement `PipelineController` et ses signaux.

#### B.2.3 Widgets de prévisualisation (`preview_widgets.py`)

* `RasterPreview`

  * widget Qt pour images raster (PNG/BMP…) ;
  * fond noir ;
  * `show_image(path)` :

    * charge la QPixmap ;
    * l’affiche **centrée** en conservant le ratio
      (`Qt.KeepAspectRatio`, pas de stretch) ;
    * gère correctement les redimensionnements de la fenêtre.

* `SvgPreview`

  * widget Qt pour fichiers SVG (via `QSvgRenderer`) ;
  * fond noir ;
  * lors du `paintEvent` :

    * lit le `viewBox` du SVG ;
    * calcule un `target_rect` centré dans le widget
      avec le **même ratio** que le `viewBox` ;
    * rend le SVG dans ce rectangle → plus de déformation en plein écran.

* La preview ILDA utilise actuellement un `SvgPreview` alimenté avec un SVG
  représentatif (approximation). Une future version utilisera un rendu réel
  via `ilda_preview.py`.

#### B.2.4 Point d’entrée GUI (`gui_main.py`)

Fichier minimal qui :

* crée l’application Qt,
* instancie `MainWindow`,
* lance la boucle d’événements.

---

## C. Organisation des données de projet

Tous les outputs sont regroupés par **nom de projet** sous `PROJECTS_ROOT`
(par défaut `projects/` à la racine du repo ; surcharge possible via
`LPIP_PROJECTS_ROOT`).

Pour un projet `mon_projet` :

* `projects/mon_projet/frames/`
  PNG extraits par FFmpeg
  (`frame_0001.png`, `frame_0002.png`, …).

* `projects/mon_projet/bmp/`
  BMP générés par ImageMagick.

* `projects/mon_projet/svg/`
  SVG vectorisés par Potrace.

* `projects/mon_projet/ilda/`
  fichiers `.ild` exportés.

Cette arborescence est **contractuelle** pour le pipeline, la GUI
et les éventuels tests.

---

## D. État fonctionnel actuel

### D.1 Fonctionnel

À la dernière mise à jour de ce document :

* Le pipeline complet **FFmpeg → BMP → SVG → ILDA** fonctionne sur des cas
  réels (ex. vidéo *La Linea*) et produit des `.ild` que LaserOS accepte
  et lit comme **animations** (plus seulement une frame statique).

* L’interface graphique permet :

  * de lancer chaque étape séparément ;
  * de suivre la progression via une barre de progression commune ;
  * d’annuler proprement un step en cours ;
  * de prévisualiser :

    * la dernière frame PNG (step 1),
    * la dernière frame BMP (step 2),
    * la dernière frame SVG (step 3),
    * une approximation de la sortie ILDA via les SVG (step 4).

* `MainWindow` ne gère plus directement les threads ; tout passe par
  `PipelineController` (respect de l’architecture prévue).

### D.2 Limitations connues et comportement ILDA observé

En important le `.ild` dans LaserOS (cas de *La Linea*), on observe :

1. **Animation correcte mais image trop petite**

   * L’animation centrale (le personnage/la ligne) est bien **animée**,
     frame après frame.
   * Toutefois, l’image n’occupe pas toute la surface
     de projection disponible dans LaserOS :

     * taille réduite,
     * marge visible tout autour.

   → Le `fill_ratio` et/ou la marge (`frame_margin_rel`) sont encore
   **trop conservateurs**. Objectif : proposer un réglage permettant de
   rapprocher la trajectoire des bords sans clipping, idéalement jusqu’à
   exploiter au maximum le carré ILDA.

2. **Cadre rectangulaire parasite**

   * Un **cadre** rectangulaire (provenant du contour du “tableau” dans la
     vidéo) est souvent présent autour de la scène.
   * Ce cadre est visiblement animé (léger tremblement),
     ce qui confirme qu’il provient des frames elles-mêmes et pas d’un bug
     de scaling.
   * Des heuristiques existent pour supprimer un path correspondant à la
     bounding box globale, mais elles ne suffisent pas toujours :
     le cadre reste parfois présent.

   → Travail futur : améliorer la détection/suppression des paths
   correspondant à ce cadre (par ex. heuristique de taille + position +
   nombre de segments).

3. **Lignes parasites / shoots vers le bord gauche**

   * Des segments parasites partent parfois d’un point
     situé près du bord gauche de l’écran et rejoignent d’autres éléments.
   * Hypothèses :

     * transitions **blanked → non-blanked** imparfaites,
     * réutilisation d’un point précédent comme origine d’un nouveau path,
     * mauvaise insertion d’un point de “saut” blanked entre deux chemins.

   → Travail futur :

   * vérifier que **chaque path** commence par un point blanked placé
     exactement au premier point “visible” du path ;
   * ajouter explicitement des points blanked entre deux paths séparés ;
   * éventuellement forcer un retour à un point neutre (0,0) blanked
     en fin de frame si nécessaire.

4. **Marges et centrage ILDA**

   * Malgré la normalisation globale, le contenu reste légèrement centré
     “en bas” ou “en haut” selon les scènes.
   * Objectif : s’assurer que la bounding box globale est calculée
     correctement, et que le centrage X/Y se fait bien sur cette box,
     pas sur les coordonnées ILDA déjà normalisées.

5. **Performance**

   * Sur la vidéo *La Linea*, les étapes Bitmap et Potrace peuvent prendre
     plusieurs minutes pour parcourir toutes les frames.
   * C’est acceptable pour un “rendu final”, mais pas idéal pour les tests.

   → Pistes ultérieures :

   * mode “draft” avec sous-échantillonnage de frames ;
   * réduction de résolution avant vectorisation pour les prétests.

---

## E. Invariants et règles pour les futures modifications

Pour garder le projet cohérent, les règles suivantes sont considérées comme
**inviolables**, sauf refonte volontaire et documentée :

1. **Pas de QThread direct dans `MainWindow`**

   * Toute gestion de thread passe par `PipelineController`.

2. **Code métier dans `core/` uniquement**

   * Aucun import Qt dans `core/`.
   * Communication uniquement via `StepCallbacks` et `StepResult`.

3. **Prévisualisation = responsabilité de la GUI**

   * Le core signale :

     * la progression globale (0–100),
     * les `FrameProgress` (index, total, `frame_path`).
   * La GUI décide quel widget mettre à jour (`RasterPreview`, `SvgPreview`,
     futur preview ILDA).

4. **Types stables dans le pipeline**

   * `FrameProgress` doit au minimum conserver :

     * `frame_index`,
     * `total_frames`,
     * `frame_path`.
   * `StepResult` doit rester extensible sans casser la compatibilité
     (ajout de champs OK ; changements destructifs à éviter).

5. **Nouveaux steps**

   Pour ajouter une nouvelle étape :

   1. créer `core/pipeline/<step_name>_step.py` avec une fonction
      `run_<step_name>_step(callbacks, ...)` respectant le modèle
      `StepCallbacks` / `StepResult` ;
   2. enregistrer cette étape dans `PipelineController` via une méthode
      `start_<step_name>(...)` et les signaux existants ;
   3. n’ajouter dans `MainWindow` que :

      * un bouton / groupe de paramètres,
      * la gestion des signaux `step_started`, `step_progress`,
        `step_finished`, `step_error` pour cette étape.

6. **Gestion des outils externes**

   * Toujours passer par `core.config` pour connaître les chemins de
     FFmpeg, ImageMagick et Potrace.
   * Ne jamais re-hardcoder ces chemins ailleurs dans le code.
   * Encourager l’utilisation des variables d’environnement `LPIP_*`
     ou d’outils installés dans le `PATH`.
     Des binaires peuvent être fournis dans le repo, mais restent
     configurés via ces mécanismes.

7. **Style général du code**

   * viser un style : générique, portable, robuste, orienté objets,
     avec une attention particulière à :

     * la lisibilité,
     * la séparation des responsabilités,
     * la testabilité (steps réutilisables en CLI ou tests unitaires).

---

## F. Liens

* Dépôt GitHub :
  [https://github.com/HyperionXXI/laser_pipeline_gui](https://github.com/HyperionXXI/laser_pipeline_gui)
