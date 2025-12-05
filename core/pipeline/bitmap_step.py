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

    On délègue à convert_project_frames_to_bmp() qui gère déjà la boucle
    de traitement des frames. Pour l'instant, on ne dispose pas d'un hook
    interne par frame, donc on simule la progression (0% → 100%).
    """
    step_name = "bitmap"

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage Bitmap (ImageMagick)…",
                frame_index=0,
                total_frames=None,
                frame_path=None,
            )
        )

    out_dir = convert_project_frames_to_bmp(
        project,
        threshold=threshold,
        use_thinning=use_thinning,
        max_frames=max_frames,
    )

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Conversion BMP terminée.",
                frame_index=0,
                total_frames=None,
                frame_path=Path(out_dir) if out_dir is not None else None,
            )
        )

    return StepResult(
        success=True,
        message=f"BMP générés dans : {out_dir}",
        output_dir=Path(out_dir),
    )
