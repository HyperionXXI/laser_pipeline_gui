# core/pipeline/ffmpeg_step.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.step_ffmpeg import extract_frames
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


def run_ffmpeg_step(
    video_path: str,
    project: str,
    fps: int,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Step pipeline pour l'extraction des frames via FFmpeg.

    Pour l'instant, on délègue à core.step_ffmpeg.extract_frames()
    qui ne supporte pas le rapport de progression par frame.
    On se contente donc d'émettre un event "0%" au début et "100%" à la fin.
    """
    step_name = "ffmpeg"

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage FFmpeg…",
                frame_index=0,
                total_frames=None,
                frame_path=None,
            )
        )

    out_dir = extract_frames(video_path, project, fps=fps)

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Extraction terminée.",
                frame_index=0,
                total_frames=None,
                frame_path=Path(out_dir),
            )
        )

    return StepResult(
        success=True,
        message=f"Frames extraites dans : {out_dir}",
        output_dir=Path(out_dir),
    )
