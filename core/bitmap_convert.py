# core/bitmap_convert.py
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Optional

from .config import MAGICK_PATH, PROJECTS_ROOT

# Pillow est généralement dispo (vu aussi dans ton projet), mais on reste safe
try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]


def _maybe_invert_bmp_for_potrace(bmp_path: Path) -> None:
    """
    Potrace vectorise les pixels NOIRS (foreground).
    Si un BMP est "trait blanc sur fond noir", Potrace risque de vectoriser le fond
    => grand contour rectangulaire (le cadre) + trous.

    Heuristique simple et robuste :
    - on lit le BMP en niveaux de gris,
    - on calcule la proportion de pixels sombres,
    - si l'image est majoritairement sombre (fond noir dominant), on inverse.

    IMPORTANT:
    - On n'échoue pas la pipeline si cette étape échoue (best-effort).
    """
    if Image is None or ImageOps is None:
        return

    try:
        im = Image.open(bmp_path).convert("L")

        # Histogramme 256 bins. Pixels < 128 = "sombres"
        hist = im.histogram()
        total = sum(hist)
        if total <= 0:
            return

        dark = sum(hist[:128])
        dark_ratio = dark / total

        # Si > 50% sombre, typiquement fond noir => inversion
        if dark_ratio > 0.50:
            inv = ImageOps.invert(im)
            inv.save(bmp_path)
    except Exception:
        # best-effort : ne pas casser la pipeline
        return


def _convert_png_to_bmp(
    png_path: Path,
    bmp_path: Path,
    threshold: int,
    thinning: bool,
) -> None:
    if not (0 <= threshold <= 100):
        raise ValueError("threshold doit être dans [0..100]")

    bmp_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(MAGICK_PATH),
        str(png_path),
        "-colorspace",
        "Gray",
        "-threshold",
        f"{threshold}%",
    ]

    if thinning:
        cmd += ["-morphology", "Thinning", "Skeleton"]

    cmd.append(str(bmp_path))

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        raise RuntimeError(f"ImageMagick a échoué :\n{stderr}") from e

    # Normalisation de polarité pour Potrace (anti-cadre)
    _maybe_invert_bmp_for_potrace(bmp_path)


def convert_project_frames_to_bmp(
    project_name: str,
    threshold: int,
    use_thinning: bool,
    max_frames: Optional[int] = None,
    frame_callback: Optional[Callable[[int, int, Path], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> Path:
    project_root = PROJECTS_ROOT / project_name
    frames_dir = project_root / "frames"
    bmp_dir = project_root / "bmp"
    bmp_dir.mkdir(parents=True, exist_ok=True)

    png_files = sorted(frames_dir.glob("frame_*.png"))
    if max_frames is not None:
        png_files = png_files[:max_frames]

    total = len(png_files)
    if total == 0:
        raise RuntimeError(f"Aucune frame PNG trouvée dans {frames_dir}")

    for idx, png_path in enumerate(png_files, start=1):
        if cancel_cb and cancel_cb():
            raise RuntimeError("BMP conversion canceled by user.")

        bmp_path = bmp_dir / (png_path.stem + ".bmp")
        _convert_png_to_bmp(png_path, bmp_path, threshold, use_thinning)

        if frame_callback:
            frame_callback(idx, total, bmp_path)

    return bmp_dir
