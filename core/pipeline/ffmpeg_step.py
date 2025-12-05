# core/pipeline/ffmpeg_step.py
from __future__ import annotations

from pathlib import Path

from core.step_ffmpeg import extract_frames
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


def run_ffmpeg_step(
    video_path: Path,
    project_name: str,
    fps: int,
    on_progress: ProgressCallback | None = None,
    check_cancel: CancelCallback | None = None,
) -> StepResult:
    """
    Étape FFmpeg du pipeline, interface générique.

    Pour l'instant on ne sait pas estimer le nombre de frames ni la progression
    fine, donc on émet au mieux un évènement "100%" à la fin.
    """
    step_name = "ffmpeg"

    try:
        # Appel de ta fonction existante.
        out_dir_str = extract_frames(
            str(video_path),
            project_name,
            fps=fps,
        )
        out_dir = Path(out_dir_str)

        # Évènement de progression "final" (placeholder).
        if on_progress is not None:
            evt = FrameProgress(
                step=step_name,
                index=1,
                total=1,
                last_output=None,  # on ne sait pas encore quelle frame exacte
            )
            on_progress(evt)

        msg = f"Frames extraites dans : {out_dir}"
        return StepResult(step=step_name, success=True, message=msg, output_dir=out_dir)

    except Exception as e:
        return StepResult(step=step_name, success=False, message=str(e))
