# core/ilda_export.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import xml.etree.ElementTree as ET

from svgpathtools import Line, parse_path
from PIL import Image  # ajoute ceci

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
    if not vis:
        return 0, 0, 0, 0
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

def _arcade_palette_256() -> list[tuple[int, int, int]]:
    """
    Palette 256 entrées. On remplit quelques indices utiles, le reste noir.
    Indices choisis arbitrairement MAIS cohérents car on embarque la palette (format 2).
    """
    pal = [(0, 0, 0)] * 256
    pal[0] = (0, 0, 0)          # noir
    pal[1] = (255, 255, 255)    # blanc
    pal[2] = (255, 0, 0)        # rouge
    pal[3] = (0, 255, 0)        # vert
    pal[4] = (0, 0, 255)        # bleu
    pal[5] = (255, 255, 0)      # jaune
    pal[6] = (0, 255, 255)      # cyan
    pal[7] = (255, 0, 255)      # magenta
    pal[8] = (255, 165, 0)      # orange
    return pal


def _nearest_palette_index(rgb: tuple[int, int, int], palette: list[tuple[int, int, int]], allowed: list[int]) -> int:
    r, g, b = rgb
    best_i = allowed[0]
    best_d = 1e18
    for i in allowed:
        pr, pg, pb = palette[i]
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def _sample_subpath_color(img_rgb: Image.Image, pts: list[tuple[float, float]]) -> tuple[int, int, int]:
    """
    Echantillonne une polyligne et retourne une couleur représentative.
    Arcade: on cherche des pixels non noirs (traits).
    """
    w, h = img_rgb.size
    px = img_rgb.load()

    # échantillonnage: ~64 points max
    n = len(pts)
    if n == 0:
        return (255, 255, 255)

    step = max(1, n // 64)
    candidates: list[tuple[int, int, int]] = []

    for i in range(0, n, step):
        x, y = pts[i]
        xi = min(w - 1, max(0, int(round(x))))
        yi = min(h - 1, max(0, int(round(y))))
        r, g, b = px[xi, yi]

        # ignore quasi-noir (fond)
        if r + g + b < 40:
            continue
        candidates.append((r, g, b))

    if not candidates:
        # fallback: on prend la moyenne globale des samples même si sombres
        x, y = pts[n // 2]
        xi = min(w - 1, max(0, int(round(x))))
        yi = min(h - 1, max(0, int(round(y))))
        return tuple(px[xi, yi])

    # couleur dominante simple: moyenne robuste
    sr = sum(c[0] for c in candidates)
    sg = sum(c[1] for c in candidates)
    sb = sum(c[2] for c in candidates)
    m = len(candidates)
    return (sr // m, sg // m, sb // m)


def _estimate_linea_emotion_color(img_rgb: Image.Image) -> tuple[int, int, int]:
    """
    Pour La Linea : le trait est blanc, le fond exprime l'émotion.
    On estime la couleur dominante du fond en ignorant les pixels très clairs.
    """
    w, h = img_rgb.size
    px = img_rgb.load()

    # échantillonne une grille (rapide)
    samples: list[tuple[int, int, int]] = []
    grid = 60
    for gy in range(0, h, max(1, h // grid)):
        for gx in range(0, w, max(1, w // grid)):
            r, g, b = px[gx, gy]
            # ignore pixels très clairs (trait)
            if r > 230 and g > 230 and b > 230:
                continue
            samples.append((r, g, b))

    if not samples:
        return (255, 255, 255)

    sr = sum(c[0] for c in samples)
    sg = sum(c[1] for c in samples)
    sb = sum(c[2] for c in samples)
    m = len(samples)
    return (sr // m, sg // m, sb // m)


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

        # charge la PNG source pour la couleur (si dispo)
        png_path = (project_root / "frames" / f"frame_{frame_idx+1:04d}.png")
        img_rgb = None
        if png_path.exists() and mode in ("arcade", "la_linea"):
            # IMPORTANT (Windows): utiliser un context manager pour éviter de garder le fichier ouvert.
            with Image.open(png_path) as im:
                img_rgb = im.convert("RGB")

        points: List[IldaPoint] = []

        # --- Couleur (robuste) -------------------------------------------------
        # classic : couleur fixe (profile.base_color_index)
        # arcade  : couleur par sous-chemin, estimée dans la PNG source, puis quantifiée vers une palette embarquée
        # la_linea: couleur unique "émotion" estimée via la couleur dominante du fond (hors pixels très clairs)
        palette = None
        allowed = None
        linea_idx = None

        if mode in ("arcade", "la_linea"):
            palette = _arcade_palette_256()
            # Indices utilisables (non noirs). On pourra élargir plus tard sans casser le format.
            allowed = [1, 2, 3, 4, 5, 6, 7, 8]

            if mode == "la_linea" and img_rgb is not None:
                emo_rgb = _estimate_linea_emotion_color(img_rgb)
                linea_idx = _nearest_palette_index(emo_rgb, palette, allowed)

        # --- Géométrie : blank jump + tracé par sous-chemin (évite les liaisons parasites) ---
        for sp in frame_subpaths:
            if not sp.points:
                continue

            # choix couleur par sous-chemin
            if mode == "arcade" and img_rgb is not None and palette is not None and allowed is not None:
                sp_rgb = _sample_subpath_color(img_rgb, sp.points)
                color_idx = _nearest_palette_index(sp_rgb, palette, allowed)
            elif mode == "la_linea" and linea_idx is not None:
                color_idx = linea_idx
            else:
                color_idx = profile.base_color_index

            coords = [normalizer(x, y) for x, y in sp.points]
            x0, y0 = coords[0]

            points.append(IldaPoint(x=x0, y=y0, z=0, blanked=True, color_index=color_idx))
            for x, y in coords[1:]:
                points.append(IldaPoint(x=x, y=y, z=0, blanked=False, color_index=color_idx))

        # Frame vide => point blanked pour conserver le nombre de frames
        if not points:
            points.append(IldaPoint(x=0, y=0, z=0, blanked=True, color_index=profile.base_color_index))

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
            report_progress(frame_idx + 1, total_frames)

    out_path = ilda_dir / f"{project_name}.ild"
    if mode in ("arcade", "la_linea"):
        write_ilda_file(out_path, frames, palette_rgb_256=_arcade_palette_256())
    else:
        write_ilda_file(out_path, frames)
    return out_path