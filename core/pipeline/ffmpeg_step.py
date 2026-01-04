# core/pipeline/ffmpeg_step.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

from core.ffmpeg_extract import extract_frames
from core.pipeline.base import StepResult, FrameProgress, ProgressCallback, CancelCallback


@dataclass(frozen=True)
class FfmpegParams:
    video_path: Path
    project: str
    fps: int
    max_frames: int = 0  # 0 = toutes


def run_ffmpeg_step(
    video_path: Path | str,
    project: str,
    fps: int,
    max_frames: int = 0,
    scale: float | None = None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
    # compat: si d'anciens callers passent des kwargs inattendus, on ignore
    **_compat: Any,
) -> StepResult:
    """
    Step FFmpeg: extrait des frames PNG dans projects/<project>/frames.

    - max_frames: 0 = toutes (comportement historique)
    """
    if cancel_cb and cancel_cb():
        return StepResult(False, "Canceled.")

    p = FfmpegParams(
        video_path=Path(video_path),
        project=str(project),
        fps=int(fps),
        max_frames=int(max_frames or 0),
    )

    try:
        frames_dir = extract_frames(
            p.video_path,
            p.project,
            p.fps,
            max_frames=p.max_frames,
            scale=scale,
        )
    except Exception as exc:  # noqa: BLE001
        return StepResult(False, f"Erreur FFmpeg : {exc}")

    frames = sorted(frames_dir.glob("frame_*.png"))
    if not frames:
        return StepResult(False, f"No PNG frames computed in: {frames_dir}")

    if progress_cb:
        # On expose au moins une frame et un total (utile UI preview/progress).
        progress_cb(
            FrameProgress(
                step_name="ffmpeg",
                frame_index=0,
                total_frames=len(frames),
                frame_path=frames[0],
            )
        )

    return StepResult(True, f"Frames computed in: {frames_dir} ({len(frames)} frames)")
