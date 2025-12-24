# core/pipeline/arcade_lines_step.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Dict

import numpy as np
import cv2

from core.config import PROJECTS_ROOT
from core.ilda_writer import IldaFrame, IldaPoint, write_ilda_file
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback

ILDA_MIN = -32767
ILDA_MAX = 32767
ILDA_SPAN = ILDA_MAX - ILDA_MIN


# ----------------------------
# Utilitaires géométrie
# ----------------------------
def _rdp(points: List[Tuple[int, int]], eps: float) -> List[Tuple[int, int]]:
    # Ramer–Douglas–Peucker simplifié (iteratif)
    if len(points) < 3 or eps <= 0:
        return points

    pts = np.array(points, dtype=np.float32)

    def dist_point_line(p, a, b) -> float:
        ab = b - a
        if np.allclose(ab, 0):
            return float(np.linalg.norm(p - a))
        t = float(np.dot(p - a, ab) / np.dot(ab, ab))
        t = max(0.0, min(1.0, t))
        proj = a + t * ab
        return float(np.linalg.norm(p - proj))

    keep = np.zeros(len(pts), dtype=bool)
    keep[0] = True
    keep[-1] = True
    stack = [(0, len(pts) - 1)]

    while stack:
        i, j = stack.pop()
        a = pts[i]
        b = pts[j]
        max_d = 0.0
        max_k = None
        for k in range(i + 1, j):
            d = dist_point_line(pts[k], a, b)
            if d > max_d:
                max_d = d
                max_k = k
        if max_k is not None and max_d > eps:
            keep[max_k] = True
            stack.append((i, max_k))
            stack.append((max_k, j))

    return [points[i] for i in range(len(points)) if keep[i]]


def _neighbors8(y: int, x: int) -> List[Tuple[int, int]]:
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            out.append((y + dy, x + dx))
    return out


def _zs_thinning(binary01: np.ndarray, max_iter: int = 50) -> np.ndarray:
    """
    Zhang-Suen thinning fallback.
    binary01: uint8 (0/1)
    """
    img = (binary01.copy() > 0).astype(np.uint8)
    h, w = img.shape[:2]

    def iter_step(step: int) -> int:
        to_del = []
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                p1 = img[y, x]
                if p1 != 1:
                    continue
                p2 = img[y - 1, x]
                p3 = img[y - 1, x + 1]
                p4 = img[y, x + 1]
                p5 = img[y + 1, x + 1]
                p6 = img[y + 1, x]
                p7 = img[y + 1, x - 1]
                p8 = img[y, x - 1]
                p9 = img[y - 1, x - 1]
                neigh = [p2, p3, p4, p5, p6, p7, p8, p9]
                B = sum(neigh)
                if B < 2 or B > 6:
                    continue
                A = 0
                seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
                for i in range(8):
                    if seq[i] == 0 and seq[i + 1] == 1:
                        A += 1
                if A != 1:
                    continue
                if step == 0:
                    if p2 * p4 * p6 != 0:
                        continue
                    if p4 * p6 * p8 != 0:
                        continue
                else:
                    if p2 * p4 * p8 != 0:
                        continue
                    if p2 * p6 * p8 != 0:
                        continue
                to_del.append((y, x))
        for (y, x) in to_del:
            img[y, x] = 0
        return len(to_del)

    for _ in range(max_iter):
        c0 = iter_step(0)
        c1 = iter_step(1)
        if c0 + c1 == 0:
            break
    return img


def _thin(binary01: np.ndarray) -> np.ndarray:
    # essaie ximgproc.thinning si dispo, sinon fallback ZS
    try:
        ximg = cv2.ximgproc.thinning((binary01 * 255).astype(np.uint8))
        return (ximg > 0).astype(np.uint8)
    except Exception:
        return _zs_thinning(binary01)


def _skeleton_to_polylines(skel01: np.ndarray) -> List[List[Tuple[int, int]]]:
    """
    Convertit un squelette (0/1) en polylines en parcourant le graphe 8-connexe.
    """
    h, w = skel01.shape
    ys, xs = np.where(skel01 > 0)
    if len(ys) == 0:
        return []

    # degrés
    deg = np.zeros_like(skel01, dtype=np.uint8)
    for y, x in zip(ys, xs):
        d = 0
        for ny, nx in _neighbors8(y, x):
            if 0 <= ny < h and 0 <= nx < w and skel01[ny, nx] > 0:
                d += 1
        deg[y, x] = d

    endpoints = [(y, x) for y, x in zip(ys, xs) if deg[y, x] == 1]
    junctions = {(y, x) for y, x in zip(ys, xs) if deg[y, x] >= 3}

    visited_edges: set[Tuple[Tuple[int, int], Tuple[int, int]]] = set()

    def mark_edge(a, b):
        if a <= b:
            visited_edges.add((a, b))
        else:
            visited_edges.add((b, a))

    def edge_visited(a, b) -> bool:
        return (a, b) in visited_edges or (b, a) in visited_edges

    def next_neighbors(p):
        y, x = p
        out = []
        for ny, nx in _neighbors8(y, x):
            if 0 <= ny < h and 0 <= nx < w and skel01[ny, nx] > 0:
                out.append((ny, nx))
        return out

    polylines: List[List[Tuple[int, int]]] = []

    # 1) traces depuis endpoints
    for ep in endpoints:
        for nb in next_neighbors(ep):
            if edge_visited(ep, nb):
                continue
            line = [ep]
            prev = ep
            cur = nb
            mark_edge(prev, cur)
            while True:
                line.append(cur)
                if cur in junctions or deg[cur] == 1:
                    break
                nbs = next_neighbors(cur)
                # continuer tout droit : choisir le voisin != prev
                nxt = None
                for cand in nbs:
                    if cand != prev:
                        nxt = cand
                        break
                if nxt is None:
                    break
                prev, cur = cur, nxt
                if edge_visited(prev, cur):
                    break
                mark_edge(prev, cur)
            polylines.append(line)

    # 2) cycles (pas d'endpoints)
    for y, x in zip(ys, xs):
        p = (y, x)
        for nb in next_neighbors(p):
            if edge_visited(p, nb):
                continue
            line = [p]
            prev = p
            cur = nb
            mark_edge(prev, cur)
            while True:
                line.append(cur)
                nbs = next_neighbors(cur)
                nxt = None
                for cand in nbs:
                    if cand != prev and not edge_visited(cur, cand):
                        nxt = cand
                        break
                if nxt is None:
                    break
                prev, cur = cur, nxt
                mark_edge(prev, cur)
                if cur == p:
                    break
            polylines.append(line)

    # convert (y,x) -> (x,y)
    return [[(x, y) for (y, x) in pl] for pl in polylines]


def _compute_global_norm(frames_polys: List[List[List[Tuple[int, int]]]]) -> Tuple[Tuple[float, float], float]:
    all_pts = [pt for frame in frames_polys for poly in frame for pt in poly] if frames_polys else []
    if not all_pts:
        return (0.0, 0.0), 1.0
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    scale = ILDA_SPAN / span
    return (cx, cy), scale

def _norm_xy(
    x: int,
    y: int,
    center: Tuple[float, float],
    scale: float,
    fill_ratio: float,
    *,
    invert_y: bool = False,
) -> Tuple[int, int]:
    cx, cy = center
    s = scale * float(fill_ratio)
    xn = int(round((x - cx) * s))

    dy = (y - cy)
    if invert_y:
        dy = -dy
    yn = int(round(dy * s))

    xn = max(ILDA_MIN, min(ILDA_MAX, xn))
    yn = max(ILDA_MIN, min(ILDA_MAX, yn))
    return xn, yn


def _sample_rgb_along_poly(img_bgr, poly, step: int = 6, radius: int = 1):
    """
    Sample color along polyline:
    - take points every `step`
    - for each point, look at a (2r+1)x(2r+1) window
    - pick the brightest pixel in that window to avoid background
    - aggregate via median (robust)
    """
    import numpy as np

    if img_bgr is None or poly is None or len(poly) < 2:
        return 255, 255, 255

    h, w = img_bgr.shape[:2]
    samples = []

    pts = poly[:: max(1, int(step))]
    for (x, y) in pts:
        xi = int(round(x))
        yi = int(round(y))
        if xi < 0 or yi < 0 or xi >= w or yi >= h:
            continue

        x0 = max(0, xi - radius)
        x1 = min(w - 1, xi + radius)
        y0 = max(0, yi - radius)
        y1 = min(h - 1, yi + radius)

        patch = img_bgr[y0 : y1 + 1, x0 : x1 + 1]  # BGR
        if patch.size == 0:
            continue

        # Brightness = sum(B,G,R). Pick brightest pixel in patch.
        flat = patch.reshape(-1, 3)
        idx = int(np.argmax(flat.sum(axis=1)))
        b, g, r = flat[idx]
        samples.append((int(r), int(g), int(b)))  # convert to RGB

    if not samples:
        return 255, 255, 255

    arr = np.array(samples, dtype=np.int32)
    r = int(np.median(arr[:, 0]))
    g = int(np.median(arr[:, 1]))
    b = int(np.median(arr[:, 2]))
    return r, g, b

def _order_polylines(polylines: List[List[Tuple[int, int]]]) -> List[List[Tuple[int, int]]]:
    # greedy nearest-neighbor ordering (simple et efficace)
    if not polylines:
        return []
    remaining = polylines[:]
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1][-1]
        best_i = 0
        best_d = 1e18
        best_rev = False
        for i, pl in enumerate(remaining):
            d1 = (pl[0][0] - last[0]) ** 2 + (pl[0][1] - last[1]) ** 2
            d2 = (pl[-1][0] - last[0]) ** 2 + (pl[-1][1] - last[1]) ** 2
            if d1 < best_d:
                best_d = d1
                best_i = i
                best_rev = False
            if d2 < best_d:
                best_d = d2
                best_i = i
                best_rev = True
        nxt = remaining.pop(best_i)
        if best_rev:
            nxt = list(reversed(nxt))
        ordered.append(nxt)
    return ordered


def run_arcade_lines_step(
    project: str,
    *,
    fps: int,
    max_frames: int | None = None,
    kpps: int = 30,
    ppf_ratio: float = 0.75,
    max_points_per_frame: Optional[int] = None,
    fill_ratio: float = 0.95,
    canny1: int = 50,
    canny2: int = 140,
    blur_ksize: int = 3,
    min_poly_len: int = 30,
    simplify_eps: float = 1.2,
    sample_color: bool = False,
    invert_y: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Arcade v2 (laser-first):
    frames PNG -> edges -> thinning -> polylines -> ordering -> ILDA truecolor.

    kpps/ppf_ratio/max_points_per_frame:
      - kpps: vitesse laser (kilo-points par seconde)
      - budget auto: (kpps*1000/fps)*ppf_ratio
      - max_points_per_frame force un budget explicite si fourni
    """
    step_name = "arcade_lines"

    project_root = PROJECTS_ROOT / project
    frames_dir = project_root / "frames"
    out_path = project_root / f"{project}.ild"

    pngs = sorted(frames_dir.glob("frame_*.png"))
    if max_frames is not None and max_frames > 0:
        pngs = pngs[:max_frames]
    if not pngs:
        return StepResult(False, "Aucune frame PNG trouvée (step FFmpeg).", project_root)

    if max_points_per_frame is None:
        # budget "safe" (blanking + marge)
        max_points_per_frame = int((kpps * 1000 / max(1, fps)) * float(ppf_ratio))
        max_points_per_frame = max(200, min(60000, max_points_per_frame))

    if progress_cb:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=(
                    "Extraction traits (OpenCV)… "
                    f"(fps={fps}, kpps={kpps}, budget={max_points_per_frame} pts/frame, "
                    f"canny=({canny1},{canny2}), blur={blur_ksize}, min_poly_len={min_poly_len}, eps={simplify_eps})"
                ),
                frame_index=0,
                total_frames=len(pngs),
                frame_path=None,
            )
        )

    # 1) construire toutes les polylines (pour normalisation globale stable)
    all_frames_polys: List[List[List[Tuple[int, int]]]] = []

    # on stocke aussi l'image BGR si sampling couleur
    bgr_cache: Dict[int, np.ndarray] = {}

    for idx, p in enumerate(pngs):
        if cancel_cb and cancel_cb():
            return StepResult(False, "Annulé.", project_root)

        img_bgr = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img_bgr is None:
            all_frames_polys.append([])
            continue

        if sample_color:
            bgr_cache[idx] = img_bgr

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        if blur_ksize and blur_ksize >= 3:
            k = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
            gray = cv2.GaussianBlur(gray, (k, k), 0)

        edges = cv2.Canny(gray, threshold1=canny1, threshold2=canny2)
        binary01 = (edges > 0).astype(np.uint8)

        skel01 = _thin(binary01)

        polylines = _skeleton_to_polylines(skel01)
        # filtre longueur
        polylines = [pl for pl in polylines if len(pl) >= max(2, min_poly_len)]
        # simplification
        polylines = [_rdp(pl, simplify_eps) for pl in polylines]
        polylines = [pl for pl in polylines if len(pl) >= 2]
        # ordering pour limiter les jumps
        polylines = _order_polylines(polylines)

        all_frames_polys.append(polylines)

        if progress_cb:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=f"Frame {idx+1}/{len(pngs)}: polylines={len(polylines)}",
                    frame_index=idx + 1,
                    total_frames=len(pngs),
                    frame_path=p,
                )
            )

    center, scale = _compute_global_norm(all_frames_polys)

    # 2) conversion ILDA (avec cap points/frame)
    frames_out: List[IldaFrame] = []

    for idx, polylines in enumerate(all_frames_polys):
        if cancel_cb and cancel_cb():
            return StepResult(False, "Annulé.", project_root)

        pts_out: List[IldaPoint] = []
        img_bgr = bgr_cache.get(idx) if sample_color else None

        for poly in polylines:
            if len(pts_out) >= max_points_per_frame:
                break

            rgb = _sample_rgb_along_poly(img_bgr, poly) if sample_color else (255, 255, 255)

            x0, y0 = poly[0]
            xn0, yn0 = _norm_xy(x0, y0, center, scale, fill_ratio, invert_y=invert_y)
            pts_out.append(IldaPoint(x=xn0, y=yn0, blanked=True, r=rgb[0], g=rgb[1], b=rgb[2]))
            
            for (x, y) in poly[1:]:
                if len(pts_out) >= max_points_per_frame:
                    break
                xn, yn = _norm_xy(x, y, center, scale, fill_ratio, invert_y=invert_y)
                pts_out.append(IldaPoint(x=xn, y=yn, blanked=False, r=rgb[0], g=rgb[1], b=rgb[2]))
        
        if not pts_out:
            pts_out.append(IldaPoint(x=0, y=0, blanked=True, r=255, g=255, b=255))

        frames_out.append(IldaFrame(name=f"F{idx:04d}", company="LPIP", points=pts_out, projector=0))

        if progress_cb:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=f"Frame {idx+1}/{len(all_frames_polys)}: points={len(pts_out)}/{max_points_per_frame} (kpps={kpps}, fps={fps})",
                    frame_index=idx + 1,
                    total_frames=len(all_frames_polys),
                    frame_path=None,
                )
            )

    write_ilda_file(out_path, frames_out, mode="truecolor")

    return StepResult(True, f"Arcade v2 OK -> {out_path}", project_root)
