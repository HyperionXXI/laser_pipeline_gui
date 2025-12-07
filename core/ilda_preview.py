# core/ilda_preview.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from .ilda_writer import IldaPoint, IldaFrame

ILDA_MAGIC = b"ILDA"
ILDA_HEADER_SIZE = 32


# ======================================================================
# Lecture ILDA (format 0)
# ======================================================================


def _read_u16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "big", signed=False)


def _read_s16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "big", signed=True)


def load_ilda_frames(path: Path, max_frames: Optional[int] = None) -> List[IldaFrame]:
    """
    Lit un fichier ILDA (format 0 = 3D indexed) et retourne une liste de IldaFrame.

    - `max_frames` : si non nul, limite le nombre de frames lues.
    - Les frames avec 0 points sont conservées (frames vides) afin de
      garder la synchronisation avec la vidéo.
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
                break  # fin de fichier
            if len(header) < ILDA_HEADER_SIZE:
                raise RuntimeError("Header ILDA tronqué")

            if header[0:4] != ILDA_MAGIC:
                raise RuntimeError("Fichier ILDA invalide (magic manquant)")

            format_code = int.from_bytes(header[4:8], "big", signed=False)
            if format_code != 0:
                raise RuntimeError(
                    f"Format ILDA non supporté: {format_code} (seul 0 est géré)"
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


# ======================================================================
# Rendu en PNG
# ======================================================================


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

    - `frame_index` est l'index de **frame vidéo** (0-based).
      On cherche la frame ILDA dont le champ `name` vaut `Fxxxx` (xxxx
      = frame_index sur 4 digits). Si elle n'existe pas, on prend la
      frame dont le numéro dans `name` est le plus proche, ou la première
      frame si aucune info exploitable n'est disponible.
    """
    frames = load_ilda_frames(ilda_path, max_frames=None)
    if not frames:
        raise RuntimeError("Aucune frame ILDA lisible dans le fichier")

    target_name = f"F{frame_index:04d}"

    # 1) Recherche exacte sur le nom de frame
    selected: Optional[IldaFrame] = None
    for fr in frames:
        if fr.name == target_name:
            selected = fr
            break

    # 2) Si non trouvé, on cherche la frame "la plus proche"
    if selected is None:
        target_num = frame_index
        best_frame: Optional[IldaFrame] = None
        best_dist: Optional[int] = None

        for fr in frames:
            if not fr.name:
                continue
            # On tolère "F0123" ou "0123"
            name = fr.name
            if name[0] in ("F", "f"):
                name = name[1:]
            try:
                num = int(name)
            except ValueError:
                continue

            dist = abs(num - target_num)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_frame = fr

        if best_frame is not None:
            selected = best_frame
        else:
            selected = frames[0]

    return render_ilda_frame_to_png(selected, out_png)
