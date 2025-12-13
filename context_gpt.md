# Projet `laser_pipeline_gui` – Contexte technique consolidé pour ChatGPT

**Version : 2025-12-13**  
**Commit de référence : `540716c` (SHA complet `540716cef5533ef1f557dc9a07949ed7e0d4b4f9`)**  
Dépôt public : https://github.com/HyperionXXI/laser_pipeline_gui  
Le développeur autorise explicitement ChatGPT à consulter ce dépôt.

---

## 0. Objectif de ce document (IMPORTANT)

Ce fichier sert de **mémoire technique stable** pour :
- reprendre le projet dans une nouvelle conversation **sans perte de contexte** ;
- éviter les **erreurs récurrentes** (mauvaise arborescence, fichiers inexistants, imports circulaires) ;
- préserver les **décisions d’architecture déjà validées** ;
- permettre à ChatGPT de raisonner comme un **développeur senior reprenant un projet existant**, et non comme un générateur de code isolé.

👉 **Règle absolue** : toute discussion future doit se baser sur **CE document** et sur l’arborescence décrite ci-dessous.

---

## 1. Arborescence CANONIQUE du dépôt (à ne pas remettre en question)

Issue directement de `arbo_clean.txt`, sans `.venv` ni bruit :

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

### Règles structurelles strictes
- ❌ Ne jamais réintroduire `core/step_*.py`
- ❌ Ne jamais inventer `core/steps/`, `pipeline/steps/`, etc.
- ✅ Toute orchestration = `core/pipeline/*_step.py`
- ✅ Toute logique métier = `core/*.py`

---

## 2. Philosophie d’architecture (VERROUILLÉE)

### 2.1 Séparation des responsabilités

| Couche | Rôle |
|------|------|
| `core/*.py` | Logique métier pure (FFmpeg, bitmap, Potrace, ILDA) |
| `core/pipeline/*_step.py` | Orchestration, callbacks, gestion erreurs |
| `gui/` | Interface utilisateur PySide6 |
| `projects/` | Données générées (jamais de logique) |

👉 **Règle clé** :  
`core/pipeline/*_step.py` peut importer `core/*.py`  
`core/*.py` **ne doit jamais importer** `core/pipeline/*`

---

## 3. Objectif fonctionnel du projet

Créer une **GUI Python (PySide6)** qui automatise la conversion :

```
Vidéo MP4
 → Frames PNG (FFmpeg)
 → Bitmap BMP (seuil + thinning)
 → Vectorisation SVG (Potrace)
 → Animation ILDA (.ild)
```

Avec :
- prévisualisations à chaque étape,
- conservation stricte du nombre de frames,
- fichiers ILDA propres (sans cadre parasite).

---

## 4. Pipeline logique (immuable)

1. **FFmpeg**
   - Entrée : MP4
   - Sortie : `projects/<project>/frames/frame_0001.png`
2. **Bitmap**
   - PNG → BMP
   - Seuil (%) + thinning optionnel
3. **Potrace**
   - BMP → SVG
4. **ILDA**
   - SVG → points ILDA
   - Export `.ild`

---

## 5. Couche `core.pipeline` – API standardisée

### 5.1 Types communs (`base.py`)
- `StepResult`
  - `success: bool`
  - `message: str`
  - `output_dir: Optional[Path]`
- `ProgressCallback`
- `CancelCallback`

👉 Les signatures doivent être **identiques partout** (GUI incluse).

### 5.2 Steps
Chaque step :
- encapsule un module `core/*.py`,
- gère exceptions,
- ne fait **aucune logique métier lourde**.

---

## 6. Règles ILDA (CRITIQUES)

- Une frame vide **n’est jamais supprimée**.
- Si aucun point visible :
  - ajouter **un point blanked unique** au centre `(0,0)`.
- Le premier point de chaque chemin est toujours `blanked=True`.

👉 Ceci évite toute désynchronisation temporelle.

---

## 7. Problème central restant (PRIORITÉ #1)

### Symptôme
- Apparition d’un **cadre/rectangle parasite** dans LaserShowGen.

### Observations validées
- Le cadre disparaît si on **inverse manuellement la polarité BMP**.
- Le problème est **amont**, pas ILDA.

### Cause la plus probable
- Potrace vectorise le **fond** au lieu du trait utile
- Problème de noir/blanc (foreground/background)

### Où corriger
✅ `core/potrace_vectorize.py`  
✅ `core/pipeline/potrace_step.py`  
❌ PAS dans `ilda_export.py`  
❌ PAS dans la GUI

---

## 8. Priorités de travail recommandées

1. Stabiliser définitivement la polarité BMP → Potrace
2. Rendre la progression GUI fiable à 100 %
3. Réduction des lignes parasites SVG
4. Tests reproductibles (frames repères)
5. Robustesse (rerun pipeline, nettoyage dossiers)

---

## 9. Instructions explicites pour ChatGPT (à respecter)

- Le dépôt est public et consultable.
- Le commit de référence est `540716c`.
- L’arborescence ci-dessus est **canonique**.
- Ne jamais proposer une refonte globale sans demande explicite.
- Ne jamais ignorer une décision documentée ici.
- Toujours analyser avant de coder.

---

**FIN DU DOCUMENT – Toute conversation future doit s’appuyer sur ce fichier.**
