# core/step_potrace.py

import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

from .config import POTRACE_PATH


def _postprocess_svg(svg_path: Path) -> None:
    """
    Ouvre le SVG généré par Potrace et force un rendu "ligne blanche
    sur fond transparent" adapté au laser.

    - Tous les <g> et <path> passent en fill="none"
    - stroke="#FFFFFF", stroke-width=1, linejoin/linecap=round
    """
    try:
        text = svg_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    if not text.strip():
        # SVG vide, rien à faire
        return

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        # En dernier recours : on garde l'ancien replace() simple
        text_new = text.replace(
            'fill="#000000" stroke="none"',
            (
                'fill="none" '
                'stroke="#FFFFFF" '
                'stroke-width="1" '
                'stroke-linejoin="round" '
                'stroke-linecap="round"'
            ),
        )
        text_new = text_new.replace('fill="#000000"', 'fill="none"')
        if text_new != text:
            svg_path.write_text(text_new, encoding="utf-8")
        return

    # Gestion du namespace éventuel (Potrace met parfois du SVG "nu",
    # parfois avec xmlns)
    def iter_all(tag):
        # tag sans namespace, ex: "g" ou "path"
        for elem in root.iter():
            if elem.tag.endswith(tag):
                yield elem

    # On applique les attributs sur tous les groupes et paths
    for elem in list(iter_all("g")) + list(iter_all("path")):
        # Pas de remplissage
        elem.attrib["fill"] = "none"
        # Trait blanc
        elem.attrib["stroke"] = "#FFFFFF"
        # Épaisseur minimale (tu pourras l'exposer plus tard dans l'UI si besoin)
        elem.attrib.setdefault("stroke-width", "1")
        # Rendu plus propre
        elem.attrib.setdefault("stroke-linejoin", "round")
        elem.attrib.setdefault("stroke-linecap", "round")

    # On ré-écrit le fichier
    new_text = ET.tostring(root, encoding="unicode")
    svg_path.write_text(new_text, encoding="utf-8")


def _run_potrace_single(bmp_path: Path, svg_path: Path) -> None:
    """
    Lance Potrace sur un BMP et génère un SVG, puis post-traite le SVG
    pour qu'il soit adapté au laser (contours blancs, pas de fond noir).
    """
    bmp_path = Path(bmp_path)
    svg_path = Path(svg_path)

    svg_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(POTRACE_PATH),
        "-s",          # sortie SVG
        "--invert",    # ligne claire sur fond sombre -> on inverse
        "-o", str(svg_path),
        str(bmp_path),
    ]
    subprocess.run(cmd, check=True)

    _postprocess_svg(svg_path)


def bitmap_to_svg_folder(bmp_dir: str, svg_dir: str) -> str:
    """
    Pour chaque BMP 'frame_XXXX.bmp' du dossier bmp_dir, génère un SVG
    'frame_XXXX.svg' dans svg_dir via Potrace + post-traitement.
    """
    bmp_dir = Path(bmp_dir)
    svg_dir = Path(svg_dir)
    svg_dir.mkdir(parents=True, exist_ok=True)

    for bmp_path in sorted(bmp_dir.glob("frame_*.bmp")):
        svg_path = svg_dir / (bmp_path.stem + ".svg")
        _run_potrace_single(bmp_path, svg_path)

    return str(svg_dir)
