from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import xml.etree.ElementTree as ET

from svgpathtools import parse_path, Line

from .config import PROJECTS_ROOT
from .ilda_writer import (
    IldaPoint,
    IldaFrame,
    write_ilda_file,
    write_demo_square,  # conservé pour compat éventuelle
)
from .ilda_profiles import IldaProfile, get_ilda_profile

# Backward-compat (anciens noms utilisés ailleurs dans le projet)
ILDAPoint = IldaPoint
ILDAFrame = IldaFrame


# =====================================================================
# Constantes & structures internes
# =====================================================================

ILDA_MIN = -32767.0
ILDA_MAX = +32767.0
ILDA_SPAN = ILDA_MAX - ILDA_MIN


@dataclass
class _PathData:
    points: List[Tuple[float, float]]
    bbox: Tuple[float, float, float, float]  # (min_x, max_x, min_y, max_y)
    is_outer_frame: bool = False


# =====================================================================
# Utilitaires géométriques / SVG
# =====================================================================


def _path_to_polyline(path, samples_per_curve: int = 24) -> List[Tuple[float, float]]:
    """
    Convertit un svgpathtools.Path en liste de points (x, y).

    - Segments de type Line : on prend start et end.
    - Autres segments (courbes) : on échantillonne `samples_per_curve` points.
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
            # Bezier / arcs : on échantillonne
            for i in range(1, samples_per_curve + 1):
                t = i / samples_per_curve
                z = seg.point(t)
                pts.append((float(z.real), float(z.imag)))

    return pts


def _load_svg_paths(svg_file: Path) -> List[_PathData]:
    """
    Charge un SVG Potrace et retourne une liste de _PathData.

    On ignore complètement les questions de namespace :
    on prend tous les éléments dont la balise se termine par 'path',
    on lit l'attribut 'd', et on le passe à svgpathtools.parse_path.
    """
    svg_file = Path(svg_file)
    tree = ET.parse(svg_file)
    root = tree.getroot()

    result: List[_PathData] = []

    for elem in root.iter():
        tag = elem.tag.lower()
        # Tolérant aux namespaces : '{uri}path' se termine par 'path'
        if not tag.endswith("path"):
            continue

        d_attr = elem.get("d")
        if not d_attr:
            continue

        try:
            sp_path = parse_path(d_attr)
        except Exception:
            # On ignore les chemins que parse_path n'arrive pas à lire
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
    """Combine plusieurs bounding boxes en une seule."""
    if not bboxes:
        raise RuntimeError("Aucune bounding box disponible pour le calcul global")

    min_x = min(b[0] for b in bboxes)
    max_x = max(b[1] for b in bboxes)
    min_y = min(b[2] for b in bboxes)
    max_y = max(b[3] for b in bboxes)
    return min_x, max_x, min_y, max_y


def _mark_outer_frame_paths(
    frames_paths: List[List[_PathData]],
    global_bbox: Tuple[float, float, float, float],
    frame_margin_rel: float,
) -> None:
    """
    Marque les chemins correspondant au *cadre extérieur*.

    Deux niveaux d'heuristique :

    1) Niveau global (héritage de l'ancienne version) :
       - chemins dont la bbox colle à la bbox globale sur X/Y
         (avec une tolérance `frame_margin_rel`).

    2) Niveau par frame :
       - détection de segments très fins qui longent un bord de la
         bbox de la frame (haut/bas/gauche/droite), et qui couvrent
         presque toute la largeur ou la hauteur.
       - typiquement : les 4 côtés du cadre généré par Potrace.
    """
    gx0, gx1, gy0, gy1 = global_bbox
    span_x = gx1 - gx0
    span_y = gy1 - gy0
    if span_x <= 0 or span_y <= 0:
        return

    tol_x_global = span_x * frame_margin_rel
    tol_y_global = span_y * frame_margin_rel
    global_area = span_x * span_y

    # Seuils internes globaux (conservateurs).
    coverage_threshold_global = 0.9
    span_ratio_threshold_global = 0.8

    # -----------------------------------------------------------------
    # 1) Premier passage : détection globale (ancienne logique
    #    + couverture de surface).
    # -----------------------------------------------------------------
    for frame_paths in frames_paths:
        for pd in frame_paths:
            x0, x1, y0, y1 = pd.bbox
            w = x1 - x0
            h = y1 - y0
            if w <= 0 or h <= 0:
                continue

            tight_match = (
                abs(x0 - gx0) <= tol_x_global
                and abs(x1 - gx1) <= tol_x_global
                and abs(y0 - gy0) <= tol_y_global
                and abs(y1 - gy1) <= tol_y_global
            )

            coverage = (w * h) / global_area if global_area > 0 else 0.0
            span_ratio_x = w / span_x if span_x > 0 else 0.0
            span_ratio_y = h / span_y if span_y > 0 else 0.0

            looks_like_outer_frame = (
                coverage >= coverage_threshold_global
                and span_ratio_x >= span_ratio_threshold_global
                and span_ratio_y >= span_ratio_threshold_global
            )

            if tight_match or looks_like_outer_frame:
                pd.is_outer_frame = True

    # -----------------------------------------------------------------
    # 2) Deuxième passage : heuristique par frame pour les côtés fins
    #    du cadre (haut, bas, gauche, droite).
    # -----------------------------------------------------------------
    border_span_threshold = 0.95   # couvre ≥ 95 % de la largeur/hauteur
    thickness_threshold = 0.12     # épaisseur ≤ 12 % de la dimension

    for frame_paths in frames_paths:
        if not frame_paths:
            continue

        # bbox de la frame (en incluant tout, même ce qui sera peut-être
        # marqué comme cadre) :
        frame_bboxes = [pd.bbox for pd in frame_paths]
        fx0, fx1, fy0, fy1 = _combine_bbox(frame_bboxes)
        fspan_x = fx1 - fx0
        fspan_y = fy1 - fy0
        if fspan_x <= 0 or fspan_y <= 0:
            continue

        edge_tol_x = fspan_x * frame_margin_rel
        edge_tol_y = fspan_y * frame_margin_rel

        for pd in frame_paths:
            if pd.is_outer_frame:
                # Déjà qualifié de cadre par la logique globale
                continue

            x0, x1, y0, y1 = pd.bbox
            w = x1 - x0
            h = y1 - y0
            if w <= 0 or h <= 0:
                continue

            rel_w = w / fspan_x if fspan_x > 0 else 0.0
            rel_h = h / fspan_y if fspan_y > 0 else 0.0

            # Contact avec les bords de la frame
            near_left = abs(x0 - fx0) <= edge_tol_x
            near_right = abs(x1 - fx1) <= edge_tol_x
            near_bottom = abs(y0 - fy0) <= edge_tol_y
            near_top = abs(y1 - fy1) <= edge_tol_y

            is_horizontal_border = (
                rel_w >= border_span_threshold
                and rel_h <= thickness_threshold
                and near_left
                and near_right
                and (near_bottom or near_top)
            )

            is_vertical_border = (
                rel_h >= border_span_threshold
                and rel_w <= thickness_threshold
                and near_top
                and near_bottom
                and (near_left or near_right)
            )

            if is_horizontal_border or is_vertical_border:
                pd.is_outer_frame = True


# =====================================================================
# Nettoyage du cadre au NIVEAU ILDA
# =====================================================================

def _remove_outer_rectangle_from_ilda_frames(
    frames: List[IldaFrame],
    frame_margin_rel: float,
) -> None:
    """
    Post-traitement ILDA : supprime les points appartenant au grand
    rectangle extérieur (cadre) si on détecte un rectangle complet.

    - On travaille sur les coordonnées ILDA normalisées (x, y).
    - On ne touche qu'aux frames qui présentent clairement un rectangle
      couvrant presque toute la largeur ET toute la hauteur.
    """
    # 1) Bbox globale basée sur les points NON blanked
    xs: List[int] = []
    ys: List[int] = []
    for frame in frames:
        for p in frame.points:
            if p.blanked:
                continue
            xs.append(p.x)
            ys.append(p.y)

    if not xs:
        return

    gx0 = min(xs)
    gx1 = max(xs)
    gy0 = min(ys)
    gy1 = max(ys)
    span_x = gx1 - gx0
    span_y = gy1 - gy0
    if span_x <= 0 or span_y <= 0:
        return

    tol_x = span_x * frame_margin_rel
    tol_y = span_y * frame_margin_rel
    border_span_threshold = 0.90  # ≥ 90 % de la largeur/hauteur

    def _has_full_rectangle(points: List[IldaPoint]) -> bool:
        bottom = [p for p in points if abs(p.y - gy0) <= tol_y]
        top = [p for p in points if abs(p.y - gy1) <= tol_y]
        left = [p for p in points if abs(p.x - gx0) <= tol_x]
        right = [p for p in points if abs(p.x - gx1) <= tol_x]

        if not (bottom and top and left and right):
            return False

        bx_min = min(p.x for p in bottom)
        bx_max = max(p.x for p in bottom)
        tx_min = min(p.x for p in top)
        tx_max = max(p.x for p in top)
        ly_min = min(p.y for p in left)
        ly_max = max(p.y for p in left)
        ry_min = min(p.y for p in right)
        ry_max = max(p.y for p in right)

        horiz_ok = (
            (bx_max - bx_min) >= span_x * border_span_threshold
            and (tx_max - tx_min) >= span_x * border_span_threshold
        )
        vert_ok = (
            (ly_max - ly_min) >= span_y * border_span_threshold
            and (ry_max - ry_min) >= span_y * border_span_threshold
        )
        return horiz_ok and vert_ok

    # 2) Filtrage des points sur le cadre
    for frame in frames:
        pts = frame.points
        if not pts:
            continue

        if not _has_full_rectangle(pts):
            continue

        # On supprime tous les points qui collent à un bord global.
        new_points: List[IldaPoint] = [
            p
            for p in pts
            if not (
                abs(p.y - gy0) <= tol_y
                or abs(p.y - gy1) <= tol_y
                or abs(p.x - gx0) <= tol_x
                or abs(p.x - gx1) <= tol_x
            )
        ]
        frame.points = new_points


def _make_normalizer(
    global_bbox: Tuple[float, float, float, float],
    fit_axis: str,
    fill_ratio: float,
) -> Callable[[float, float], Tuple[int, int]]:
    """
    Construit une fonction (x, y) -> (X_ilda, Y_ilda).

    - `fit_axis` : "max" (par défaut), "min", "x" ou "y"
    - `fill_ratio` : portion de la plage [-32767, +32767] utilisée.
    """
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
    else:  # "max" ou valeur invalide → on utilise span_max
        base_span = span_max

    if base_span <= 0:
        base_span = span_max or 1.0

    usable_span = ILDA_SPAN * max(0.0, min(1.0, fill_ratio))
    scale = usable_span / base_span

    def _norm(x: float, y: float) -> Tuple[int, int]:
        xn = (x - cx) * scale
        yn = (y - cy) * scale

        # clamp dans la plage ILDA
        xn = max(ILDA_MIN, min(ILDA_MAX, xn))
        yn = max(ILDA_MIN, min(ILDA_MAX, yn))

        return int(round(xn)), int(round(yn))

    return _norm


# =====================================================================
# API principale : export ILDA
# =====================================================================


def export_project_to_ilda(
    project_name: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    remove_outer_frame: bool = True,
    frame_margin_rel: float = 0.02,
    check_cancel: Optional[Callable[[], bool]] = None,
    report_progress: Optional[Callable[[int], None]] = None,
    mode: str = "classic",
) -> Path:
    """
    Export ILDA pour un projet donné.

    Paramètres :
    - project_name      : nom du projet (dossier dans PROJECTS_ROOT)
    - fit_axis          : "max", "min", "x", "y" (axe de référence pour le zoom)
    - fill_ratio        : ratio de remplissage de la fenêtre ILDA globale
    - min_rel_size      : taille relative minimale pour garder un chemin
    - remove_outer_frame: si True, essaie de supprimer le "cadre"
    - frame_margin_rel  : tolérance pour la détection de cadre
    - check_cancel      : callback d'annulation
    - report_progress   : callback de progression prenant l’index de frame (0-based)
    - mode              : nom du profil ILDA ("classic", "arcade", ...)

    Prototype compatible avec l’ancienne version pour éviter
    de casser les appels existants.
    """
    project_root = PROJECTS_ROOT / project_name
    svg_dir = project_root / "svg"
    ilda_dir = project_root / "ilda"
    ilda_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(svg_dir.glob("frame_*.svg"))
    if not svg_files:
        raise RuntimeError(f"Aucun SVG trouvé dans {svg_dir}")

    # Profil ILDA (classic / arcade / autre)
    profile: IldaProfile = get_ilda_profile(mode)

    # --------------------------------------------------------------
    # 1) Lecture de tous les SVG en chemins + bboxes
    # --------------------------------------------------------------
    frames_paths: List[List[_PathData]] = []

    for svg_file in svg_files:
        if check_cancel is not None and check_cancel():
            raise RuntimeError("Export ILDA annulé par l'utilisateur (lecture SVG).")

        frame_paths = _load_svg_paths(svg_file)
        frames_paths.append(frame_paths)

    all_bboxes: List[Tuple[float, float, float, float]] = [
        pd.bbox for frame_paths in frames_paths for pd in frame_paths
    ]
    if not all_bboxes:
        raise RuntimeError("Aucun chemin exploitable trouvé dans les SVG du projet.")

    global_bbox_initial = _combine_bbox(all_bboxes)

    # --------------------------------------------------------------
    # 2) Optionnel : détection / suppression du cadre extérieur (niveau SVG)
    # --------------------------------------------------------------
    if remove_outer_frame:
        _mark_outer_frame_paths(frames_paths, global_bbox_initial, frame_margin_rel)
        filtered_bboxes: List[Tuple[float, float, float, float]] = [
            pd.bbox
            for frame_paths in frames_paths
            for pd in frame_paths
            if not pd.is_outer_frame
        ]
        if filtered_bboxes:
            global_bbox = _combine_bbox(filtered_bboxes)
        else:
            # Sécurité : si on a tout viré, on annule le marquage
            # et on revient à la bbox initiale.
            for frame_paths in frames_paths:
                for pd in frame_paths:
                    pd.is_outer_frame = False
            global_bbox = global_bbox_initial
    else:
        global_bbox = global_bbox_initial

    normalizer = _make_normalizer(global_bbox, fit_axis=fit_axis, fill_ratio=fill_ratio)

    gx0, gx1, gy0, gy1 = global_bbox
    span_x = gx1 - gx0
    span_y = gy1 - gy0
    global_span = max(span_x, span_y)

    # --------------------------------------------------------------
    # 3) Construction des frames ILDA
    # --------------------------------------------------------------
    frames: List[IldaFrame] = []
    total_frames = len(svg_files)

    for idx, frame_paths in enumerate(frames_paths):
        if check_cancel is not None and check_cancel():
            raise RuntimeError(
                "Export ILDA annulé par l'utilisateur (construction frames)."
            )

        ilda_points: List[IldaPoint] = []

        for pd in frame_paths:
            if pd.is_outer_frame:
                continue

            x0, x1, y0, y1 = pd.bbox
            w = x1 - x0
            h = y1 - y0
            rel_size = max(w, h) / global_span if global_span > 0 else 1.0
            if rel_size < min_rel_size:
                # Petit parasite → on ignore
                continue

            pts = pd.points
            if not pts:
                continue

            # Conversion des points en coordonnées ILDA
            ilda_coords = [normalizer(x, y) for (x, y) in pts]

            # Premier point blanked = déplacement sans trace
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

            # Points lumineux
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

        # Si aucun point, on crée un point blanked central (frame noire).
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

        frame = IldaFrame(
            name=f"F{idx:04d}",
            company="LPIP",
            points=ilda_points,
            projector=0,
        )
        frames.append(frame)

        if report_progress is not None:
            report_progress(idx)

    # --------------------------------------------------------------
    # 4) Nettoyage ILDA du cadre + sécurité "au moins 1 point"
    # --------------------------------------------------------------
    if remove_outer_frame:
        _remove_outer_rectangle_from_ilda_frames(frames, frame_margin_rel)

    for frame in frames:
        if not frame.points:
            frame.points.append(
                IldaPoint(
                    x=0,
                    y=0,
                    z=0,
                    blanked=True,
                    color_index=profile.base_color_index,
                )
            )

    # --------------------------------------------------------------
    # 5) Écriture du fichier ILDA
    # --------------------------------------------------------------
    out_path = ilda_dir / f"{project_name}.ild"
    write_ilda_file(out_path, frames)
    return out_path
