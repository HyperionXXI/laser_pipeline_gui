# core/pipeline/full_pipeline_step.py
from __future__ import annotations

from typing import Optional
import dataclasses

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

    # Wrap progress_cb to ensure FrameProgress carries the sub-step name
    if progress_cb is not None:
        def _progress(fp):
            # Try to inject step_name in the most compatible way possible
            try:
                cur = getattr(fp, "step_name", None)
                if not cur:
                    try:
                        setattr(fp, "step_name", label)
                    except Exception:
                        # frozen dataclass (or similar)
                        if dataclasses.is_dataclass(fp):
                            fp = dataclasses.replace(fp, step_name=label)
                progress_cb(fp)
            except Exception:
                # Never break the pipeline for a progress issue
                progress_cb(fp)
        kwargs.setdefault("progress_cb", _progress)
    else:
        kwargs.setdefault("progress_cb", None)
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

    res = _wrap_step(
        "ffmpeg",
        run_ffmpeg_step,
        progress_cb,
        cancel_cb,
        video_path,
        project,
        fps,
    )
    if not res.success:
        return res

    # ---- Arcade v2 : FFmpeg -> ArcadeLines(OpenCV) -> ILDA (direct)
    if (ilda_mode or "").lower() == "arcade":
        # lazy import pour éviter de casser le GUI si le module n'existe pas
        # ⚠️ adapte le nom du module selon ton fichier réel :
        from core.pipeline.arcade_lines_step import run_arcade_lines_step
        # from core.pipeline.arcade_lines_step import run_arcade_lines_step

        return _wrap_step(
            "arcade_lines",
            run_arcade_lines_step,
            progress_cb,
            cancel_cb,
            project,
            fps=fps,              # passe en nommé (robuste)
            fill_ratio=fill_ratio # si ton step le supporte, sinon retire
        )

    # ---- Classic / autres : FFmpeg -> Bitmap -> Potrace -> ILDA
    res = _wrap_step(
        "bitmap",
        run_bitmap_step,
        progress_cb,
        cancel_cb,
        project,
        threshold,
        use_thinning,
        max_frames,
        mode=ilda_mode,
    )
    if not res.success:
        return res

    res = _wrap_step(
        "potrace",
        run_potrace_step,
        progress_cb,
        cancel_cb,
        project,
        mode=ilda_mode,
    )
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
