# core/pipeline/full_pipeline_step.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
import inspect

from core.config import PROJECTS_ROOT
from core.pipeline.base import FrameProgress, ProgressCallback, StepResult, CancelCallback

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
    threshold: int
    use_thinning: bool
    max_frames: int  # 0 = all
    ilda_mode: str
    arcade_params: Optional[dict[str, Any]]


def _is_cancelled(cancel_cb: Optional[CancelCallback]) -> bool:
    return bool(cancel_cb and cancel_cb())


def _wrap_progress(
    step_name: str,
    progress_cb: Optional[ProgressCallback],
) -> Optional[ProgressCallback]:
    """
    Garantit que fp.step_name est renseigné (sans dépendre du fait que chaque step le fasse).
    """
    if progress_cb is None:
        return None

    def _cb(fp: FrameProgress) -> None:
        try:
            if not getattr(fp, "step_name", None):
                fp.step_name = step_name  # type: ignore[attr-defined]
        except Exception:
            # Si FrameProgress est immuable dans une variante, on laisse passer tel quel.
            pass
        progress_cb(fp)

    return _cb


def _frames_dir(project: str) -> Path:
    return Path(PROJECTS_ROOT) / project / "frames"


def _find_png_frames(project: str) -> list[Path]:
    d = _frames_dir(project)
    if not d.exists():
        return []
    frames = sorted(d.glob("frame_*.png"))
    if frames:
        return frames
    return sorted(d.glob("*.png"))


def run_full_pipeline_step(
    video_path: Path | str,
    project: str,
    fps: int,
    threshold: int = 60,
    use_thinning: bool = False,
    max_frames: int = 0,
    ilda_mode: str = "classic",
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    arcade_params: Optional[dict[str, Any]] = None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
    # compat: anciens callers (thinning=...) etc.
    **_compat: Any,
) -> StepResult:
    """
    Orchestrateur "full pipeline".

    - Classic : FFmpeg -> Bitmap -> Potrace -> ILDA
    - Arcade  : FFmpeg -> arcade_lines (et on s'arrête là)

    Points importants (stabilité):
    - N’importe aucun module fantôme.
    - Ne passe max_frames à run_ffmpeg_step que si son API l’accepte.
    - max_frames = 0 signifie "toutes".
    """

    # Compat: thinning=... -> use_thinning
    if "thinning" in _compat and "use_thinning" not in _compat:
        use_thinning = bool(_compat["thinning"])

    p = _Params(
        video_path=Path(video_path),
        project=str(project),
        fps=int(fps),
        threshold=int(threshold),
        use_thinning=bool(use_thinning),
        max_frames=int(max_frames) if max_frames is not None else 0,
        ilda_mode=str(ilda_mode),
        arcade_params=dict(arcade_params) if arcade_params else None,
    )

    if _is_cancelled(cancel_cb):
        return StepResult(False, "Canceled.")

    # ----------------------------
    # Step 1: FFmpeg (always)
    # ----------------------------
    ffmpeg_kwargs: dict[str, Any] = {
        "video_path": p.video_path,
        "project": p.project,
        "fps": p.fps,
        "progress_cb": _wrap_progress("ffmpeg", progress_cb),
        "cancel_cb": cancel_cb,
    }

    # Passe max_frames à FFmpeg UNIQUEMENT si l'API le supporte (anti-régression).
    try:
        sig = inspect.signature(run_ffmpeg_step)
        if "max_frames" in sig.parameters:
            ffmpeg_kwargs["max_frames"] = (None if p.max_frames == 0 else p.max_frames)
    except Exception:
        # Si signature() échoue pour une raison quelconque, on n'envoie rien.
        pass

    ffmpeg_res = run_ffmpeg_step(**ffmpeg_kwargs)
    if not ffmpeg_res.success:
        return StepResult(False, f"Echec FFmpeg: {ffmpeg_res.message}")

    png_frames = _find_png_frames(p.project)
    if not png_frames:
        return StepResult(
            False,
            f"Aucune frame PNG trouvée après FFmpeg. Attendu dans: {_frames_dir(p.project)}",
        )

    mode = p.ilda_mode.strip().lower()

    # ----------------------------
    # Arcade branch
    # ----------------------------
    if mode == "arcade":
        if _is_cancelled(cancel_cb):
            return StepResult(False, "Canceled.")

        extra = dict(p.arcade_params or {})

        # Valeurs robustes par défaut (tu peux les surcharger via arcade_params)
        # 60 kpps = souhait exprimé
        kpps = int(extra.pop("kpps", 60))
        ppf_ratio = float(extra.pop("ppf_ratio", 0.90))
        invert_y = bool(extra.pop("invert_y", False))
        sample_color = bool(extra.pop("sample_color", True))

        # 0 ("toutes") -> None (API arcade_lines_step)
        arcade_max_frames: Optional[int] = None if p.max_frames == 0 else p.max_frames

        arcade_res = run_arcade_lines_step(
            p.project,
            fps=p.fps,
            max_frames=arcade_max_frames,
            kpps=kpps,
            ppf_ratio=ppf_ratio,
            sample_color=sample_color,
            invert_y=invert_y,
            progress_cb=_wrap_progress("arcade_lines", progress_cb),
            cancel_cb=cancel_cb,
            **extra,
        )
        if not arcade_res.success:
            return StepResult(False, f"Echec Arcade: {arcade_res.message}")
        return arcade_res

    # ----------------------------
    # Classic pipeline
    # ----------------------------
    if _is_cancelled(cancel_cb):
        return StepResult(False, "Canceled.")

    bitmap_res = run_bitmap_step(
        p.project,
        threshold=p.threshold,
        use_thinning=p.use_thinning,
        max_frames=(None if p.max_frames == 0 else p.max_frames),
        progress_cb=_wrap_progress("bitmap", progress_cb),
        cancel_cb=cancel_cb,
    )
    if not bitmap_res.success:
        return StepResult(False, f"Echec Bitmap: {bitmap_res.message}")

    if _is_cancelled(cancel_cb):
        return StepResult(False, "Canceled.")

    potrace_res = run_potrace_step(
        p.project,
        max_frames=(None if p.max_frames == 0 else p.max_frames),
        progress_cb=_wrap_progress("potrace", progress_cb),
        cancel_cb=cancel_cb,
    )
    if not potrace_res.success:
        return StepResult(False, f"Echec Potrace: {potrace_res.message}")

    if _is_cancelled(cancel_cb):
        return StepResult(False, "Canceled.")

    ilda_res = run_ilda_step(
        p.project,
        fit_axis=fit_axis,
        fill_ratio=fill_ratio,
        min_rel_size=min_rel_size,
        mode="classic",
        progress_cb=_wrap_progress("ilda", progress_cb),
        cancel_cb=cancel_cb,
    )
    if not ilda_res.success:
        return StepResult(False, f"Echec ILDA: {ilda_res.message}")

    return ilda_res
