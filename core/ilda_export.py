# core/ilda_export.py
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import xml.etree.ElementTree as ET

from svgpathtools import Line, parse_path

from .config import PROJECTS_ROOT
from .ilda_profiles import get_ilda_profile
from .ilda_writer import IldaFrame, IldaHeader, IldaPoint, write_ilda_file

ILDA_MIN = -32767
ILDA_MAX = 32767
ILDA_SPAN = ILDA_MAX - ILDA_MIN


def _path_to_polyline(path, samples: int = 64) -> List[Tuple[float, float]]:
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
            for i in range(1, samples + 1):
                z = seg.point(i / samples)
                pts.append((float(z.real), float(z.imag)))
    return pts


def _compute_global_normalization(svg_files: List[Path]) -> Tuple[Tuple[float, float], float]:
    """
    Normalisation globale : centre + scale communs à toutes les frames.
    """
    all_pts: List[Tuple[float, float]] = []

    for svg_path in svg_files:
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
        except Exception:
            continue

        for elem in root.iter():
            if not elem.tag.lower().endswith("path"):
                continue
            d = elem.get("d")
            if not d:
                continue
            try:
                sp = parse_path(d)
            except Exception:
                continue
            all_pts.extend(_path_to_polyline(sp))

    if not all_pts:
        # fallback neutre
        return (0.0, 0.0), 1.0

    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    scale = ILDA_SPAN / span
    return (cx, cy), scale


def _normalize_points(
    pts: List[Tuple[float, float]],
    *,
    center: Tuple[float, float],
    scale: float,
    fill_ratio: float,
) -> List[Tuple[int, int]]:
    cx, cy = center
    out: List[Tuple[int, int]] = []
    s = scale * float(fill_ratio)

    for x, y in pts:
        xn = int(round((x - cx) * s))
        yn = int(round((y - cy) * s))
        xn = max(ILDA_MIN, min(ILDA_MAX, xn))
        yn = max(ILDA_MIN, min(ILDA_MAX, yn))
        out.append((xn, yn))

    return out


_RGB_RE = re.compile(r"^\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*$")


def _parse_data_rgb(val: Optional[str]) -> Optional[Tuple[int, int, int]]:
    if not val:
        return None
    m = _RGB_RE.match(val)
    if not m:
        return None
    r, g, b = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    return r, g, b


def export_project_to_ilda(
    project_name: str,
    *,
    fit_axis: str = "max",         # accepté, pas encore utilisé ici (normalisation globale)
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,    # accepté, pas encore utilisé ici
    mode: str = "classic",
    swap_rb: bool = False,
    check_cancel: Optional[Callable[[], bool]] = None,
    report_progress: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """
    Compute ILDA from SVGs.
    - classic: indexed (format 0)
    - arcade: truecolor (format 5) via data-rgb sur les <path>
    """
    project_root = PROJECTS_ROOT / project_name
    svg_dir = project_root / "svg"
    bmp_dir = project_root / "bmp"
    out_path = project_root / f"{project_name}.ild"

    mode = (mode or "classic").lower()
    profile = get_ilda_profile(mode)

    # ------------------------------------------------------------------
    # Arcade : on s'appuie sur le manifest pour la liste des frames
    # ------------------------------------------------------------------
    if mode == "arcade":
        manifest_path = bmp_dir / "_layers_manifest.json"
        if not manifest_path.exists():
            raise RuntimeError("Manifest arcade '_layers_manifest.json' introuvable (step bitmap arcade).")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        frames_meta = manifest.get("frames", [])
        svg_files = [svg_dir / f'{fr["frame"]}.svg' for fr in frames_meta]
        svg_files = [p for p in svg_files if p.exists()]

        if not svg_files:
            raise RuntimeError("Aucun SVG arcade trouvé (step potrace arcade).")

        center, scale = _compute_global_normalization(svg_files)

        frames_out: List[IldaFrame] = []
        total = len(svg_files)

        for idx, svg_path in enumerate(svg_files):
            if check_cancel and check_cancel():
                raise RuntimeError("ILDA computation canceled")

            tree = ET.parse(svg_path)
            root = tree.getroot()

            pts_out: List[IldaPoint] = []

            for elem in root.iter():
                if not elem.tag.lower().endswith("path"):
                    continue

                d = elem.get("d")
                if not d:
                    continue

                rgb = _parse_data_rgb(elem.get("data-rgb")) or (255, 255, 255)
                if swap_rb:
                    rgb = (rgb[2], rgb[1], rgb[0])

                try:
                    sp = parse_path(d)
                except Exception:
                    continue

                poly = _path_to_polyline(sp)
                coords = _normalize_points(poly, center=center, scale=scale, fill_ratio=fill_ratio)
                if not coords:
                    continue

                # blank jump au début du sous-chemin
                x0, y0 = coords[0]
                pts_out.append(IldaPoint(x=x0, y=y0, blanked=True, r=rgb[0], g=rgb[1], b=rgb[2]))
                for x, y in coords[1:]:
                    pts_out.append(IldaPoint(x=x, y=y, blanked=False, r=rgb[0], g=rgb[1], b=rgb[2]))

            if not pts_out:
                pts_out.append(IldaPoint(x=0, y=0, blanked=True, r=255, g=255, b=255))

            frames_out.append(IldaFrame(header=IldaHeader(format_code=5, frame_name=f"F{idx:04d}", scanner_head=0), points=pts_out))

            if report_progress:
                report_progress(idx, total)

        write_ilda_file(out_path, frames_out, mode="truecolor")
        return out_path

    # ------------------------------------------------------------------
    # Classic / La_linea : on prend les frame_*.svg standards
    # ------------------------------------------------------------------
    svg_files = sorted(svg_dir.glob("frame_*.svg"))
    if not svg_files:
        raise RuntimeError("No SVG found for ILDA computation.")

    center, scale = _compute_global_normalization(svg_files)

    frames_out: List[IldaFrame] = []
    total = len(svg_files)

    for idx, svg_path in enumerate(svg_files):
        if check_cancel and check_cancel():
            raise RuntimeError("ILDA computation canceled")

        tree = ET.parse(svg_path)
        root = tree.getroot()

        pts_out: List[IldaPoint] = []

        for elem in root.iter():
            if not elem.tag.lower().endswith("path"):
                continue
            d = elem.get("d")
            if not d:
                continue

            try:
                sp = parse_path(d)
            except Exception:
                continue

            poly = _path_to_polyline(sp)
            coords = _normalize_points(poly, center=center, scale=scale, fill_ratio=fill_ratio)
            if not coords:
                continue

            # blank jump
            x0, y0 = coords[0]
            pts_out.append(IldaPoint(x=x0, y=y0, blanked=True, color_index=profile.base_color_index))
            for x, y in coords[1:]:
                pts_out.append(IldaPoint(x=x, y=y, blanked=False, color_index=profile.base_color_index))

        if not pts_out:
            pts_out.append(IldaPoint(x=0, y=0, blanked=True, color_index=profile.base_color_index))

        frames_out.append(IldaFrame(header=IldaHeader(format_code=0, frame_name=f"F{idx:04d}", scanner_head=0), points=pts_out))

        if report_progress:
            report_progress(idx, total)

    write_ilda_file(out_path, frames_out, mode="indexed")
    return out_path
