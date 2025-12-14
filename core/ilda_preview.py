# core/ilda_preview.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from .ilda_writer import IldaPoint, IldaFrame

ILDA_MAGIC = b"ILDA"
ILDA_HEADER_SIZE = 32


# ======================================================================
# Helpers bas niveau
# ======================================================================

def _read_u16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "big", signed=False)


def _read_s16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "big", signed=True)


# ======================================================================
# Lecture ILDA (preview-safe)
# ======================================================================

def load_ilda_frames(path: Path, max_frames: Optional[int] = None) -> List[IldaFrame]:
    """
    Lit un fichier ILDA et retourne uniquement les frames format 0 (3D indexed).
    Ignore proprement les sections palette (format 2) et true color (format 5).
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

            # EOF finale
            if format_code == 0 and num_records == 0 and not name and not company:
                break

            # Palette (format 2) → skip
            if format_code == 2:
                f.read(num_records * 3)
                continue

            # True color (format 5) → skip (8 bytes par point)
            if format_code == 5:
                f.read(num_records * 8)
                continue

            # Autres formats → abandon preview
            if format_code != 0:
                break

            points: List[IldaPoint] = []

            for _ in range(num_records):
                data = f.read(8)
                if len(data) < 8:
                    raise RuntimeError("Données de point ILDA tronquées")

                x = _read_s16_be(data, 0)
                y = _read_s16_be(data, 2)
                z = _read_s16_be(data, 4)
                status = data[6]
                color_index = data[7]

                blanked = bool(status & 0x40)

                points.append(
                    IldaPoint(
                        x=x,
                        y=y,
                        z=z,
                        blanked=blanked,
                        color_index=color_index,
                    )
                )

            frames.append(
                IldaFrame(
                    name=name,
                    company=company,
                    points=points,
                    projector=projector,
                )
            )

    return frames


# ======================================================================
# Rendu PNG
# ======================================================================

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

    prev = None
    for pt in frame.ensure_points():
        x, y = _ilda_to_screen(pt.x, pt.y, width, height, margin)
        if pt.blanked or prev is None:
            prev = (x, y)
            continue
        draw.line([prev, (x, y)], fill=(255, 255, 255))
        prev = (x, y)

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
        if fr.name == target:
            return render_ilda_frame_to_png(fr, out_png)

    return render_ilda_frame_to_png(frames[0], out_png)
