# Contexte GPT – Projet *Laser Pipeline GUI*

Ce document sert de **mémoire stable** pour les futures conversations avec ChatGPT
autour du projet `laser_pipeline_gui`.  
Objectif : éviter de “refaire et défaire” les mêmes choses, garder trace des
décisions, invariants et bugs connus.

Ligne directrice demandée par Florian :

> code **générique**, **portable**, **robuste**, **orienté objets** et pensé **intelligemment**.


---

## A. But du projet

### A.1. Idée générale

Transformer automatiquement une **vidéo** (MP4, etc.) en **animation laser** au
format ILDA (`.ild`), avec :

1. Un **pipeline modulaire** en plusieurs étapes (CLI / core Python).
2. Une **interface graphique** PySide6 (GUI) qui pilote ce pipeline.

Cas visés :

- Jeux d’arcade / visuels vectoriels (Starwars Arcade, Tempest, etc.).
- Séries filaires stylisées (*La Linea*).
- D’autres vidéos suffisamment contrastées / stylisées.

Cible principale : produire des `.ild` exploitables dans **LaserOS** pour piloter
des **LaserCube** (Florian possède plusieurs LaserCube Pro 2.5W, utilisés en LAN).


### A.2. Modules externes

Sur la machine de Florian (Windows) :

- **FFmpeg**  
  Installé dans : `C:\ffmpeg-7.1-essentials_build\bin`
- **Potrace**  
  Installé dans : `C:\potrace-1.16.win64`
- **ImageMagick**  
  Installé et accessible dans le `PATH`.

Le fichier `core/config.py` stocke les chemins :

- `FFMPEG_PATH`
- `MAGICK_PATH`
- `POTRACE_PATH`
- `PROJECTS_ROOT` (dossier racine des projets, ex. `projects/`).

Ces chemins doivent rester facilement modifiables et **non hardcodés ailleurs**.


---

## B. Pipeline : de la vidéo au fichier ILDA

Pipeline nominal (4 steps) :

1. **FFmpeg** : vidéo → PNG  
2. **Bitmap (ImageMagick)** : PNG → BMP binaires / affinés  
3. **Potrace** : BMP → SVG (chemins vectoriels)  
4. **ILDA** : SVG → `.ild` (points ILDA)

Chaque step :

- lit/écrit dans un sous-dossier de `projects/<projet>/`,
- est utilisable **indépendamment**,
- est piloté depuis le GUI (un bouton par étape) *et* via un module core.

L’idée à terme : un bouton “**Exécuter les 4 étapes**” dans la GUI qui enchaîne
FFmpeg → Bitmap → Potrace → ILDA en une fois (TODO, cf. section H).


---

## C. Architecture du code

### C.1. Arborescence

- `core/`
  - `config.py` : chemins externes, `PROJECTS_ROOT`, etc.
  - `step_ffmpeg.py` : extraction de frames PNG (core CLI).
  - `step_bitmap.py` : conversion PNG → BMP (core CLI).
  - `step_potrace.py` : vectorisation BMP → SVG (core CLI).
  - `step_ilda.py` : conversion SVG → ILDA (core CLI).
  - `ilda_writer.py` : écriture bas niveau des fichiers ILDA.
  - `ilda_profiles.py` : profils ILDA (`classic`, `arcade`, etc.).
  - `ilda_preview.py` : rendu raster d’une frame ILDA (base pour un preview).
  - `pipeline/`
    - `base.py` : `FrameProgress`, `StepResult`, types de callback.
    - `ffmpeg_step.py` : wrapper pipeline pour FFmpeg.
    - `bitmap_step.py` : wrapper pipeline pour Bitmap.
    - `potrace_step.py` : wrapper pipeline pour Potrace.
    - `ilda_step.py` : wrapper pipeline pour ILDA.

- `gui/`
  - `main_window.py` : fenêtre principale, wiring des boutons.
  - `pipeline_controller.py` : orchestre les steps (1–4).
  - `preview_widgets.py` : widgets de prévisualisation (PNG, BMP, SVG, ILDA).
  - etc.

- `gui_main.py` : point d’entrée de l’application GUI.


### C.2. Concepts principaux

- **Step core** (`core/step_*.py`)  
  → logique pure, indépendante de la GUI, orientée “ligne de commande”.

- **Step pipeline** (`core/pipeline/*_step.py`)  
  → adaptation entre le core et le GUI : progression, annulation, logs, etc.

- **GUI**  
  → paramétrage utilisateur, lancement de chaque step, affichage de la progression,
    affichage des previews, zone de log.


---

## D. Détails des steps

### D.1. Step 1 – FFmpeg : vidéo → PNG

Core : `core/step_ffmpeg.py`

```python
def extract_frames(input_video: str, project_name: str, fps: int = 25) -> Path:
    # crée projects/<project>/frames/frame_XXXX.png
    # lance ffmpeg (subprocess.run) avec -vf fps=<fps>
    # lève RuntimeError si ffmpeg échoue

Pipeline : core/pipeline/ffmpeg_step.py

    run_ffmpeg_step(video_path, project, fps, progress_cb, cancel_cb) :

        assure la création de projects/<projet>/frames/.

        appelle extract_frames.

        Bug connu : la progression envoyée à progress_cb n’est pas une
        vraie progression en pourcentage (il n’y a qu’un callback de fin
        avec "Extraction terminée.").
        → cf. section H.1 (TODO pour la progression réelle).

### D.2. Step 2 – Bitmap : PNG → BMP (ImageMagick)

Core : core/step_bitmap.py

    Conversion des PNG de frames/ vers des BMP dans bmp/ :

        binarisation (seuil %),

        option thinning pour réduire des traits épais,

        max_frames (0 = toutes).

Pipeline : core/pipeline/bitmap_step.py

    Lancement de convert_project_frames_to_bmp(...).

    Gestion de la progression par frame (basée sur le nombre de PNG).

D.3. Step 3 – Potrace : BMP → SVG

Core : core/step_potrace.py

    Conversion des BMP bmp/frame_XXXX.bmp en svg/frame_XXXX.svg :

        appels à Potrace en ligne de commande,

        post-traitement minimal des SVG (en cours d’évolution).

Pipeline : core/pipeline/potrace_step.py

    Lancement de vectorize_project_bmp_to_svg(...).

    Prépare un preview SVG rasterisé dans la GUI.

D.4. Step 4 – ILDA : SVG → .ild

Core : core/step_ilda.py (commit de référence pour ce contexte :
231c0730372fc1ef1fe99361479fd97f66328ecd)

Résumé du fonctionnement :

    Lecture de tous les SVG du projet via _load_svg_paths(svg_file) :

        récupération de tous les <path> (sans se soucier des namespaces),

        utilisation de svgpathtools.parse_path pour obtenir des segments,

        conversion en listes de points (x, y) avec _path_to_polyline(...),

        calcul d’une bbox (min_x, max_x, min_y, max_y) pour chaque chemin,

        stockage dans une structure interne _PathData.

    Calcul d’une bounding box globale global_bbox_initial :

        sur l’ensemble des chemins de toutes les frames.

    Optionnel : détection/suppression du “cadre extérieur”
    via _mark_outer_frame_paths(frames_paths, global_bbox_initial, frame_margin_rel) :

        critère actuel (simplifié) :

            bbox très proche de la bbox globale, avec tolérance frame_margin_rel,

        marque les chemins en is_outer_frame = True,

        recalcule une global_bbox sans ces chemins,

        si tous les chemins sont supprimés → on revient à la bbox initiale.

    ⚠️ Problème constaté (La Linea, arcade) :
    le rectangle généré par Potrace n’est pas toujours suffisamment “collé”
    à la bbox globale pour passer ce test → le cadre persiste dans
    le fichier ILDA (voir section F).

    Normalisation dans l’espace ILDA :

        ILDA_MIN = -32767, ILDA_MAX = +32767,

        choix de l’axe de référence via fit_axis ("max", "min", "x", "y"),

        fill_ratio pour laisser une marge (éviter le clipping),

        fonction _make_normalizer(global_bbox, fit_axis, fill_ratio) qui
        renvoie un mapping (x, y) → (X_ilda, Y_ilda).

    Filtrage anti-poussière :

rel_size = max(w, h) / global_span
if rel_size < min_rel_size:
    continue  # on jette le chemin

    global_span = max(span_x, span_y) (à partir de global_bbox),

    min_rel_size est paramétrable et est actuellement typiquement
    0.01 (1 % de la taille globale).

→ Si tous les chemins d’une frame sont en dessous du seuil :

    la frame devient “vide” du point de vue ILDA (on ne garde que
    le placeholder, voir ci-dessous).

Blanking & construction de la frame :

    pour chaque chemin retenu :

        premier point ILDA : blanked = True (déplacement sans trace),

        points suivants : blanked = False (laser allumé),

        tous les points partagent le même color_index (cf. profil ILDA).

    si, après filtrage, ilda_points est vide :

        on ajoute un point unique :

            IldaPoint(x=0, y=0, z=0, blanked=True, color_index=profile.base_color_index)

            invariant important : 1 frame vidéo → 1 frame ILDA, même si
            visuellement la frame est noire (placeholder invisible).

    Écriture du fichier .ild :

        via ilda_writer.write_ilda_file(out_path, frames),

        format 0 (3D + couleur indexée) utilisé actuellement,

        frame de terminaison ILDA standard (0 points).

Pipeline : core/pipeline/ilda_step.py

    run_ilda_step(project_name, fit_axis, fill_ratio, min_rel_size, ilda_mode, ...)

    Construit une IldaExportConfig :

        mode : "classic" ou "arcade" (toute valeur inconnue → "classic"),

        fit_axis normalisé,

        fill_ratio clampé,

        min_rel_size clampé,

        remove_outer_frame = True dans les deux modes,

        frame_margin_rel = 0.02 en classic, 0.05 en arcade.

    Appelle export_project_to_ilda(...) du core avec ces paramètres.

    Note : dans le code actuel, export_project_to_ilda appelle
    report_progress(idx) avec idx = index de frame (0-based), tandis que
    _report_progress dans ilda_step.py suppose recevoir un pourcentage
    (pct) dans [0..100].
    → Incohérence de progression à corriger (cf. section H.2).

E. Profils ILDA et cas d’usage
E.1. Profils ILDA (IldaProfile)

core/ilda_profiles.py :

    structure IldaProfile (au moins : name, base_color_index, etc.),

    fonction get_ilda_profile(mode: str) → IldaProfile.

Actuellement :

    classic : profil utilisé par défaut, base_color_index fixé à 0.

    arcade : profil “expérimental”, pour l’instant très proche de classic.

Conséquence actuelle :

    Tous les points ont color_index=0 → selon la palette ILDA standard,
    ils apparaissent rouges dans LaserShowGen / LaserOS.

    La couleur n’est pas encore paramétrable côté GUI,
    ni gérée finement par profil.

E.2. Mode classic

Usage :

    Mode “générique” pour la majorité des tests,

    Autorise des heuristiques plus agressives (filtrage, suppression de cadre),

    Tolère l’idée de “mettre un peu les mains dans la boue” pour avoir
    des images propres.

Caractéristiques :

    min_rel_size peut être utilisé pour “nettoyer” les petits artefacts.

    remove_outer_frame=True, mais l’heuristique actuelle de détection
    du cadre n’est pas parfaite (cadre persistant sur certains projets).

    Couleur uniforme (rouge) pour l’instant.

E.3. Mode arcade – objectif cible (non encore atteint)

Objectif déclaré par Florian :

    En mode arcade, chaque ligne, segment, motif présent dans la vidéo
    doit être fidèlement restitué par le laser,
    avec les mêmes couleurs, autant que possible.

Concrètement, cela implique à terme :

    Très peu de filtrage :

        min_rel_size plutôt petit,

        suppression uniquement des artefacts évident (ex. cadre Potrace),

    Gestion réelle des couleurs (via profils / palettes / indexation),

    Conservation maximale de la géométrie d’origine,

    Pas (ou très peu) de simplification des paths.

État actuel :

    Mode arcade ne diffère de classic que par frame_margin_rel (0.05 vs 0.02).

    Aucun mapping couleur sophistiqué n’est encore implémenté.

    Le comportement “1:1 arcade” est donc un objectif futur, pas la
    réalité actuelle.

E.4. Cas spécial : La Linea

Cas d’usage particulier :

    Vidéo avec un trait de crayon épais (contour blanc) sur un fond non
    uniformément noir (le fond peut être légèrement coloré, texturé, etc.).

    Idéalement, on souhaiterait :

        “Le trait de crayon épais de la vidéo devient un trait fin projeté
        par le laser.”

Problèmes spécifiques :

    Le fond n’est pas toujours parfaitement noir → binarisation délicate.

    Le trait épais donne après Potrace des surfaces et des contours plus
    complexes qu’une simple ligne.

    Un thinning trop agressif peut laisser des artefacts de fond (traits résiduels).

État actuel :

    L’option “trait épais → trait fin laser” n’a pas encore été conçue
    ni implémentée.

    La Linea est donc, pour l’instant, un cas “expérimental” où :

        le cadre généré par Potrace reste problématique,

        une grande partie des frames deviennent “vides” après filtrage
        (min_rel_size),

        le résultat ILDA n’est pas encore satisfaisant.

F. Observations ILDA concrètes (La Linea / Arcade)
F.1. Projet La Linea (exemple analysé)

Vidéo : La Linea (30 sec) à 25 fps

    30 s × 25 fps = 750 frames vidéo.

    Fichier ILDA généré : projet_demo_LaLinea.ild.

Analyse binaire du .ild :

    751 en-têtes ILDA :

        750 frames “normales”,

        1 frame de terminaison (0 points).

    Format utilisé : format 0 (3D + couleur indexée).

    Tous les points ont color_index = 0 (rouge).

    Répartition des frames :

        532 frames avec 1 seul point (le placeholder blanké au centre),

        218 frames avec plus d’un point (contenu dessin réel),

        nombre max de points dans une frame : de l’ordre de 3000–4000.

Conclusion :

    L’invariant 1 frame vidéo → 1 frame ILDA est respecté.

    Il n’y a aucune frame corrompue au sens du format ILDA :

        soit frame “vide” (1 point blanked),

        soit frame avec des points plausibles.

Les frames “bizarres” vues dans LaserShowGen / LaserOS sont donc
principalement :

    des frames où il ne reste qu’un petit morceau de trait (après filtrage),

    des frames où le cadre de Potrace reste présent.

F.2. Origine probable des frames vides

Mécanisme :

    Le filtrage min_rel_size compare la taille de chaque chemin à la
    global_span (taille max de la bbox globale).

    Lorsque la vidéo évolue (zoom, déplacements, petits détails) :

        certains chemins deviennent très petits par rapport à la bbox globale,

        leur rel_size passe sous le seuil min_rel_size (ex. 0.01),

        ils sont jetés comme “parasites”.

Résultat :

    Dès qu’une frame ne contient plus que des chemins dont rel_size < min_rel_size :

        tous les chemins sont filtrés → frame “vide”,

        un point blanked est inséré pour garder la continuité.

Effet constaté sur La Linea :

    Moitié des frames sont “visuellement vides” (placeholder uniquement),

    ce qui donne l’impression d’une animation qui se “fige” ou se vide,
    alors que du point de vue du fichier ILDA, la structure est parfaitement
    valide.

F.3. Le “cadre” Potrace

Problème de longue date :

    Potrace, en partant d’une image avec un “trait” blanc épais sur fond sombre,
    a tendance à générer :

        d’une part des chemins pour le trait,

        d’autre part un grand rectangle englobant (le “cadre”).

Constat :

    Ce rectangle ne figure pas dans la vidéo d’origine,
    mais apparaît systématiquement dans les SVG.

    L’heuristique _mark_outer_frame_paths ne le détecte pas toujours
    (tolérance trop faible, légères différences de bbox).

Décision fonctionnelle :

    Le cadre ne doit pas exister dans l’animation ILDA s’il ne figure pas
    dans la vidéo d’origine.

En pratique :

    Aujourd’hui, pour les cas testés (La Linea, Starwars, Tempest), le cadre
    est considéré comme un artefact systématique de Potrace, donc à supprimer.

    Pour d’éventuels cas futurs où un “cadre” ferait vraiment partie du
    visuel (HUD, interface, etc.), il faudra :

        soit rendre le filtrage optionnel / configurable,

        soit disposer d’une information supplémentaire pour distinguer
        “cadre réel” de “parasite Potrace”.

F.4. Segments “parasites” dans LaserShowGen

Observation :

    Dans LaserShowGen, certaines diagonales ou traits semblent relier
    des éléments qui ne devraient pas être connectés (ex. bouche → main).

Explication :

    Ce sont les segments correspondant aux déplacements du scanner
    entre chemins :

        premier point de chaque chemin = blanked=True,

        LaserShowGen affiche parfois le segment précédent comme une ligne
        (pour visualiser le parcours),

        sur un vrai projecteur, ces segments sont invisibles (laser éteint).

G. Invariants et règles de conception

Résumé des invariants importants :

    1 frame vidéo → 1 frame ILDA

        même si la frame est “vide” (placeholder),

        pas de suppression physique de frames après FFmpeg.

    Pas de cadre fantôme

        Tout cadre qui n’est pas réellement présent dans la vidéo doit
        être supprimé.

        Aujourd’hui, cela concerne principalement le rectangle Potrace.

    Pas de suppression silencieuse de contenu important

        Le filtrage min_rel_size doit être utilisé avec prudence :

            en mode classic, on peut être plus agressif (objectif “image propre”),

            en mode arcade, l’objectif à terme est de conserver un maximum
            de traits (sauf artefacts clairement identifiés).

    Paramétrage explicite plutôt que “magie cachée”

        Toute heuristique (suppression de cadre, filtrage de petits chemins,
        thinning, etc.) doit être clairement identifiée et, si possible,
        paramétrable (GUI ou fichier de config).

H. Bugs connus et TODO
H.1. Progression Step 1 (FFmpeg)

État actuel :

    core/step_ffmpeg.py lance ffmpeg via subprocess.run et attend la fin.

    core/pipeline/ffmpeg_step.py appelle progress_cb(...) essentiellement
    à la fin, avec un message “Extraction terminée.”.

    La barre de progression GUI ne reflète donc pas une vraie progression
    en pourcentage (elle se contente de passer à l’état final).

TODO (idée) :

    Soit :

        estimer le nombre de frames attendu (durée vidéo × FPS),

        surveiller en temps réel le nombre de PNG créés dans frames/,

        émettre des callbacks de progression en conséquence.

    Soit :

        récupérer les logs de FFmpeg (grand nombre d’outils permettent de
        suivre la progression via stdout/stderr),

        parser les lignes pour estimer % et mettre à jour la barre.

H.2. Progression Step 4 (ILDA)

État actuel :

    core/step_ilda.py appelle report_progress(idx) avec idx = index
    de frame (0-based).

    _report_progress dans core/pipeline/ilda_step.py traite l’argument
    comme un pourcentage et tente de reconstruire l’index de frame à partir
    de là.

Résultat :

    Incohérence entre core et pipeline,

    progression affichée peu fiable.

TODO :

    Décider d’un invariant clair :

        soit export_project_to_ilda émet un pourcentage 0–100,

        soit il émet un index de frame et _report_progress ne fait
        que le relayer.

    Ajuster l’un ou l’autre pour être cohérent.

H.3. Bouton “Exécuter les 4 steps”

État actuel :

    La GUI a un bouton par step :

        Run FFmpeg, Run Bitmap, Run Potrace, Export ILDA.

    Pas de bouton pour lancer les 4 d’un coup.

Besoin :

    Un bouton type “Pipeline complet” qui :

        vérifie les paramètres,

        exécute FFmpeg → Bitmap → Potrace → ILDA dans l’ordre,

        s’arrête proprement si une étape échoue,

        utilise la barre de progression et les logs pour donner du feedback.

Lieu naturel :

    gui/pipeline_controller.py est l’endroit logique pour implémenter
    la logique d’enchaînement des steps.

H.4. Cadre Potrace persistant

    Bug “historique” : le cadre généré par Potrace reste visible dans
    les ILDA pour La Linea et les cas arcades.

    L’heuristique _mark_outer_frame_paths est trop fragile ; elle ne
    couvre pas tous les cas (tolérance, légère déformation, etc.).

TODO :

    Rendre la détection du cadre plus robuste :

        combinaison de :

            proximité aux bords de la bbox globale,

            couverture surfacique (ex. ≥ 90–95 %),

            éventuellement vérification de la “rectangularité” du path.

    Garder remove_outer_frame optionnel (True par défaut en classic/arcade
    pour les cas actuels).

H.5. Couleurs ILDA

    Actuellement : tout est rouge (index 0).

    Pour le mode arcade, l’objectif est de retrouver les couleurs de la vidéo
    (ou au moins un mapping raisonnable) :

        soit via plusieurs passes,

        soit via indexation simple (fond noir, objets colorés, etc.).

TODO :

    Étendre IldaProfile :

        palette(s) supportées,

        manière de mapper des classes d’objets à des couleurs.

    Ajouter des paramètres GUI :

        couleur de base en mode classic (rouge/vert/bleu/blanc),

        éventuellement, mapping simplifié pour arcade.

H.6. Cas La Linea (trait épais)

    Le pipeline actuel est pensé pour des visuels “déjà fins” (arcade, vectoriel).

    Pour La Linea, il manque une brique conceptuelle :

        “éclater” un trait épais (surface blanche) en une seule ligne fine,
        relativement stable dans le temps, sans artefacts de fond.

TODO (piste) :

    Travailler davantage dans le step Bitmap :

        thinning adapté,

        gestion avancée du seuil,

        détection du “centre” du trait.

    Adapter Potrace / post-traitement SVG pour ne garder qu’un seul chemin
    “squelette” par trait.

I. Consignes pour les futures interventions ChatGPT

Pour éviter les régressions et les pertes de temps :

    Toujours respecter les invariants listés en section G (1 frame vidéo →
    1 frame ILDA, pas de cadre fantôme, etc.).

    Ne pas modifier silencieusement :

        la valeur par défaut de min_rel_size,

        la logique d’IldaProfile,

        la structure de base d’export_project_to_ilda.

    Lorsque des changements sont proposés :

        privilégier l’ajout de nouveaux paramètres ou de nouveaux profils,

        documenter clairement dans ce fichier les décisions prises (nouvelle
        section ou sous-section).

    Toujours garder à l’esprit :

        classic : mode “laboratoire / expérimental” ou “propreté visuelle”.

        arcade : objectif “fidélité maximale” à la vidéo en lignes/couleurs.

        La Linea : cas spécial à part (trait épais) qui nécessitera une
        réflexion dédiée.