from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.ilda_preview import render_ilda_preview


@dataclass(frozen=True)
class FramePreviewPaths:
    png: Optional[Path] = None
    bmp: Optional[Path] = None
    svg: Optional[Path] = None
    arcade: Optional[Path] = None
    ilda_png: Optional[Path] = None


class PreviewService:
    """Computes which preview files to show, and generates ILDA raster previews."""

    def frame_paths(self, project_root: Path, frame_index_1based: int) -> FramePreviewPaths:
        idx = max(1, int(frame_index_1based))
        png = project_root / "frames" / f"frame_{idx:04d}.png"
        bmp = project_root / "bmp" / f"frame_{idx:04d}.bmp"
        svg = project_root / "svg" / f"frame_{idx:04d}.svg"
        arcade = project_root / "preview" / f"arcade_preview_{idx:04d}.png"

        return FramePreviewPaths(
            png=png if png.exists() else None,
            bmp=bmp if bmp.exists() else None,
            svg=svg if svg.exists() else None,
            arcade=arcade if arcade.exists() else None,
        )

    def ensure_ilda_preview(
        self,
        ilda_path: Path,
        out_png: Path,
        frame_index_0based: int,
        palette_name: str,
    ) -> None:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        render_ilda_preview(
            ilda_path,
            out_png,
            frame_index=max(0, int(frame_index_0based)),
            palette_name=str(palette_name),
        )
