# core/ilda_preview.py

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw  # pip install pillow

from .step_ilda import ILDAPoint, ILDAFrame


ILDA_HEADER_SIZE = 32
ILDA_MAGIC = b"ILDA"


def _read_u16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset+2], "big", signed=False)


def _read_s16_be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset+2], "big", signed=True)


def load_ilda_frames(path: Path) -> List[ILDAFrame]:
    """
    Lit un fichier ILDA (format 0 = 3D indexed) et retourne une liste de ILDAFrame.
    Ignore la frame EOF (0 points).
    """
    frames: List[ILDAFrame] = []
    path = Path(path)

    with path.open("rb") as f:
        while True:
            header = f.read(ILDA_HEADER_SIZE)
            if len(header) == 0:
                break  # fin de fichier
            if len(header) < ILDA_HEADER_SIZE:
                raise RuntimeError("Header ILDA tronqué")

            if header[0:4] != ILDA_MAGIC:
                raise RuntimeError("Fichier ILDA invalide (magic manquant)")

            format_code = int.from_bytes(header[4:8], "big", signed=False)
            if format_code != 0:
                raise RuntimeError(f"Format ILDA non supporté: {format_code} (seul 0 est géré)")

            num_points = _read_u16_be(header, 24)
            # seq_no      = _read_u16_be(header, 26)
            # total_frames = _read_u16_be(header, 28)
            projector = header[30]

            # Frame EOF : num_points == 0
            if num_points == 0:
                break

            points: List[ILDAPoint] = []

            for i in range(num_points):
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
                    ILDAPoint(
                        x=x,
                        y=y,
                        z=z,
                        blanked=blanked,
                        color_index=color_index,
                    )
                )

            frame = ILDAFrame(
                name="",      # pas nécessaire pour la preview
                company="",
                points=points,
                projector=projector,
            )
            frames.append(frame)

    return frames


def render_ilda_frame_to_png(
    ilda_path: Path,
    out_png_path: Path,
    frame_index: int = 0,
    size: Tuple[int, int] = (512, 512),
    margin: int = 10,
) -> Path:
    """
    Rend une frame ILDA en image PNG.

    - ilda_path   : chemin du .ild
    - out_png_path: chemin de sortie du PNG (dirs créées au besoin)
    - frame_index : index de la frame à rendre (0 = première)
    - size        : taille de l'image (w, h)
    - margin      : marge en pixels autour du dessin
    """
    ilda_path = Path(ilda_path)
    out_png_path = Path(out_png_path)

    frames = load_ilda_frames(ilda_path)
    if not frames:
        raise RuntimeError("Aucune frame dans le fichier ILDA")

    idx = max(0, min(frame_index, len(frames) - 1))
    frame = frames[idx]

    # Création de l'image
    w, h = size
    img = Image.new("RGB", (w, h), "black")
    draw = ImageDraw.Draw(img)

    # Conversion ILDA [-32768..32767] → coords écran
    span_ilda = 2 * 32767
    scale_x = (w - 2 * margin) / span_ilda
    scale_y = (h - 2 * margin) / span_ilda
    scale = min(scale_x, scale_y)

    cx = w / 2.0
    cy = h / 2.0

    def ilda_to_screen(px: int, py: int) -> Tuple[int, int]:
        # py inversé : ILDA Y vers le haut, écran Y vers le bas
        x = int(round(cx + px * scale))
        y = int(round(cy - py * scale))
        return x, y

    prev: Tuple[int, int] | None = None

    for pt in frame.ensure_points():
        x, y = ilda_to_screen(pt.x, pt.y)

        if pt.blanked:
            # déplacement sans tracer
            prev = (x, y)
            continue

        if prev is not None:
            # couleur simple : blanc
            draw.line([prev, (x, y)], fill=(255, 255, 255))

        prev = (x, y)

    out_png_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png_path)
    return out_png_path
