# core/step_ffmpeg.py
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import FFMPEG_PATH, PROJECTS_ROOT


def extract_frames(input_video: str, project_name: str, fps: int = 25) -> Path:
    """
    Extrait des frames PNG depuis une vidéo dans un dossier de projet.

    Returns:
        Path du dossier contenant les frames.
    """
    root = PROJECTS_ROOT / project_name
    frames_dir = root / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(FFMPEG_PATH),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        input_video,
        "-vf",
        f"fps={fps}",
        str(frames_dir / "frame_%04d.png"),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        raise RuntimeError(f"FFmpeg a échoué :\n{stderr}") from e

    return frames_dir
