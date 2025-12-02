# core/step_bitmap.py

import subprocess
from pathlib import Path

from .config import MAGICK_PATH


def png_frames_to_bmp_folder(input_dir: str, output_dir: str) -> Path:
    """
    Convertit tous les PNG d'un dossier en BMP via ImageMagick.

    Args:
        input_dir: dossier contenant des .png (frames)
        output_dir: dossier où écrire les .bmp

    Returns:
        Path vers le dossier de sortie (output_dir).

    Remarques:
        - Cette fonction ne fait que la conversion de format.
        - D'autres traitements (threshold, nettoyage) pourront être ajoutés plus tard.
    """
    in_path = Path(input_dir)
    out_path = Path(output_dir)

    if not in_path.is_dir():
        raise ValueError(f"Dossier d'entrée inexistant: {in_path}")

    out_path.mkdir(parents=True, exist_ok=True)

    png_files = sorted(in_path.glob("*.png"))
    if not png_files:
        raise RuntimeError(f"Aucun fichier .png trouvé dans {in_path}")

    for png_file in png_files:
        bmp_name = png_file.stem + ".bmp"
        bmp_file = out_path / bmp_name

        cmd = [
            str(MAGICK_PATH),
            str(png_file),
            str(bmp_file),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"ImageMagick a échoué pour {png_file} "
                f"(code {result.returncode}):\n{result.stderr}"
            )

    return out_path


from .config import PROJECTS_ROOT


def convert_project_frames_to_bmp(project_name: str) -> Path:
    """
    Utilitaire: convertit les frames PNG d'un projet en BMP.

    - Entrée:  projects/<project_name>/frames/*.png
    - Sortie:  projects/<project_name>/bmp/*.bmp
    """
    project_root = PROJECTS_ROOT / project_name
    frames_dir = project_root / "frames"
    bmp_dir = project_root / "bmp"

    return png_frames_to_bmp_folder(str(frames_dir), str(bmp_dir))
