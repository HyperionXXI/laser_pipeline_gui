from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

from core.config import FFMPEG_PATH
from gui.services.suggestion_models import (
    SuggestedParams,
    SuggestionResult,
    SuggestionStats,
)


class SuggestionError(RuntimeError):
    """Raised when parameter suggestions cannot be computed."""


class SuggestionService:
    def __init__(self, projects_root: Path) -> None:
        self._projects_root = projects_root

    def suggest_params(
        self,
        *,
        video_path: str,
        project: str,
        fps: int,
        max_frames: int = 20,
        timeout_s: int = 30,
    ) -> SuggestionResult:
        """Compute BMP/OpenCV parameters from sampled video frames.

        Extracts frames into a temporary preview folder, derives simple
        heuristics (Otsu threshold, edge density), and returns suggested
        parameters plus aggregate stats. Temporary frames are cleaned up.
        """
        sample_dir = self._prepare_sample_dir(project)
        self._extract_frames(
            video_path=video_path,
            sample_dir=sample_dir,
            fps=fps,
            max_frames=max_frames,
            timeout_s=timeout_s,
        )
        frames = sorted(sample_dir.glob("frame_*.png"))
        if not frames:
            raise SuggestionError("no sample frames")

        stats = self._compute_stats(frames)
        self._cleanup_frames(frames)
        params = self._compute_params(stats)

        return SuggestionResult(params=params, stats=stats)

    def _prepare_sample_dir(self, project: str) -> Path:
        sample_dir = self._projects_root / project / "preview" / "_suggest"
        try:
            sample_dir.mkdir(parents=True, exist_ok=True)
            for path in sample_dir.glob("frame_*.png"):
                try:
                    path.unlink()
                except Exception:
                    pass
        except Exception as exc:
            raise SuggestionError(f"prepare failed: {exc}") from exc
        return sample_dir

    def _extract_frames(
        self,
        *,
        video_path: str,
        sample_dir: Path,
        fps: int,
        max_frames: int,
        timeout_s: int,
    ) -> None:
        out_pattern = sample_dir / "frame_%04d.png"
        cmd = [
            str(FFMPEG_PATH),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"fps={int(fps)}",
            "-frames:v",
            str(int(max_frames)),
            str(out_pattern),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=timeout_s)
        except Exception as exc:
            raise SuggestionError(f"ffmpeg failed: {exc}") from exc

    def _compute_stats(self, frames: list[Path]) -> SuggestionStats:
        edge_densities: list[float] = []
        medians: list[float] = []
        stds: list[float] = []
        otsu_values: list[float] = []

        for path in frames:
            img = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            medians.append(float(np.median(gray)))
            stds.append(float(np.std(gray)))

            otsu_thr, _ = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
            otsu_values.append(float(otsu_thr))

            edges = cv2.Canny(gray, 50, 150)
            edge_density = float(np.mean(edges > 0))
            edge_densities.append(edge_density)

        if not edge_densities:
            raise SuggestionError("no readable frames")

        return SuggestionStats(
            frames=len(frames),
            median=float(np.median(medians)),
            std=float(np.median(stds)),
            edge=float(np.median(edge_densities)),
            otsu=float(np.median(otsu_values)),
        )

    def _compute_params(self, stats: SuggestionStats) -> SuggestedParams:
        threshold_pct = int(round((stats.otsu / 255.0) * 100.0))
        threshold_pct = max(0, min(100, threshold_pct))

        c1 = int(max(1, round(0.66 * stats.median)))
        c2 = int(max(c1 + 1, round(1.33 * stats.median)))
        c1 = max(20, c1)
        c2 = max(60, c2)
        c1 = min(1000, c1)
        c2 = min(1000, c2)

        if stats.edge > 0.12 or stats.std > 60:
            blur_ksize = 5
        else:
            blur_ksize = 3

        if stats.edge > 0.2:
            min_poly_len = 10
        elif stats.edge > 0.1:
            min_poly_len = 8
        elif stats.edge > 0.05:
            min_poly_len = 6
        else:
            min_poly_len = 5

        thinning = stats.edge < 0.05
        simplify_eps = 0.8
        kpps = 60
        ppf_ratio = 1.6
        max_points_per_frame = 12000
        skeleton_mode = True

        return SuggestedParams(
            threshold=threshold_pct,
            thinning=thinning,
            canny1=c1,
            canny2=c2,
            blur_ksize=blur_ksize,
            skeleton_mode=skeleton_mode,
            simplify_eps=simplify_eps,
            min_poly_len=min_poly_len,
            kpps=kpps,
            ppf_ratio=ppf_ratio,
            max_points_per_frame=max_points_per_frame,
        )

    def _cleanup_frames(self, frames: list[Path]) -> None:
        for path in frames:
            try:
                path.unlink()
            except Exception:
                pass
