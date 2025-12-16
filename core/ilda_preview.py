# core/ilda_preview.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from .ilda_writer import IldaPoint, IldaFrame

ILDA_MAGIC = b"ILDA"
ILDA_HEADER_SIZE = 32


def _read_u16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big", signed=False)


def _read_s16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "big", signed=True)


def load_ilda_frames(path: Path, max_frames: Optional[int] = None) -> List[IldaFrame]:
    """
    Lit un fichier ILDA et retourne les frames 2D:
      - format 1 : indexed color (x,y,status,color_index) 6 bytes/record
      - format 5 : true color    (x,y,status,r,g,b)       8 bytes/record

    Ignore proprement :
      - format 2 (palette)
      - autres formats non supportés
    """
    frames: List[IldaFrame] = []
    path = Path(path)

    with path.open("rb") as f:
        while True:
            if max_frames is not None and len(frames) >= max_frames:
                break

            header = f.read(ILDA_HEADER_SIZE)
            if len(header) == 0:
                break
            if len(header) < ILDA_HEADER_SIZE:
                raise RuntimeError("Header ILDA tronqué")

            if header[0:4] != ILDA_MAGIC:
                raise RuntimeError("Fichier ILDA invalide (magic manquant)")

            format_code = header[7]
            num_records = _read_u16_be(header, 24)

            name = header[8:16].decode("ascii", "ignore").rstrip("\x00")
            company = header[16:24].decode("ascii", "ignore").rstrip("\x00")
            projector = header[30]

            # EOF : dans la pratique, on considère format=0 + 0 record comme fin
            # (le writer peut mettre un nom "EoF")
            if format_code == 0 and num_records == 0:
                break

            # Palette (format 2) → skip (3 bytes/record)
            if format_code == 2:
                f.read(num_records * 3)
                continue

            # --- Format 5 : true color 2D (8 bytes/record)
            if format_code == 5:
                points: List[IldaPoint] = []
                for _ in range(num_records):
                    data = f.read(8)
                    if len(data) < 8:
                        raise RuntimeError("Données de point ILDA tronquées (format 5)")

                    x = _read_s16_be(data, 0)
                    y = _read_s16_be(data, 2)
                    status = data[4]
                    r = data[5]
                    g = data[6]
                    b = data[7]
                    blanked = bool(status & 0x40)

                    points.append(IldaPoint(x=x, y=y, blanked=blanked, r=r, g=g, b=b))

                frames.append(IldaFrame(name=name or "FRAME", company=company or "LPIP", points=points, projector=projector))
                continue

            # --- Format 1 : indexed color 2D (6 bytes/record)
            if format_code == 1:
                points = []
                for _ in range(num_records):
                    data = f.read(6)
                    if len(data) < 6:
                        raise RuntimeError("Données de point ILDA tronquées (format 1)")

                    x = _read_s16_be(data, 0)
                    y = _read_s16_be(data, 2)
                    status = data[4]
                    color_index = data[5]
                    blanked = bool(status & 0x40)

                    points.append(IldaPoint(x=x, y=y, blanked=blanked, color_index=color_index))

                frames.append(IldaFrame(name=name or "FRAME", company=company or "LPIP", points=points, projector=projector))
                continue

            # Autres formats → on saute les records si on peut, sinon stop.
            # On ne "devine" pas les tailles record: on arrête proprement.
            break

    return frames


def _ilda_to_screen(px: int, py: int, width: int, height: int, margin: int) -> Tuple[int, int]:
    span = 2 * 32767.0
    scale = min(
        (width - 2 * margin) / span,
        (height - 2 * margin) / span,
    )
    cx = width / 2.0
    cy = height / 2.0
    x = int(round(cx + px * scale))
    y = int(round(cy - py * scale))
    return x, y


def render_ilda_frame_to_png(
    frame: IldaFrame,
    out_png: Path,
    *,
    width: int = 640,
    height: int = 480,
    margin: int = 10,
) -> Path:
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    pts = list(frame.points or [])
    prev_xy: Optional[Tuple[int, int]] = None
    prev_rgb: Tuple[int, int, int] = (255, 255, 255)

    for pt in pts:
        x, y = _ilda_to_screen(pt.x, pt.y, width, height, margin)

        # couleur : si format 5, r/g/b seront renseignés (sinon defaults 0)
        # on garde blanc pour l'indexed (comportement historique, sans surprise)
        if getattr(pt, "r", 0) or getattr(pt, "g", 0) or getattr(pt, "b", 0):
            rgb = (int(pt.r), int(pt.g), int(pt.b))
        else:
            rgb = (255, 255, 255)

        if pt.blanked or prev_xy is None:
            prev_xy = (x, y)
            prev_rgb = rgb
            continue

        draw.line([prev_xy, (x, y)], fill=prev_rgb)
        prev_xy = (x, y)
        prev_rgb = rgb

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return out_png


def render_ilda_preview(
    ilda_path: Path,
    out_png: Path,
    *,
    frame_index: int = 0,
) -> Path:
    frames = load_ilda_frames(ilda_path)
    if not frames:
        raise RuntimeError("Aucune frame ILDA lisible")

    target = f"F{frame_index:04d}"
    for fr in frames:
        if (fr.name or "") == target:
            return render_ilda_frame_to_png(fr, out_png)

    return render_ilda_frame_to_png(frames[0], out_png)
