# core/pipeline/base.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Dict, Any


@dataclass
class FrameProgress:
    """
    Évènement de progression pour une étape du pipeline.
    - step  : nom logique de l'étape ("ffmpeg", "bitmap", "potrace", "ilda", ...)
    - index : index de frame courant (1-based si pertinent)
    - total : nombre total estimé (None si inconnu)
    - last_output : dernier fichier produit pour cette étape (image, svg, etc.)
    """
    step: str
    index: int = 0
    total: Optional[int] = None
    last_output: Optional[Path] = None


@dataclass
class StepResult:
    """
    Résultat d'une étape du pipeline.
    - success     : booléen succès/échec
    - message     : texte lisible (affiché dans le log)
    - output_dir  : répertoire principal produit par l’étape, si applicable
    - extra       : dictionnaire libre pour des infos additionnelles
    """
    step: str
    success: bool
    message: str
    output_dir: Optional[Path] = None
    extra: Optional[Dict[str, Any]] = None


# Types de callbacks utilisés par les étapes
ProgressCallback = Callable[[FrameProgress], None]
CancelCallback = Callable[[], bool]