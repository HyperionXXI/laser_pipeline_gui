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

    Pour l'instant, on ne suit pas FFmpeg frame par frame.
    On émet un event de départ, puis un event final qui pointe
    sur la première frame PNG pour la prévisualisation.
    """
    step_name = "ffmpeg"

    # Début : barre indéterminée
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

    # Lancement réel d'FFmpeg (bloquant)
    out_dir = extract_frames(video_path, project, fps=fps)

    # Après extraction : on cherche au moins une frame PNG
    png_files = sorted(Path(out_dir).glob("frame_*.png"))
    if png_files:
        # On prend la première frame pour la preview
        frame_path = png_files[0]
        total_frames = len(png_files)
        frame_index = total_frames - 1  # → barre à ~100%
    else:
        frame_path = None
        total_frames = 1
        frame_index = 0

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Extraction terminée.",
                frame_index=frame_index,
                total_frames=total_frames,
                frame_path=frame_path,
            )
        )

    return StepResult(
        success=True,
        message=f"Frames extraites dans : {out_dir}",
        output_dir=Path(out_dir),
    )
