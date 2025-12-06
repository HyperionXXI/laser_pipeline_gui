# core/pipeline/potrace_step.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.config import PROJECTS_ROOT
from core.step_potrace import bitmap_to_svg_folder
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


def run_potrace_step(
    project: str,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Step pipeline : BMP -> SVG via Potrace pour un projet donné.

    - BMP attendus dans projects/<project>/bmp
    - SVG écrits dans projects/<project>/svg
    """
    step_name = "potrace"

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage vectorisation (Potrace)…",
                frame_index=0,
                total_frames=None,
                frame_path=None,
            )
        )

    project_root = PROJECTS_ROOT / project
    bmp_dir = project_root / "bmp"
    svg_dir = project_root / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)

    last_svg: Optional[Path] = None

    def on_frame_done(idx: int, total: int, svg_path: Path) -> None:
        nonlocal last_svg
        last_svg = svg_path
        if progress_cb is not None:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=f"Frame {idx}/{total}",
                    frame_index=idx,
                    total_frames=total,
                    frame_path=svg_path,
                )
            )

    try:
        out_dir_str = bitmap_to_svg_folder(
            str(bmp_dir),
            str(svg_dir),
            max_frames=None,
            frame_callback=on_frame_done,
            cancel_cb=cancel_cb,
        )
        out_dir = Path(out_dir_str)
    except Exception as e:  # annulation ou erreur Potrace
        msg = f"Erreur Potrace : {e}"
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
        return StepResult(success=False, message=msg, output_dir=svg_dir)

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Vectorisation terminée.",
                frame_index=None,
                total_frames=None,
                frame_path=last_svg,
            )
        )

    msg = f"SVG générés dans : {out_dir}"
    return StepResult(
        success=True,
        message=msg,
        output_dir=out_dir,
    )
