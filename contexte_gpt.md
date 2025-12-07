# Contexte GPT – Projet `laser_pipeline_gui`
Commit de référence : `f73209b736854e845a6d07d311a7618a0212cae4`
Repo : https://github.com/HyperionXXI/laser_pipeline_gui

## 1. Objectif du projet

Application Python avec GUI (PyQt5) pour convertir une **vidéo** en **fichier ILDA (.ild)** via un pipeline en 4 étapes :

1. FFmpeg : extraction des frames PNG.
2. Bitmap : seuillage → BMP binaires adaptés à Potrace.
3. Potrace : vectorisation BMP → SVG.
4. ILDA : conversion des SVG en un fichier ILDA unique (une frame ILDA par frame vidéo).

Cas d’usage principaux :
- Animation **La Linea** : garder uniquement le trait principal (personnage), supprimer le cadre et les parasites.
- À terme : contenus plus complexes (ex. Star Wars Arcade).

Contraintes :
- Code générique, portable, robuste.
- Architecture claire et rejouable.
- Un projet = un sous-dossier dans `projects/`.

---

## 2. Structure générale du dépôt

- `gui_main.py` : point d’entrée, lance la GUI.
- `gui/`
  - `main_window.py` : classe `MainWindow`, gestion de l’UI.
  - `pipeline_controller.py` : orchestration des steps pipeline + annulation.
- `core/`
  - `config.py` : chemins de base, notamment `PROJECTS_ROOT = Path("projects")`.
  - `ilda_writer.py` : structures ILDA + écriture fichiers `.ild`.
  - `ilda_preview.py` : lecture ILDA + rendu PNG pour la prévisualisation.
  - `step_ilda.py` : conversion SVG → ILDA.
  - `pipeline/`
    - `ffmpeg_step.py` : extraction vidéo → PNG.
    - `bitmap_step.py` : PNG → BMP (seuil).
    - `potrace_step.py` : BMP → SVG (appel externe Potrace).
    - `ilda_step.py` : wrapper autour de `export_project_to_ilda`.

Arborescence d’un projet typique (`projet_demo`) :

projects/
  projet_demo/
    frames/   # PNG FFmpeg
    bmp/      # BMP seuillés
    svg/      # SVG Potrace
    ilda/     # Fichiers .ild
    preview/  # PNG pour prévisualisation ILDA

---

## 3. GUI : `gui_main.py`, `gui/main_window.py`, `gui/pipeline_controller.py`

### 3.1. `gui_main.py`

- Fait : `from gui.main_window import run` puis `run()`.

### 3.2. `MainWindow` (`gui/main_window.py`)

Interface :
- Sélection vidéo (chemin).
- Nom de projet.
- FPS.
- Boutons :
  - FFmpeg, Bitmap, Potrace, ILDA, Pipeline complet.
  - **Annuler la tâche en cours**.
- Zone de log (affiche les messages `[FFmpeg]`, `[BMP]`, `[Potrace]`, `[ILDA]`, `[Preview]`…).
- Zone de prévisualisation avec 4 colonnes :
  1. PNG (frame vidéo).
  2. BMP (après seuil).
  3. SVG (après Potrace).
  4. ILDA (rendu PNG d’une frame du `.ild`).

Callback important (restauré) :

```python
def on_cancel_task(self) -> None:
    self.btn_cancel_task.setEnabled(False)
    self.pipeline.cancel_current_step()
```

### 3.3. `PipelineController` (`gui/pipeline_controller.py`)

- Lance les steps dans des tâches non bloquantes pour la GUI.
- Fournit :
  - `cancel_current_step()` pour l’annulation.
  - Callbacks de progression et de logs vers la fenêtre principale.
- Step ILDA appelle `core.pipeline.ilda_step.run_ilda_step`, qui lui-même appelle `core.step_ilda.export_project_to_ilda()`.

---

## 4. Steps du pipeline

### 4.1. Step FFmpeg – `core/pipeline/ffmpeg_step.py`

- Entrées :
  - vidéo, nom de projet, FPS.
- Efface/recrée `projects/<project>/frames`.
- Appelle FFmpeg pour générer `frame_XXXX.png`.
- Log typique :
  - `[FFmpeg] Démarrage extraction frames...`
  - `frames` générés dans le dossier.

Statut : **OK / stable**.

### 4.2. Step Bitmap – `core/pipeline/bitmap_step.py`

- Entrées :
  - `frames/frame_XXXX.png`.
  - Paramètres : `threshold_percent`, `thinning`, `max_frames`.
- Convertit en niveaux de gris, applique seuil, écrit BMP noir/blanc :
  - `bmp/frame_XXXX.bmp`.
- Log :
  - `[BMP] Conversion PNG -> BMP ...`
  - `[bitmap] Images BMP générées...`

Statut : **OK / stable**.

### 4.3. Step Potrace – `core/pipeline/potrace_step.py`

- Entrées : BMP.
- Appelle `potrace.exe` (binaire externe).
- Sorties : `svg/frame_XXXX.svg`.
- Gère les namespaces (`<ns0:path>` etc.).
- Log :
  - `[Potrace] Vectorisation BMP -> SVG ...`
  - `[potrace] SVG générés...`

Statut : **OK / stable**.

### 4.4. Step ILDA (wrapper) – `core/pipeline/ilda_step.py`

- Appelle `core.step_ilda.export_project_to_ilda(project_name, ...)`.
- Ecrit `projects/<project>/ilda/<project>.ild`.
- Log :
  - `[ILDA] Export ILDA ...`
  - `[ilda] Fichier ILDA généré : ...` ou message d’erreur.

Statut : **OK (fonctionne avec la nouvelle version de `step_ilda.py`)**.

---

## 5. Cœur ILDA : `core/ilda_writer.py`

### 5.1. Types

```python
@dataclass
class IldaPoint:
    x: int
    y: int
    z: int = 0
    blanked: bool = False
    color_index: int = 255

@dataclass
class IldaFrame:
    name: str = ""
    company: str = "LPIP"
    points: List[IldaPoint] | None = None
    projector: int = 0

    def ensure_points(self) -> List[IldaPoint]:
        ...
```

- Coordonnées X/Y/Z attendues dans `[-32768, +32767]`.
- `blanked=True` : déplacement sans tracer.
- `color_index` : index de palette ILDA (LaserShowGen affiche souvent en rouge, ce qui explique les traits rouges observés).

### 5.2. Écriture : `write_ilda_file(path, frames)`

- Écrit un fichier ILDA **format 0 (3D indexed)** :

  - Header 32 octets :
    - magic "ILDA".
    - format code = 0.
    - nom de la frame (8 chars), company (8 chars).
    - nombre de points.
    - numéro de frame, nombre total de frames.
    - projecteur.

  - Points : 8 octets chacun (X,Y,Z,status,color_index).
  - Ajoute **une frame EOF** finale :
    - `name == ""`, `company == ""`, `num_points == 0`.

- Les frames **vides** (0 points) sont gardées pour la synchronisation.

---

## 6. Prévisualisation ILDA : `core/ilda_preview.py`

### 6.1. Lecture : `load_ilda_frames(path, max_frames=None)`

- Lit un `.ild` :

  - Vérifie le magic "ILDA".
  - Vérifie `format_code == 0`.
  - Lit `num_points`, `name`, `company`, `projector`.
  - Si `num_points == 0` et `name == ""` et `company == ""` → EOF (on s’arrête).
  - Sinon, lit `num_points` points et construit un `IldaFrame`.

- `max_frames` permet de limiter la lecture (utile pour la preview).

### 6.2. Rendu : `render_ilda_frame_to_png(frame, out_png, ...)`

- Convertit les coordonnées ILDA en pixels via `_ilda_to_screen`.
- Trace les segments non blanked en blanc sur fond noir.
- Utilisé par la GUI pour la 4e colonne (ILDA).

### 6.3. Helper : `render_ilda_preview(ilda_path, out_png, frame_index=0)`

- Charge suffisamment de frames pour couvrir `frame_index`.
- Si l’index est dans l’intervalle → frame correspondante.
- Sinon → `frames[0]`.
- Sauvegarde le PNG dans `projects/<project>/preview/ilda_preview_XXXX.png`.

---

## 7. Conversion SVG → ILDA : `core/step_ilda.py`

### 7.1. But

Convertir `svg/frame_XXXX.svg` en une série de `IldaFrame` puis écrire `projects/<project>/ilda/<project>.ild`.

### 7.2. Parsing SVG

- Utilise `xml.etree.ElementTree` + `svgpathtools.parse_path`.

  - `_load_svg_paths(svg_file)` :
    - Parcourt tous les éléments XML.
    - Garde ceux tels que `elem.tag.lower().endswith("path")` (gère namespaces).
    - Lit `d = elem.get("d")`.
    - Passe `d` à `parse_path(d)`.
    - Convertit chaque `Path` en polyligne (`_path_to_polyline`) :
      - `Line` → start + end.
      - Courbes → échantillonnées en plusieurs points.
    - Calcule une bbox `(min_x, max_x, min_y, max_y)`.
    - Retourne une liste de `_PathData(points, bbox)`.

### 7.3. Bbox globale

- `_combine_bbox(all_bboxes)` calcule :

  - `global_bbox_initial = (min_x_global, max_x_global, min_y_global, max_y_global)`.

### 7.4. Détection / suppression de cadre

- Si `remove_outer_frame=True` :

  - `_mark_outer_frame_paths(frames_paths, global_bbox_initial, frame_margin_rel)` :
    - Marque `is_outer_frame=True` si bbox ≈ bbox globale (tolérance relative).
  - Recalcule une bbox globale filtrée sans les chemins marqués `is_outer_frame`.

- Sinon, `global_bbox = global_bbox_initial`.

### 7.5. Normalisation ILDA

- `_make_normalizer(global_bbox, fit_axis, fill_ratio)` :

  - Centre sur le centre de la bbox.
  - Choisit un span de référence :
    - `"max"` (par défaut), `"min"`, `"x"`, `"y"`.
  - Applique `fill_ratio` pour garder une marge.
  - Convertit chaque `(x, y)` en `(X_ilda, Y_ilda)` dans la plage ILDA en clampant.

### 7.6. Filtrage des petits chemins

- Calcule `global_span = max(span_x, span_y)` (bbox globale).
- Pour chaque `_PathData` :

  - `w = x1 - x0`, `h = y1 - y0`.
  - `rel_size = max(w, h) / global_span`.
  - Si `rel_size < min_rel_size` → chemin ignoré (parasite).

### 7.7. Construction des `IldaFrame`

- Pour chaque frame (index `idx`) :

  - Pour chaque chemin `_PathData` :
    - Si `is_outer_frame=True` ou `rel_size < min_rel_size` → ignoré.
    - Sinon :
      - Convertit tous les points en coordonnées ILDA via `normalizer`.
      - Ajoute un premier point en `blanked=True` (déplacement sans trace).
      - Ajoute les points suivants en `blanked=False`.

  - Crée un `IldaFrame` :
    - `name=f"F{idx:04d}"` (F0000, F0001, …).
    - `company="LPIP"`.
    - `points=ilda_points`.

- Écrit tout avec `write_ilda_file(...)`.

### 7.8. Signature de `export_project_to_ilda`

```python
def export_project_to_ilda(
    project_name: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    remove_outer_frame: bool = True,
    frame_margin_rel: float = 0.02,
    check_cancel: Optional[Callable[[], bool]] = None,
    report_progress: Optional[Callable[[int], None]] = None,
) -> Path:
    ...
```

- Compatible avec les appels existants (notamment `run_ilda_step`).

---

## 8. Comportement observé & problèmes connus (La Linea)

### 8.1. Logs typiques

- Pipeline complet :

  - FFmpeg → OK.
  - Bitmap → OK.
  - Potrace → OK.
  - ILDA → OK (`projet_demo.ild` généré).

### 8.2. GUI

- Sur les frames 10, 100, 150, 151 :
  - PNG / BMP / SVG cohérents.
  - ILDA : personnage centré, rendu correct.

### 8.3. LaserShowGen

- Le fichier `projet_demo.ild` :
  - S’ouvre correctement.
  - Traits souvent affichés en rouge (palette du viewer).
  - Certaines frames semblent “manquantes” (ex. autour de 150) :
    - Il s’agit en fait de **frames ILDA vides** (0 points) :
      - tous les chemins de la frame ont été filtrés (cadre ou parasites).

### 8.4. LaserOS

- À l’import :
  - Le motif central semble **assez fixe**.
  - Le **cadre** ou des éléments périphériques semblent **bouger** au cours de l’animation.
- Causes probables :
  - Heuristique de cadre encore imparfaite.
  - Légères variations de la bbox globale d’une frame à l’autre, ce qui modifie le “zoom” et la position relative de certains éléments.

---

## 9. Limitations actuelles

1. **Cadre parasite encore présent / mouvant** :
   - L’algorithme `_mark_outer_frame_paths` est assez simple (bbox ≈ bbox globale).

2. **Frames vides** → impression de “trames manquantes” :
   - Dès qu’une frame n’a que des chemins supprimés (cadre ou trop petits), la frame ILDA est vide.

3. **Contenus complexes (Star Wars Arcade)** :
   - Paramètre `min_rel_size` adapté à La Linea mais trop agressif pour les scènes très détaillées.

4. **Décalage visuel entre vidéo et ILDA dans la GUI** :
   - Inévitable car l’ILDA est normalisé et centré dans la fenêtre de projection.

---

## 10. Pistes pour évolution future

1. Améliorer la détection du cadre externe :
   - Ajouter des critères géométriques (nombre de côtés, rectitude, ratio largeur/hauteur…).
   - Stabiliser la bbox de référence pour limiter les variations d’une frame à l’autre.

2. Gérer mieux les frames vides :
   - Optionnel : recopier les points de la dernière frame non vide au lieu de produire une frame vide.

3. Profils de traitement :
   - Profil “La Linea” : suppression de cadre + filtrage agressif des petits parasites.
   - Profil “Arcade” : suppression de cadre optionnelle, `min_rel_size` très faible.

4. Exposer des paramètres ILDA dans la GUI :
   - `min_rel_size`, `frame_margin_rel`, `fit_axis`, `fill_ratio`.

---

## 11. Référence de reprise

- Commit de base : `f73209b736854e845a6d07d311a7618a0212cae4`.
- Projet de test principal : `projet_demo` basé sur `la_linea (30sec).mp4`.
- Points clés :
  - Le pipeline complet fonctionne.
  - Le parsing SVG (namespaces) et l’écriture ILDA sont maintenant robustes.
  - Les problèmes restants sont surtout **heuristiques** (cadre, filtrage) et non structurels.

