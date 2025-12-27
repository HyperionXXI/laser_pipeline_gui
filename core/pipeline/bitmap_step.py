# core/pipeline/bitmap_step.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
from PIL import Image

from core.config import PROJECTS_ROOT
from core.bitmap_convert import convert_project_frames_to_bmp
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


# ----------------------------------------------------------------------
# Arcade helpers
# ----------------------------------------------------------------------

def _cancelled(cancel_cb: Optional[CancelCallback]) -> bool:
    return bool(cancel_cb and cancel_cb())


def _rgb_distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> int:
    return (c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2


def _is_near_black(rgb: Tuple[int, int, int], thr: int = 40) -> bool:
    return (rgb[0] + rgb[1] + rgb[2]) <= thr


def _morph_open_close(mask: np.ndarray, open_iters: int, close_iters: int) -> np.ndarray:
    """
    Morphologie simple sur binaire (0/1):
    - open = erosion puis dilation
    - close = dilation puis erosion

    Implémentée via convolution max/min par voisinage 3x3, itératif.
    """
    if open_iters <= 0 and close_iters <= 0:
        return mask

    def erode(m: np.ndarray) -> np.ndarray:
        # pixel reste 1 si tous ses voisins 3x3 sont 1
        padded = np.pad(m, 1, mode="constant", constant_values=0)
        out = np.ones_like(m, dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                out &= padded[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]]
        return out

    def dilate(m: np.ndarray) -> np.ndarray:
        # pixel devient 1 si un voisin 3x3 est 1
        padded = np.pad(m, 1, mode="constant", constant_values=0)
        out = np.zeros_like(m, dtype=np.uint8)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                out |= padded[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]]
        return out

    out = mask
    for _ in range(open_iters):
        out = dilate(erode(out))
    for _ in range(close_iters):
        out = erode(dilate(out))
    return out


def _remove_small_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    """
    Supprime les composantes connexes (4-connexité) dont l'aire < min_area.
    mask: np.uint8 (0/1)
    """
    if min_area <= 1:
        return mask

    h, w = mask.shape
    visited = np.zeros((h, w), dtype=np.uint8)
    out = mask.copy()

    def neighbors(y: int, x: int):
        if y > 0:
            yield y - 1, x
        if y + 1 < h:
            yield y + 1, x
        if x > 0:
            yield y, x - 1
        if x + 1 < w:
            yield y, x + 1

    for y in range(h):
        for x in range(w):
            if out[y, x] == 0 or visited[y, x] == 1:
                continue

            # BFS
            stack = [(y, x)]
            visited[y, x] = 1
            comp = [(y, x)]

            while stack:
                cy, cx = stack.pop()
                for ny, nx in neighbors(cy, cx):
                    if out[ny, nx] == 1 and visited[ny, nx] == 0:
                        visited[ny, nx] = 1
                        stack.append((ny, nx))
                        comp.append((ny, nx))

            if len(comp) < min_area:
                for py, px in comp:
                    out[py, px] = 0

    return out


def _quantize_image(img_rgb: Image.Image, n_colors: int) -> Image.Image:
    """
    Quantification adaptive palette (PIL) → retourne image en mode 'P'.
    """
    # dither=0 pour éviter du bruit sur les bords
    return img_rgb.quantize(colors=int(n_colors), method=Image.MEDIANCUT, dither=Image.Dither.NONE)


def _palette_from_p_image(img_p: Image.Image) -> List[Tuple[int, int, int]]:
    pal = img_p.getpalette() or []
    colors = []
    for i in range(0, len(pal), 3):
        colors.append((pal[i], pal[i + 1], pal[i + 2]))
    return colors


def _pick_background_index(img_p: Image.Image, palette: List[Tuple[int, int, int]]) -> int:
    """
    Choisit l'index de fond :
    - priorise une couleur "proche du noir" qui est très fréquente
    - fallback: index le plus fréquent
    """
    arr = np.array(img_p, dtype=np.uint8)
    hist = np.bincount(arr.ravel(), minlength=256)

    # indices triés par fréquence décroissante
    by_freq = np.argsort(-hist)

    for idx in by_freq[:min(16, len(by_freq))]:
        if idx < len(palette) and _is_near_black(palette[idx]):
            return int(idx)

    return int(by_freq[0])


def _write_bmp_bw(path: Path, mask01: np.ndarray) -> None:
    """
    Écrit un BMP noir sur fond blanc (potrace-friendly, invert_for_potrace=False):
    - foreground (mask=1) → noir (0)
    - background (mask=0) → blanc (255)
    """
    img = Image.fromarray(np.where(mask01 > 0, 0, 255).astype(np.uint8), mode="L")
    img.save(path)


def _generate_arcade_layers_for_frame(
    png_path: Path,
    bmp_dir: Path,
    *,
    n_colors: int,
    min_area: int,
    morph_open: int,
    morph_close: int,
) -> Dict[str, Any]:
    """
    Génère les couches arcade d'une frame :
    - frame_XXXX_cYY.bmp
    - frame_XXXX.bmp (union preview)
    - frame_XXXX_layers.json
    """
    frame_stem = png_path.stem.replace("frame_", "")  # "0001"
    frame_id = frame_stem

    img_rgb = Image.open(png_path).convert("RGB")
    img_p = _quantize_image(img_rgb, n_colors=n_colors)
    palette = _palette_from_p_image(img_p)

    arr = np.array(img_p, dtype=np.uint8)
    bg_idx = _pick_background_index(img_p, palette)

    # indices présents (hors background)
    present = np.unique(arr)
    layer_indices = [int(i) for i in present if int(i) != bg_idx]

    layers_meta: List[Dict[str, Any]] = []
    union_mask = np.zeros(arr.shape, dtype=np.uint8)

    for li, idx in enumerate(layer_indices):
        rgb = palette[idx] if idx < len(palette) else (255, 255, 255)

        mask = (arr == idx).astype(np.uint8)

        # Nettoyage morpho + bruit
        mask = _morph_open_close(mask, open_iters=morph_open, close_iters=morph_close)
        mask = _remove_small_components(mask, min_area=min_area)

        if mask.sum() == 0:
            continue

        union_mask |= mask

        bmp_name = f"frame_{frame_id}_c{li:02d}.bmp"
        bmp_path = bmp_dir / bmp_name
        _write_bmp_bw(bmp_path, mask)

        layers_meta.append(
            {
                "layer_index": li,
                "palette_index": idx,
                "rgb": [int(rgb[0]), int(rgb[1]), int(rgb[2])],
                "bmp": bmp_name,
            }
        )

    # Preview union (pour compat preview & pipeline existant)
    preview_bmp = bmp_dir / f"frame_{frame_id}.bmp"
    if union_mask.sum() == 0:
        # frame vide → blanc
        Image.new("L", img_rgb.size, 255).save(preview_bmp)
    else:
        _write_bmp_bw(preview_bmp, union_mask)

    frame_manifest = {
        "frame": f"frame_{frame_id}",
        "source_png": png_path.name,
        "n_colors": int(n_colors),
        "background_palette_index": int(bg_idx),
        "layers": layers_meta,
        "preview_bmp": preview_bmp.name,
    }

    manifest_path = bmp_dir / f"frame_{frame_id}_layers.json"
    manifest_path.write_text(json.dumps(frame_manifest, indent=2), encoding="utf-8")

    return frame_manifest


# ----------------------------------------------------------------------
# PUBLIC STEP
# ----------------------------------------------------------------------

def run_bitmap_step(
    project: str,
    threshold: int,
    use_thinning: bool,
    max_frames: Optional[int] = None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
    *,
    mode: str = "arcade",
    arcade_n_colors: int = 16,
    arcade_min_area: int = 12,
    arcade_morph_open: int = 1,
    arcade_morph_close: int = 0,
) -> StepResult:
    """
    Step pipeline : PNG -> BMP pour un projet donné.

    Classic (par défaut):
      - comportement inchangé : convert_project_frames_to_bmp(... threshold, thinning ...)

    Arcade:
      - quantification couleurs + séparation en couches BMP
      - écrit aussi un BMP union "frame_XXXX.bmp" pour compat preview
      - écrit des manifests JSON
    """
    step_name = "bitmap"

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage conversion bitmap…",
                frame_index=0,
                total_frames=None,
                frame_path=None,
            )
        )

    # ------------------------------------------------------------
    # Classic path : inchangé
    # ------------------------------------------------------------
    if mode.lower() != "arcade":
        def on_frame_done(idx: int, total: int, bmp_path):
            if progress_cb is not None:
                progress_cb(
                    FrameProgress(
                        step_name=step_name,
                        message=f"Frame {idx}/{total}",
                        frame_index=idx,
                        total_frames=total,
                        frame_path=bmp_path,
                    )
                )

        try:
            out_dir = convert_project_frames_to_bmp(
                project_name=project,
                threshold=threshold,
                use_thinning=use_thinning,
                max_frames=max_frames,
                frame_callback=on_frame_done,
                cancel_cb=cancel_cb,
            )
        except Exception as e:
            msg = f"Erreur Bitmap : {e}"
            if progress_cb is not None:
                progress_cb(
                    FrameProgress(
                        step_name=step_name,
                        message=msg,
                        frame_index=None,
                        total_frames=None,
                        frame_path=None,
                    )
                )
            return StepResult(success=False, message=msg, output_dir=None)

        msg = f"BMP images computed in: {out_dir}"
        return StepResult(success=True, message=msg, output_dir=out_dir)

    # ------------------------------------------------------------
    # Arcade path : quantize + layers
    # ------------------------------------------------------------
    project_root = PROJECTS_ROOT / project
    frames_dir = project_root / "frames"
    bmp_dir = project_root / "bmp"
    bmp_dir.mkdir(parents=True, exist_ok=True)

    png_files = sorted(frames_dir.glob("frame_*.png"))
    if max_frames is not None:
        png_files = png_files[:max_frames]

    if not png_files:
        msg = "Aucune frame PNG trouvée (projects/<project>/frames)."
        return StepResult(success=False, message=msg, output_dir=bmp_dir)

    global_manifest: Dict[str, Any] = {
        "project": project,
        "mode": "arcade",
        "n_colors": int(arcade_n_colors),
        "min_area": int(arcade_min_area),
        "morph_open": int(arcade_morph_open),
        "morph_close": int(arcade_morph_close),
        "frames": [],
    }

    total = len(png_files)
    last_path: Optional[Path] = None

    for i, png_path in enumerate(png_files, start=1):
        if _cancelled(cancel_cb):
            return StepResult(
                success=False,
                message="Bitmap computation canceled.",
                output_dir=bmp_dir,
            )

        frame_manifest = _generate_arcade_layers_for_frame(
            png_path=png_path,
            bmp_dir=bmp_dir,
            n_colors=arcade_n_colors,
            min_area=arcade_min_area,
            morph_open=arcade_morph_open,
            morph_close=arcade_morph_close,
        )
        global_manifest["frames"].append(frame_manifest)

        # pour la preview existante : on pointe sur le preview union frame_XXXX.bmp
        last_path = bmp_dir / frame_manifest["preview_bmp"]

        if progress_cb is not None:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=f"Frame {i}/{total} (arcade layers)",
                    frame_index=i,
                    total_frames=total,
                    frame_path=last_path,
                )
            )

    (bmp_dir / "_layers_manifest.json").write_text(
        json.dumps(global_manifest, indent=2),
        encoding="utf-8",
    )

    msg = f"Arcade BMP images computed in: {bmp_dir} (layers + preview union + manifests)"
    return StepResult(success=True, message=msg, output_dir=bmp_dir)
