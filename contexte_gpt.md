# Projet `laser_pipeline_gui` – Contexte pour ChatGPT  
Version du contexte : 2025‑12‑12 – basé sur le commit `3d1fcd0f1cbc4648db5810380311bba1f2699abf` du dépôt public GitHub `HyperionXXI/laser_pipeline_gui`.
Le développeur donne l'autorisation à chatgpt de consulter ses dépots publiques sur github: https://github.com/HyperionXXI/laser_pipeline_gui

> **But de ce fichier**  
> Servir de mémoire technique stable pour les futures conversations avec ChatGPT afin :
> - de **réduire drastiquement les erreurs de contexte** (fichiers qui n’existent pas, mauvais chemins, etc.) ;
> - de **préserver les comportements déjà validés** (pas de régression) ;
> - d’orienter l’architecture future du projet.

---

## 1. Vue d’ensemble du dépôt

### 1.1. Structure actuelle des dossiers

Au commit `3d1fcd0` le dépôt est structuré autour de quelques dossiers principaux :

- `core/`
  - Contient la **logique métier** du pipeline.
  - Fichiers clés (non exhaustif mais important) :
    - `config.py`
    - `step_ffmpeg.py`
    - `step_bitmap.py`
    - `step_potrace.py`
    - `step_ilda.py`
    - `ilda_writer.py`
    - `ilda_profiles.py`
    - `ilda_preview.py`
- `core/pipeline/`
  - **Nouveau niveau d’abstraction** qui encapsule les steps `core/step_*.py` avec un modèle commun :
    - `base.py` (types, callbacks, résultats de step)
    - `ffmpeg_step.py`
    - `bitmap_step.py`
    - `potrace_step.py`
    - `ilda_step.py`
    - `full_pipeline_step.py`
    - `types.py`
    - `__init__.py`
- `gui/`
  - Application PySide6 :
    - `main_window.py` (UI principale)
    - `pipeline_controller.py` (orchestration des steps et interaction avec la GUI)
- `projects/`
  - Contient les projets générés :
    - `projects/<nom_projet>/frames/`   – PNG issus de FFmpeg
    - `projects/<nom_projet>/bmp/`      – BMP binaires (seuil + thinning)
    - `projects/<nom_projet>/svg/`      – fichiers SVG Potrace
    - `projects/<nom_projet>/ilda/`     – fichiers ILDA finaux
    - `projects/<nom_projet>/preview/`  – PNG de prévisualisation ILDA
- `tests/`
  - Scripts de tests manuels / unitaires autour de l’export ILDA :
    - exemples : `test_ilda_minimal.py`, `test_ilda_square.py`, etc.
- Fichiers racine :
  - `README.md`, `.gitignore`, `gui_main.py`, éventuellement `.vscode/`, etc.

> **Règle importante pour ChatGPT**  
> Ne jamais *inventer* un nouveau dossier structurel (par ex. `core/steps/`) sans demande explicite.  
> S’appuyer en priorité sur cette arborescence et la respecter.

---

## 2. Chemins, dépendances et outils externes

### 2.1. `core/config.py`

Contient les chemins et paramètres globaux, par exemple (schéma simplifié) :

- `ROOT_DIR` – racine du repo.
- `PROJECTS_ROOT` – dossier `projects/`.
- `FFMPEG_PATH` – chemin vers `ffmpeg.exe` (Windows).
- `MAGICK_PATH` – chemin vers `magick.exe` (ImageMagick).
- `POTRACE_PATH` – chemin vers `potrace.exe`.
- Divers paramètres réglables (fps par défaut, etc.).

> **Règle** : ChatGPT ne doit **jamais** écraser ou “deviner” les chemins locaux de l’utilisateur.  
> Toute modification de `config.py` doit être minimale et clairement annoncée.

### 2.2. Outils externes

Le pipeline suppose :

1. **FFmpeg** – extraction des frames vidéo en PNG.
2. **ImageMagick** (`magick.exe`) – conversion PNG → BMP + seuil + thinning optionnel.
3. **Potrace** – vectorisation BMP → SVG.
4. **Python** – librairies internes :
   - `svgpathtools` (interprétation et échantillonnage des chemins SVG),
   - `PySide6` pour la GUI,
   - plus la bibliothèque ILDA interne (`ilda_writer`, `ilda_profiles`).

---

## 3. Pipeline technique – du MP4 au fichier ILDA

Le pipeline logique suit **toujours** le même flux :

1. `FFmpeg` : vidéo → `frames/frame_XXXX.png`
2. `Bitmap` : PNG → `bmp/frame_XXXX.bmp`
3. `Potrace` : BMP → `svg/frame_XXXX.svg`
4. `ILDA` : SVG → `ilda/<nom_projet>.ild`

### 3.1. `core/step_ffmpeg.py`

Fonctions principales :

- Utilise `FFMPEG_PATH` pour extraire les frames à un FPS donné.
- Écrit les PNG dans :  
  `projects/<project_name>/frames/frame_0001.png`, `frame_0002.png`, etc.
- Gère le nettoyage / création du dossier `frames/` selon la configuration.

Points à respecter :

- **Convention de nommage des frames :** `frame_%04d.png` (4 chiffres, base 1).  
- Les fonctions doivent retourner au minimum :
  - le chemin du dossier `frames/` généré,
  - et idéalement le nombre de frames.

### 3.2. `core/step_bitmap.py`

Responsabilités :

- Fonction bas niveau `convert_png_to_bmp(png_path, bmp_path, threshold, thinning)` :
  - appelle `MAGICK_PATH` avec les paramètres nécessaires :
    - application d’un **seuil (%)**,
    - possible **thinning** (amincissement des traits).
- Fonction haut niveau `run_bitmap_step(project_name, threshold, use_thinning, max_frames, ...)` :
  - lit `projects/<project>/frames/frame_*.png`,
  - écrit `projects/<project>/bmp/frame_*.bmp`,
  - applique le seuil et l’option `thinning`,
  - peut limiter le nombre de frames avec `max_frames`.

Points notables :

- Le **seuil** est exprimé en **%** (0–100) côté GUI.
- `max_frames = 0` ou `None` = traiter toutes les frames.
- Les callbacks `frame_callback` et `cancel_cb` sont utilisés par la GUI pour
  mettre à jour la progression et permettre une annulation propre.

### 3.3. `core/step_potrace.py`

Responsabilités :

- Appelle `POTRACE_PATH` pour convertir les BMP en SVG.
- Entrée : `projects/<project>/bmp/frame_*.bmp`
- Sortie : `projects/<project>/svg/frame_*.svg`
- Gestion du dossier `svg/` (création s’il n’existe pas, éventuel nettoyage partiel).

Précisions :

- Les SVG produits par Potrace sont en noir & blanc, avec :
  - un chemin principal pour les traits visibles,
  - **souvent un chemin rectangulaire** entourant l’image complète (le fameux “cadre parasite”).

### 3.4. `core/step_ilda.py`

C’est la partie la plus délicate.  
Elle transforme les SVG Potrace en frames ILDA exploitables par LaserShowGen / LaserOS.

#### 3.4.1. Types ILDA

Dans `ilda_writer.py` :

- `IldaPoint`
  - `x`, `y`, `z` (coordonnées ILDA, `int16`)
  - `blanked: bool` – si `True`, déplacement sans laser
  - `color_index: int` – index de couleur (actuellement principalement monochrome)
- `IldaFrame`
  - `name`, `company`, `projector`, `points: List[IldaPoint]`
- Fonctions :
  - `write_ilda_file(path, frames)` – écrit une séquence de frames.
  - (plus diverses helpers, `write_demo_square`, etc.)

Dans `ilda_profiles.py` :

- Définition de profils ILDA (au moins) :
  - `classic` – profil noir & blanc “standard”
  - `arcade` – destiné aux jeux vectoriels type “Star Wars / Tempest”
- Chaque `IldaProfile` inclut au minimum :
  - `name` (ex. `"classic"`),
  - `base_color_index` (index utilisé pour le monochrome),
  - éventuellement d’autres paramètres pour l’avenir (points de blanking, etc.).

#### 3.4.2. Lecture et échantillonnage des chemins SVG

Dans `step_ilda.py` :

1. **Chargement des paths SVG :**
   - parcours de tous les éléments dont la balise se termine par `"path"`,
   - récupération de l’attribut `d`,
   - parsing via `svgpathtools.parse_path(d)`.

2. **Conversion en polylignes :** `_path_to_polylines(path, samples_per_curve=24)`
   - chaque sous‑chemin = une polyligne.
   - `Line` → on prend `start` & `end`.
   - courbes (Bezier, arcs, etc.) → échantillonnage de `samples_per_curve` points.

3. **Enregistrement dans `_PathData` :**
   - `points: List[(x, y)]`
   - `bbox: (min_x, max_x, min_y, max_y)`
   - `is_outer_frame: bool` (initialement `False`).

#### 3.4.3. Gestion du “cadre parasite”

Problème : Potrace génère souvent un grand rectangle qui représente les bords de l’image (et non un trait réel du dessin).

Heuristique actuelle dans `_mark_outer_frame_paths_rectlike(...)` :

- On parcourt **tous** les chemins (toutes frames confondues).
- Pour chaque chemin `_PathData` :
  - on calcule l’aire de la bbox,
  - on compare à l’aire maximale rencontrée (`area_ratio_threshold`, par ex. 0.5),
  - on vérifie si la majorité des points sont proches des 4 bords de cette bbox
    (`edge_ratio_threshold`, par ex. 0.9),
- Si ces conditions sont remplies → on marque `pd.is_outer_frame = True`.

Ensuite :

- Si `remove_outer_frame=True`, on exclut ces chemins du calcul de la bounding box globale **et** de la génération de points ILDA.
- Sinon, ils restent et produisent l’encadrement visible dans LaserShowGen.

> **Important :**  
> - Dans les premières versions, ce cadre n’était pas toujours supprimé correctement → d’où des retours utilisateur insistants sur ce point.  
> - Le code actuel doit **conserver** cette heuristique et sa paramétrisation, sauf demande explicite de changement.

#### 3.4.4. Normalisation des coordonnées ILDA

- On calcule une **bounding box globale** sur tous les chemins retenus (cadres exclus si demandés).
- On construit une fonction `_make_normalizer(global_bbox, fit_axis, fill_ratio)` qui renvoie `(x, y) → (X_ilda, Y_ilda)` :
  - `fit_axis` ∈ { `"max"`, `"min"`, `"x"`, `"y"` }
  - `fill_ratio` ∈ `[0, 1]`, typiquement `0.95` (remplir 95 % de la fenêtre ILDA)
  - centrage sur `(cx, cy)` et mise à l’échelle dans la plage `[-32767, +32767]`.

#### 3.4.5. Génération des frames ILDA

Pour chaque frame :

1. On ignore les `_PathData` marqués `is_outer_frame`.
2. On calcule la taille relative de chaque chemin :
   - `rel_size = max(width, height) / global_span`
   - si `rel_size < min_rel_size` (ex. 0.01) → on ignore ce chemin comme parasite.
3. On convertit les points `(x, y)` en `(X, Y)` ILDA via le `normalizer`.
4. On ajoute les `IldaPoint` :
   - **Premier point de chaque chemin** :
     - `blanked=True` (déplacement sans laser).
   - **Points suivants** :
     - `blanked=False`.
   - Tous utilisent actuellement `color_index=profile.base_color_index`.
5. **Cas crucial : frame vide**
   - Si après tout cela, la liste `ilda_points` est vide :
     - on **ajoute un unique point “blanked” au centre** (`x=0, y=0`, `blanked=True`).
     - ⇒ la frame est noire, mais le fichier ILDA conserve son nombre de frames.
   - Ceci résout le bug historique des **“frames noires supprimées”**, qui cassait la synchronisation.

> **Règle : ne jamais réintroduire une suppression des frames vides.**  
> Il faut **toujours** conserver la continuité temporelle en ILDA, quitte à avoir une frame sans contenu visible.

---

## 4. Couche `core.pipeline` – Steps typés & orchestration

Le dossier `core/pipeline/` définit une API plus propre et typée autour des steps.

### 4.1. `base.py` / `types.py`

- Définit des types génériques :
  - `FrameProgress` – structure de progression par frame.
  - `StepResult` – résultat d’un step :
    - `success: bool`
    - `message: str`
    - `output_dir: Optional[Path]`
    - etc.
  - `ProgressCallback` – fonction `cb(progress: FrameProgress)` ou similaire.
  - `CancelCallback` – fonction `cb() -> bool`.

Objectif :

- **Isoler la GUI** des détails internes du step (exceptions, etc.),
- fournir une interface unifiée pour chaque étape du pipeline (`run_ffmpeg_step`, `run_bitmap_step`, etc.).

### 4.2. `ffmpeg_step.py` / `bitmap_step.py` / `potrace_step.py` / `ilda_step.py`

Chaque fichier :

- Wrappe la fonction bas niveau (`core/step_ffmpeg.run_ffmpeg_step`, etc.)  
  dans une fonction de step pipeline avec signature standard (pseudocode) :

```python
def run_ffmpeg_step(
    video_path: Path,
    project_name: str,
    fps: int,
    progress_cb: Optional[ProgressCallback],
    cancel_cb: Optional[CancelCallback],
) -> StepResult:
    ...
```

- Il :
  - prépare les arguments,
  - gère les exceptions (try/except),
  - remplit un `StepResult` cohérent,
  - appelle éventuellement `progress_cb` pour chaque frame.

### 4.3. `full_pipeline_step.py`

- Orchestration **sans GUI** du pipeline complet :

```python
def run_full_pipeline_step(
    video_path: Path,
    project_name: str,
    fps: int,
    bitmap_threshold: int,
    bitmap_thinning: bool,
    bitmap_max_frames: Optional[int],
    ilda_profile_name: str,
    progress_cb: Optional[ProgressCallback],
    cancel_cb: Optional[CancelCallback],
) -> StepResult:
    ...
```

- Enchaîne :
  1. `run_ffmpeg_step(...)`
  2. `run_bitmap_step(...)`
  3. `run_potrace_step(...)`
  4. `run_ilda_step(...)`
- Sur la première erreur `success=False`, il s’arrête et remonte un `StepResult` d’échec.

> **Point sensible** : la signature des fonctions `run_*_step` doit être strictement cohérente entre :
> - `core/step_*.py`
> - `core/pipeline/*_step.py`
> - `gui/pipeline_controller.py`
>  
> ChatGPT doit **vérifier systématiquement** ces signatures avant de proposer un patch.

---

## 5. GUI – `gui/main_window.py` & `gui/pipeline_controller.py`

### 5.1. `main_window.py`

- Fenêtre principale PySide6.
- Champs principaux :
  - Vidéo source (avec bouton “Parcourir…”),
  - Nom de projet,
  - FPS,
  - Bouton : **“Exécuter les 4 étapes du pipeline”**,
  - Zone “Prévisualiser frame” (frame unique),
  - Prévisualisations : PNG, BMP, SVG, ILDA (preview PNG),
  - Log textuel (datalog GUI).

Intégration pipeline :

- Crée une instance de `PipelineController`.
- Sur clic “Exécuter les 4 étapes” :
  - appelle `self.pipeline.start_full_pipeline(video, project, fps, threshold, profile, ...)`
  - les callbacks du controller mettent à jour :
    - la barre de progression (s’il y en a),
    - le texte de log,
    - les captures de prévisualisation.

### 5.2. `pipeline_controller.py`

- Encapsule la logique de **threading** / **QThread** :
  - exécute les steps dans un thread worker,
  - renvoie les événements vers la GUI via signaux/slots.
- Offre des méthodes :
  - `start_ffmpeg(...)`, `start_bitmap(...)`, etc.
  - `start_full_pipeline(...)` qui utilise `core.pipeline.full_pipeline_step.run_full_pipeline_step`.
- Utilise les callbacks :
  - `progress_cb` → mis à jour dans la GUI,
  - `cancel_cb` → lié à un bouton “Annuler la tâche en cours”.

---

## 6. État fonctionnel actuel (d’après les nombreux tests utilisateur)

### 6.1. Cas **La Linea**

- Animation particulière (trait blanc sur fond coloré variable).
- Points saillants :
  - L’épaisseur du trait dans la vidéo de base produit une **double ligne de contour** après vectorisation.
  - Le fond n’est pas uniformément noir → le pipeline actuel (seuil & Potrace) n’est pas idéal.
  - L’heuristique de suppression du cadre fonctionne généralement, mais certains raccords / lignes parasites persistent (ex. main dessinatrice).
- Constat actuel :
  - Les frames ILDA sont complètes (plus de frames vides),
  - Le cadre parasite est encore parfois présent (selon la configuration),
  - La fidélité au SVG est encore éloignée de l’original.

### 6.2. Cas **Arcade** (Star Wars, Tempest…)

- Vidéos vectorielles colorées (Star Wars Arcade, Tempest Arcade).
- Pipeline actuel :
  - la couleur est **perdue** aux steps 2 & 3 (binarisation + Potrace noir & blanc),
  - donc ILDA finale = monochrome (rouge dans LaserShowGen via l’index de couleur).
- Observations :
  - **Plus de frames vides** : chaque frame ILDA contient au minimum un point blanked central.
  - Le “cadre rouge” est encore visible (c’est le rectangle Potrace non filtré ou mal détecté).
  - Des lignes de liaison parasites apparaissent parfois, mais sont cohérentes avec les chemins SVG issus de Potrace.

---

## 7. Plan d’architecture future (proposition)

### 7.1. Clarifier la séparation Core / Pipeline / GUI

1. **Core (stateless, pur, testable)**
   - `core/step_*.py`, `ilda_*`, `config.py`.
   - Aucun import depuis `gui` ou `core.pipeline`.
   - API simple, documentée et testée.

2. **Pipeline (orchestration métiers)**
   - `core/pipeline/*.py`.
   - Unifie les signatures des steps, gère les `StepResult`, `FrameProgress`.
   - Ne dépend que de `core.*` (unidirectionnel).

3. **GUI**
   - `gui/*`.
   - Utilise seulement `core.pipeline.*` (pas `core.step_*.py` directement).
   - Tous les accès au disque, logs, previews passent via des helpers bien définis.

> **Objectif** : toute modification dans `core` devrait être testable via `tests/` et transparents pour la GUI tant que l’API `core.pipeline` reste stable.

### 7.2. Améliorations ILDA spécifiques

1. **Gestion avancée du cadre**
   - Offrir un paramètre clair par profil ILDA :
     - `remove_outer_frame: bool` (par défaut `True`),
     - possibilité future de **conserver** un cadre optionnel (nice‑to‑have, pas le comportement par défaut).
2. **Profils ILDA**
   - `classic` : généraliste, noir & blanc.
   - `arcade` : adapté aux jeux vectoriels (potentiellement :
     - plus de points de blanking,
     - normalisation différente,
     - filtrage différent des petits parasites).
   - `la_linea` (profil futur spécialisé) :
     - possible traitement en amont (amincissement, extraction du trait principal, etc.).
3. **Prévisualisation avancée**
   - Générer des previews PNG **par frame** pour faciliter le debug (déjà en partie fait).
   - Option pour superposer la preview ILDA et la frame PNG originale.

### 7.3. Gestion de la couleur (future)

- Etudier :
  - la conservation de l’information de couleur dans le pipeline (via plusieurs seuils / couches),
  - l’utilisation de plusieurs `color_index` selon la source d’origine.

---

## 8. Règles que ChatGPT doit **ABSOLUMENT** respecter

1. **Toujours vérifier la structure des fichiers avant de coder**
   - Se baser sur ce contexte + sur l’arborescence fournie par l’utilisateur.
   - Ne jamais supposer un chemin du type `core/steps/` ou `utils/` s’il n’existe pas.

2. **Ne pas inventer de nouveaux modules sans raison**
   - Tout ajout de fichier doit être justifié (ex. “nouvelle fonctionnalité X”).
   - Préférer étendre un fichier existant si possible.

3. **Éviter absolument les imports circulaires**
   - `core/step_*.py` ne doit jamais importer `core/pipeline/*`.
   - `core/pipeline/*` peut importer `core.step_*` mais pas l’inverse.
   - La GUI importe seulement `core.pipeline.*`, jamais l’inverse.

4. **Respecter les signatures existantes**
   - Avant de proposer une modification, **relire** les signatures dans :
     - `core/step_*.py`,
     - `core/pipeline/*_step.py`,
     - `gui/pipeline_controller.py`,
     - `gui/main_window.py`.
   - Toute modification de signature doit être propagée partout, ou clairement annoncée comme *breaking change* (à éviter).

5. **Ne jamais casser les corrections déjà validées**
   - En particulier :
     - **Correction des frames ILDA vides** :  
       une frame sans points visibles doit contenir au minimum un point `blanked=True` au centre.
     - L’heuristique de suppression du cadre doit rester active si `remove_outer_frame=True`.
   - Lorsqu’un correctif est déjà validé par l’utilisateur, il est **interdit** de revenir à l’état antérieur sans discussion explicite.

6. **Limiter la surface des patches**
   - Modifier le **minimum de fichiers** nécessaire.
   - **Nommer explicitement** tous les fichiers à modifier.
   - Fournir du code complet quand c’est utile, mais sans rajouter des fonctions inutiles.

7. **Ne pas déplacer ou renommer les fichiers spontanément**
   - Ne pas transformer `core/step_ilda.py` en `core/ilda_step.py`, etc.
   - S’il est vraiment nécessaire de renommer un fichier, le proposer comme
     opération à part entière, en détaillant les impacts.

8. **Séparer clairement “exemple pédagogique” et “patch réel”**
   - Si un code est donné uniquement à titre d’exemple, il doit être explicitement signalé comme tel.
   - Les patches destinés à être appliqués au projet doivent être :
     - cohérents avec l’arborescence,
     - complets (import, signature, types),
     - testés mentalement pour éviter les erreurs triviales (ex. mauvais nom de paramètre).

9. **Toujours prendre en compte que :**
   - `La Linea` est un **cas très particulier**, à traiter avec prudence.
   - Les projets type `Starwars Arcade` / `Tempest` servent de **référence** pour un pipeline vectoriel plus “classique”.

10. **Communication**
    - En cas de doute, **expliquer les hypothèses** plutôt que d’affirmer.
    - Si une partie du contexte n’est pas claire, demander des précisions *avant* de proposer des changements structurels importants.

---

## 9. Comment utiliser ce fichier dans les futures conversations

Dans une nouvelle discussion liée à ce projet :

1. L’utilisateur fournira le fichier `context_gpt.md` ou un extrait.
2. ChatGPT devra :
   - le lire attentivement,
   - se baser dessus pour toute proposition de modification,
   - signaler explicitement s’il s’en écarte.

Ce fichier doit être **mis à jour** dès qu’un changement architectural majeur est validé (nouvelle structure de dossier, nouveau profil ILDA, etc.).

