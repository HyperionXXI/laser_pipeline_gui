# Arcade v2 state (quick resume)

## Branch / release
- Stable branch: main
- Latest release tag: v0.2.0

## Functional status
- Classic pipeline: FFmpeg -> Bitmap -> Potrace -> ILDA works
- Arcade v2 pipeline: OpenCV -> lines -> ILDA truecolor works
- ILDA preview supports formats 0/1/4/5 (indexed + truecolor)
- UI parameters persist per project in projects/<project>/settings.json

## ILDA files (binary check)
- Arcade: format 5 (truecolor), magic OK
- Classic: format 0 (indexed), magic OK

## Known issue
- None tracked for ILDA preview at this time.

## Next planned fix
1) Re-check arcade line quality and tuning (OpenCV params)

## Reference videos
- Classic: La Linea
- Arcade: Tempest (ARCADE)
