# core/pipeline/full_pipeline_step.py
from __future__ import annotations

from typing import Optional

from core.pipeline.base import StepResult, ProgressCallback, CancelCallback
from core.pipeline.ffmpeg_step import run_ffmpeg_step
from core.pipeline.bitmap_step import run_bitmap_step
from core.pipeline.potrace_step import run_potrace_step
from core.pipeline.ilda_step import run_ilda_step
from core.config import PROJECTS_ROOT


def _wrap_step(
    label: str,
    func,
    progress_cb: Optional[ProgressCallback],
    cancel_cb: Optional[CancelCallback],
    *args,
    **kwargs,
) -> StepResult:
    if cancel_cb is not None and cancel_cb():
        return StepResult(
            success=False,
            message=f"Pipeline annulé avant le step '{label}'.",
            output_dir=PROJECTS_ROOT,
        )

    kwargs.setdefault("progress_cb", progress_cb)
    kwargs.setdefault("cancel_cb", cancel_cb)

    result = func(*args, **kwargs)
    if not getattr(result, "success", False):
        msg = getattr(result, "message", "") or ""
        return StepResult(
            success=False,
            message=f"Echec du step '{label}' : {msg}",
            output_dir=getattr(result, "output_dir", PROJECTS_ROOT),
        )
    return result


def run_full_pipeline_step(
    video_path: str,
    project: str,
    fps: int,
    threshold: int,
    use_thinning: bool,
    max_frames: Optional[int],
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    ilda_mode: str = "classic",
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:

    res = _wrap_step("ffmpeg", run_ffmpeg_step, progress_cb, cancel_cb, video_path, project, fps)
    if not res.success:
        return res

    res = _wrap_step(
        "bitmap",
        run_bitmap_step,
        progress_cb,
        cancel_cb,
        project,
        threshold,
        use_thinning,
        max_frames,
    )
    if not res.success:
        return res

    res = _wrap_step("potrace", run_potrace_step, progress_cb, cancel_cb, project)
    if not res.success:
        return res

    res = _wrap_step(
        "ilda",
        run_ilda_step,
        progress_cb,
        cancel_cb,
        project,
        fit_axis,
        fill_ratio,
        min_rel_size,
        ilda_mode,
    )
    if not res.success:
        return res

    return StepResult(
        success=True,
        message="Pipeline complet terminé (FFmpeg → Bitmap → Potrace → ILDA).",
        output_dir=res.output_dir,
    )
