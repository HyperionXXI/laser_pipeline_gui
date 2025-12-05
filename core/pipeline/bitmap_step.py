# core/pipeline/bitmap_step.py

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.step_bitmap import convert_project_frames_to_bmp
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


def run_bitmap_step(
    project: str,
    threshold: int,
    use_thinning: bool,
    max_frames: Optional[int],
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Step pipeline pour la conversion PNG → BMP (ImageMagick).

    - PNG attendus dans  projects/<project>/frames
    - BMP écrits dans    projects/<project>/bmp
    - Retourne un StepResult avec output_dir = dossier BMP.

    La progression frame par frame est remontée via progress_cb(FrameProgress).
    """

    step_name = "bitmap"

    # --- Message de démarrage ---
    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=(
                    f"Démarrage Bitmap (ImageMagick)… "
                    f"(threshold={threshold}%, thinning={use_thinning}, "
                    f"max_frames={max_frames or 'toutes'})"
                ),
                frame_index=0,
                total_frames=None,
                frame_path=None,
            )
        )

    # Callback appelée par convert_project_frames_to_bmp après chaque frame
    def on_frame_done(idx: int, total: int, bmp_path: Path) -> None:
        if progress_cb is None:
            return
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=f"Frame {idx}/{total} convertie",
                frame_index=idx,
                total_frames=total,
                frame_path=bmp_path,
            )
        )

    # Appel du code métier : c'est convert_project_frames_to_bmp qui boucle
    out_dir = convert_project_frames_to_bmp(
        project_name=project,
        threshold=threshold,
        use_thinning=use_thinning,
        max_frames=max_frames,
        frame_callback=on_frame_done,  # <-- important pour la preview progressive
    )

    # --- Message de fin ---
    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Conversion BMP terminée.",
                frame_index=0,
                total_frames=None,
                frame_path=None,
            )
        )

    return StepResult(
        success=True,
        message=f"BMP générés dans : {out_dir}",
        output_dir=Path(out_dir),
    )
