# core/ilda_export.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import xml.etree.ElementTree as ET

from svgpathtools import Line, parse_path

from .config import PROJECTS_ROOT
from .ilda_profiles import IldaProfile, get_ilda_profile
from .ilda_writer import IldaFrame, IldaPoint, write_ilda_file

ILDA_MIN = -32767.0
ILDA_MAX = +32767.0
ILDA_SPAN = ILDA_MAX - ILDA_MIN


@dataclass
class _SubpathData:
    points: List[Tuple[float, float]]
    bbox: Tuple[float, float, float, float]


# ----------------------------------------------------------------------
# SVG parsing helpers
# ----------------------------------------------------------------------

def _path_to_polyline(path, samples_per_curve: int = 64) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    first = True

    for seg in path:
        if first:
            z0 = seg.start
            pts.append((float(z0.real), float(z0.imag)))
            first = False

        if isinstance(seg, Line):
            z1 = seg.end
            pts.append((float(z1.real), float(z1.imag)))
        else:
            for i in range(1, samples_per_curve + 1):
                t = i / samples_per_curve
                z = seg.point(t)
                pts.append((float(z.real), float(z.imag)))

    return pts


def _load_svg_subpaths(svg_file: Path) -> List[_SubpathData]:
    """
    Charge un SVG et retourne une liste de sous-chemins (subpaths) indépendants.
    Important: un <path> SVG peut contenir plusieurs sous-chemins (plusieurs M).
    """
    tree = ET.parse(svg_file)
    root = tree.getroot()

    subpaths: List[_SubpathData] = []

    for elem in root.iter():
        if not elem.tag.lower().endswith("path"):
            continue

        d_attr = elem.get("d")
        if not d_attr:
            continue

        try:
            p = parse_path(d_attr)
        except Exception:
            continue

        # Split en sous-chemins continus => évite les liaisons parasites entre "M ... M ..."
        for sub in p.continuous_subpaths():
            pts = _path_to_polyline(sub)
            if not pts:
                continue

            xs = [x for x, _ in pts]
            ys = [y for _, y in pts]
            bbox = (min(xs), max(xs), min(ys), max(ys))
            subpaths.append(_SubpathData(points=pts, bbox=bbox))

    return subpaths


def _combine_bbox(bboxes: List[Tuple[float, float, float, float]]):
    min_x = min(b[0] for b in bboxes)
    max_x = max(b[1] for b in bboxes)
    min_y = min(b[2] for b in bboxes)
    max_y = max(b[3] for b in bboxes)
    return min_x, max_x, min_y, max_y


# ----------------------------------------------------------------------
# Normalisation ILDA
# ----------------------------------------------------------------------

def _make_normalizer(global_bbox, fit_axis: str, fill_ratio: float):
    gx0, gx1, gy0, gy1 = global_bbox
    cx = (gx0 + gx1) / 2
    cy = (gy0 + gy1) / 2
    span_x = gx1 - gx0
    span_y = gy1 - gy0

    if fit_axis == "x":
        base = span_x
    elif fit_axis == "y":
        base = span_y
    elif fit_axis == "min":
        base = min(span_x, span_y)
    else:
        base = max(span_x, span_y)

    base = max(base, 1e-6)
    scale = (ILDA_SPAN * fill_ratio) / base

    def norm(x: float, y: float):
        xn = (x - cx) * scale
        yn = (y - cy) * scale
        xn = max(ILDA_MIN, min(ILDA_MAX, xn))
        yn = max(ILDA_MIN, min(ILDA_MAX, yn))
        return int(round(xn)), int(round(yn))

    return norm


# ----------------------------------------------------------------------
# Outer-frame filtering (SVG-side, may miss multi-stroke frames)
# ----------------------------------------------------------------------

def _is_outer_frame(
    sub_bbox: Tuple[float, float, float, float],
    global_bbox: Tuple[float, float, float, float],
    pts: List[Tuple[float, float]],
    *,
    rel_tol: float = 0.90,          # plus permissif
    edge_rel_eps: float = 0.012,
    min_edge_fraction: float = 0.35 # plus permissif
) -> bool:
    sx0, sx1, sy0, sy1 = sub_bbox
    gx0, gx1, gy0, gy1 = global_bbox

    sw, sh = (sx1 - sx0), (sy1 - sy0)
    gw, gh = (gx1 - gx0), (gy1 - gy0)

    if gw <= 1e-9 or gh <= 1e-9:
        return False

    # doit être "grand" par rapport au global
    if (sw / gw) < rel_tol or (sh / gh) < rel_tol:
        return False

    eps = edge_rel_eps * max(gw, gh)

    def near(a: float, b: float) -> bool:
        return abs(a - b) <= eps

    on_edge = 0
    corners = [0, 0, 0, 0]  # TL, TR, BL, BR

    for x, y in pts:
        is_left = near(x, sx0)
        is_right = near(x, sx1)
        is_bot = near(y, sy0)
        is_top = near(y, sy1)

        if is_left or is_right or is_bot or is_top:
            on_edge += 1

        if is_left and is_top:
            corners[0] = 1
        elif is_right and is_top:
            corners[1] = 1
        elif is_left and is_bot:
            corners[2] = 1
        elif is_right and is_bot:
            corners[3] = 1

    frac = on_edge / max(1, len(pts))
    has_4_corners = sum(corners) >= 3

    return (frac >= min_edge_fraction) and has_4_corners


# ----------------------------------------------------------------------
# Frame-border removal (ILDA-side, robust even if the frame is multi-stroke)
# ----------------------------------------------------------------------

def _split_strokes(points: List[IldaPoint]) -> List[List[IldaPoint]]:
    """
    Découpe en strokes: un stroke démarre à chaque point blanked=True (jump).
    Le stroke contient ce jump + les points non-blank suivants.
    """
    strokes: List[List[IldaPoint]] = []
    cur: List[IldaPoint] = []

    for p in points:
        if p.blanked:
            if cur:
                strokes.append(cur)
            cur = [p]
        else:
            if not cur:
                # sécurité: stroke visible sans jump -> on injecte un jump
                cur = [
                    IldaPoint(
                        x=p.x,
                        y=p.y,
                        z=p.z,
                        blanked=True,
                        color_index=p.color_index,
                    )
                ]
            cur.append(p)

    if cur:
        strokes.append(cur)

    return strokes


def _stroke_bbox(stroke: List[IldaPoint]) -> Tuple[int, int, int, int]:
    vis = [p for p in stroke if not p.blanked]
    xs = [p.x for p in vis]
    ys = [p.y for p in vis]
    return min(xs), max(xs), min(ys), max(ys)


def _is_frame_stroke(
    stroke: List[IldaPoint],
    *,
    span: float,
    rel_tol: float = 0.90,
    edge_eps_rel: float = 0.015,
    min_edge_fraction: float = 0.35,
    min_axis_aligned_fraction: float = 0.75,
) -> bool:
    """
    Détecte un stroke qui ressemble à un cadre rectangulaire en coordonnées ILDA.
    """
    vis = [p for p in stroke if not p.blanked]
    if len(vis) < 40:
        return False

    x0, x1, y0, y1 = _stroke_bbox(stroke)
    w = x1 - x0
    h = y1 - y0

    if w < rel_tol * span or h < rel_tol * span:
        return False

    eps = edge_eps_rel * span

    def near(a: int, b: int) -> bool:
        return abs(a - b) <= eps

    on_edge = 0
    corners = [0, 0, 0, 0]  # TL, TR, BL, BR
    axis_aligned = 0
    segs = 0

    for i, p in enumerate(vis):
        is_left = near(p.x, x0)
        is_right = near(p.x, x1)
        is_bot = near(p.y, y0)
        is_top = near(p.y, y1)

        if is_left or is_right or is_bot or is_top:
            on_edge += 1

        if is_left and is_top:
            corners[0] = 1
        elif is_right and is_top:
            corners[1] = 1
        elif is_left and is_bot:
            corners[2] = 1
        elif is_right and is_bot:
            corners[3] = 1

        if i > 0:
            dx = abs(p.x - vis[i - 1].x)
            dy = abs(p.y - vis[i - 1].y)
            segs += 1
            if dx <= eps or dy <= eps:
                axis_aligned += 1

    frac_edge = on_edge / max(1, len(vis))
    frac_axis = axis_aligned / max(1, segs)
    has_corners = sum(corners) >= 3

    return (frac_edge >= min_edge_fraction) and has_corners and (frac_axis >= min_axis_aligned_fraction)


def _remove_frame_strokes(points: List[IldaPoint]) -> List[IldaPoint]:
    """
    Supprime les strokes détectés comme "cadre" au niveau ILDA.
    Si tout est supprimé par erreur, retourne les points originaux.
    """
    strokes = _split_strokes(points)

    kept: List[IldaPoint] = []
    for st in strokes:
        if _is_frame_stroke(st, span=ILDA_SPAN):
            continue
        kept.extend(st)

    if not kept:
        return points
    return kept


# ----------------------------------------------------------------------
# PUBLIC API — used by pipeline ONLY
# ----------------------------------------------------------------------

def export_project_to_ilda(
    project_name: str,
    *,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    mode: str = "classic",
    check_cancel: Optional[Callable[[], bool]] = None,
    report_progress: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """
    Exporte projects/<project>/svg/*.svg → projects/<project>/ilda/<project>.ild
    """
    project_root = PROJECTS_ROOT / project_name
    svg_dir = project_root / "svg"
    ilda_dir = project_root / "ilda"
    ilda_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(svg_dir.glob("frame_*.svg"))
    total_frames = len(svg_files)
    if total_frames == 0:
        raise RuntimeError("Aucun SVG trouvé pour l'export ILDA")

    profile: IldaProfile = get_ilda_profile(mode)

    frames_subpaths: List[List[_SubpathData]] = []
    for svg in svg_files:
        if check_cancel and check_cancel():
            raise RuntimeError("Export ILDA annulé")
        frames_subpaths.append(_load_svg_subpaths(svg))

    all_bboxes = [sp.bbox for frame in frames_subpaths for sp in frame]
    if not all_bboxes:
        raise RuntimeError("Aucun chemin exploitable dans les SVG")

    global_bbox = _combine_bbox(all_bboxes)
    gx0, gx1, gy0, gy1 = global_bbox
    gw = max(1e-9, gx1 - gx0)
    gh = max(1e-9, gy1 - gy0)

    # Filtrage: bruit + cadre (SVG-side)
    filtered_frames: List[List[_SubpathData]] = []
    for frame in frames_subpaths:
        kept: List[_SubpathData] = []
        for sp in frame:
            sx0, sx1, sy0, sy1 = sp.bbox
            sw = sx1 - sx0
            sh = sy1 - sy0

            # Nettoyage bruit (utilise min_rel_size)
            if (sw / gw) < min_rel_size and (sh / gh) < min_rel_size:
                continue

            # Suppression cadre (peut rater si le cadre est multi-stroke)
            if _is_outer_frame(sp.bbox, global_bbox, sp.points):
                continue

            kept.append(sp)

        filtered_frames.append(kept)

    normalizer = _make_normalizer(global_bbox, fit_axis, fill_ratio)

    frames: List[IldaFrame] = []

    for frame_idx, frame_subpaths in enumerate(filtered_frames):
        if check_cancel and check_cancel():
            raise RuntimeError("Export ILDA annulé")

        points: List[IldaPoint] = []

        # blank jump + tracé par sous-chemin (évite les liaisons parasites)
        for sp in frame_subpaths:
            if not sp.points:
                continue

            coords = [normalizer(x, y) for x, y in sp.points]
            x0, y0 = coords[0]

            points.append(
                IldaPoint(
                    x=x0,
                    y=y0,
                    z=0,
                    blanked=True,
                    color_index=profile.base_color_index,
                )
            )

            for x, y in coords[1:]:
                points.append(
                    IldaPoint(
                        x=x,
                        y=y,
                        z=0,
                        blanked=False,
                        color_index=profile.base_color_index,
                    )
                )

        if not points:
            points.append(
                IldaPoint(
                    x=0,
                    y=0,
                    z=0,
                    blanked=True,
                    color_index=profile.base_color_index,
                )
            )

        # --- suppression cadre au niveau ILDA (robuste) ---
        points = _remove_frame_strokes(points)

        frames.append(
            IldaFrame(
                name=f"F{frame_idx:04d}",
                company="LPIP",
                points=points,
                projector=0,
            )
        )

        if report_progress:
            report_progress(frame_idx, total_frames)

    out_path = ilda_dir / f"{project_name}.ild"
    write_ilda_file(out_path, frames)
    return out_path
