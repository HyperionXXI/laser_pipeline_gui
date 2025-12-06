# core/step_bitmap.py
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Optional, Callable

from .config import PROJECTS_ROOT, MAGICK_PATH


def convert_png_to_bmp(
    png_path: Path,
    bmp_path: Path,
    threshold: int,
    thinning: bool,
) -> None:
    """
    Convertit un PNG en BMP noir/blanc via ImageMagick.

    - threshold : 0..100 (%)
    - thinning : True/False pour l'option -morphology Thinning
    """
    bmp_path.parent.mkdir(parents=True, exist_ok=True)

    # Commande de base : gris -> seuil -> BMP
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

    subprocess.run(cmd, check=True)


def convert_project_frames_to_bmp(
    project_name: str,
    threshold: int,
    use_thinning: bool,
    max_frames: Optional[int] = None,
    frame_callback: Optional[Callable[[int, int, Path], None]] = None,
) -> Path:
    """
    Parcourt projects/<project>/frames/frame_*.png et génère
    projects/<project>/bmp/frame_*.bmp.

    - threshold : 0..100 (%)
    - use_thinning : applique ou non le Thinning
    - max_frames : si non None, limite au N premières frames
    - frame_callback : appelé à chaque frame générée :
      frame_callback(index_1_based, total_frames, bmp_path)
    """
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
        bmp_path = bmp_dir / (png_path.stem + ".bmp")

        convert_png_to_bmp(
            png_path=png_path,
            bmp_path=bmp_path,
            threshold=threshold,
            thinning=use_thinning,
        )

        if frame_callback is not None:
            frame_callback(idx, total, bmp_path)

    return bmp_dir
