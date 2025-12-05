# core/pipeline/potrace_step.py

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import (
    FrameProgress,
    StepResult,
    ProgressCallback,
    CancelCallback,
)
from core.config import PROJECTS_ROOT
from core.step_potrace import bitmap_to_svg_folder


def run_potrace_step(
    project: str,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Step pipeline : BMP -> SVG via Potrace pour un projet donné.

    - BMP attendus dans  projects/<project>/bmp
    - SVG écrits dans   projects/<project>/svg

    Retourne un StepResult :
        success     : bool
        message     : str humain lisible
        output_dir  : Path du dossier contenant les SVG
    """

    step_name = "potrace"

    # Signal de démarrage (optionnel)
    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage Potrace…",
                frame_index=None,
                total_frames=None,
                frame_path=None,
            )
        )

    project_root = PROJECTS_ROOT / project
    bmp_dir = project_root / "bmp"
    svg_dir = project_root / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)

    # NOTE : pour l’instant, on ne peut pas annuler "au milieu"
    # de bitmap_to_svg_folder, donc cancel_cb n’est pas exploité.
    try:
        out_dir_str = bitmap_to_svg_folder(str(bmp_dir), str(svg_dir))
        out_dir = Path(out_dir_str)
    except Exception as e:
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

    # On choisit un SVG « représentatif » pour la prévisualisation :
    # la dernière frame frame_*.svg si dispo.
    last_svg: Optional[Path] = None
    svg_files = sorted(out_dir.glob("frame_*.svg"))
    if svg_files:
        last_svg = svg_files[-1]

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
