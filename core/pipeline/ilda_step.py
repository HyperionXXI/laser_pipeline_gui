# core/pipeline/ilda_step.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.step_ilda import export_project_to_ilda
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
    Step pipeline : SVG -> ILDA pour un projet donné.

    - SVG attendus dans projects/<project>/svg/frame_*.svg
    - Fichier .ild généré dans projects/<project>/ilda/<project>.ild

    Paramètres:
      - fit_axis : "max", "x" ou "y"
      - fill_ratio : fraction de la fenêtre ILDA utilisée (0..1)
      - min_rel_size : filtre des petits chemins (parasites)
    """
    step_name = "ilda"

    # Progrès 0 % : démarrage
    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage export ILDA…",
                frame_index=0,
                total_frames=100,
                frame_path=None,
            )
        )

    def _check_cancel() -> bool:
        return cancel_cb is not None and cancel_cb()

    def _report_progress(p: int) -> None:
        # p ∈ [0..100]
        if progress_cb is not None:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=f"Export ILDA… {p}%",
                    frame_index=p,
                    total_frames=100,
                    frame_path=None,
                )
            )

    try:
        out_path: Path = export_project_to_ilda(
            project_name=project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
            check_cancel=_check_cancel,
            report_progress=_report_progress,
        )
    except Exception as e:  # pragma: no cover - chemin d'erreur simple
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

    # Progrès 100 % : terminé
    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=f"Export ILDA terminé : {out_path.name}",
                frame_index=100,
                total_frames=100,
                frame_path=out_path,
            )
        )

    return StepResult(
        success=True,
        message=f"Fichier ILDA généré : {out_path}",
        output_dir=out_path.parent,
    )
