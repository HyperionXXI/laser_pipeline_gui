# core/pipeline/potrace_step.py
from __future__ import annotations

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from core.config import PROJECTS_ROOT, POTRACE_PATH
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def _run_potrace_bmp_to_svg(
    bmp_path: Path,
    svg_path: Path,
    *,
    cancel_cb: Optional[CancelCallback] = None,
) -> None:
    """
    Convertit un BMP binaire (noir sur blanc) en SVG via potrace.
    """
    if cancel_cb and cancel_cb():
        raise RuntimeError("Annulé")

    svg_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [str(POTRACE_PATH), "-s", "-o", str(svg_path), str(bmp_path)]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Potrace introuvable. Vérifie POTRACE_PATH ou LPIP_POTRACE. Détail: {e}"
        ) from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        stdout = (e.stdout or "").strip()
        msg = "Potrace a échoué."
        if stderr:
            msg += f" STDERR: {stderr}"
        elif stdout:
            msg += f" STDOUT: {stdout}"
        raise RuntimeError(msg) from e


def _is_path_tag(tag: str) -> bool:
    # gère <path> et <{ns}path>
    return tag.endswith("path")


def _read_paths_from_svg(svg_path: Path) -> List[ET.Element]:
    """
    Parse le SVG et renvoie une liste d'éléments <path> complets.
    """
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError as e:
        raise RuntimeError(f"SVG Potrace invalide: {svg_path.name} -> {e}") from e

    root = tree.getroot()
    paths: List[ET.Element] = []
    for elem in root.iter():
        if _is_path_tag(elem.tag):
            paths.append(elem)
    return paths


def _clone_path_with_rgb(src: ET.Element, rgb: Tuple[int, int, int]) -> ET.Element:
    """
    Clone un <path> en conservant ses attributs + ajoute data-rgb.
    """
    # ET.Element ne supporte pas copy() proprement -> recrée + copie attribs
    dst = ET.Element(src.tag)
    for k, v in src.attrib.items():
        dst.set(k, v)
    dst.set("data-rgb", f"{rgb[0]},{rgb[1]},{rgb[2]}")
    return dst


def run_potrace_step(
    project: str,
    *,
    mode: str = "classic",
    max_frames: Optional[int] = None,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    step_name = "potrace"

    project_root = PROJECTS_ROOT / project
    bmp_dir = project_root / "bmp"
    svg_dir = project_root / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)

    if progress_cb:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage vectorisation (Potrace)…",
                frame_index=0,
                total_frames=None,
                frame_path=None,
            )
        )

    # ------------------------------------------------------------
    # CLASSIC : 1 BMP -> 1 SVG (frame_XXXX.bmp uniquement)
    # ------------------------------------------------------------
    if mode.lower() != "arcade":
        bmp_files = sorted(bmp_dir.glob("frame_[0-9][0-9][0-9][0-9].bmp"))
        if max_frames is not None:
            bmp_files = bmp_files[:max_frames]
        if not bmp_files:
            return StepResult(False, "Aucun BMP frame_XXXX.bmp trouvé pour Potrace.", svg_dir)

        total = len(bmp_files)
        for i, bmp_path in enumerate(bmp_files, start=1):
            if cancel_cb and cancel_cb():
                return StepResult(False, "Vectorisation annulée.", svg_dir)

            out_svg = svg_dir / f"{bmp_path.stem}.svg"
            _run_potrace_bmp_to_svg(bmp_path, out_svg, cancel_cb=cancel_cb)

            if progress_cb:
                progress_cb(
                    FrameProgress(
                        step_name=step_name,
                        message=f"Frame {i}/{total}",
                        frame_index=i,
                        total_frames=total,
                        frame_path=out_svg,
                    )
                )

        return StepResult(True, f"SVG générés dans : {svg_dir}", svg_dir)

    # ------------------------------------------------------------
    # ARCADE : vectorisation par couche + fusion XML correcte + data-rgb
    # ------------------------------------------------------------
    manifest_path = bmp_dir / "_layers_manifest.json"
    if not manifest_path.exists():
        return StepResult(False, "Manifest arcade '_layers_manifest.json' introuvable.", svg_dir)

    manifest: Dict = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames: List[Dict] = manifest.get("frames", [])
    if max_frames is not None:
        frames = frames[:max_frames]
    if not frames:
        return StepResult(False, "Manifest arcade vide (aucune frame).", svg_dir)

    total = len(frames)

    for i, frame in enumerate(frames, start=1):
        if cancel_cb and cancel_cb():
            return StepResult(False, "Vectorisation annulée.", svg_dir)

        frame_id = frame["frame"]  # ex: frame_0001

        # Nouveau SVG racine (namespace SVG)
        out_root = ET.Element(f"{{{SVG_NS}}}svg")

        for layer in frame.get("layers", []):
            bmp_name = layer.get("bmp")
            rgb = layer.get("rgb", [255, 255, 255])
            rgb_t = (int(rgb[0]), int(rgb[1]), int(rgb[2]))

            if not bmp_name:
                continue

            bmp_path = bmp_dir / bmp_name
            if not bmp_path.exists():
                continue

            tmp_svg = svg_dir / f"{bmp_path.stem}.svg"
            _run_potrace_bmp_to_svg(bmp_path, tmp_svg, cancel_cb=cancel_cb)

            # Parse proprement les paths
            for p in _read_paths_from_svg(tmp_svg):
                out_root.append(_clone_path_with_rgb(p, rgb_t))

        out_svg = svg_dir / f"{frame_id}.svg"
        ET.ElementTree(out_root).write(out_svg, encoding="utf-8", xml_declaration=True)

        if progress_cb:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=f"Frame {i}/{total} (arcade layers)",
                    frame_index=i,
                    total_frames=total,
                    frame_path=out_svg,
                )
            )

    return StepResult(True, f"SVG arcade générés dans : {svg_dir}", svg_dir)
