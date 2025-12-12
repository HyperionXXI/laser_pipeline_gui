# core/step_potrace.py
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from .config import POTRACE_PATH


def _run_potrace_single(bmp_path: Path, svg_path: Path) -> None:
    """Lance Potrace pour convertir un BMP en SVG."""
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(POTRACE_PATH),
        "-s",
        "-o",
        str(svg_path),
        str(bmp_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        raise RuntimeError(f"Potrace a échoué :\n{stderr}") from e


def _postprocess_svg(svg_path: Path) -> None:
    """
    Post-traitement SVG Potrace (uniquement pour preview, pas utilisé pour l'ILDA).
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(svg_path)
    root = tree.getroot()

    def is_tag(elem, local: str) -> bool:
        return elem.tag == local or elem.tag.endswith("}" + local)

    for elem in root.iter():
        if is_tag(elem, "path"):
            elem.set("fill", "none")
            elem.set("stroke", "#FFFFFF")
            elem.set("stroke-width", "3")
            elem.set("stroke-linejoin", "round")
            elem.set("stroke-linecap", "round")
            if "style" in elem.attrib:
                del elem.attrib["style"]

    tree.write(svg_path, encoding="utf-8")


def bitmap_to_svg_folder(
    bmp_dir: str,
    svg_dir: str,
    max_frames: Optional[int] = None,
    frame_callback: Optional[Callable[[int, int, Path], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
) -> str:
    """Convertit frame_*.bmp -> frame_*.svg pour un dossier."""
    bmp_dir_p = Path(bmp_dir)
    svg_dir_p = Path(svg_dir)
    svg_dir_p.mkdir(parents=True, exist_ok=True)

    bmp_files: List[Path] = sorted(bmp_dir_p.glob("frame_*.bmp"))
    if max_frames is not None:
        bmp_files = bmp_files[:max_frames]

    total = len(bmp_files)
    if total == 0:
        raise RuntimeError(f"Aucun BMP trouvé dans {bmp_dir_p}")

    for idx, bmp_path in enumerate(bmp_files, start=1):
        if cancel_cb is not None and cancel_cb():
            raise RuntimeError("Vectorisation Potrace annulée par l'utilisateur.")

        svg_path = svg_dir_p / (bmp_path.stem + ".svg")

        _run_potrace_single(bmp_path, svg_path)
        _postprocess_svg(svg_path)

        if frame_callback is not None:
            frame_callback(idx, total, svg_path)

    return str(svg_dir_p)
