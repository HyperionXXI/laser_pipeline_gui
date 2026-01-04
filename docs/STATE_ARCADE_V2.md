# Arcade v2 state (quick resume)

## Branch / release
- Stable branch: main
- Latest release tag: v0.2.0

## Functional status
- Classic pipeline: FFmpeg -> Bitmap -> Potrace -> ILDA works
- Arcade v2 pipeline: OpenCV -> lines -> ILDA truecolor works
- UI parameters persist per project in projects/<project>/settings.json

## ILDA files (binary check)
- Arcade: format 5 (truecolor), magic OK
- Classic: format 0 (indexed), magic OK

## Known issue
- GUI preview:
  - Classic: no readable ILDA frames
  - Arcade: incorrect "missing magic" message even though magic OK
- Cause: limitations in core/ilda_preview.py
  - format 0 (Classic) not supported
  - incorrect magic validation logic in preview (writer is OK)

## Next planned fix
1) Extend core/ilda_preview.py to support format 0 (indexed)
2) Fix preview magic validation
3) Re-check arcade line quality after preview fix

## Reference videos
- Classic: La Linea
- Arcade: Tempest (ARCADE)
