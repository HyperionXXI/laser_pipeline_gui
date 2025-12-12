# core/pipeline/bitmap_step.py
from __future__ import annotations

from typing import Optional

from core.bitmap_convert import convert_project_frames_to_bmp
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


def run_bitmap_step(
    project: str,
    threshold: int,
    use_thinning: bool,
    max_frames: Optional[int] = None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Step pipeline : PNG -> BMP pour un projet donné.

    - PNG attendus dans projects/<project>/frames
    - BMP générés dans projects/<project>/bmp
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
    except Exception as e:  # annulation ou erreur ImageMagick
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
        return StepResult(
            success=False,
            message=msg,
            output_dir=None,
        )

    msg = f"Images BMP générées dans : {out_dir}"
    return StepResult(
        success=True,
        message=msg,
        output_dir=out_dir,
    )
