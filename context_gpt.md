# Projet `laser_pipeline_gui` – CONTEXTE LONG (reprendre vite, éviter les erreurs)

**Date : 2025-12-13 (Europe/Zurich)**  
**Commit de référence : `540716c` (SHA complet `540716cef5533ef1f557dc9a07949ed7e0d4b4f9`)**  
Dépôt public : https://github.com/HyperionXXI/laser_pipeline_gui  
Autorisation : le développeur autorise explicitement ChatGPT à consulter le dépôt public.

---

## 0) Ce que ChatGPT doit faire en début de conversation (routine de reprise)

1. **Se caler sur le commit** : si l’utilisateur est sur un autre SHA, le noter d’emblée (les noms/fichiers peuvent diverger).  
2. **Se caler sur l’arbo canonique** (section 1). Ne pas inventer de dossiers/fichiers.  
3. **Lire le problème du moment** : souvent “cadre parasite” (section 8) et/ou “artefacts lignes”.  
4. **Avant tout patch** : vérifier la cohérence **signatures/callbacks** (section 7).  
5. Proposer des changements **minimaux et localisés** (architecture verrouillée section 2).

---

## 1) Arborescence CANONIQUE du dépôt (repo-only)

> Cette arbo est la référence. Toute proposition doit s’y conformer.

```
laser_pipeline_gui/
│
├─ core/
│  ├─ config.py
│  ├─ ffmpeg_extract.py
│  ├─ bitmap_convert.py
│  ├─ potrace_vectorize.py
│  ├─ ilda_export.py
│  ├─ ilda_writer.py
│  ├─ ilda_profiles.py
│  ├─ ilda_preview.py
│  └─ __init__.py
│
│  └─ pipeline/
│     ├─ base.py
│     ├─ ffmpeg_step.py
│     ├─ bitmap_step.py
│     ├─ potrace_step.py
│     ├─ ilda_step.py
│     ├─ full_pipeline_step.py
│     └─ __init__.py
│
├─ gui/
│  ├─ main_window.py
│  ├─ pipeline_controller.py
│  ├─ preview_widgets.py
│  └─ __init__.py
│
├─ projects/
│  └─ <nom_projet>/
│     ├─ frames/
│     ├─ bmp/
│     ├─ svg/
│     ├─ preview/
│     └─ <nom_projet>.ild
│
├─ gui_main.py
├─ README.md
└─ .gitignore
```

### Règles strictes “anti-confusion”
- ❌ Ne jamais réintroduire `core/step_*.py` (historique : imports cassés + imports circulaires).  
- ❌ Ne jamais inventer `core/steps/`, `pipeline/steps/`, etc.  
- ✅ Les orchestrateurs sont **uniquement** dans `core/pipeline/*_step.py`.  
- ✅ La logique métier est dans `core/*.py`.

---

## 2) Architecture (VERROUILLÉE)

### 2.1 Séparation des responsabilités
- `core/*.py` : logique métier (conversion, parsing, export), pas de GUI.
- `core/pipeline/*_step.py` : orchestration standardisée, callbacks, cancellation, logs, StepResult.
- `gui/*` : UI PySide6 + contrôleur.
- `projects/*` : sorties générées.

👉 **Règle d’imports :**
- `core/pipeline/*` peut importer `core/*`
- `core/*` **ne doit jamais importer** `core/pipeline/*`
- `gui/*` importe `core/pipeline/*` (pas l’inverse)

---

## 3) Objectif produit
Générique, structuré, si possible portable.
GUI Python (VSCode, style PEP 8) pour convertir une vidéo en animation laser ILDA :

1) Frames PNG (FFmpeg)  
2) Bitmap BMP (seuil + thinning optionnel)  
3) SVG (Potrace)  
4) ILDA `.ild` (SVG → points)

Avec :
- prévisualisations à chaque étape,
- comportement reproductible,
- export ILDA propre (pas de cadre parasite, artefacts minimisés),
- pas de “perte de frames” (synchronisation temporelle).
---

## 4) Environnement & outils externes

### 4.1 Python
- Exécution locale sous Windows via `.venv`
- Le code doit rester générique/portable (chemins configurables)

### 4.2 Outils externes
- **FFmpeg** : extraction frames
- **Potrace** : BMP → SVG
- (Optionnel selon versions : ImageMagick pour PNG→BMP + seuil/thinning)

### 4.3 `core/config.py` (règles de modification)
- Contient les chemins (`FFMPEG_PATH`, `POTRACE_PATH`, éventuellement `MAGICK_PATH`) + racines (`PROJECTS_ROOT`, etc.).
- **Règle** : ne jamais “deviner” les chemins locaux de l’utilisateur. Toute modif doit être minimale et annoncée.

---

## 5) Pipeline – conventions & sorties

### 5.1 Flux immuable
```
MP4 → frames/*.png → bmp/*.bmp → svg/*.svg → <projet>.ild
```

### 5.2 Convention de nommage frames
- `frame_0001.png` (padding 4 chiffres, base 1)
- Même logique pour BMP/SVG

### 5.3 Dossiers par projet
`projects/<project_name>/`
- `frames/` : PNG FFmpeg
- `bmp/` : BMP binarisés
- `svg/` : SVG Potrace
- `preview/` : PNG preview (bitmap/svg/ilda)
- `<project_name>.ild` : résultat final

---

## 6) GUI (PySide6) – composants

### 6.1 `gui/main_window.py`
- UI principale : sélection vidéo, nom projet, FPS, threshold, thinning, max_frames, profil ILDA.
- Bouton “Exécuter les 4 étapes”.
- Zone preview frame.
- Zone logs.

### 6.2 `gui/pipeline_controller.py`
- Orchestration des steps `run_*_step` et mise à jour UI.
- Point sensible : **progress callbacks** et cancellation.

### 6.3 `gui/preview_widgets.py`
- Widgets de prévisualisation des sorties (png/bmp/svg/ilda preview).

---

## 7) Progress / callbacks / signatures (PIÈGE N°1)

### 7.1 Problème typique historique
- erreurs du type : `report_progress() takes 1 positional argument but 2 were given`
- ou mismatch `progress(percent)` vs `progress(done, total)`

### 7.2 Règle d’or
- Choisir **une** signature de progression (définie dans `core/pipeline/base.py`) et l’appliquer partout :
  - steps (`core/pipeline/*_step.py`)
  - GUI controller

### 7.3 Avant tout patch
- **Lire** la définition dans `base.py`
- **Rechercher** tous les appels côté steps + GUI
- Adapter systématiquement, sinon régression.

---

## 8) Problème principal actuel : “cadre/rectangle parasite” (PRIORITÉ #1)

### 8.1 Symptôme
Dans LaserShowGen, un rectangle/cadre apparaît autour de la zone utile (beaucoup de frames).

### 8.2 Observations terrain VALIDÉES
- Inverser manuellement la polarité d’un BMP (test paint.net) puis relancer Potrace + export ILDA → le cadre peut disparaître.
- Donc le cadre est très probablement **amont** : polarité bitmap / comportement Potrace.

### 8.3 Hypothèse la plus probable
Le pipeline fournit à Potrace un bitmap où :
- le “fond” est considéré comme forme principale
- Potrace vectorise le contour du fond → cadre

### 8.4 Où corriger (et où ne pas corriger)
✅ Corriger au niveau BMP→SVG :
- `core/potrace_vectorize.py`
- `core/pipeline/potrace_step.py`

❌ Ne pas “patcher” en aval :
- pas dans `ilda_export.py` (trop tard : le cadre est déjà un chemin SVG)
- pas dans la GUI

### 8.5 Direction recommandée
- Stabiliser la polarité d’entrée Potrace :
  - garantir **fond blanc / trait noir** (ou l’inverse, mais de façon stable)
  - introduire un mécanisme contrôlé `invert_for_potrace` (interne au début)
- Tester sur frames repères (ex: 10, 100, 150, 151 si disponibles dans le projet de test).

---

## 9) ILDA – règles CRITIQUES (PIÈGE N°2)

### 9.1 Principe de blanking
- Premier point de chaque chemin : `blanked=True` (déplacement sans laser)
- Points suivants : `blanked=False`

### 9.2 Frames vides : NE JAMAIS SUPPRIMER
- Si une frame ne produit aucun point :
  - ajouter **un point unique “blanked”** au centre `(0,0)`
- Objectif : conserver le **même nombre de frames** du début à la fin du pipeline.

> Règle absolue : ne jamais réintroduire une logique qui “drop” les frames vides.

---

## 10) Potrace – erreurs rencontrées (historique utile)

- Patch testé : plus d’erreurs type `unknown option -i` (donc arguments Potrace déjà corrigés côté projet).
- Erreur observée et corrigée dans le passé :
  - `bitmap_to_svg_folder() got an unexpected keyword argument 'invert_for_potrace'`
  → cause : signature non harmonisée entre orchestrateur et logique.

👉 Leçon : **si on introduit un nouveau paramètre**, le propager proprement :
- GUI (si exposé)
- `core/pipeline/potrace_step.py`
- `core/potrace_vectorize.py`

---

## 11) Dossiers temporaires / rerun pipeline (PIÈGE N°3)

- Si le pipeline est interrompu, certains dossiers peuvent rester “sales”.
- Le projet doit tolérer des reruns :
  - soit en nettoyant les dossiers cibles,
  - soit en écrasant proprement,
  - mais toujours sans mélanger des résultats de runs différents.

Recommandation : avoir une politique claire par step (delete & recreate vs overwrite).

---

## 12) Checklist de reprise ultra-rapide

### 12.1 Setup
1. `python gui_main.py` → la GUI s’ouvre.
2. Lancer “Exécuter les 4 étapes” sur un petit projet test (ex : `projet_demo`).
3. Vérifier la présence de :
   - `frames/`, `bmp/`, `svg/`, `preview/`, `.ild`

### 12.2 Sanity checks
- Nombre de frames cohérent à chaque étape (sauf `max_frames`).
- Nommage padding 4 chiffres.
- Preview ILDA générée.

### 12.3 Debug “cadre”
- Comparer BMP vs SVG sur une frame où le cadre apparaît.
- Confirmer l’hypothèse polarité en inversant un BMP et en relançant Potrace.
- Si confirmé : implémenter inversion automatique avant Potrace.

---

## 13) Règles de collaboration “anti-perte de temps” (pour ChatGPT)

- Ne jamais proposer une refonte globale quand un bug local est identifié.
- Toujours :
  1) isoler la cause,
  2) patch minimal,
  3) vérifier non-régression (frames repères),
  4) seulement ensuite généraliser.

- Avant d’écrire du code :
  - vérifier que le fichier existe dans l’arbo canonique,
  - vérifier les signatures,
  - ne pas “inventer” des noms.

---

## 14) Notes Git (pratiques)

- Éviter de mixer refactor + fix fonctionnel dans le même commit.
- Commits séparés recommandés :
  - `refactor: ...`
  - `feat: invert potrace input ...`
  - `fix: callbacks signature ...`

---

## 15) “Ce que l’utilisateur attend” (rappel produit)

Objectif final : un ILDA qui contient **uniquement le trait utile** (ex. type “La Linea”) :
- sans cadre,
- avec artefacts minimaux,
- et un timing fidèle (pas de frames manquantes).

---

**FIN – Ce document doit être fourni dans toute nouvelle conversation pour reprendre le projet efficacement.**
