# core/ilda_preview.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

from PIL import Image, ImageDraw  # pillow
from .ilda_writer import IldaPoint, IldaFrame


ILDA_MAGIC = b"ILDA"
ILDA_HEADER_SIZE = 32


# ----------------------------------------------------------------------
# Lecture ILDA
# ----------------------------------------------------------------------

def _read_u16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "big", signed=False)


def _read_s16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "big", signed=True)


def load_ilda_frames(path: Path,
                     max_frames: Optional[int] = None) -> List[IldaFrame]:
    """
    Lit un fichier ILDA (format 0) et retourne une liste de IldaFrame.

    - max_frames : si non None, limite le nombre de frames lues.
    """
    frames: List[IldaFrame] = []

    with path.open("rb") as f:
        while True:
            header = f.read(ILDA_HEADER_SIZE)
            if len(header) < ILDA_HEADER_SIZE:
                break

            if header[0:4] != ILDA_MAGIC:
                # Fin de fichier ou données invalides
                break

            # Dans notre writer, le format est stocké dans les octets 4..7
            format_code = int.from_bytes(header[4:8], "big", signed=False)
            name = header[8:16].decode("ascii", errors="ignore").rstrip("\x00")
            company = header[16:24].decode("ascii", errors="ignore").rstrip("\x00")
            num_points = _read_u16_be(header, 24)
            # seq_no       = _read_u16_be(header, 26)
            # total_frames = _read_u16_be(header, 28)
            projector = header[30]

            # Frame « EOF » selon la spec
            if num_points == 0:
                break

            # Si jamais on tombait sur un autre format, on saute les points
            if format_code != 0:
                f.read(num_points * 8)
                continue

            points: List[IldaPoint] = []
            for _ in range(num_points):
                data = f.read(8)
                if len(data) < 8:
                    raise RuntimeError("Données ILDA tronquées")

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
                    company=company or "LPIP",
                    points=points,
                    projector=projector,
                )
            )

            if max_frames is not None and len(frames) >= max_frames:
                break

    return frames


# ----------------------------------------------------------------------
# Rendu en PNG
# ----------------------------------------------------------------------

def _ilda_to_screen(
    px: int,
    py: int,
    width: int,
    height: int,
    margin: int,
) -> Tuple[int, int]:
    """
    Conversion coordonnées ILDA -> coordonnées écran.

    On suppose que l'espace ILDA utile est [-32767, +32767] sur X et Y.
    """
    span_ilda = 2 * 32767.0
    scale_x = (width - 2 * margin) / span_ilda
    scale_y = (height - 2 * margin) / span_ilda
    scale = min(scale_x, scale_y)

    cx = width / 2.0
    cy = height / 2.0

    x = int(round(cx + px * scale))
    # Inversion Y (ILDA vers le haut, écran vers le bas)
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
    """
    Rend une IldaFrame en image PNG (traits blancs sur fond noir).
    """
    img = Image.new("RGB", (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    pts = frame.ensure_points()
    prev: Optional[Tuple[int, int]] = None

    for pt in pts:
        x, y = _ilda_to_screen(pt.x, pt.y, width, height, margin)

        if pt.blanked or prev is None:
            # Déplacement sans tracer (blanked) ou tout premier point
            prev = (x, y)
            continue

        # Segment lumineux
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
    """
    Rendu pratique : charge le fichier ILDA et génère un PNG pour une frame.
    Par défaut, la première frame non vide.
    """
    frames = load_ilda_frames(ilda_path, max_frames=frame_index + 1)
    if not frames:
        raise RuntimeError("Aucune frame ILDA lisible dans le fichier")

    if frame_index < len(frames):
        frame = frames[frame_index]
    else:
        frame = frames[0]

    return render_ilda_frame_to_png(frame, out_png)
