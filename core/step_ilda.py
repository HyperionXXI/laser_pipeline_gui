# core/step_ilda.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import xml.etree.ElementTree as ET

from svgpathtools import Line, parse_path

from .config import PROJECTS_ROOT
from .ilda_profiles import IldaProfile, get_ilda_profile
from .ilda_writer import IldaFrame, IldaPoint, write_ilda_file

# Backward-compat (anciens noms utilisés ailleurs dans le projet)
ILDAPoint = IldaPoint
ILDAFrame = IldaFrame

ILDA_MIN = -32767.0
ILDA_MAX = +32767.0
ILDA_SPAN = ILDA_MAX - ILDA_MIN


@dataclass
class _PathData:
    points: List[Tuple[float, float]]
    bbox: Tuple[float, float, float, float]  # (min_x, max_x, min_y, max_y)
    is_outer_frame: bool = False


def _path_to_polyline(path, samples_per_curve: int = 64) -> List[Tuple[float, float]]:
    """
    Convertit un svgpathtools.Path en liste de points (x, y).
    """
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


def _load_svg_paths(svg_file: Path) -> List[_PathData]:
    """
    Charge un SVG Potrace et retourne une liste de _PathData.
    """
    svg_file = Path(svg_file)
    tree = ET.parse(svg_file)
    root = tree.getroot()

    result: List[_PathData] = []

    for elem in root.iter():
        tag = elem.tag.lower()
        if not tag.endswith("path"):
            continue

        d_attr = elem.get("d")
        if not d_attr:
            continue

        try:
            sp_path = parse_path(d_attr)
        except Exception:
            continue

        pts = _path_to_polyline(sp_path)
        if not pts:
            continue

        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        bbox = (min(xs), max(xs), min(ys), max(ys))

        result.append(_PathData(points=pts, bbox=bbox))

    return result


def _combine_bbox(
    bboxes: List[Tuple[float, float, float, float]]
) -> Tuple[float, float, float, float]:
    if not bboxes:
        raise RuntimeError("Aucune bounding box disponible pour le calcul global")

    min_x = min(b[0] for b in bboxes)
    max_x = max(b[1] for b in bboxes)
    min_y = min(b[2] for b in bboxes)
    max_y = max(b[3] for b in bboxes)
    return min_x, max_x, min_y, max_y


def _is_rect_like_path(
    pts: List[Tuple[float, float]],
    bbox: Tuple[float, float, float, float],
    tol_ratio: float = 0.02,
    border_ratio_threshold: float = 0.8,
) -> bool:
    if not pts:
        return False

    x0, x1, y0, y1 = bbox
    span_x = x1 - x0
    span_y = y1 - y0
    if span_x <= 0 or span_y <= 0:
        return False

    tol_x = span_x * tol_ratio
    tol_y = span_y * tol_ratio

    counts = {"left": 0, "right": 0, "bottom": 0, "top": 0}
    border_points = 0

    for x, y in pts:
        on_left = abs(x - x0) <= tol_x
        on_right = abs(x - x1) <= tol_x
        on_bottom = abs(y - y0) <= tol_y
        on_top = abs(y - y1) <= tol_y

        if on_left:
            counts["left"] += 1
            border_points += 1
        elif on_right:
            counts["right"] += 1
            border_points += 1
        elif on_bottom:
            counts["bottom"] += 1
            border_points += 1
        elif on_top:
            counts["top"] += 1
            border_points += 1

    if border_points == 0:
        return False
    if not all(counts[k] > 0 for k in ("left", "right", "bottom", "top")):
        return False
    if border_points / len(pts) < border_ratio_threshold:
        return False

    return True


def _detect_outer_frame_paths(
    frames_paths: List[List[_PathData]],
    global_bbox: Tuple[float, float, float, float],
    frame_margin_rel: float,
) -> None:
    gx0, gx1, gy0, gy1 = global_bbox
    span_x = gx1 - gx0
    span_y = gy1 - gy0
    if span_x <= 0 or span_y <= 0:
        return

    tol_x = span_x * frame_margin_rel
    tol_y = span_y * frame_margin_rel

    for frame_paths in frames_paths:
        for pd in frame_paths:
            x0, x1, y0, y1 = pd.bbox
            if (
                abs(x0 - gx0) <= tol_x
                and abs(x1 - gx1) <= tol_x
                and abs(y0 - gy0) <= tol_y
                and abs(y1 - gy1) <= tol_y
            ):
                if _is_rect_like_path(pd.points, pd.bbox):
                    pd.is_outer_frame = True


def _make_normalizer(
    global_bbox: Tuple[float, float, float, float],
    fit_axis: str,
    fill_ratio: float,
) -> Callable[[float, float], Tuple[int, int]]:
    gx0, gx1, gy0, gy1 = global_bbox
    span_x = gx1 - gx0
    span_y = gy1 - gy0
    if span_x <= 0 or span_y <= 0:
        raise RuntimeError("Bounding box globale dégénérée")

    cx = (gx0 + gx1) / 2.0
    cy = (gy0 + gy1) / 2.0

    span_max = max(span_x, span_y)
    span_min = min(span_x, span_y)

    if fit_axis == "x":
        base_span = span_x
    elif fit_axis == "y":
        base_span = span_y
    elif fit_axis == "min":
        base_span = span_min
    else:
        base_span = span_max

    if base_span <= 0:
        base_span = span_max or 1.0

    usable_span = ILDA_SPAN * max(0.0, min(1.0, fill_ratio))
    scale = usable_span / base_span

    def _norm(x: float, y: float) -> Tuple[int, int]:
        xn = (x - cx) * scale
        yn = (y - cy) * scale

        xn = max(ILDA_MIN, min(ILDA_MAX, xn))
        yn = max(ILDA_MIN, min(ILDA_MAX, yn))

        return int(round(xn)), int(round(yn))

    return _norm


def export_project_to_ilda(
    project_name: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.98,
    min_rel_size: float = 0.01,
    remove_outer_frame: bool = True,
    frame_margin_rel: float = 0.02,
    check_cancel: Optional[Callable[[], bool]] = None,
    report_progress: Optional[Callable[[int], None]] = None,
    mode: str = "classic",
) -> Path:
    """
    Export ILDA pour un projet donné.

    - report_progress(idx_0_based) : index de frame 0-based.
    - mode : "classic", "arcade", ...
    """
    project_root = PROJECTS_ROOT / project_name
    svg_dir = project_root / "svg"
    ilda_dir = project_root / "ilda"
    ilda_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(svg_dir.glob("frame_*.svg"))
    if not svg_files:
        raise RuntimeError(f"Aucun SVG trouvé dans {svg_dir}")

    profile: IldaProfile = get_ilda_profile(mode)

    frames_paths: List[List[_PathData]] = []
    for svg_file in svg_files:
        if check_cancel is not None and check_cancel():
            raise RuntimeError("Export ILDA annulé par l'utilisateur (lecture SVG).")
        frames_paths.append(_load_svg_paths(svg_file))

    all_bboxes: List[Tuple[float, float, float, float]] = [
        pd.bbox for frame_paths in frames_paths for pd in frame_paths
    ]
    if not all_bboxes:
        raise RuntimeError("Aucun chemin exploitable trouvé dans les SVG du projet.")

    global_bbox = _combine_bbox(all_bboxes)

    # Comportement conservé : on se base sur l'argument remove_outer_frame.
    # (Le profil peut servir plus tard à des defaults différents.)
    if remove_outer_frame:
        _detect_outer_frame_paths(frames_paths, global_bbox, frame_margin_rel)

    normalizer = _make_normalizer(global_bbox, fit_axis=fit_axis, fill_ratio=fill_ratio)

    frames: List[IldaFrame] = []
    frame_local_spans: List[float] = []

    for frame_paths in frames_paths:
        xs: List[float] = []
        ys: List[float] = []
        for pd in frame_paths:
            if pd.is_outer_frame:
                continue
            x0, x1, y0, y1 = pd.bbox
            xs.extend([x0, x1])
            ys.extend([y0, y1])
        span = max(max(xs) - min(xs), max(ys) - min(ys)) if (xs and ys) else 0.0
        frame_local_spans.append(span)

    gx0, gx1, gy0, gy1 = global_bbox
    global_span = max(gx1 - gx0, gy1 - gy0) or 1.0

    for idx, frame_paths in enumerate(frames_paths):
        if check_cancel is not None and check_cancel():
            raise RuntimeError("Export ILDA annulé par l'utilisateur (construction frames).")

        ilda_points: List[IldaPoint] = []

        local_span = frame_local_spans[idx] if frame_local_spans[idx] > 0 else global_span

        for pd in frame_paths:
            if pd.is_outer_frame:
                continue

            x0, x1, y0, y1 = pd.bbox
            w = x1 - x0
            h = y1 - y0
            rel_size = max(w, h) / local_span if local_span > 0 else 1.0

            if min_rel_size > 0.0 and rel_size < min_rel_size:
                continue

            if not pd.points:
                continue

            ilda_coords = [normalizer(x, y) for (x, y) in pd.points]

            first_x, first_y = ilda_coords[0]
            ilda_points.append(
                IldaPoint(
                    x=first_x,
                    y=first_y,
                    z=0,
                    blanked=True,
                    color_index=profile.base_color_index,
                )
            )

            for x, y in ilda_coords[1:]:
                ilda_points.append(
                    IldaPoint(
                        x=x,
                        y=y,
                        z=0,
                        blanked=False,
                        color_index=profile.base_color_index,
                    )
                )

        if not ilda_points:
            ilda_points.append(
                IldaPoint(
                    x=0,
                    y=0,
                    z=0,
                    blanked=True,
                    color_index=profile.base_color_index,
                )
            )

        frames.append(
            IldaFrame(
                name=f"F{idx:04d}",
                company="LPIP",
                points=ilda_points,
                projector=0,
            )
        )

        if report_progress is not None:
            report_progress(idx)

    out_path = ilda_dir / f"{project_name}.ild"
    write_ilda_file(out_path, frames)
    return out_path
