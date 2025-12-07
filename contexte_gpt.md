# Contexte GPT – Projet *Laser Pipeline GUI*

## A. Vue d’ensemble et objectifs

### A.1 But du projet

Le projet **Laser Pipeline GUI** est une application expérimentale écrite en Python qui sert de **banc d’essai** pour transformer une vidéo classique en **animation laser au format ILDA** (`.ild`).

La chaîne complète est découpée en **quatre étapes indépendantes et réutilisables** :

1. **FFmpeg → PNG**  
   Extraction de frames PNG à partir d’un fichier vidéo (MP4, MOV, AVI, …).

2. **ImageMagick → BMP**  
   Prétraitement des PNG en BMP noir/blanc (binarisation, éventuellement thinning)
   pour obtenir un trait fin exploitable par la vectorisation.

3. **Potrace → SVG**  
   Vectorisation des BMP en fichiers SVG (chemins vectoriels).

4. **Export ILDA → .ild**  
   Conversion de la séquence de SVG en un fichier ILDA, destiné à être lu
   par des logiciels de show laser (LaserOS, etc.).

L’objectif est d’avoir un **pipeline modulaire**, réutilisable en ligne de commande
ou via une **interface graphique PySide6**, capable de:

- piloter les outils externes (FFmpeg, ImageMagick, Potrace) de manière robuste ;
- suivre la progression et permettre l’annulation d’une étape longue ;
- afficher des **prévisualisations** des différentes étapes (PNG, BMP, SVG, ILDA).

---

### A.2 Architecture globale

L’architecture est volontairement découpée en deux couches principales :

- **`core/`**  
  Contient la logique « métier » indépendante de l’UI :
  - `config.py` : résolution des chemins vers les exécutables externes  
    (`FFMPEG_PATH`, `POTRACE_PATH`, `MAGICK_PATH`, `PROJECTS_ROOT`), avec priorité :
      1. variables d’environnement `LPIP_*`,
      2. binaire trouvé dans le `PATH`,
      3. chemins par défaut (Windows / Unix).
  - `step_ffmpeg.py`, `step_bitmap.py`, `step_potrace.py`, `step_ilda.py` :
    fonctions de haut niveau pour chaque étape du pipeline.
  - `pipeline/` :
    - `base.py` définit les structures **génériques** de pipeline :
      - `FrameProgress` (avancement d’un step),
      - `StepResult` (résultat global d’un step),
      - callbacks `ProgressCallback` et `CancelCallback`.
    - `ffmpeg_step.py`, `bitmap_step.py`, `potrace_step.py`, `ilda_step.py` :
      wrappers pour exécuter les steps avec gestion du progrès, de l’annulation
      et d’un résultat structuré.
  - `ilda_writer.py` et `ilda_preview.py` :
    - écriture bas niveau du format ILDA ;
    - génération d’images de prévisualisation à partir d’un fichier `.ild`
      (rendu via Pillow).

- **`gui/`**  
  Couche interface graphique PySide6 :
  - `main_window.py` : fenêtre principale, layout en 4 colonnes (FFmpeg, Bitmap,
    Potrace, ILDA) + zone de log et paramètres généraux (vidéo, projet, FPS).
  - `pipeline_controller.py` :
    - encapsule les appels à `run_ffmpeg_step`, `run_bitmap_step`,
      `run_potrace_step`, `run_ilda_step` ;
    - exécute chaque step dans un `QThread` dédié via un worker générique ;
    - expose des signaux Qt :
      - `step_started(step_name: str)`
      - `step_finished(step_name: str, result: StepResult)`
      - `step_error(step_name: str, message: str)`
      - `step_progress(step_name: str, payload: FrameProgress)`
  - `preview_widgets.py` :
    - `RasterPreview` : affiche une image raster (PNG/BMP) centrée, ratio conservé ;
    - `SvgPreview` : affiche un SVG via `QSvgRenderer`, **sans distorsion**
      (calcul d’un rect cible avec le même ratio que le `viewBox`).

Les fichiers `gui_main.py` et `tests/` complètent l’ensemble :
- `gui_main.py` : point d’entrée simple pour lancer la GUI ;
- `tests/test_ilda_*.py` : scripts de test pour valider l’écriture ILDA
  (ex. carré de test).

---

### A.3 Organisation des données de projet

Tous les outputs sont regroupés par **nom de projet** sous `PROJECTS_ROOT`
(par défaut le dossier `projects/` à la racine du repo, surchargeable via
`LPIP_PROJECTS_ROOT`).

Pour un projet nommé `mon_projet`, l’arborescence cible est :

- `projects/mon_projet/frames/` : PNG extraits par FFmpeg  
  (nommage : `frame_0001.png`, `frame_0002.png`, …).
- `projects/mon_projet/bmp/` : BMP générés par ImageMagick.
- `projects/mon_projet/svg/` : SVG vectorisés par Potrace.
- `projects/mon_projet/ilda/` : fichiers `.ild` exportés.

Cette structure est **contractuelle** pour le reste du code
(pipeline, GUI, tests).

---

### A.4 Hypothèses importantes / contraintes

Pour toute future conversation avec GPT au sujet de ce projet, considérer
comme **invariants** (sauf mention contraire explicite dans un commit) :

1. **Découpage en 4 étapes**  
   L’enchaînement FFmpeg → Bitmap → Potrace → ILDA reste la base du pipeline.

2. **Dépendance à des outils externes**  
   Le projet n’embarque pas FFmpeg, ImageMagick ni Potrace :  
   il s’attend à les trouver soit via des variables d’environnement `LPIP_*`,
   soit dans le PATH, soit à des chemins par défaut raisonnables.

3. **Portabilité**  
   - Code Python 3.x, orienté **cross-platform** (Windows / Linux).  
   - Ne jamais introduire de chemin hard-codé spécifique à une machine ;
     toujours passer par `core.config`.

4. **Isolation UI / Core**  
   - Le code de `core/` ne doit pas dépendre de PySide6.  
   - La logique métier ne doit pas utiliser directement des objets Qt
     (signaux, widgets, etc.), uniquement des callbacks Python classiques.

5. **Prévisualisations**  
   - PNG/BMP/SVG doivent rester **facultatifs** pour le pipeline
     (le pipeline peut tourner sans GUI).  
   - La GUI ne doit utiliser que des API publiques : `PipelineController`,
     `RasterPreview`, `SvgPreview`, et les constantes de `config.py`.

---

### A.5 État fonctionnel général (point de départ)

À la date de rédaction de ce contexte :

- Les quatre steps du pipeline fonctionnent de bout en bout sur un cas réel
  (ex. vidéo *La Linea*), avec création d’un fichier ILDA utilisable.
- La GUI permet :
  - de lancer chaque étape séparément ;
  - de suivre la progression via une barre de progression commune ;
  - d’annuler proprement un step en cours ;
  - de prévisualiser :
    - la dernière frame PNG (step 1),
    - la dernière frame BMP (step 2),
    - la dernière frame SVG (step 3),
    - une approximation de la sortie ILDA via un SVG (step 4).
- Des optimisations et améliorations sont encore prévues
  (performances de certaines étapes, meilleure prévisualisation ILDA animée,
  réglages fins du traitement ImageMagick, etc.), mais **l’architecture
  générale décrite ci-dessus doit rester la référence**.

---


Sources du projet
https://github.com/HyperionXXI/laser_pipeline_gui

1. Objectif du projet

Outil GUI Qt (PySide6) pour convertir des vidéos en animations ILDA pour lasers (LaserCube / LaserOS).

Pipeline complet :

FFmpeg – extraction des frames (PNG)

ImageMagick – binarisation / conversion en BMP (avec options)

Potrace – vectorisation (SVG)

Export ILDA – conversion des SVG en frames ILDA

Cas d’usage visés :

Animations filaires / vectorielles (La Linea, anciens jeux d’arcade type Tempest / Star Wars 1983…).

À terme : gérer épaisseur de trait, stabilité, plein écran, couleurs, synchronisation approximative avec le son.

2. Architecture actuelle (commit 9671f6a)
2.1. Couches principales

Core (métier, sans Qt)

core/step_ffmpeg.py

core/step_bitmap.py

core/step_potrace.py

core/step_ilda.py

core/ilda_writer.py

core/ilda_preview.py (esquisse pour futur rendu ILDA → image)

Core – pipeline générique

core/pipeline/__init__.py

core/pipeline/base.py

Modèle abstrait pour les steps et la progression.

core/pipeline/ffmpeg_step.py

core/pipeline/bitmap_step.py

(en cours / à compléter) : core/pipeline/potrace_step.py, core/pipeline/ilda_step.py (ou équivalent)

GUI (Qt / PySide6)

gui/main_window.py

gui/pipeline_controller.py

gui/preview_widgets.py

gui_main.py (point d’entrée, crée l’app, appelle run()).

3. Modèle de pipeline générique
3.1. Base abstraite (core/pipeline/base.py)

À vérifier mais l’esprit est :

StepCallbacks

Fournis par la couche GUI au code métier.

Champs typiques :

log: Callable[[str], None] | None

progress: Callable[[int], None] | None (progression globale 0–100)

frame_progress: Callable[[FrameProgress], None] | None (progression par frame – utilisé pour les previews en direct)

check_cancel: Callable[[], bool] | None (pour permettre l’annulation proprement à terme)

FrameProgress

Représente la progression d’une frame individuelle pendant un step.

Champs typiques (à conserver et réutiliser partout) :

frame_index: int | None

total_frames: int | None

frame_path: str | None

éventuellement step_percent: int | None si besoin.

StepResult

Ce que chaque step retourne à la fin.

Champs typiques :

success: bool

message: str

output_dir: str | None (dossier principal de sortie du step)

éventuellement d’autres infos spécifiques : last_frame_png, last_frame_bmp, etc.

Important :
Les steps de core/pipeline/*.py ne connaissent pas Qt. Ils reçoivent juste un StepCallbacks et appellent ses hooks.

3.2. Steps spécialisés (core/pipeline/*.py)
3.2.1. ffmpeg_step.run_ffmpeg_step(callbacks, video_path, project_name, fps)

Utilise core.step_ffmpeg.extract_frames pour :

créer projects/<project>/frames/frame_XXXX.png.

Appelle :

callbacks.log(...) pour le log texte,

callbacks.progress(p) pour une progression globale,

(à systématiser) callbacks.frame_progress(FrameProgress(...)) pour chaque frame générée, avec frame_path renseigné pour pouvoir afficher en direct.

Retourne un StepResult contenant notamment :

output_dir = "projects/<project>/frames"

éventuellement last_frame_png.

3.2.2. bitmap_step.run_bitmap_step(callbacks, project_name, threshold, use_thinning, max_frames)

Utilise core.step_bitmap.convert_project_frames_to_bmp pour :

lire frames/*.png et produire bmp/*.bmp.

Paramètres :

threshold (%),

use_thinning (bool),

max_frames (int ou None).

Même philosophie de callbacks que FFmpeg :

logs,

progression,

frame_progress avec chemin de la BMP courante.

Retourne un StepResult avec :

output_dir = "projects/<project>/bmp"

éventuellement last_frame_bmp.

3.2.3. potrace_step.run_potrace_step(callbacks, project_name)

Utilise core.step_potrace.bitmap_to_svg_folder(bmp_dir, svg_dir) :

prend les bmp/*.bmp, produit des svg/*.svg.

À structurer comme FFmpeg/Bitmap :

per-frame callbacks pour prévisualisation,

StepResult avec output_dir = svg_dir + last_frame_svg.

3.2.4. step_ilda.export_project_to_ilda(...)

Convertit tous les svg/frame_*.svg en frames ILDA via un parser SVG maison.

Utilise une bounding box globale sur tous les SVG :

garantit un centrage et une taille cohérents d’une frame à l’autre (moins de “respiration”).

Normalise vers l’espace ILDA [-32768 .. +32767], avec :

un fill_ratio (actuellement ~0.95) pour éviter le clipping,

un filtre de suppression des petits paths (anti “poussière”) basé sur min_rel_size.

Gère le blanking :

premier point de chaque sous-chemin en blanked=True,

points suivants en blanked=False.

Sort un .ild dans projects/<project>/ilda/<project>.ild via core.ilda_writer.write_ilda_file.

État actuel :

Le rendu est fonctionnel mais :

l’image n’est pas pleine largeur,

il reste des lignes parasites (traits entre deux formes),

l’animation est encore un peu tremblante comparée à un pack SVG préparé à la main.

4. Couche GUI (Qt / PySide6)
4.1. gui/pipeline_controller.py

Objet central : PipelineController, instancié dans MainWindow.

Rôle :

encapsuler les QThread et ne jamais exposer Qt au code métier ;

offrir une API simple pour le GUI :

start_ffmpeg(video_path, project, fps)

start_bitmap(project, threshold, use_thinning, max_frames)

start_potrace(project)

plus tard : start_ilda(project, options) etc.

Signaux Qt exposés (depuis mémoire + code récent) :

step_started(step_name: str)

step_progress(step_name: str, percent: int | FrameProgress | object)

step_finished(step_name: str, result: StepResult)

step_error(step_name: str, message: str)

Le controller :

crée un QThread,

y installe un worker qui appelle le step métier (run_ffmpeg_step, run_bitmap_step, etc.),

forward les callbacks du step vers les signaux Qt,

détruit proprement le thread après exécution.

Important :
MainWindow ne manipule plus directement QThread, uniquement PipelineController et les signaux.

4.2. gui/main_window.py

Rôle : UI uniquement.

Composants principaux :

Groupe Paramètres généraux :

chemin vidéo,

nom de projet (ex : projet_demo),

FPS,

bouton “Tester les paramètres” (log des valeurs).

Groupe Pipeline vidéo → vecteur :

Contrôles communs (frame index, bouton “Prévisualiser frame”).

Progress bar + bouton “Annuler la tâche en cours” (pour plus tard).

4 colonnes :

FFmpeg → PNG

Bitmap (ImageMagick)

Potrace → SVG

ILDA (export)

Chaque colonne a :

un QGroupBox de paramètres,

un QGroupBox de prévisualisation.

Zone de log en bas (QTextEdit read-only).

Liaison avec PipelineController :

À l’init :

self.pipeline = PipelineController(self)

Connexion des signaux :

pipeline.step_started.connect(self.on_step_started)

pipeline.step_progress.connect(self.on_step_progress)

pipeline.step_finished.connect(self.on_step_finished)

pipeline.step_error.connect(self.on_step_error)

Callbacks GUI :

on_ffmpeg_click → pipeline.start_ffmpeg(...)

on_bmp_click → pipeline.start_bitmap(...)

(à compléter) on_potrace_click, on_export_ilda_click, etc.

Prévisualisation actuelle :

FFmpeg step :

à la fin du step, le GUI récupère output_dir et affiche la dernière frame PNG (frame_XXXX.png) dans la première preview.

Depuis la refacto, on a commencé à exploiter FrameProgress.frame_path pour la prévisualisation par frame, mais ce n’est pas encore finalisé partout.

Bitmap step :

même chose, mais pour la BMP.

Potrace / ILDA :

Potrace : preview SVG dans SvgPreview (à consolider).

ILDA : pas encore de prévisualisation animée dans le GUI. On s’appuie toujours sur LaserOS pour valider le .ild.

4.3. gui/preview_widgets.py

RasterPreview

QWidget pour images raster :

show_image(path: str) charge une QPixmap et la dessine centrée, en conservant le ratio.

Utilisé pour :

PNG (FFmpeg),

BMP (Bitmap),

plus tard : rendu 2D des frames ILDA.

SvgPreview

QWidget pour afficher un fichier SVG (soit via QSvgWidget, soit via rendu QPainter).

Utilisé pour les sorties Potrace.

5. État fonctionnel actuel
5.1. Fonctionnel

Le pipeline complet fonctionne (FFmpeg → BMP → SVG → ILDA) :

Les .ild produits sont lisibles dans LaserOS.

L’animation La Linea est reconnaissable et dans le bon sens.

La nouvelle architecture pipeline est en place :

core/pipeline/base.py + ffmpeg_step.py + bitmap_step.py + gui/pipeline_controller.py

MainWindow ne gère plus les QThread.

5.2. Limitations connues / problèmes ouverts

Prévisualisation “en temps réel”

Demande fonctionnelle : à chaque frame nouvellement produite, afficher cette frame dans la preview, pas uniquement la dernière.

FFmpeg / Bitmap :

Les callbacks frame_progress(frame_path=...) existent côté métier (ou sont en cours d’intégration).

Il reste à :

s’assurer que PipelineController forward bien chaque FrameProgress dans step_progress,

que MainWindow.on_step_progress détecte le type FrameProgress et appelle la bonne Preview (raster ou SVG),

le tout sans geler l’UI (pas de wait() dans le thread GUI, pas de I/O lourde côté GUI).

Prévisualisation ILDA dans le GUI

À faire :

un module (probablement core/ilda_preview.py) qui :

lit un fichier ILDA,

convertit une frame en liste de segments 2D,

fournit une image (QImage / PNG temporaire) pour RasterPreview.

Intégrer ça dans :

un bouton “Prévisualiser ILDA” (frame choisie),

plus tard : une prévisualisation animée dans le GUI.

Qualité ILDA (stabilité / plein écran / lignes parasites)

Problèmes observés :

L’image n’occupe pas toujours toute la fenêtre du projecteur (fill ratio + bounding box).

Des lignes parasites apparaissent parfois entre deux formes (problèmes de blanking ou d’ordre des points).

L’animation reste légèrement tremblante par rapport à des SVG propres importés directement dans LaserOS.

Pistes (à traiter plus tard) :

Exposer des paramètres ILDA dans le GUI :

fill_ratio (0.0–1.0),

min_rel_size (filtre de petits paths),

éventuellement un petit “lissage / décimation de points”.

Vérifier / ajuster :

l’ordre des points dans un path,

les points blanked ajoutés au début/fin de path.

UX / ergonomie à améliorer

Manquent encore :

Menu bar : File, Help, Settings…

Boutons pour :

ouvrir les dossiers frames/, bmp/, svg/, ilda/,

vider un projet (nettoyage).

Contrôles avancés par step :

step Bitmap : threshold, thinning, max_frames (déjà là mais à stabiliser),

step Potrace : paramètres Potrace (échantillonnage, courbure… – pas encore exposés),

step ILDA : fill ratio, filtrage des petits objets, etc.

Comportement de la progress bar :

actuellement surtout utilisée en “indéterminée”,

objectif : utiliser progress et FrameProgress.total_frames pour afficher un pourcentage cohérent et éventuellement un temps restant approximatif.

6. Invariants / règles à respecter pour la suite

Pour éviter de retomber dans le “bricolage” :

Pas de QThread direct dans MainWindow

Toute logique de thread passe par PipelineController.

Code métier dans core/ exclusivement

Les steps métiers ne doivent pas importer Qt.

Ils communiquent uniquement via StepCallbacks.

Prévisualisation = responsabilité du GUI, pas du core

Le core indique seulement “j’ai produit la frame X, chemin Y”.

Seul le GUI sait quel widget mettre à jour (RasterPreview, SvgPreview, futur ILDA Preview).

Types stables dans le pipeline

FrameProgress doit garder une signature stable : frame_index, total_frames, frame_path, etc.

StepResult doit rester lisible et extensible (sans casser le code existant).

Modifications futures

Quand on ajoute un nouveau step :

créer core/pipeline/<step_name>_step.py avec la même signature run_<step_name>_step(callbacks, ...),

l’enregistrer dans PipelineController,

n’ajouter dans MainWindow que :

un bouton / paramètres,

la gestion des signaux step_started, step_progress, step_finished, step_error.