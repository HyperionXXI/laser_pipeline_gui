# core/ilda_preview.py
from __future__ import annotations

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
    """Lit un entier non signé 16 bits big-endian à partir de data[offset:]."""
    return int.from_bytes(data[offset:offset + 2], "big", signed=False)


def _read_s16_be(data: bytes, offset: int) -> int:
    """Lit un entier signé 16 bits big-endian à partir de data[offset:]."""
    return int.from_bytes(data[offset:offset + 2], "big", signed=True)


def load_ilda_frames(path: Path, max_frames: Optional[int] = None) -> List[IldaFrame]:
    """
    Lit un fichier ILDA (format 0 = 3D Indexed) et retourne une liste de IldaFrame.

    - max_frames : si non nul, limite le nombre de frames lues.
    - Les frames avec 0 points sont conservées (frames vides) afin de garder
      la synchronisation avec la vidéo.
    - La seule frame ignorée est la frame EOF finale (nom et société vides,
      num_points == 0), si elle est présente.
    """
    frames: List[IldaFrame] = []
    path = Path(path)

    with path.open("rb") as f:
        while True:
            if max_frames is not None and len(frames) >= max_frames:
                break

            header = f.read(ILDA_HEADER_SIZE)
            if len(header) == 0:
                # Fin de fichier
                break
            if len(header) < ILDA_HEADER_SIZE:
                raise RuntimeError("Header ILDA tronqué")

            if header[0:4] != ILDA_MAGIC:
                raise RuntimeError("Fichier ILDA invalide (magic 'ILDA' absent)")

            # Spécification ILDA :
            #   4..6 : 3 octets réservés (0)
            #   7    : format code (0 = 3D indexed)
            format_code = header[7]
            if format_code != 0:
                raise RuntimeError(
                    f"Format ILDA non supporté : {format_code} (seul 0 est géré)"
                )

            num_points = _read_u16_be(header, 24)
            projector = header[30]

            name = header[8:16].decode("ascii", "ignore").rstrip("\x00")
            company = header[16:24].decode("ascii", "ignore").rstrip("\x00")

            # Frame EOF finale : nom et société vides + 0 points
            if num_points == 0 and not name and not company:
                break

            points: List[IldaPoint] = []

            for _ in range(num_points):
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

            frame = IldaFrame(
                name=name,
                company=company,
                points=points,
                projector=projector,
            )
            frames.append(frame)

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

    - frame_index est 0-based (0 = première frame du fichier).
    """
    # On ne lit que les frames nécessaires pour atteindre frame_index.
    max_frames = frame_index + 1 if frame_index >= 0 else None
    frames = load_ilda_frames(ilda_path, max_frames=max_frames)
    if not frames:
        raise RuntimeError("Aucune frame ILDA lisible dans le fichier")

    if frame_index < len(frames):
        frame = frames[frame_index]
    else:
        # Sécurité : si l'index demandé dépasse ce qui a été lu,
        # on se rabat sur la première frame.
        frame = frames[0]

    return render_ilda_frame_to_png(frame, out_png)
