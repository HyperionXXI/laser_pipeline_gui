# core/pipeline/ffmpeg_step.py
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from core.ffmpeg_extract import extract_frames
from .base import FrameProgress, StepResult, ProgressCallback, CancelCallback


def _safe_float(s: Optional[str]) -> Optional[float]:
    try:
        return float(s) if s is not None else None
    except Exception:
        return None


def _parse_fraction(fr: str) -> Optional[float]:
    # ex: "30000/1001"
    try:
        if "/" in fr:
            a, b = fr.split("/", 1)
            a_f = float(a)
            b_f = float(b)
            if b_f == 0:
                return None
            return a_f / b_f
        return float(fr)
    except Exception:
        return None


def _ffprobe_video_info(video_path: str) -> Optional[Dict[str, Any]]:
    """
    Récupère des métadonnées via ffprobe (si disponible).
    Retourne un dict ou None si ffprobe n'est pas dispo / échoue.
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except Exception:
        return None

    try:
        data = json.loads(res.stdout)
    except Exception:
        return None

    # stream vidéo principal
    streams = data.get("streams", []) or []
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    v = vstreams[0] if vstreams else None

    fmt = data.get("format", {}) or {}

    if not v:
        return None

    width = v.get("width")
    height = v.get("height")

    # fps: on préfère avg_frame_rate, sinon r_frame_rate
    fps = None
    avg = v.get("avg_frame_rate")
    rfr = v.get("r_frame_rate")
    fps = _parse_fraction(avg) or _parse_fraction(rfr)

    duration = _safe_float(fmt.get("duration"))
    bit_rate = _safe_float(fmt.get("bit_rate"))

    # certains fichiers ont un bit_rate audio/video séparé
    v_bitrate = _safe_float(v.get("bit_rate"))

    return {
        "width": width,
        "height": height,
        "fps_detected": fps,
        "duration_s": duration,
        "bitrate_total_bps": bit_rate,
        "bitrate_video_bps": v_bitrate,
        "codec": v.get("codec_name"),
    }


def _fmt_bitrate(bps: Optional[float]) -> str:
    if not bps:
        return "?"
    # affichage simple en kbits/s
    return f"{int(round(bps / 1000.0))} kbits/s"


def run_ffmpeg_step(
    video_path: str,
    project: str,
    fps: int,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
) -> StepResult:
    """
    Step pipeline pour l'extraction des frames via FFmpeg.

    - Loggue les infos vidéo via ffprobe (si dispo).
    - Extraction frames via core.ffmpeg_extract.extract_frames (bloquant).
    """
    step_name = "ffmpeg"

    # Début : barre indéterminée
    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Démarrage FFmpeg…",
                frame_index=0,
                total_frames=None,
                frame_path=None,
            )
        )

    # Probe vidéo (optionnel)
    info = _ffprobe_video_info(video_path)
    if progress_cb is not None:
        if info is None:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message="[ffprobe] Infos vidéo indisponibles (ffprobe absent ou échec).",
                    frame_index=0,
                    total_frames=None,
                    frame_path=None,
                )
            )
        else:
            w = info.get("width")
            h = info.get("height")
            fps_det = info.get("fps_detected")
            dur = info.get("duration_s")
            br_total = _fmt_bitrate(info.get("bitrate_total_bps"))
            br_vid = _fmt_bitrate(info.get("bitrate_video_bps"))
            codec = info.get("codec") or "?"

            msg = (
                f"[ffprobe] vidéo={w}x{h}, fps_detected={fps_det:.3f} "
                f"(GUI fps={fps}), durée={dur:.2f}s, codec={codec}, "
                f"bitrate_total={br_total}, bitrate_video={br_vid}"
            )
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=msg,
                    frame_index=0,
                    total_frames=None,
                    frame_path=None,
                )
            )

    # Annulation juste avant le lancement (utile si tu cliques Stop)
    if cancel_cb is not None and cancel_cb():
        return StepResult(
            success=False,
            message="Extraction annulée avant lancement FFmpeg.",
            output_dir=None,
        )

    # Lancement réel d'FFmpeg (bloquant)
    out_dir = extract_frames(video_path, project, fps=fps)

    # Après extraction : on cherche au moins une frame PNG
    png_files = sorted(Path(out_dir).glob("frame_*.png"))
    if png_files:
        frame_path = png_files[0]
        total_frames = len(png_files)
        frame_index = total_frames - 1  # barre à ~100%
    else:
        frame_path = None
        total_frames = 1
        frame_index = 0

    if progress_cb is not None:
        progress_cb(
            FrameProgress(
                step_name=step_name,
                message="Extraction terminée.",
                frame_index=frame_index,
                total_frames=total_frames,
                frame_path=frame_path,
            )
        )

    return StepResult(
        success=True,
        message=f"Frames extraites dans : {out_dir}",
        output_dir=Path(out_dir),
    )
