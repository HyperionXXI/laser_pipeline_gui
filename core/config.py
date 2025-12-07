# core/config.py
from __future__ import annotations

import os
import shutil
from pathlib import Path


def _tool_path(env_name: str, default_win: str, default_unix: str) -> Path:
    """
    Résout le chemin d'un outil externe.

    Priorité :
      1) variable d'environnement env_name (LPIP_*)
      2) binaire trouvé dans le PATH (shutil.which)
      3) fallback spécifique Windows / Unix

    Cela permet :
      - d'utiliser une installation système (PATH),
      - ou des binaires fournis dans le projet en pointant LPIP_* vers eux,
      - tout en gardant des valeurs par défaut raisonnables pour ta machine.
    """
    # 1) Variable d'environnement explicite
    env_val = os.getenv(env_name)
    if env_val:
        return Path(env_val)

    # 2) Essai via le PATH (ffmpeg, magick, potrace, etc.)
    which_name = os.path.basename(default_unix)
    found = shutil.which(which_name)
    if found:
        return Path(found)

    # 3) Fallbacks par OS
    if os.name == "nt":
        return Path(default_win)
    return Path(default_unix)


# Chemin vers ffmpeg
FFMPEG_PATH = _tool_path(
    "LPIP_FFMPEG",
    r"C:\ffmpeg-7.1-essentials_build\bin\ffmpeg.exe",
    "ffmpeg",
)

# Chemin vers Potrace
POTRACE_PATH = _tool_path(
    "LPIP_POTRACE",
    r"C:\potrace-1.16.win64\potrace.exe",
    "potrace",
)

# Chemin vers ImageMagick (magick.exe)
MAGICK_PATH = _tool_path(
    "LPIP_MAGICK",
    r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe",
    "magick",
)

# Dossier racine pour les projets
PROJECTS_ROOT = Path(os.getenv("LPIP_PROJECTS_ROOT", "projects"))
PROJECTS_ROOT.mkdir(exist_ok=True)
