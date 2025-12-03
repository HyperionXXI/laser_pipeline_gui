# core/step_bitmap.py

import subprocess
from pathlib import Path

from .config import MAGICK_PATH, PROJECTS_ROOT


def png_frames_to_bmp_folder(
    input_dir: str,
    output_dir: str,
    threshold: int = 60,
    use_thinning: bool = False,
    max_frames: int | None = None,
) -> Path:
    """
    Convertit des PNG en BMP via ImageMagick, avec pré-traitement pour Potrace.

    Traitements appliqués :
        - conversion en niveaux de gris
        - seuillage (binarisation) à 'threshold' %
        - optionnel : thinning (squelette) pour affiner les traits

    Args:
        input_dir: dossier contenant des .png (frames)
        output_dir: dossier où écrire les .bmp
        threshold: pourcentage de seuil (0-100, typiquement 40–70)
        use_thinning: si True, applique un thinning pour réduire l'épaisseur des traits
        max_frames: si non-None, limite le nombre de frames traitées (pour tests)

    Returns:
        Path vers le dossier de sortie (output_dir).
    """
    in_path = Path(input_dir)
    out_path = Path(output_dir)

    if not in_path.is_dir():
        raise ValueError(f"Dossier d'entrée inexistant: {in_path}")

    out_path.mkdir(parents=True, exist_ok=True)

    png_files = sorted(in_path.glob("*.png"))
    if not png_files:
        raise RuntimeError(f"Aucun fichier .png trouvé dans {in_path}")

    # Clamp simple du seuil
    threshold = max(0, min(100, threshold))

    for idx, png_file in enumerate(png_files):
        if max_frames is not None and idx >= max_frames:
            break

        bmp_name = png_file.stem + ".bmp"
        bmp_file = out_path / bmp_name

        cmd = [
            str(MAGICK_PATH),
            str(png_file),
            "-colorspace", "Gray",
            "-threshold", f"{threshold}%",
        ]

        # Optionnel : thinning / skeleton (plus léger qu'avant)
        if use_thinning:
            cmd += [
                "-morphology", "Thinning:1", "Skeleton",
            ]

        cmd.append(str(bmp_file))

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"ImageMagick a échoué pour {png_file} "
                f"(code {result.returncode}):\n{result.stderr}"
            )

    return out_path


def convert_project_frames_to_bmp(
    project_name: str,
    threshold: int = 60,
    use_thinning: bool = False,
    max_frames: int | None = None,
) -> Path:
    """
    Utilitaire: convertit les frames PNG d'un projet en BMP prétraités.

    - Entrée:  projects/<project_name>/frames/*.png
    - Sortie:  projects/<project_name>/bmp/*.bmp
    """
    project_root = PROJECTS_ROOT / project_name
    frames_dir = project_root / "frames"
    bmp_dir = project_root / "bmp"

    return png_frames_to_bmp_folder(
        str(frames_dir),
        str(bmp_dir),
        threshold=threshold,
        use_thinning=use_thinning,
        max_frames=max_frames,
    )
