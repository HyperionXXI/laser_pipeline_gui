# GUI Validation Contract (Stability)

Objectif : chaque changement doit préserver ces comportements.
Si un item casse, on corrige avant d’ajouter des features.

## A. Build / import (obligatoire)
- [ ] `python -m compileall core gui` passe sans erreur
- [ ] `python -c "from gui.pipeline_controller import PipelineController; print('ok')"` -> ok
- [ ] `python -c "from core.pipeline.full_pipeline_step import run_full_pipeline_step; print('ok')"` -> ok
- [ ] `python gui_main.py` lance la fenêtre sans exception console

## B. UI / Preview (obligatoire)
- [ ] En redimensionnant la fenêtre (petit ⇄ fullscreen), les 4 previews restent visibles
- [ ] Même sans image chargée, les previews “stretchent” (fond noir, zones expansibles)
- [ ] Quand une image est chargée, elle est affichée en KeepAspectRatio et rescale au resize
- [ ] Aucun `AttributeError` lié à `show_image` / preview widgets

## C. Pipeline classic (smoke test)
- [ ] Sélectionner vidéo La Linea (ou autre), mode `classic`, max_frames=50
- [ ] Bouton “Exécuter 4 étapes” produit :
  - `projects/<project>/frames/frame_0001.png` (ou équivalent)
  - `projects/<project>/svg/frame_0001.svg`
  - `projects/<project>/<project>.ild`
  - `projects/<project>/preview/ilda_preview.png`
- [ ] Le log GUI annonce les sous-steps `ffmpeg`, `bitmap`, `potrace`, `ilda`

## D. Pipeline arcade (smoke test)
- [ ] Sélectionner vidéo arcade, mode `arcade`, max_frames=50
- [ ] Bouton “Exécuter 4 étapes” produit :
  - `projects/<project>/frames/...png`
  - `projects/<project>/<project>.ild`
  - `projects/<project>/preview/ilda_preview.png`
- [ ] Le log GUI annonce les sous-steps `ffmpeg`, `arcade_lines`

## E. Cancel (obligatoire)
- [ ] Cliquer “Annuler” pendant un step stoppe proprement le traitement
- [ ] Le GUI reste utilisable après annulation (pas de thread zombie, pas de lock UI)