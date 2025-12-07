# core/pipeline/ilda_step.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.config import PROJECTS_ROOT
from core.step_ilda import export_project_to_ilda
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


def run_ilda_step(
    project: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.98,  # cf. 3.2
    min_rel_size: float = 0.003,  # au lieu de 0.01
    remove_outer_frame: bool = True,
    frame_margin_rel: float = 0.02,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Step pipeline : SVG -> ILDA pour un projet donné.

    - SVG attendus dans projects/<project>/svg/frame_*.svg
    - Fichier .ild généré dans projects/<project>/ilda/<project>.ild
    """
    step_name = "ilda"

    project_root = PROJECTS_ROOT / project
    svg_dir = project_root / "svg"
    svg_files = sorted(svg_dir.glob("frame_*.svg"))

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage export ILDA…",
                frame_index=0,
                total_frames=100,
                frame_path=svg_files[0] if svg_files else None,
            )
        )

    def _check_cancel() -> bool:
        return cancel_cb is not None and cancel_cb()

    def _report_progress(p: int) -> None:
        if progress_cb is None:
            return

        # Choix d'un SVG "proche" du pourcentage courant, pour la preview
        frame_path = None
        if svg_files:
            idx = max(0, min(len(svg_files) - 1, int(p * len(svg_files) / 100)))
            frame_path = svg_files[idx]

        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=f"Export ILDA… {p}%",
                frame_index=p,
                total_frames=100,
                frame_path=frame_path,
            )
        )

    try:
        out_path: Path = export_project_to_ilda(
            project_name=project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
            remove_outer_frame=remove_outer_frame,
            frame_margin_rel=frame_margin_rel,
            check_cancel=_check_cancel,
            report_progress=_report_progress,
        )
    except Exception as e:
        msg = f"Erreur export ILDA : {e}"
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
        return StepResult(
            success=False,
            message=msg,
            output_dir=None,
        )

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=f"Export ILDA terminé : {out_path.name}",
                frame_index=100,
                total_frames=100,
                frame_path=svg_files[-1] if svg_files else None,
            )
        )

    return StepResult(
        success=True,
        message=f"Fichier ILDA généré : {out_path}",
        output_dir=out_path.parent,
    )
