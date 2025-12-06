# core/pipeline/base.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class FrameProgress:
    """
    Représente l'avancement d'un step.

    - step_name : étiquette du step ("ffmpeg", "bitmap", "potrace", ...)
    - message : texte optionnel pour le log
    - frame_index : index de frame déjà traitée (0-based ou 1-based) ou None
    - total_frames : nombre total de frames si connu, sinon None
    - frame_path : chemin de la dernière frame écrite (PNG/BMP/SVG...)
    """

    step_name: str
    message: str = ""
    frame_index: Optional[int] = None
    total_frames: Optional[int] = None
    frame_path: Optional[Path] = None


@dataclass
class StepResult:
    """
    Résultat global d'un step de pipeline.

    - success : True si tout s'est bien passé
    - message : résumé textuel
    - output_dir : répertoire de sortie principal du step
    """

    success: bool
    message: str
    output_dir: Optional[Path] = None


# Callbacks utilisés par les steps
ProgressCallback = Callable[[FrameProgress], None]
CancelCallback = Callable[[], bool]
