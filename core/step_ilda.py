# core/step_ilda.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Iterable, Tuple
import re
import xml.etree.ElementTree as ET

from pathlib import Path
from core.config import PROJECTS_ROOT
from collections.abc import Callable
from dataclasses import dataclass

@dataclass
class Point:
    x: int
    y: int
    z: int = 0
    r: int = 255
    g: int = 255
    b: int = 255
    blanked: bool = False

# ======================================================================
# Structures ILDA
# ======================================================================

@dataclass
class ILDAPoint:
    """Un point ILDA en 3D (Z=0 pour nous), avec gestion du blanking."""
    x: int
    y: int
    z: int = 0
    blanked: bool = False
    color_index: int = 255  # index dans la palette ILDA


@dataclass
class ILDAFrame:
    """Une frame ILDA (un dessin)."""
    name: str = "FRAME"
    company: str = "LPIP"
    points: List[ILDAPoint] | None = None
    projector: int = 0  # 0–255

    def ensure_points(self) -> List[ILDAPoint]:
        if self.points is None:
            self.points = []
        return self.points


# ======================================================================
# Writer ILDA bas niveau (format code 0 = 3D indexed)
# ======================================================================

def _build_ilda_header_3d(frame: ILDAFrame, num_points: int,
                          seq_no: int, total_frames: int) -> bytes:
    """
    Construit un header ILDA 3D (format code 0) de 32 octets.
    Spécification ILDA : 3D coordinate image section.
    """
    header = bytearray(32)

    # 1–4 : "ILDA"
    header[0:4] = b"ILDA"

    # 5–8 : format code (32 bits big endian) => 0 pour 3D indexed
    header[4:8] = (0).to_bytes(4, "big", signed=False)

    # 9–16 : frame name (8 bytes, ASCII, padded with 0)
    frame_name = (frame.name or "").encode("ascii", "replace")[:8]
    header[8:16] = frame_name.ljust(8, b"\x00")

    # 17–24 : company name (8 bytes)
    company = (frame.company or "").encode("ascii", "replace")[:8]
    header[16:24] = company.ljust(8, b"\x00")

    # 25–26 : total points in this frame (1..65535, 0 = EOF frame)
    header[24:26] = num_points.to_bytes(2, "big", signed=False)

    # 27–28 : frame number
    header[26:28] = seq_no.to_bytes(2, "big", signed=False)

    # 29–30 : total frames
    header[28:30] = total_frames.to_bytes(2, "big", signed=False)

    # 31 : scanner / projector number
    header[30] = frame.projector & 0xFF

    # 32 : reserved = 0
    header[31] = 0

    return bytes(header)


def _pack_ilda_point(pt: ILDAPoint, is_last: bool) -> bytes:
    """
    Encode un point ILDA (3D) :
        X (2 bytes signed)
        Y (2 bytes signed)
        Z (2 bytes signed)
        Status (1 byte)
        Color index (1 byte)
    """
    status = 0
    if is_last:
        status |= 0x80  # last point bit
    if pt.blanked:
        status |= 0x40  # blanking bit

    return (
        int(pt.x).to_bytes(2, "big", signed=True) +
        int(pt.y).to_bytes(2, "big", signed=True) +
        int(pt.z).to_bytes(2, "big", signed=True) +
        bytes((status & 0xFF, pt.color_index & 0xFF))
    )


def write_ilda_file(path: str | Path, frames: Iterable[ILDAFrame]) -> Path:
    """
    Écrit un fichier ILDA avec une ou plusieurs frames (3D indexed).
    Ajoute à la fin une frame spéciale avec 0 points pour marquer EOF.
    """
    out_path = Path(path)
    frames_list = list(frames)
    total_frames = len(frames_list)

    with out_path.open("wb") as f:
        for seq_no, frame in enumerate(frames_list):
            pts = frame.ensure_points()
            num_points = len(pts)

            # Header
            header = _build_ilda_header_3d(frame, num_points, seq_no, total_frames)
            f.write(header)

            # Points
            for i, p in enumerate(pts):
                f.write(_pack_ilda_point(p, is_last=(i == num_points - 1)))

        # Frame EOF : header avec num_points=0
        eof_frame = ILDAFrame(name="", company="", points=[])
        eof_header = _build_ilda_header_3d(eof_frame, num_points=0,
                                           seq_no=0, total_frames=0)
        f.write(eof_header)

    return out_path


# ======================================================================
# Démo : carré de test, pour valider le format dans LaserOS
# ======================================================================

def write_demo_square(path: str | Path) -> Path:
    """
    Écrit un carré simple, centré, avec 4 couleurs différentes
    sur chaque côté. Utilisé pour les tests (tests/test_ilda_square.py).
    """
    out_path = Path(path)

    size = 20000  # +- 20000 dans l'espace ILDA (-32768..32767)
    left, right = -size, size
    bottom, top = -size, size

    pts: List[ILDAPoint] = []

    # On part du coin haut-gauche, blanked pour "sauter" depuis n'importe où.
    pts.append(ILDAPoint(left, top, 0, blanked=True, color_index=1))   # start
    pts.append(ILDAPoint(right, top, 0, blanked=False, color_index=1))  # haut (jaune / cyan selon palette)
    pts.append(ILDAPoint(right, bottom, 0, blanked=False, color_index=2))  # droite
    pts.append(ILDAPoint(left, bottom, 0, blanked=False, color_index=3))   # bas
    pts.append(ILDAPoint(left, top, 0, blanked=False, color_index=4))      # gauche

    frame = ILDAFrame(
        name="SQUARE",
        company="LPIP",
        points=pts,
        projector=0,
    )

    return write_ilda_file(out_path, [frame])


# ======================================================================
# Conversion SVG → ILDA
# ======================================================================

# Regex très simple pour parser les commandes M/L/H/V/Z (absolues/relatives)
_PATH_TOKEN_RE = re.compile(r"([MmLlHhVvZz])|(-?\d+(?:\.\d+)?)")


def _parse_svg_path_d(d: str) -> List[Tuple[float, float]]:
    """
    Parse très simplifié de la commande 'd' des <path>.
    Supporte : M/m, L/l, H/h, V/v, Z/z.
    Retourne une liste de (x, y) en coordonnées SVG.
    """
    tokens = _PATH_TOKEN_RE.findall(d)
    points: List[Tuple[float, float]] = []

    current_cmd: str | None = None
    buf: List[float] = []
    x = y = 0.0
    first_point_of_path: Tuple[float, float] | None = None

    for cmd, num in tokens:
        if cmd:
            current_cmd = cmd
            buf = []

            if cmd in "Zz" and first_point_of_path is not None:
                # Fermer le path : on revient au premier point
                points.append(first_point_of_path)
            continue

        # nombre
        v = float(num)
        buf.append(v)

        def flush_xy(nx: float, ny: float):
            nonlocal x, y, first_point_of_path
            x, y = nx, ny
            points.append((x, y))
            if first_point_of_path is None:
                first_point_of_path = (x, y)

        if current_cmd in ("M", "L"):
            if len(buf) >= 2:
                flush_xy(buf[0], buf[1])
                buf = buf[2:]
        elif current_cmd in ("m", "l"):
            if len(buf) >= 2:
                dx, dy = buf[0], buf[1]
                flush_xy(x + dx, y + dy)
                buf = buf[2:]
        elif current_cmd in ("H",):
            # H x
            flush_xy(v, y)
            buf = []
        elif current_cmd in ("h",):
            flush_xy(x + v, y)
            buf = []
        elif current_cmd in ("V",):
            flush_xy(x, v)
            buf = []
        elif current_cmd in ("v",):
            flush_xy(x, y + v)
            buf = []

    return points

def svg_to_points(svg_path: Path) -> list[Point]:
    """
    TODO: convertir un SVG en liste de points ILDA.
    Pour l'instant, stub qui retourne une liste vide.
    """
    return []

def _svg_file_to_points(svg_path: Path) -> List[ILDAPoint]:
    """
    Lit un SVG vectorisé (Potrace) et retourne une liste de ILDAPoint.
    Hypothèses simplificatrices :
      - On suit tous les <path>, <polyline>, <polygon>.
      - On met le bit "blanked" uniquement sur le premier point de chaque path
        pour éviter les segments parasites entre deux formes.
      - Couleur : index 255 (blanc) pour tous les points (on gèrera
        la colorisation plus tard).
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Gestion des namespaces SVG
    def is_tag(elem, local_name: str) -> bool:
        return elem.tag.endswith("}" + local_name) or elem.tag == local_name

    all_points: List[Tuple[float, float, bool]] = []  # (x, y, is_start_of_path)

    # Parcours de tous les paths / polylines / polygons
    for elem in root.iter():
        if is_tag(elem, "path"):
            d = elem.get("d") or ""
            xy = _parse_svg_path_d(d)
        elif is_tag(elem, "polyline") or is_tag(elem, "polygon"):
            pts_str = elem.get("points") or ""
            coords: List[float] = []
            for tok in pts_str.replace(",", " ").split():
                try:
                    coords.append(float(tok))
                except ValueError:
                    pass
            xy = list(zip(coords[0::2], coords[1::2]))
            if is_tag(elem, "polygon") and xy:
                xy.append(xy[0])  # fermer le polygone
        else:
            continue

        if not xy:
            continue

        first = True
        for x, y in xy:
            all_points.append((x, y, first))
            first = False

    if not all_points:
        return []

    # Normalisation vers l'espace ILDA [-32768 .. +32767]
    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0
    span = max(span_x, span_y)

    # marge de 80 % de la fenêtre ILDA pour éviter le clipping
    scale = (32767 * 0.8) / span

    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    result: List[ILDAPoint] = []
    for x, y, is_start in all_points:
        nx = int(round((x - cx) * scale))
        ny = int(round((cy - y) * scale))  # inversion de l’axe Y
        result.append(
            ILDAPoint(
                x=nx,
                y=ny,
                z=0,
                blanked=is_start,      # premier point du path : blanked
                color_index=255,       # blanc (palette ILDA standard)
            )
        )

    return result


# ======================================================================
# Étape pipeline : export ILDA pour un projet
# ======================================================================


def export_project_to_ilda(project_name: str) -> Path:
    """
    Export ILDA pour un projet donné.
    - Cherche les SVG dans projects/<project_name>/svg
    - Écrit un fichier .ild dans projects/<project_name>/ilda/<project_name>.ild
    - Retourne le Path du fichier créé.
    """
    project_root = PROJECTS_ROOT / project_name
    svg_dir = project_root / "svg"
    ilda_dir = project_root / "ilda"
    ilda_dir.mkdir(parents=True, exist_ok=True)

    out_path = ilda_dir / f"{project_name}.ild"

    # TODO: ici tu appelles ton vrai writer ILDA en utilisant les SVG.
    # Pour l'instant, on peut faire un placeholder minimal ou réutiliser ton code de démo.
    # Exemple minimal :
    with out_path.open("wb") as f:
        f.write(b"ILDA")  # pour ne pas avoir un fichier vide

    return out_path


