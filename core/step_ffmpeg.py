# core/step_ffmpeg.py

# core/step_ffmpeg.py

import subprocess
from pathlib import Path

from .config import FFMPEG_PATH, PROJECTS_ROOT


def extract_frames(input_video: str, project_name: str, fps: int = 25) -> Path:
    """
    Extrait des frames PNG depuis une vidéo dans un dossier de projet.

    Args:
        input_video: chemin vers le fichier vidéo source (.mp4, .mov, etc.)
        project_name: nom du sous-dossier de projet (ex: "projet_demo")
        fps: nombre d'images par seconde à extraire

    Returns:
        Path vers le dossier contenant les frames.
    """
    # Dossier du projet
    root = PROJECTS_ROOT / project_name
    frames_dir = root / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Commande FFmpeg : vidéo -> frames/frame_0001.png, etc.
    cmd = [
        str(FFMPEG_PATH),
        "-i", input_video,
        "-vf", f"fps={fps}",
        str(frames_dir / "frame_%04d.png"),
    ]

    # Lancer ffmpeg
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg a échoué (code {result.returncode}) :\n{result.stderr}"
        )

    return frames_dir

