# core/pipeline/ilda_step.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.ilda_export import export_project_to_ilda
from core.pipeline.base import StepResult, FrameProgress, ProgressCallback, CancelCallback


def run_ilda_step(
    project: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    mode: str = "classic",
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
    # compat: callers may pass max_frames even though export currently ignores it
    max_frames: Optional[int] = None,
) -> StepResult:
    step_name = "ilda"

    def check_cancel() -> bool:
        return bool(cancel_cb and cancel_cb())

    def report_progress(frame_index: int, total_frames: int) -> None:
        if progress_cb:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=f"Frame {frame_index + 1}/{total_frames}",
                    frame_index=frame_index + 1,
                    total_frames=total_frames,
                    frame_path=None,
                )
            )

    try:
        out_path: Path = export_project_to_ilda(
            project_name=project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
            mode=mode,
            check_cancel=check_cancel,
            report_progress=report_progress,
        )

        return StepResult(
            success=True,
            message=f"Export ILDA terminé : {out_path.name} (mode={mode})",
            output_dir=out_path.parent,
        )

    except Exception as exc:
        return StepResult(
            success=False,
            message=f"Erreur export ILDA : {exc}",
            output_dir=None,
        )
