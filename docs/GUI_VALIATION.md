# GUI_VALIDATION.md
Contrat de stabilité UI pour laser_pipeline_gui

Objectif : éviter les régressions lors du refactor (découpage UI, services, adaptation pipeline).
Cette check-list doit être OK avant/après chaque commit significatif.

---

## A) Sanity / Import / Démarrage

- [ ] `python -c "import gui.main_window as m; print('ok')"` affiche `ok`
- [ ] `python gui_main.py` démarre sans exception
- [ ] Aucune erreur d’import (circulaire / module manquant)

---

## B) Menus / Raccourcis / Actions

- [ ] Les menus s’affichent (File / Project / View / Help ou équivalent)
- [ ] Les actions principales ne crashent pas :
  - [ ] Open Project…
  - [ ] Open Video…
  - [ ] New Project…
  - [ ] Clear generated outputs…
  - [ ] Reveal in Explorer…
  - [ ] Refresh previews (F5)
  - [ ] Toggle fullscreen (F11)
  - [ ] Exit
- [ ] F5 rafraîchit les previews (même si aucune vidéo n’est sélectionnée)

---

## C) Projet / Entrées (sans vidéo)

- [ ] Open Project fonctionne SANS vidéo
- [ ] Le champ projet est rempli et les chemins projet sont cohérents
- [ ] Reveal in Explorer ouvre le dossier du projet
- [ ] Clear outputs ne crash pas (même si les dossiers n’existent pas / sont vides)

---

## D) "Tester les paramètres" doit être utile

- [ ] Le log affiche au minimum :
  - [ ] project root + exists True/False
  - [ ] video path + exists True/False (si défini)
  - [ ] counts : frames FFmpeg / BMP / SVG / ILD
  - [ ] mode actuel : classic / arcade (v2)
  - [ ] warnings explicites si un output manque (ex: "⚠️ BMP manquants")
- [ ] Ne doit jamais afficher seulement "OK"

---

## E) Previews (robustesse + resize)

- [ ] Previews affichent un placeholder si fichier absent
- [ ] KeepAspectRatio correct au resize
- [ ] Refresh previews (F5) met à jour l’affichage sans crash
- [ ] Preview ILDA (frame N) fonctionne (si .ild présent)
- [ ] Aucune colonne preview ne "s’écrase" quand step2/step3 sont absents

---

## F) Contrat Busy / Progress / Cancel (général)

- [ ] Pendant un step :
  - [ ] boutons Run désactivés
  - [ ] Cancel activé
  - [ ] progress visible (bar + texte)
- [ ] En fin de step :
  - [ ] UI revient idle
  - [ ] progress réinitialisé / status propre
- [ ] En cas d’erreur :
  - [ ] message clair dans le log
  - [ ] UI revient idle
  - [ ] on peut relancer un step après

- [ ] Cancel pendant un step :
  - [ ] stoppe effectivement le traitement
  - [ ] UI revient idle
  - [ ] ne laisse pas l’app dans un état incohérent

---

## G) Mode Classic : pipeline complet

Mettre mode = classic.

- [ ] Run FFmpeg : progress atteint 100%
- [ ] Run Bitmap : progress atteint 100%
- [ ] Run Potrace : progress atteint 100%
- [ ] Run ILDA : progress atteint 100%
- [ ] Run All produit un `.ild` final
- [ ] Cancel fonctionne au moins sur FFmpeg et Potrace

---

## H) Mode Arcade v2 : pipeline complet

Mettre mode = arcade (v2).

- [ ] Run All produit un `.ild` final
- [ ] Potrace / Bitmap ne sont PAS exécutés (via logs/événements)
- [ ] progress atteint 100%
- [ ] Cancel fonctionne pendant ArcadeLines
- [ ] UI n’affiche pas de "Step2/Step3 requis" (soit grisés, soit marqués N/A)

---

## I) Trace d’événements (anti-régressions)

Le log UI doit permettre de prouver l’enchaînement, par ex :

- [ ] `STEP_STARTED name=...`
- [ ] `STEP_PROGRESS name=... i/n`
- [ ] `STEP_FINISHED name=...`
- [ ] `STEP_ERROR name=... msg=...`

Sans cette trace, il devient difficile de vérifier "Potrace ne tourne pas en arcade".
