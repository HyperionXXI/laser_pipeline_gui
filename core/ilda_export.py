# core/ilda_export.py
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Tuple
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from svgpathtools import Line, parse_path

from .config import PROJECTS_ROOT
from .ilda_profiles import IldaProfile, get_ilda_profile
from .ilda_writer import IldaFrame, IldaPoint, write_ilda_file


ILDA_MIN = -32767.0
ILDA_MAX = +32767.0
ILDA_SPAN = ILDA_MAX - ILDA_MIN


@dataclass
class _PathData:
    points: List[Tuple[float, float]]
    bbox: Tuple[float, float, float, float]
    is_outer_frame: bool = False


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


def _load_svg_paths(svg_file: Path) -> List[_PathData]:
    tree = ET.parse(svg_file)
    root = tree.getroot()
    paths: List[_PathData] = []

    for elem in root.iter():
        if not elem.tag.lower().endswith("path"):
            continue

        d_attr = elem.get("d")
        if not d_attr:
            continue

        try:
            sp = parse_path(d_attr)
        except Exception:
            continue

        pts = _path_to_polyline(sp)
        if not pts:
            continue

        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        bbox = (min(xs), max(xs), min(ys), max(ys))
        paths.append(_PathData(points=pts, bbox=bbox))

    return paths


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
    report_progress: Optional[Callable[[int,int], None]] = None,
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
    if not svg_files:
        raise RuntimeError("Aucun SVG trouvé pour l'export ILDA")

    profile: IldaProfile = get_ilda_profile(mode)

    frames_paths = []
    for svg in svg_files:
        if check_cancel and check_cancel():
            raise RuntimeError("Export ILDA annulé")
        frames_paths.append(_load_svg_paths(svg))

    all_bboxes = [pd.bbox for fps in frames_paths for pd in fps]
    if not all_bboxes:
        raise RuntimeError("Aucun chemin exploitable dans les SVG")

    global_bbox = _combine_bbox(all_bboxes)
    normalizer = _make_normalizer(global_bbox, fit_axis, fill_ratio)

    frames: List[IldaFrame] = []

    for frame_idx, frame_paths in enumerate(frames_paths):
        if check_cancel and check_cancel():
            raise RuntimeError("Export ILDA annulé")

        points: List[IldaPoint] = []

        for pd in frame_paths:
            if not pd.points:
                continue

            coords = [normalizer(x, y) for x, y in pd.points]

            # blank jump
            x0, y0 = coords[0]
            points.append(
                IldaPoint(x=x0, y=y0, z=0, blanked=True, color_index=profile.base_color_index)
            )

            for x, y in coords[1:]:
                points.append(
                    IldaPoint(x=x, y=y, z=0, blanked=False, color_index=profile.base_color_index)
                )

        if not points:
            points.append(
                IldaPoint(x=0, y=0, z=0, blanked=True, color_index=profile.base_color_index)
            )

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
