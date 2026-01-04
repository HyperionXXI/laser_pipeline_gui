# core/ffmpeg_extract.py
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import FFMPEG_PATH, PROJECTS_ROOT


def extract_frames(
    input_video: Path,
    project_name: str,
    fps: int,
    *,
    max_frames: int = 0,  # 0 = toutes
    scale: float | None = None,
) -> Path:
    """
    Extrait les frames PNG de input_video dans:
      projects/<project_name>/frames/frame_%04d.png

    - fps: échantillonnage temporel (fps=25 -> 25 images/seconde)
    - max_frames: 0 = toutes, sinon limite le nombre de frames extraites
    """
    input_video = Path(input_video)
    if not input_video.exists():
        raise FileNotFoundError(f"Vidéo introuvable: {input_video}")

    out_dir = PROJECTS_ROOT / project_name / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_pattern = out_dir / "frame_%04d.png"

    vf = f"fps={int(fps)}"
    if scale is not None and float(scale) > 1.0:
        vf = f"{vf},scale=iw*{float(scale)}:ih*{float(scale)}:flags=lanczos"

    cmd: list[str] = [
        str(FFMPEG_PATH),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_video),
        "-vf",
        vf,
    ]

    if int(max_frames) > 0:
        cmd += ["-frames:v", str(int(max_frames))]

    cmd += [str(out_pattern)]

    subprocess.run(cmd, check=True)
    return out_dir
