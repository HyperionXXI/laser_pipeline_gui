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
    """
    env_val = os.getenv(env_name)
    if env_val:
        return Path(env_val)

    # Essai via PATH : on prend le basename du default (gère "ffmpeg", "magick", "magick.exe")
    which_name = os.path.basename(default_unix) or default_unix
    found = shutil.which(which_name)
    if found:
        return Path(found)

    if os.name == "nt":
        return Path(default_win)
    return Path(default_unix)


FFMPEG_PATH = _tool_path(
    "LPIP_FFMPEG",
    r"C:\ffmpeg-7.1-essentials_build\bin\ffmpeg.exe",
    "ffmpeg",
)

POTRACE_PATH = _tool_path(
    "LPIP_POTRACE",
    r"C:\potrace-1.16.win64\potrace.exe",
    "potrace",
)

MAGICK_PATH = _tool_path(
    "LPIP_MAGICK",
    r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe",
    "magick",
)

PROJECTS_ROOT = Path(os.getenv("LPIP_PROJECTS_ROOT", "projects"))
PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
