from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from core.pipeline.base import CancelCallback, ProgressCallback, StepResult

from core.pipeline.ffmpeg_step import run_ffmpeg_step
from core.pipeline.bitmap_step import run_bitmap_step
from core.pipeline.potrace_step import run_potrace_step
from core.pipeline.ilda_step import run_ilda_step
from core.pipeline.arcade_lines_step import run_arcade_lines_step


@dataclass(frozen=True)
class _Params:
    video_path: Path
    project: str
    fps: int

    # bitmap / classic
    threshold: int
    use_thinning: bool
    max_frames: int  # 0 = all
    fit_axis: str
    fill_ratio: float
    min_rel_size: float

    # mode
    ilda_mode: str
    arcade_params: Optional[dict[str, Any]]


def _is_cancelled(cancel_cb: Optional[CancelCallback]) -> bool:
    return bool(cancel_cb and cancel_cb())


def _coerce_arcade_params(obj: Any) -> dict[str, Any]:
    """
    Robustesse: certains callers peuvent passer autre chose qu'un dict (ex: dataclass).
    On tente dict -> __dict__ -> {}.
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    d = getattr(obj, "__dict__", None)
    if isinstance(d, dict):
        return dict(d)
    return {}


_ALLOWED_ARCADE_KW: set[str] = {
    # run_arcade_lines_step kwargs (except project, fps, max_frames, kpps, ppf_ratio)
    "max_points_per_frame",
    "fill_ratio",
    "canny1",
    "canny2",
    "blur_ksize",
    "min_poly_len",
    "simplify_eps",
    "sample_color",
    "invert_y",
}


def run_full_pipeline_step(
    video_path: Path | str,
    project: str,
    fps: int,
    threshold: int = 60,
    use_thinning: bool = False,
    max_frames: int | None = 0,
    fit_axis: str = "both",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    ilda_mode: str = "classic",
    arcade_params: Optional[dict[str, Any]] = None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
    # Compat: certains anciens callers utilisent thinning=... au lieu de use_thinning=...
    # et/ou max_frames=None (UI) au lieu de 0 (core)
    **_compat: Any,
) -> StepResult:
    """
    Orchestrateur "full pipeline".

    - Classic : FFmpeg -> Bitmap -> Potrace -> ILDA
    - Arcade  : FFmpeg -> arcade_lines (et on s'arrête là)

    Compat:
    - On accepte thinning=... via **_compat.
    - On accepte max_frames=None (UI) : traité comme "toutes" => 0.
    """

    if "thinning" in _compat and "use_thinning" not in _compat:
        use_thinning = bool(_compat["thinning"])

    # None (UI) => 0 ("toutes") pour les steps classic
    max_frames_i = 0 if (max_frames is None) else int(max_frames)

    p = _Params(
        video_path=Path(video_path),
        project=str(project),
        fps=int(fps),
        threshold=int(threshold),
        use_thinning=bool(use_thinning),
        max_frames=max_frames_i,
        fit_axis=str(fit_axis),
        fill_ratio=float(fill_ratio),
        min_rel_size=float(min_rel_size),
        ilda_mode=str(ilda_mode),
        arcade_params=arcade_params,
    )

    # ----------------------------
    # Step 1: FFmpeg (always)
    # ----------------------------
    if _is_cancelled(cancel_cb):
        return StepResult(False, "Annulé.")

    ffmpeg_res = run_ffmpeg_step(
        str(p.video_path),
        p.project,
        p.fps,
        progress_cb=progress_cb,
        cancel_cb=cancel_cb,
    )
    if not ffmpeg_res.success:
        return StepResult(False, f"Echec FFmpeg: {ffmpeg_res.message}")

    # ----------------------------
    # Arcade branch: Step 2 = arcade_lines only
    # ----------------------------
    mode = p.ilda_mode.strip().lower()
    if mode == "arcade":
        if _is_cancelled(cancel_cb):
            return StepResult(False, "Annulé.")

        # UI: max_frames=None => toutes les frames.
        # arcade_lines_step: None => toutes les frames.
        arcade_max_frames: int | None = None if (max_frames is None or max_frames_i == 0) else max_frames_i

        extra = _coerce_arcade_params(p.arcade_params)

        # Valeurs par défaut (modifiable plus tard via arcade_params/UI Expert)
        kpps = int(extra.pop("kpps", 60))          # 60kpps par défaut
        ppf_ratio = float(extra.pop("ppf_ratio", 0.75))

        # Filtrer les kwargs inconnus pour éviter des crashs "unexpected keyword argument"
        filtered: dict[str, Any] = {}
        for k in list(extra.keys()):
            if k in _ALLOWED_ARCADE_KW:
                filtered[k] = extra[k]

        arcade_res = run_arcade_lines_step(
            p.project,
            fps=p.fps,
            max_frames=arcade_max_frames,
            kpps=kpps,
            ppf_ratio=ppf_ratio,
            progress_cb=progress_cb,
            cancel_cb=cancel_cb,
            **filtered,
        )
        if not arcade_res.success:
            return StepResult(False, f"Echec Arcade: {arcade_res.message}")
        return arcade_res

    # ----------------------------
    # Classic pipeline: Bitmap -> Potrace -> ILDA
    # ----------------------------
    if _is_cancelled(cancel_cb):
        return StepResult(False, "Annulé.")

    bitmap_res = run_bitmap_step(
        p.project,
        threshold=p.threshold,
        use_thinning=p.use_thinning,
        max_frames=p.max_frames,
        fit_axis=p.fit_axis,
        fill_ratio=p.fill_ratio,
        min_rel_size=p.min_rel_size,
        ilda_mode="classic",
        progress_cb=progress_cb,
        cancel_cb=cancel_cb,
    )
    if not bitmap_res.success:
        return StepResult(False, f"Echec Bitmap: {bitmap_res.message}")

    if _is_cancelled(cancel_cb):
        return StepResult(False, "Annulé.")

    potrace_res = run_potrace_step(
        p.project,
        max_frames=p.max_frames,
        progress_cb=progress_cb,
        cancel_cb=cancel_cb,
    )
    if not potrace_res.success:
        return StepResult(False, f"Echec Potrace: {potrace_res.message}")

    if _is_cancelled(cancel_cb):
        return StepResult(False, "Annulé.")

    ilda_res = run_ilda_step(
        p.project,
        fit_axis=p.fit_axis,
        fill_ratio=p.fill_ratio,
        min_rel_size=p.min_rel_size,
        max_frames=p.max_frames,
        progress_cb=progress_cb,
        cancel_cb=cancel_cb,
    )
    if not ilda_res.success:
        return StepResult(False, f"Echec ILDA: {ilda_res.message}")

    return ilda_res
