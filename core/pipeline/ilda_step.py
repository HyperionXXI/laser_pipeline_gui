from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core.config import PROJECTS_ROOT
from core.pipeline.base import FrameProgress, StepResult
from core.step_ilda import export_project_to_ilda


# ---------------------------------------------------------------------------
# Configuration "debug"
# ---------------------------------------------------------------------------

# Quand True, on ajoute au message final un listing du nombre de points ILDA
# par frame (en lisant le fichier .ild généré).
#
# Par défaut False pour ne pas flooder le log. Tu peux le passer à True
# localement si tu veux inspecter la densité de points.
DEBUG_LOG_POINTS_PER_FRAME: bool = False


# ---------------------------------------------------------------------------
# Petites structures d'aide internes
# ---------------------------------------------------------------------------

@dataclass
class IldaExportConfig:
    """Paramètres effectifs passés au core d'export ILDA."""
    mode: str
    fit_axis: str
    fill_ratio: float
    min_rel_size: float
    remove_outer_frame: bool
    frame_margin_rel: float


def _normalise_mode(raw_mode: Optional[str]) -> str:
    """
    Normalise la chaîne de mode en 'classic' ou 'arcade'.

    Toute valeur inconnue retombe sur 'classic' pour rester robuste.
    """
    if not raw_mode:
        return "classic"

    m = raw_mode.strip().lower()
    if m == "arcade":
        return "arcade"
    return "classic"


def _build_config(
    fit_axis: str,
    fill_ratio: float,
    min_rel_size: float,
    raw_mode: Optional[str],
) -> IldaExportConfig:
    """
    Construit la config d'export à partir des paramètres du pipeline.

    - `classic` : comportement historique (mais on supprime déjà le cadre).
    - `arcade`  : profil expérimental, avec filtrage de cadre un peu plus
                  agressif via `frame_margin_rel`.
    """

    mode = _normalise_mode(raw_mode)

    # Sécurisation minimale des paramètres numériques
    fit_axis_norm = fit_axis if fit_axis in ("min", "max", "x", "y") else "max"
    fill_ratio_clamped = max(0.1, min(float(fill_ratio), 1.0))
    min_rel_size_clamped = max(0.0, min(float(min_rel_size), 1.0))

    if mode == "classic":
        # On essaie déjà de virer le cadre parasite
        remove_outer_frame = True
        frame_margin_rel = 0.02
    else:
        # Mode "arcade" : filtrage de cadre un peu plus large
        remove_outer_frame = True
        frame_margin_rel = 0.05

    return IldaExportConfig(
        mode=mode,
        fit_axis=fit_axis_norm,
        fill_ratio=fill_ratio_clamped,
        min_rel_size=min_rel_size_clamped,
        remove_outer_frame=remove_outer_frame,
        frame_margin_rel=frame_margin_rel,
    )


# ---------------------------------------------------------------------------
# Lecture légère des headers ILDA pour compter les points par frame
# ---------------------------------------------------------------------------

def _read_points_per_frame(ilda_path: Path) -> list[int]:
    """
    Lis le fichier ILDA et renvoie une liste [n_points_frame0, n_points_frame1, ...].

    On s'appuie sur le header ILDA standard :
    - octets 0..3  : b"ILDA"
    - octet 7      : format code
    - octets 24..25: nombre de "records" (big-endian)

    Pour les formats 0 et 1, chaque record est un point (8 octets).
    Pour les palettes (2 et 3), on ne fait que sauter les données.
    """
    points: list[int] = []

    try:
        with ilda_path.open("rb") as f:
            while True:
                header = f.read(32)
                if len(header) < 32:
                    break

                if header[0:4] != b"ILDA":
                    # Header inattendu → on arrête proprement.
                    break

                fmt = header[7]
                num_records = int.from_bytes(header[24:26], "big", signed=False)

                if fmt in (0, 1):
                    # Frame 3D/2D → chaque record correspond à un point
                    points.append(num_records)
                    record_size = 8
                elif fmt in (2, 3):
                    # Palette → on ne compte pas comme frame d'affichage
                    record_size = 3
                else:
                    # Format inconnu : on sort sans tout casser.
                    break

                # On saute les données de la frame/palette
                if num_records > 0 and record_size > 0:
                    f.seek(num_records * record_size, 1)
    except Exception:
        # En cas de souci de lecture, on renvoie simplement ce qu'on a pu lire
        pass

    return points


# ---------------------------------------------------------------------------
# Fonction appelée par le PipelineController
# ---------------------------------------------------------------------------

def run_ilda_step(
    project_name: str,
    fit_axis: str,
    fill_ratio: float,
    min_rel_size: float,
    ilda_mode: str,
    *,
    progress_cb: Optional[Callable[[FrameProgress], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> StepResult:
    """
    Step pipeline : export SVG -> ILDA.

    Signature compatible avec `PipelineController` :

        run_ilda_step(project, fit_axis, fill_ratio, min_rel_size, ilda_mode,
                      progress_cb=..., cancel_cb=...)

    Cette fonction s'occupe surtout de :
      - préparer les chemins,
      - adapter les paramètres (fit_axis, min_rel_size, mode, filtrage de cadre),
      - relayer la progression vers le GUI,
      - produire un StepResult pour le log final,
      - et éventuellement ajouter un log détaillé du nombre de points par frame.
    """
    project_root = PROJECTS_ROOT / project_name
    svg_dir = project_root / "svg"
    ilda_dir = project_root / "ilda"
    ilda_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------
    # Préparation des paramètres d'export
    # ----------------------------------------
    cfg = _build_config(
        fit_axis=fit_axis,
        fill_ratio=fill_ratio,
        min_rel_size=min_rel_size,
        raw_mode=ilda_mode,
    )

    # On compte les SVG pour donner une idée du total au GUI (progress bar)
    try:
        total_frames = len(sorted(svg_dir.glob("frame_*.svg")))
    except Exception:
        total_frames = None

    # ----------------------------------------
    # Fonctions de callback pour le core
    # ----------------------------------------

    def _report_progress(pct: int) -> None:
        """
        Bridge entre la progression entière [0..100] du core ILDA
        et l'objet FrameProgress attendu par le GUI.
        """
        if progress_cb is None:
            return

        if total_frames and total_frames > 0:
            # On approxime l'index de frame à partir du pourcentage.
            frame_index = int(pct * total_frames / 100.0) - 1
            if frame_index < 0:
                frame_index = 0
            if frame_index >= total_frames:
                frame_index = total_frames - 1
            tf = total_frames
        else:
            # Fallback : progression purement "indéterminée"
            frame_index = max(pct - 1, 0)
            tf = 100

        fp = FrameProgress(
            step_name="ilda",
            message="",
            frame_index=frame_index,
            total_frames=tf,
            frame_path=None,   # pas de preview frame par frame pendant l'export
        )
        progress_cb(fp)

    def _check_cancel() -> bool:
        """Bridge pour la demande d'annulation depuis le GUI."""
        return bool(cancel_cb and cancel_cb())

    # ----------------------------------------
    # Appel au core d'export ILDA
    # ----------------------------------------
    try:
        out_path = export_project_to_ilda(
            project_name=project_name,
            fit_axis=cfg.fit_axis,
            fill_ratio=cfg.fill_ratio,
            min_rel_size=cfg.min_rel_size,
            remove_outer_frame=cfg.remove_outer_frame,
            frame_margin_rel=cfg.frame_margin_rel,
            check_cancel=_check_cancel,
            report_progress=_report_progress,
            mode=cfg.mode,
        )
    except Exception as e:
        return StepResult(
            success=False,
            message=f"Erreur lors de l'export ILDA : {e}",
            output_dir=ilda_dir,
        )

    # Sécurité : on vérifie que le fichier a bien été créé
    if not out_path or not isinstance(out_path, Path) or not out_path.exists():
        return StepResult(
            success=False,
            message="Erreur lors de l'export ILDA (fichier .ild non généré).",
            output_dir=ilda_dir,
        )

    # ----------------------------------------
    # Log optionnel : nombre de points par frame
    # ----------------------------------------
    debug_lines: list[str] = []
    if DEBUG_LOG_POINTS_PER_FRAME:
        frame_points = _read_points_per_frame(out_path)
        if frame_points:
            debug_lines.append("Densité de points par frame :")
            for idx, n in enumerate(frame_points):
                debug_lines.append(f"  Frame {idx + 1:04d} : {n} points")
        else:
            debug_lines.append(
                "Impossible de lire le nombre de points par frame "
                "(format ILDA inattendu ou fichier vide)."
            )

    mode_label = cfg.mode
    base_msg = f"Fichier ILDA généré : {out_path.name} (mode={mode_label})"
    if debug_lines:
        message = base_msg + "\n" + "\n".join(debug_lines)
    else:
        message = base_msg

    return StepResult(
        success=True,
        message=message,
        output_dir=ilda_dir,
    )
