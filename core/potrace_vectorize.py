# core/potrace_vectorize.py
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from .config import POTRACE_PATH


def _run_potrace_single(bmp_path: Path, svg_path: Path, *, invert: bool) -> None:
    """Lance Potrace sur un BMP et génère un SVG.

    Notes importantes:
    - Potrace vectorise les pixels NOIRS (foreground).
    - Si tes BMP sont "trait blanc sur fond noir", Potrace trace surtout le fond
      et génère typiquement un grand contour rectangulaire (le "cadre") + des trous.
    - L'option '-i' inverse les couleurs côté Potrace pour vectoriser les traits.
    """
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    cmd: List[str] = [
        str(POTRACE_PATH),
        "-s",                 # output SVG
        "-o",
        str(svg_path),
    ]

    if invert:
        cmd.append("-i")

    cmd.append(str(bmp_path))

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()

        # Message plus explicite si la version de potrace ne supporte pas -i
        if invert and ("unknown option" in stderr.lower() or "unrecognized option" in stderr.lower()):
            raise RuntimeError(
                "Potrace a échoué: l'option '-i' (invert) n'est pas reconnue par cette version.\n"
                "Solutions:\n"
                " - Mettre à jour Potrace (recommandé), ou\n"
                " - Désactiver l'inversion côté Potrace et inverser les BMP en amont (ImageMagick/step bitmap).\n"
                f"Détail: {stderr}"
            ) from e

        raise RuntimeError(f"Potrace a échoué :\n{stderr}") from e


def bitmap_to_svg_folder(
    bmp_dir: str,
    svg_dir: str,
    max_frames: Optional[int] = None,
    frame_callback: Optional[Callable[[int, int, Path], None]] = None,
    cancel_cb: Optional[Callable[[], bool]] = None,
    *,
    invert: bool = True,
    invert_for_potrace: Optional[bool] = None,
) -> str:
    """Vectorise tous les frame_*.bmp d'un dossier vers des frame_*.svg.

    Args:
        bmp_dir: Dossier contenant des BMP nommés frame_*.bmp
        svg_dir: Dossier cible pour les SVG
        max_frames: Limite optionnelle du nombre de frames traitées
        frame_callback: callback(idx, total, svg_path)
        cancel_cb: callback() -> bool, True pour annuler
        invert: Active l'inversion via Potrace '-i' (défaut True).
        invert_for_potrace: Alias rétro-compatible (anciens appels). Override 'invert' si fourni.
    """
    if invert_for_potrace is not None:
        invert = bool(invert_for_potrace)

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
        if cancel_cb and cancel_cb():
            raise RuntimeError("Potrace vectorization canceled by user.")

        svg_path = svg_dir_p / (bmp_path.stem + ".svg")
        _run_potrace_single(bmp_path, svg_path, invert=invert)

        if frame_callback:
            frame_callback(idx, total, svg_path)

    return str(svg_dir_p)
