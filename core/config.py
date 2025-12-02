# core/config.py

from pathlib import Path

# ⚠️ À adapter si besoin selon l'endroit où est installé ffmpeg
FFMPEG_PATH = Path(r"C:\ffmpeg-7.1-essentials_build\bin\ffmpeg.exe")

# Dossier racine où seront créés les projets d'export
PROJECTS_ROOT = Path("projects")
PROJECTS_ROOT.mkdir(exist_ok=True)
