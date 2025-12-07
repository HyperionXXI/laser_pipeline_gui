# core/step_ilda.py
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Callable, Optional
import re
import xml.etree.ElementTree as ET

from .config import PROJECTS_ROOT
from .ilda_writer import (
    IldaPoint as ILDAPoint,
    IldaFrame as ILDAFrame,
    write_ilda_file,
    write_demo_square,  # Ré-export pour compatibilité éventuelle
)

# ======================================================================
# SVG → polyline(s) → points ILDA
# ======================================================================

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

    Retourne une liste de sous-chemins, chaque sous-chemin est une liste
    de (x, y) en coordonnées SVG.
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
            current_cmd = cmd
            buf = []
            if cmd in "Zz":
                if current_path:
                    current_path.append(current_path[0])
                continue
            continue

        v = float(num)
        buf.append(v)

        # M/m : moveto
        if current_cmd in ("M", "m"):
            while len(buf) >= 2:
                nx, ny = buf[0], buf[1]
                buf = buf[2:]
                if current_cmd == "m":
                    nx += x
                    ny += y
                start_new_path(nx, ny)
            current_cmd = "L" if current_cmd == "M" else "l"

        # L/l : lineto
        elif current_cmd in ("L", "l"):
            while len(buf) >= 2:
                nx, ny = buf[0], buf[1]
                buf = buf[2:]
                if current_cmd == "l":
                    nx += x
                    ny += y
                add_point(nx, ny)

        # H/h : horizontal lineto
        elif current_cmd in ("H", "h"):
            while buf:
                nx = buf.pop(0)
                if current_cmd == "h":
                    nx += x
                add_point(nx, y)

        # V/v : vertical lineto
        elif current_cmd in ("V", "v"):
            while buf:
                ny = buf.pop(0)
                if current_cmd == "v":
                    ny += y
                add_point(x, ny)

        # C/c : cubic Bézier
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
                samples = _sample_cubic_bezier(
                    p0, p1, p2, p3, steps=curve_steps
                )
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
      - scale(sx, sy) ou scale(s)

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
            continue
        m = _mult_m(m, tm)
    return m


def _apply_matrix(m, x: float, y: float) -> Tuple[float, float]:
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _is_tag(elem, local_name: str) -> bool:
    return elem.tag.endswith("}" + local_name) or elem.tag == local_name


def _load_svg_paths(svg_path: Path, curve_steps: int = 20) -> List[List[Tuple[float, float]]]:
    """
    Charge un SVG et retourne la liste des polylignes (liste de points)
    après application des transforms (translate/scale).
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

        subpaths: Optional[List[List[Tuple[float, float]]]] = None

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
                xy.append(xy[0])
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


def _compute_bounds(
    frames_paths: List[List[List[Tuple[float, float]]]],
    remove_outer_frame: bool = False,
    frame_margin_rel: float = 0.02,
    min_rel_size: float = 0.01,
) -> Tuple[float, float, float, float]:
    """
    Calcule la bounding box globale sur l'ensemble des frames.

    Si ``remove_outer_frame`` est True, on tente d'ignorer un éventuel
    grand path fermé jouant le rôle de "cadre" extérieur (typiquement
    la bordure du tableau dans *La Linea*), afin que la normalisation
    ILDA utilise uniquement le contenu utile (personnages, décor intérieur).

    Heuristique utilisée pour marquer un path comme cadre :

    - path fermé (via :func:`_is_closed_path`) ;
    - surface de sa bounding box >= 50% de la surface globale ;
    - au moins 3 côtés de sa bounding box sont proches (à ``frame_margin_rel``
      près) de la bounding box globale.
    """
    xs_all: List[float] = []
    ys_all: List[float] = []
    for paths in frames_paths:
        for p in paths:
            for x, y in p:
                xs_all.append(x)
                ys_all.append(y)

    if not xs_all:
        raise RuntimeError("Aucun point vectoriel trouvé dans les SVG.")

    min_x = min(xs_all)
    max_x = max(xs_all)
    min_y = min(ys_all)
    max_y = max(ys_all)

    # Cas simple : pas de tentative de suppression de cadre
    if not remove_outer_frame:
        return min_x, max_x, min_y, max_y

    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0
    global_span = max(span_x, span_y)
    frame_tol = global_span * frame_margin_rel
    global_area = span_x * span_y or 1.0

    # 1) Détection des paths "cadre"
    frame_paths: set[tuple[int, int]] = set()
    for fi, paths in enumerate(frames_paths):
        for pi, path in enumerate(paths):
            if len(path) < 4:
                continue

            xs = [x for x, _ in path]
            ys = [y for _, y in path]
            span_px = (max(xs) - min(xs)) or 0.0
            span_py = (max(ys) - min(ys)) or 0.0
            path_span = max(span_px, span_py)

            # Trop petit pour être un cadre
            if path_span < global_span * min_rel_size:
                continue

            if not _is_closed_path(path, tol=frame_tol):
                continue

            path_area = span_px * span_py

            near_left = abs(min(xs) - min_x) <= frame_tol
            near_right = abs(max(xs) - max_x) <= frame_tol
            near_bottom = abs(min(ys) - min_y) <= frame_tol
            near_top = abs(max(ys) - max_y) <= frame_tol
            touches = sum((near_left, near_right, near_bottom, near_top))

            # Il couvre la majeure partie de la scène et touche au moins
            # trois bords : on le considère comme un cadre.
            if touches >= 3 and path_area >= global_area * 0.5:
                frame_paths.add((fi, pi))

    # 2) Re-calcul de la bounding box en ignorant les cadres trouvés
    if not frame_paths:
        return min_x, max_x, min_y, max_y

    xs: List[float] = []
    ys: List[float] = []
    for fi, paths in enumerate(frames_paths):
        for pi, p in enumerate(paths):
            if (fi, pi) in frame_paths:
                continue
            for x, y in p:
                xs.append(x)
                ys.append(y)

    # Si tout a été filtré par erreur, on revient à la bbox globale initiale
    if not xs:
        return min_x, max_x, min_y, max_y

    return min(xs), max(xs), min(ys), max(ys)


def _is_closed_path(path: List[Tuple[float, float]], tol: float) -> bool:
    if len(path) < 3:
        return False
    (x0, y0) = path[0]
    (x1, y1) = path[-1]
    return abs(x0 - x1) + abs(y0 - y1) <= tol


def _paths_to_ilda_points(
    paths: List[List[Tuple[float, float]]],
    bounds: Tuple[float, float, float, float],
    min_rel_size: float = 0.01,
    fill_ratio: float = 0.95,
    fit_axis: str = "max",   # "max" (défaut), "x" ou "y"
    remove_outer_frame: bool = True,
    frame_margin_rel: float = 0.02,
) -> List[ILDAPoint]:
    """
    Normalise des chemins (liste de listes de (x,y)) dans l'espace ILDA.

    - bounding box commune fournie par 'bounds'
    - Z = 0, couleur = blanc
    - début de chaque sous-chemin en 'blanked=True'
    - supprime les paths trop petits (lignes parasites)
    - si remove_outer_frame=True, supprime un grand path fermé dont
      la bounding box colle à la bounding box globale (cadre extérieur)
    """
    min_x, max_x, min_y, max_y = bounds
    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0
    global_span = max(span_x, span_y)

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

    frame_tol = global_span * frame_margin_rel

    for path in paths:
        if len(path) < 2:
            continue

        xs = [x for x, _ in path]
        ys = [y for _, y in path]
        span_px = (max(xs) - min(xs)) or 0.0
        span_py = (max(ys) - min(ys)) or 0.0
        path_span = max(span_px, span_py)

        # 1) Option : suppression du cadre extérieur
        if remove_outer_frame and len(path) >= 4 and path_span > 0:
            # grand path fermé dont la bbox colle à la bbox globale
            if _is_closed_path(path, tol=frame_tol):
                near_left   = abs(min(xs) - min_x) <= frame_tol
                near_right  = abs(max(xs) - max_x) <= frame_tol
                near_bottom = abs(min(ys) - min_y) <= frame_tol
                near_top    = abs(max(ys) - max_y) <= frame_tol

                # Il "encadre" pratiquement toute la scène
                if near_left and near_right and near_bottom and near_top:
                    # On considère que c'est un cadre décoratif → on l'ignore
                    continue

        # 2) Filtre anti-poussière : paths trop petits
        if path_span < global_span * min_rel_size:
            continue

        first = True
        for x, y in path:
            nx = int(round((x - cx) * scale))
            ny = int(round((cy - y) * scale))  # inversion Y

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
    (Sans suppression de cadre global, car il n'y en a pas sur un seul fichier.)
    """
    paths = _load_svg_paths(Path(svg_path))
    if not paths:
        return []
    bounds = _compute_bounds([paths])
    return _paths_to_ilda_points(
        paths,
        bounds,
        remove_outer_frame=False,  # sur un seul fichier, on ne peut pas savoir
    )


# ======================================================================
# Étape pipeline : export ILDA pour un projet
# ======================================================================


def export_project_to_ilda(
    project_name: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    remove_outer_frame: bool = True,
    frame_margin_rel: float = 0.02,
    check_cancel: Optional[Callable[[], bool]] = None,
    report_progress: Optional[Callable[[int], None]] = None,
) -> Path:
    """
    Export ILDA pour un projet donné.

    - Cherche les SVG dans projects/<project>/svg/frame_*.svg
    - Calcule une bounding box GLOBALE sur l'ensemble des SVG pour
      garantir une taille et un centrage stables d'une frame à l'autre.
    - Si remove_outer_frame=True : supprime un éventuel cadre qui colle
      à cette bounding box globale (typique La Linea).
    - Écrit un fichier .ild dans projects/<project>/ilda/<project>.ild
    - Retourne le Path du fichier créé.
    """
    project_root = PROJECTS_ROOT / project_name
    svg_dir = project_root / "svg"
    ilda_dir = project_root / "ilda"
    ilda_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(svg_dir.glob("frame_*.svg"))
    if not svg_files:
        raise RuntimeError(f"Aucun SVG trouvé dans {svg_dir}")

    # 1) Première passe : charger les chemins et accumuler la bbox globale
    per_frame_paths: List[List[List[Tuple[float, float]]]] = []
    for svg_file in svg_files:
        if check_cancel is not None and check_cancel():
            raise RuntimeError("Export ILDA annulé par l'utilisateur (phase 1).")
        paths = _load_svg_paths(svg_file)
        if not paths:
            continue
        per_frame_paths.append(paths)

    if not per_frame_paths:
        raise RuntimeError(
            "Aucun chemin exploitable trouvé dans les SVG du projet."
        )

    bounds = _compute_bounds(
        per_frame_paths,
        remove_outer_frame=remove_outer_frame,
        frame_margin_rel=frame_margin_rel,
        min_rel_size=min_rel_size,
    )


    # 2) Seconde passe : normalisation + construction des frames ILDA
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
            remove_outer_frame=remove_outer_frame,
            frame_margin_rel=frame_margin_rel,
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
