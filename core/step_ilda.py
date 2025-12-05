# core/step_ilda.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple, Callable

import re
import xml.etree.ElementTree as ET

from .config import PROJECTS_ROOT


# ======================================================================
# Structures ILDA bas niveau
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
# Writer ILDA bas niveau (format 0 = 3D indexed)
# ======================================================================

def _build_ilda_header_3d(frame: ILDAFrame, num_points: int,
                          seq_no: int, total_frames: int) -> bytes:
    """
    Construit un header ILDA 3D (format code 0) de 32 octets.
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
# Démo : carré de test
# ======================================================================

def write_demo_square(path: str | Path) -> Path:
    """
    Écrit un carré simple, centré, avec 4 côtés.
    Toujours pratique pour tester dans LaserOS.
    """
    out_path = Path(path)

    size = 20000  # +- 20000 dans l'espace ILDA (-32768..32767)
    left, right = -size, size
    bottom, top = -size, size

    pts: List[ILDAPoint] = []

    # On part du coin haut-gauche, blanked pour "sauter" depuis n'importe où.
    pts.append(ILDAPoint(left, top, 0, blanked=True))       # start (blank)
    pts.append(ILDAPoint(right, top, 0, blanked=False))     # haut
    pts.append(ILDAPoint(right, bottom, 0, blanked=False))  # droite
    pts.append(ILDAPoint(left, bottom, 0, blanked=False))   # bas
    pts.append(ILDAPoint(left, top, 0, blanked=False))      # gauche

    frame = ILDAFrame(
        name="SQUARE",
        company="LPIP",
        points=pts,
        projector=0,
    )

    return write_ilda_file(out_path, [frame])


# ======================================================================
# SVG → polyline(s) → points ILDA
# ======================================================================

# Regex pour parser les commandes de path SVG :
#  - commandes : M/m, L/l, H/h, V/v, C/c, Z/z
#  - nombres : flottants, avec éventuel exposant
_PATH_TOKEN_RE = re.compile(
    r"([MmLlHhVvCcZz])|(-?\d*\.?\d+(?:[eE][+\-]?\d+)?)"
)


def _sample_cubic_bezier(p0, p1, p2, p3, steps: int = 16):
    """Approxime une courbe de Bézier cubique par 'steps' segments."""
    (x0, y0) = p0
    (x1, y1) = p1
    (x2, y2) = p2
    (x3, y3) = p3
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        # formule de Bézier cubique
        x = (
            u * u * u * x0
            + 3 * u * u * t * x1
            + 3 * u * t * t * x2
            + t * t * t * x3
        )
        y = (
            u * u * u * y0
            + 3 * u * u * t * y1
            + 3 * u * t * t * y2
            + t * t * t * y3
        )
        pts.append((x, y))
    return pts


def _parse_svg_path_d(
    d: str,
    curve_steps: int = 16,
) -> list[list[tuple[float, float]]]:
    """
    Parse de l'attribut 'd' d'un <path> SVG.

    Supporte :
      - M/m : moveto
      - L/l : lineto
      - H/h : horizontal lineto
      - V/v : vertical lineto
      - C/c : courbe de Bézier cubique (approximée par polyline)
      - Z/z : closepath

    Retourne une liste de sous-chemins, chaque sous-chemin est une
    liste de (x, y) en coordonnées SVG.
    """

    tokens = _PATH_TOKEN_RE.findall(d)
    subpaths: list[list[tuple[float, float]]] = []
    current_path: list[tuple[float, float]] = []

    current_cmd: str | None = None
    buf: list[float] = []

    x = y = 0.0  # position courante

    def start_new_path(nx: float, ny: float):
        nonlocal current_path, x, y
        if current_path:
            subpaths.append(current_path)
        current_path = [(nx, ny)]
        x, y = nx, ny

    def add_point(nx: float, ny: float):
        nonlocal current_path, x, y
        x, y = nx, ny
        current_path.append((x, y))

    for cmd, num in tokens:
        if cmd:
            # nouvelle commande
            current_cmd = cmd
            buf = []

            if cmd in "Zz":
                # on ferme le path sur son premier point
                if current_path:
                    current_path.append(current_path[0])
                continue

            continue  # on attend les nombres

        # ici : nombre
        v = float(num)
        buf.append(v)

        # --------------------------------------------------
        # M/m : moveto (premier point d'un sous-chemin)
        # --------------------------------------------------
        if current_cmd in ("M", "m"):
            while len(buf) >= 2:
                nx, ny = buf[0], buf[1]
                buf = buf[2:]

                if current_cmd == "m":
                    nx += x
                    ny += y

                start_new_path(nx, ny)
                # spec : après le premier couple, M devient L implicite
                current_cmd = "L" if current_cmd == "M" else "l"

        # --------------------------------------------------
        # L/l : lineto
        # --------------------------------------------------
        elif current_cmd in ("L", "l"):
            while len(buf) >= 2:
                nx, ny = buf[0], buf[1]
                buf = buf[2:]

                if current_cmd == "l":
                    nx += x
                    ny += y

                add_point(nx, ny)

        # --------------------------------------------------
        # H/h : horizontal lineto
        # --------------------------------------------------
        elif current_cmd in ("H", "h"):
            while buf:
                nx = buf.pop(0)
                if current_cmd == "h":
                    nx += x
                add_point(nx, y)

        # --------------------------------------------------
        # V/v : vertical lineto
        # --------------------------------------------------
        elif current_cmd in ("V", "v"):
            while buf:
                ny = buf.pop(0)
                if current_cmd == "v":
                    ny += y
                add_point(x, ny)

        # --------------------------------------------------
        # C/c : cubic Bézier
        # --------------------------------------------------
        elif current_cmd in ("C", "c"):
            while len(buf) >= 6:
                x1, y1, x2, y2, x3, y3 = buf[0:6]
                buf = buf[6:]

                if current_cmd == "c":
                    x1 += x
                    y1 += y
                    x2 += x
                    y2 += y
                    x3 += x
                    y3 += y

                p0 = (x, y)
                p1 = (x1, y1)
                p2 = (x2, y2)
                p3 = (x3, y3)

                # approxime la courbe en polyline
                samples = _sample_cubic_bezier(p0, p1, p2, p3, steps=curve_steps)
                # on a déjà p0 dans current_path, donc on ignore le premier
                for (sx, sy) in samples[1:]:
                    add_point(sx, sy)

    if current_path:
        subpaths.append(current_path)

    return subpaths



# ======================================================================
# Transform SVG (translate / scale) → matrice 2D
# ======================================================================

_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # a, b, c, d, e, f


def _mult_m(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _parse_transform(s: str):
    """
    Parse très simple de 'transform' pour les cas Potrace :
    - translate(tx, ty)
    - scale(sx, sy)  ou  scale(s)
    Composés éventuels : translate(...) scale(...)
    """
    s = (s or "").strip()
    if not s:
        return _IDENTITY

    func_re = re.compile(r"([a-zA-Z]+)\(([^)]*)\)")
    m = _IDENTITY

    for fn, args_str in func_re.findall(s):
        args = [float(x) for x in re.split(r"[,\s]+", args_str.strip()) if x]
        fn = fn.lower()
        if fn == "translate":
            tx = args[0]
            ty = args[1] if len(args) > 1 else 0.0
            tm = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif fn == "scale":
            sx = args[0]
            sy = args[1] if len(args) > 1 else sx
            tm = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        else:
            # autres transforms (rotate, matrix, ...) ignorées pour l'instant
            continue

        m = _mult_m(m, tm)

    return m


def _apply_matrix(m, x: float, y: float) -> Tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _is_tag(elem, local_name: str) -> bool:
    # gestion naïve des namespaces
    return elem.tag.endswith("}" + local_name) or elem.tag == local_name


def _load_svg_paths(svg_path: Path, curve_steps: int = 20) -> List[List[Tuple[float, float]]]:
    """
    Charge un SVG et retourne la liste des polylignes (liste de points)
    après application des transforms (translate/scale).
    Chaque entrée est une liste de (x, y) en coordonnées écran SVG.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()

    paths: List[List[Tuple[float, float]]] = []

    def walk(elem, parent_m):
        m = parent_m
        tr = elem.get("transform")
        if tr:
            tm = _parse_transform(tr)
            m = _mult_m(parent_m, tm)

        subpaths: List[List[Tuple[float, float]]] | None = None

        if _is_tag(elem, "path"):
            d = elem.get("d") or ""
            subpaths = _parse_svg_path_d(d, curve_steps=curve_steps)

        elif _is_tag(elem, "polyline") or _is_tag(elem, "polygon"):
            pts_str = elem.get("points") or ""
            coords: List[float] = []
            for tok in pts_str.replace(",", " ").split():
                try:
                    coords.append(float(tok))
                except ValueError:
                    pass
            xy = list(zip(coords[0::2], coords[1::2]))
            if _is_tag(elem, "polygon") and xy:
                xy.append(xy[0])  # fermer
            subpaths = [xy]

        if subpaths:
            for sp in subpaths:
                if len(sp) < 2:
                    continue
                transformed = [_apply_matrix(m, x, y) for (x, y) in sp]
                paths.append(transformed)

        for child in list(elem):
            walk(child, m)

    walk(root, _IDENTITY)
    return paths


def _compute_bounds(frames_paths: List[List[List[Tuple[float, float]]]]
                    ) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for paths in frames_paths:
        for p in paths:
            for x, y in p:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise RuntimeError("Aucun point vectoriel trouvé dans les SVG.")
    return min(xs), max(xs), min(ys), max(ys)


def _paths_to_ilda_points(
    paths: List[List[Tuple[float, float]]],
    bounds: Tuple[float, float, float, float],
    min_rel_size: float = 0.01,
    fill_ratio: float = 0.95,
    fit_axis: str = "max",   # "max" (défaut), "x" ou "y"
) -> List[ILDAPoint]:
    """
    Normalise des chemins (liste de listes de (x,y)) dans l'espace ILDA.

    - bounding box commune fournie par 'bounds'
    - Z = 0, couleur = blanc
    - début de chaque sous-chemin en 'blanked=True'
    - supprime les paths trop petits (lignes parasites) :
      taille < min_rel_size * taille_globale
    - fill_ratio : fraction de la fenêtre ILDA utilisée (0.0..1.0)
    - fit_axis : "max" (comportement actuel), "x" (remplit la largeur),
                 "y" (remplit la hauteur)
    """
    min_x, max_x, min_y, max_y = bounds
    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0
    global_span = max(span_x, span_y)

    # Choix de l’axe de référence pour le scale
    if fit_axis == "x":
        base_span = span_x
    elif fit_axis == "y":
        base_span = span_y
    else:
        base_span = global_span

    scale = (32767 * fill_ratio) / base_span
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    result: List[ILDAPoint] = []

    for path in paths:
        if len(path) < 2:
            continue

        # Taille locale du path
        xs = [x for x, _ in path]
        ys = [y for _, y in path]
        span_px = (max(xs) - min(xs)) or 0.0
        span_py = (max(ys) - min(ys)) or 0.0
        path_span = max(span_px, span_py)

        # Filtre anti-poussière : on ignore les paths trop petits
        if path_span < global_span * min_rel_size:
            continue

        first = True
        for x, y in path:
            nx = int(round((x - cx) * scale))
            # Inversion Y : SVG (origine en haut) -> ILDA (origine au centre, Y vers le haut)
            ny = int(round((cy - y) * scale))

            result.append(
                ILDAPoint(
                    x=nx,
                    y=ny,
                    z=0,
                    blanked=first,
                    color_index=255,
                )
            )
            first = False

    return result

def svg_to_points(svg_path: Path) -> List[ILDAPoint]:
    """
    API simple : convertit un fichier SVG isolé en liste de ILDAPoint.
    Utilise la bounding box de CE seul fichier pour la normalisation.
    """
    paths = _load_svg_paths(Path(svg_path))
    if not paths:
        return []
    bounds = _compute_bounds([paths])
    return _paths_to_ilda_points(paths, bounds)


# ======================================================================
# Étape pipeline : export ILDA pour un projet
# ======================================================================

def export_project_to_ilda(
    project_name: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    check_cancel: Callable[[], bool] | None = None,
    report_progress: Callable[[int], None] | None = None,
) -> Path:
    """
    Export ILDA pour un projet donné.

    - Cherche les SVG dans projects/<project_name>/svg/frame_*.svg
    - Calcule une bounding box GLOBALE sur l'ensemble des SVG
      pour garantir une taille et un centrage stables d'une frame à l'autre.
    - Écrit un fichier .ild dans projects/<project_name>/ilda/<project_name>.ild
    - Retourne le Path du fichier créé.

    check_cancel()    → si fourni, permet d'interrompre proprement.
    report_progress(p) avec p ∈ [0..100] pour la barre de progression.
    """
    project_root = PROJECTS_ROOT / project_name
    svg_dir = project_root / "svg"
    ilda_dir = project_root / "ilda"
    ilda_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(svg_dir.glob("frame_*.svg"))
    if not svg_files:
        raise RuntimeError(f"Aucun SVG trouvé dans {svg_dir}")

    # --------------------------------------------------------------
    # 1) Première passe : charger les chemins et accumuler la bbox
    # --------------------------------------------------------------
    per_frame_paths: List[List[List[Tuple[float, float]]]] = []

    for svg_file in svg_files:
        if check_cancel is not None and check_cancel():
            raise RuntimeError("Export ILDA annulé par l'utilisateur (phase 1).")

        paths = _load_svg_paths(svg_file)
        if not paths:
            # on ignore les frames vides, mais on pourrait aussi lever une erreur
            continue

        per_frame_paths.append(paths)

    if not per_frame_paths:
        raise RuntimeError("Aucun chemin exploitable trouvé dans les SVG du projet.")

    bounds = _compute_bounds(per_frame_paths)

    # --------------------------------------------------------------
    # 2) Seconde passe : normalisation + construction des frames ILDA
    # --------------------------------------------------------------
    frames: List[ILDAFrame] = []
    total = len(per_frame_paths)

    for idx, paths in enumerate(per_frame_paths):
        if check_cancel is not None and check_cancel():
            raise RuntimeError("Export ILDA annulé par l'utilisateur (phase 2).")

        ilda_points = _paths_to_ilda_points(
            paths,
            bounds,
            min_rel_size=min_rel_size,
            fill_ratio=fill_ratio,
            fit_axis=fit_axis,
            )

        frame = ILDAFrame(
            name=f"F{idx:04d}",
            company="LPIP",
            points=ilda_points,
            projector=0,
        )
        frames.append(frame)

        if report_progress is not None and total > 0:
            report_progress(int((idx + 1) * 100 / total))

    out_path = ilda_dir / f"{project_name}.ild"
    write_ilda_file(out_path, frames)
    return out_path
