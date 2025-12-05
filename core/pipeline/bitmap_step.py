# core/pipeline/bitmap_step.py
from __future__ import annotations

from pathlib import Path
import subprocess

from core.step_bitmap import convert_project_frames_to_bmp
from core.config import PROJECTS_ROOT, MAGICK_PATH
from .base import StepResult, FrameProgress, ProgressCallback, CancelCallback


def run_bitmap_step(
    project_name: str,
    threshold: int = 60,
    use_thinning: bool = False,
    max_frames: int | None = None,
    on_progress: ProgressCallback | None = None,
    check_cancel: CancelCallback | None = None,
) -> StepResult:
    """
    Étape BITMAP du pipeline (PNG -> BMP via ImageMagick), avec progression.

    - Lit projects/<project_name>/frames/frame_*.png
    - Écrit projects/<project_name>/bmp/frame_*.bmp
    - Applique :
        * niveaux de gris
        * threshold %
        * optionnel : thinning

    Renvoie un StepResult :
        success=True/False
        message=texte pour le log
        output_dir = dossier BMP
    """
    step_name = "bitmap"

    project_root = PROJECTS_ROOT / project_name
    frames_dir = project_root / "frames"
    bmp_dir = project_root / "bmp"
    bmp_dir.mkdir(parents=True, exist_ok=True)

    png_files = sorted(frames_dir.glob("frame_*.png"))
    if not png_files:
        return StepResult(
            step=step_name,
            success=False,
            message=f"Aucun PNG trouvé dans {frames_dir}",
            output_dir=None,
        )

    # Clamp du seuil
    threshold = max(0, min(100, threshold))

    total = len(png_files)
    processed = 0

    for idx, png_file in enumerate(png_files):
        # Limitation du nombre de frames (optionnel)
        if max_frames is not None and processed >= max_frames:
            break

        if check_cancel is not None and check_cancel():
            return StepResult(
                step=step_name,
                success=False,
                message="Conversion BMP annulée par l'utilisateur.",
                output_dir=bmp_dir,
            )

        bmp_file = bmp_dir / (png_file.stem + ".bmp")

        cmd = [
            str(MAGICK_PATH),
            str(png_file),
            "-colorspace", "Gray",
            "-threshold", f"{threshold}%",
        ]

        if use_thinning:
            cmd += ["-morphology", "Thinning:1", "Skeleton"]

        cmd.append(str(bmp_file))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return StepResult(
                step=step_name,
                success=False,
                message=(
                    f"ImageMagick a échoué pour {png_file} "
                    f"(code {result.returncode}):\n{result.stderr}"
                ),
                output_dir=bmp_dir,
            )

        processed += 1

        # Progression : une frame de plus traitée
        if on_progress is not None:
            on_progress(
                FrameProgress(
                    step=step_name,
                    index=processed,
                    total=total if max_frames is None else min(total, max_frames),
                    last_output=bmp_file,
                )
            )

    msg = f"BMP générés dans : {bmp_dir} (frames traitées : {processed})"
    return StepResult(step=step_name, success=True, message=msg, output_dir=bmp_dir)
