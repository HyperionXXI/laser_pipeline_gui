# core/pipeline/ilda_step.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.config import PROJECTS_ROOT
from core.step_ilda import export_project_to_ilda
from core.ilda_preview import render_ilda_preview
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


def run_ilda_step(
    project: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Step pipeline ILDA : SVG -> .ild + PNG de prévisualisation.
    """
    step_name = "ilda"
    project_root = PROJECTS_ROOT / project
    svg_dir = project_root / "svg"

    svg_files = sorted(svg_dir.glob("frame_*.svg"))

    # Progress initial (si on a déjà au moins un SVG)
    if progress_cb is not None:
        first_svg = svg_files[0] if svg_files else None
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="[ilda] Préparation export ILDA…",
                frame_index=0,
                total_frames=100,
                frame_path=first_svg,
            )
        )

    def _check_cancel() -> bool:
        return cancel_cb is not None and cancel_cb()

    def _report_progress(percent: int) -> None:
        if progress_cb is None:
            return
        # On mappe directement sur 0..100
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=f"[ilda] Export ILDA… {percent} %",
                frame_index=percent,
                total_frames=100,
                frame_path=None,
            )
        )

    try:
        out_path = export_project_to_ilda(
            project_name=project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
            check_cancel=_check_cancel,
            report_progress=_report_progress,
        )
    except Exception as e:
        return StepResult(
            success=False,
            message=f"Erreur lors de l'export ILDA : {e}",
            output_dir=None,
        )

    # ------------------------------------------------------------------
    # Génération de la preview PNG à partir du .ild
    # ------------------------------------------------------------------
    preview_dir = project_root / "preview"
    preview_png = preview_dir / "ilda_preview.png"
    preview_path: Optional[Path] = None

    try:
        preview_path = render_ilda_preview(out_path, preview_png)
    except Exception:
        # On ne casse pas le step pour un souci de preview
        preview_path = None

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=f"[ilda] Export ILDA terminé : {out_path.name}",
                frame_index=100,
                total_frames=100,
                frame_path=preview_path,
            )
        )

    return StepResult(
        success=True,
        message=f"Fichier ILDA généré : {out_path}",
        output_dir=out_path.parent,
    )
