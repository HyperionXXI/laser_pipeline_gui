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
                    # Ferme le chemin sur lui-même
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
            # Les moveto suivants deviennent des lineto
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


def _is_closed_path(path: List[Tuple[float, float]], tol: float) -> bool:
    if len(path) < 3:
        return False
    (x0, y0) = path[0]
    (x1, y1) = path[-1]
    return abs(x0 - x1) + abs(y0 - y1) <= tol


def _compute_bounds(
    frames_paths: List[List[List[Tuple[float, float]]]],
    remove_outer_frame: bool = False,
    frame_margin_rel: float = 0.02,
    min_rel_size: float = 0.01,
) -> tuple[tuple[float, float, float, float], set[tuple[int, int]]]:
    """
    Calcule la bounding box globale sur l'ensemble des frames.

    Si ``remove_outer_frame`` est True, on tente d'ignorer un éventuel
    grand path fermé jouant le rôle de "cadre" extérieur (typiquement la
    bordure du tableau dans *La Linea*), afin que la normalisation ILDA
    utilise uniquement le contenu utile (personnages, décor intérieur).

    Retourne un tuple :

        (bounds, frame_paths)

    - ``bounds`` est (min_x, max_x, min_y, max_y) sur le contenu utile.
    - ``frame_paths`` est l'ensemble des couples (frame_index, path_index)
      correspondant aux chemins considérés comme "cadres" et donc exclus.
    """

    # ------------------------------------------------------------------
    # 1) BBOX GLOBALE (tous chemins, toutes frames)
    # ------------------------------------------------------------------
    all_x: list[float] = []
    all_y: list[float] = []

    for frame in frames_paths:
        for path in frame:
            for x, y in path:
                all_x.append(x)
                all_y.append(y)

    if not all_x:
        # Pas de contenu du tout.
        return (0.0, 0.0, 0.0, 0.0), set()

    min_x = min(all_x)
    max_x = max(all_x)
    min_y = min(all_y)
    max_y = max(all_y)

    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    global_span = max(span_x, span_y)
    global_area = span_x * span_y

    if not remove_outer_frame:
        # On ne touche à rien : bbox globale et aucun chemin exclu.
        return (min_x, max_x, min_y, max_y), set()

    frame_paths: set[tuple[int, int]] = set()

    margin_x = span_x * frame_margin_rel
    margin_y = span_y * frame_margin_rel
    tol_closed = global_span * 1e-3  # tolérance de fermeture relative

    # ------------------------------------------------------------------
    # 2) CLASSEMENT DES CHEMINS "CADRES"
    # ------------------------------------------------------------------
    for fi, frame in enumerate(frames_paths):
        for pi, path in enumerate(frame):
            if len(path) < 3:
                continue

            xs = [p[0] for p in path]
            ys = [p[1] for p in path]
            px_min, px_max = min(xs), max(xs)
            py_min, py_max = min(ys), max(ys)
            width = px_max - px_min
            height = py_max - py_min
            path_span = max(width, height)

            # Trop petit pour être un cadre → on ignore.
            if path_span < global_span * float(min_rel_size):
                continue

            if not _is_closed_path(path, tol=tol_closed):
                # Un cadre est forcément fermé.
                continue

            # Étendue relative du path par rapport à la bbox globale.
            rel_x = width / span_x if span_x > 0 else 0.0
            rel_y = height / span_y if span_y > 0 else 0.0

            # ---- Cas 1 : "vrai cadre plein écran" très agressif ----
            if rel_x >= 0.95 and rel_y >= 0.95:
                frame_paths.add((fi, pi))
                continue

            # ---- Cas 2 : cadre large touchant plusieurs bords ----
            touches = 0
            if abs(px_min - min_x) <= margin_x:
                touches += 1
            if abs(px_max - max_x) <= margin_x:
                touches += 1
            if abs(py_min - min_y) <= margin_y:
                touches += 1
            if abs(py_max - max_y) <= margin_y:
                touches += 1

            # Aire via la formule du "shoelace" (chemin fermé).
            path_area = 0.0
            for (x0, y0), (x1, y1) in zip(path, path[1:] + path[:1]):
                path_area += x0 * y1 - x1 * y0
            path_area = abs(path_area) * 0.5

            # On accepte comme cadre :
            #  - ce qui touche au moins 3 bords
            #  - ET occupe au moins 20 % de l'aire globale.
            if global_area > 0 and touches >= 3 and path_area >= global_area * 0.2:
                frame_paths.add((fi, pi))

    # ------------------------------------------------------------------
    # 3) RE-CALCUL DE LA BBOX EN EXCLUANT LES CADRES
    # ------------------------------------------------------------------
    if not frame_paths:
        # Rien n'a été identifié comme cadre : on garde la bbox globale.
        return (min_x, max_x, min_y, max_y), frame_paths

    xs_useful: list[float] = []
    ys_useful: list[float] = []

    for fi, frame in enumerate(frames_paths):
        for pi, path in enumerate(frame):
            if (fi, pi) in frame_paths:
                continue
            for x, y in path:
                xs_useful.append(x)
                ys_useful.append(y)

    # Si tout a été filtré (cas pathologique), on revient à la bbox globale.
    if not xs_useful:
        frame_paths.clear()
        return (min_x, max_x, min_y, max_y), frame_paths

    return (
        min(xs_useful),
        max(xs_useful),
        min(ys_useful),
        max(ys_useful),
    ), frame_paths



def _paths_to_ilda_points(
    paths: List[List[Tuple[float, float]]],
    bounds: Tuple[float, float, float, float],
    *,
    min_rel_size: float,
    fill_ratio: float,
    fit_axis: str,
    remove_outer_frame: bool = False,
    frame_margin_rel: float = 0.0,
    blank_move_points: int = 4,
) -> List[ILDAPoint]:
    """
    Convertit une liste de chemins 2D en points ILDA.

    - `bounds` : (min_x, max_x, min_y, max_y) communs à toutes les frames.
    - `min_rel_size` : filtre les très petits chemins (bruit).
    - `fill_ratio` : fraction de la plage [-32767, +32767] utilisée.
    - `fit_axis` : "max" (par défaut), "x" ou "y" pour le choix de
      l’axe de référence.
    - `remove_outer_frame` / `frame_margin_rel` : paramètres conservés
      pour compatibilité ; la détection de cadre est faite en amont.
    - `blank_move_points` : nombre de points blankés insérés pour les
      déplacements entre chemins (limite les lignes parasites).
    """
    min_x, max_x, min_y, max_y = bounds

    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    # Étendue maximale que l'on souhaite utiliser dans l'espace ILDA
    max_extent = 32767.0 * float(fill_ratio)

    # Choix de l'axe de référence pour le scaling
    if fit_axis == "x":
        span_ref = span_x
    elif fit_axis == "y":
        span_ref = span_y
    else:  # "max"
        span_ref = max(span_x, span_y)

    if span_ref <= 0.0:
        return []

    # On est centré autour du milieu, donc les extrémités sont à ±span_ref/2.
    # Pour les mapper sur ±max_extent, il faut :
    #   scale = max_extent / (span_ref / 2) = 2 * max_extent / span_ref
    scale = (2.0 * max_extent) / span_ref

    x_center = (min_x + max_x) / 2.0
    y_center = (min_y + max_y) / 2.0

    def clamp16(v: int) -> int:
        # Petits garde-fous pour rester dans la plage ILDA valide.
        return max(-32767, min(32767, v))

    def to_ilda_xy(x: float, y: float) -> Tuple[int, int]:
        # Coordonnées centrées, inversion de l'axe Y pour correspondre à ILDA.
        nx = int(round((x - x_center) * scale))
        ny = int(round((y_center - y) * scale))
        return clamp16(nx), clamp16(ny)

    ilda_points: List[ILDAPoint] = []
    prev_end_xy: Optional[Tuple[int, int]] = None

    for path in paths:
        if len(path) < 2:
            continue

        # Filtre bruit : uniquement les très petits chemins FERMÉS.
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        path_span = max(width, height)

        # Seulement si c'est vraiment minuscule ET fermé (souvent poussière / points isolés)
        if path_span < max(span_x, span_y) * min_rel_size and _is_closed_path(path, tol=1e-6):
            continue


        # Premier point du chemin en coordonnées ILDA
        start_x, start_y = to_ilda_xy(*path[0])

        # Si on vient d'un autre chemin, on insère des points de déplacement
        # blankés entre la fin précédente et le début du nouveau chemin.
        if prev_end_xy is not None and blank_move_points > 0:
            px, py = prev_end_xy
            for i in range(1, blank_move_points + 1):
                t = i / (blank_move_points + 1)
                ix = int(round(px + t * (start_x - px)))
                iy = int(round(py + t * (start_y - py)))
                ix, iy = clamp16(ix), clamp16(iy)
                ilda_points.append(
                    ILDAPoint(x=ix, y=iy, z=0, blanked=True, color_index=255)
                )

        # Points du chemin lui-même
        for idx, (x, y) in enumerate(path):
            if idx == 0:
                nx, ny = start_x, start_y
            else:
                nx, ny = to_ilda_xy(x, y)

            # Premier point du chemin : blanked=True (on "pose" le faisceau)
            blanked = idx == 0
            ilda_points.append(
                ILDAPoint(x=nx, y=ny, z=0, blanked=blanked, color_index=255)
            )

        # Mémorise la fin de ce chemin pour le prochain déplacement blanké
        prev_end_xy = to_ilda_xy(*path[-1])

    return ilda_points


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
      à cette bounding box globale (typique *La Linea*).
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

    bounds, frame_paths = _compute_bounds(
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

        # On retire explicitement les paths marqués comme "cadre"
        if frame_paths:
            filtered_paths = [
                p for pi, p in enumerate(paths) if (idx, pi) not in frame_paths
            ]
        else:
            filtered_paths = paths

        ilda_points = _paths_to_ilda_points(
            filtered_paths,
            bounds,
            min_rel_size=min_rel_size,
            fill_ratio=fill_ratio,
            fit_axis=fit_axis,
            remove_outer_frame=remove_outer_frame,
            frame_margin_rel=frame_margin_rel,
        )

        # 🔹 NOUVEAU : si aucun point utile, on saute la frame
        if not ilda_points:
            if report_progress is not None and total > 0:
                report_progress(int((idx + 1) * 100 / total))
            continue

        frame = ILDAFrame(
            # On garde l’index réel dans le nom, même si certaines frames sont sautées
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
