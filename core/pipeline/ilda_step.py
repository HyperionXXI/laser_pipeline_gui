# core/pipeline/ilda_step.py
from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable, List

from core.config import PROJECTS_ROOT
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback
from core.step_ilda import export_project_to_ilda
from core.ilda_preview import render_ilda_preview


def run_ilda_step(
    project_name: str,
    *,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    mode_normalised: Optional[str] = None,
    remove_outer_frame: bool = True,
    frame_margin_rel: float = 0.02,
    progress_cb: ProgressCallback = None,
    cancel_cb: CancelCallback = None,
) -> StepResult:
    """
    Exécute le step ILDA pour un projet donné.

    Cette fonction est appelée par le contrôleur de pipeline (PipelineController)
    dans le thread de travail, via StepWorker.

    Paramètres
    ----------
    project_name:
        Nom du projet (sous-dossier de PROJECTS_ROOT).
        Par ex. "projet_demo".

    fit_axis:
        Contrôle la manière de remplir la fenêtre ILDA.
        - "max" (par défaut) : on remplit l'axe le plus contraignant (max span).
        - "min"              : on remplit selon le plus petit span (image moins zoomée).
        - "x"                : on se base sur l'étendue en X.
        - "y"                : on se base sur l'étendue en Y.

    fill_ratio:
        Ratio (0.0 – 1.0) de la plage ILDA utilisée.
        Avec 0.95, on laisse une petite marge pour éviter de clipper sur les bords.

    min_rel_size:
        Taille relative minimale pour garder un chemin SVG.
        Les chemins dont la taille (largeur/hauteur max) est inférieure à
        `min_rel_size * global_span` sont considérés comme des artefacts et supprimés.

    mode_normalised:
        Mode de normalisation ILDA (actuellement symbolique).
        - None ou "classic" : comportement standard.
        - "arcade"          : préfigure un mode d'export orienté jeux/arcade
                              (gestion avancée des couleurs, etc.).
        Pour l'instant, le mode est surtout documenté dans le message final
        et préparé pour de futures évolutions.

    remove_outer_frame:
        Si True, tente de détecter et supprimer les grands chemins qui
        correspondent au cadre extérieur (bien adapté à La Linea).

    frame_margin_rel:
        Tolérance relative pour la détection du cadre extérieur.

    progress_cb:
        Callback optionnel pour signaler une mise à jour de progression.
        Signature : (FrameProgress) -> None

    cancel_cb:
        Callback optionnel pour tester si l'utilisateur a demandé l'annulation.
        Signature : () -> bool

    Retour
    ------
    StepResult
        - success: bool
        - message: str
        - output_dir: Path | None
          (dossier contenant le .ild, typiquement PROJECTS_ROOT/project_name/ilda)
    """
    step_name = "ilda"

    def _raise_if_cancelled() -> None:
        if cancel_cb is not None and cancel_cb():
            # On lève une exception pour interrompre proprement le step.
            raise RuntimeError("Step ILDA annulé par l'utilisateur.")

    # Petite fonction utilitaire pour signaler la progression (en pourcentage).
    def _report_progress_percent(pct: int, message: str | None = None) -> None:
        if progress_cb is None:
            return
        # On borne pct dans [0, 100]
        pct_clamped = max(0, min(100, int(pct)))

        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=message or f"Export ILDA : {pct_clamped}%",
                frame_index=pct_clamped,
                total_frames=100,
                frame_path=None,
            )
        )

    try:
        _raise_if_cancelled()

        # ------------------------------------------------------------------
        # 1) Export ILDA via la fonction de core.step_ilda
        # ------------------------------------------------------------------
        def check_cancel_inner() -> bool:
            if cancel_cb is None:
                return False
            return bool(cancel_cb())

        def report_progress_inner(pct: int) -> None:
            _report_progress_percent(
                pct,
                message=f"Export ILDA en cours... ({pct}%)",
            )

        _report_progress_percent(0, "Préparation de l'export ILDA...")

        out_path = export_project_to_ilda(
            project_name=project_name,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
            remove_outer_frame=remove_outer_frame,
            frame_margin_rel=frame_margin_rel,
            check_cancel=check_cancel_inner,
            report_progress=report_progress_inner,
        )

        _raise_if_cancelled()
        _report_progress_percent(90, "Génération de la prévisualisation ILDA...")

        # ------------------------------------------------------------------
        # 2) Génération d'une prévisualisation ILDA (PNG) pour la GUI
        # ------------------------------------------------------------------
        project_root = PROJECTS_ROOT / project_name
        preview_dir = project_root / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)

        preview_png = preview_dir / "ilda_preview.png"

        try:
            render_ilda_preview(
                ilda_path=out_path,
                out_png=preview_png,
                frame_index=0,
            )
        except Exception as e_preview:
            # On ne bloque pas l'export ILDA lui-même si la preview échoue.
            if progress_cb is not None:
                progress_cb(
                    FrameProgress(
                        step_name=step_name,
                        message=f"Export OK, mais erreur lors de la prévisualisation ILDA : {e_preview}",
                        frame_index=0,
                        total_frames=None,
                        frame_path=None,
                    )
                )
            return StepResult(success=False, message=str(e_preview), output_dir=out_path.parent)

        _report_progress_percent(100, "Export ILDA terminé.")

    except Exception as exc:
        # En cas d'erreur ou d'annulation, on retourne un StepResult en échec.
        msg = f"Erreur lors de l'export ILDA : {exc}"
        if progress_cb is not None:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=msg,
                    frame_index=0,
                    total_frames=None,
                    frame_path=None,
                )
            )
        return StepResult(success=False, message=msg, output_dir=None)

    # Si on arrive ici, tout s'est bien passé
    msg = (
        f"Fichier ILDA généré : {out_path.name} "
        f"(mode={mode_normalised or 'classic'})"
    )
    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message=msg,
                frame_index=100,
                total_frames=100,
                frame_path=None,
            )
        )

    return StepResult(success=True, message=msg, output_dir=out_path.parent)
