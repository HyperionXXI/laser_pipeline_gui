# État du projet — Arcade v2 (point de reprise)

## Branche
- feature/arcade-v2-stabilize
- working tree clean
- tout est pushé sur GitHub

## Fonctionnel OK
- Pipeline Classic (FFmpeg → Bitmap → Potrace → ILDA)
- Pipeline Arcade v2 (OpenCV → skeleton → polylines → ILDA truecolor)
- Preview GUI ILDA fonctionnelle
- Preview truecolor Arcade OK
- invert_y géré proprement côté Arcade
- sample_color activé pour Arcade
- chemins ILDA résolus correctement côté GUI

## État des fichiers ILDA (vérifié en binaire)
- Arcade: format 5 (truecolor), magic OK
- Classic: format 0 (indexed), magic OK

## Problème ACTUEL
- Preview GUI:
  - Classic: “Aucune frame ILDA lisible”
  - Arcade: message erroné “magic manquant” alors que magic OK
- Cause identifiée: limitation de `ilda_preview.py`
  - format 0 (Classic) non supporté
  - erreur de logique côté preview, pas côté writer

## Prochaine action prévue
1. Étendre `ilda_preview.py` pour supporter format 0 (indexed 3D)
2. Corriger la logique de validation “magic” côté preview
3. Revenir ensuite à la qualité du trait (OpenCV)

## Vidéos de référence
- Classic: La Linea
- Arcade: Tempest (ARCADE)
