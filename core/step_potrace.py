# core/step_potrace.py

import subprocess
from pathlib import Path

from .config import POTRACE_PATH


def bitmap_to_svg_folder(input_dir: str, output_dir: str) -> Path:
    """
    Convertit tous les fichiers BMP d'un dossier en SVG via Potrace.

    Args:
        input_dir: dossier contenant des .bmp
        output_dir: dossier où écrire les .svg

    Returns:
        Path vers le dossier de sortie (output_dir).

    Remarques:
        - Cette fonction ne gère pour l'instant que les fichiers .bmp.
        - La conversion PNG -> BMP / threshold sera gérée dans un step séparé.
    """
    in_path = Path(input_dir)
    out_path = Path(output_dir)

    if not in_path.is_dir():
        raise ValueError(f"Dossier d'entrée inexistant: {in_path}")

    out_path.mkdir(parents=True, exist_ok=True)

    # Lister les BMP
    bmp_files = sorted(in_path.glob("*.bmp"))
    if not bmp_files:
        raise RuntimeError(f"Aucun fichier .bmp trouvé dans {in_path}")

    for bmp_file in bmp_files:
        svg_name = bmp_file.stem + ".svg"
        svg_file = out_path / svg_name

        cmd = [
            str(POTRACE_PATH),
            "-s",                      # sortie SVG
            "-o", str(svg_file),      # fichier de sortie
            str(bmp_file),            # fichier d'entrée
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"Potrace a échoué pour {bmp_file} "
                f"(code {result.returncode}):\n{result.stderr}"
            )

    return out_path
