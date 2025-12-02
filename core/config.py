# core/config.py

from pathlib import Path

# Chemin vers ffmpeg
FFMPEG_PATH = Path(r"C:\ffmpeg-7.1-essentials_build\bin\ffmpeg.exe")

# Chemin vers Potrace
POTRACE_PATH = Path(r"C:\potrace-1.16.win64\potrace.exe")

# Dossier racine pour les projets
PROJECTS_ROOT = Path("projects")
PROJECTS_ROOT.mkdir(exist_ok=True)

