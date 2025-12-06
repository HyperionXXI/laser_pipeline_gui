# core/config.py
from __future__ import annotations

import os
from pathlib import Path


def _tool_path(env_name: str, default: str) -> Path:
    """
    Résout le chemin d'un outil externe :

    - si la variable d'environnement env_name est définie → on l'utilise
    - sinon on tombe sur 'default'
    """
    env_val = os.getenv(env_name)
    if env_val:
        return Path(env_val)
    return Path(default)


# Chemin vers ffmpeg
FFMPEG_PATH = _tool_path(
    "LPIP_FFMPEG",
    r"C:\ffmpeg-7.1-essentials_build\bin\ffmpeg.exe",
)

# Chemin vers Potrace
POTRACE_PATH = _tool_path(
    "LPIP_POTRACE",
    r"C:\potrace-1.16.win64\potrace.exe",
)

# Chemin vers ImageMagick (magick.exe)
MAGICK_PATH = _tool_path(
    "LPIP_MAGICK",
    r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe",
)

# Dossier racine pour les projets
PROJECTS_ROOT = Path(os.getenv("LPIP_PROJECTS_ROOT", "projects"))
PROJECTS_ROOT.mkdir(exist_ok=True)
