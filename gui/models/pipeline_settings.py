from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GeneralSettings:
    video_path: str
    project: str
    fps: int
    max_frames: Optional[int]


@dataclass(frozen=True)
class BitmapSettings:
    threshold: int
    thinning: bool
    max_frames: Optional[int]


@dataclass(frozen=True)
class ArcadeOpenCVSettings:
    sample_color: bool
    canny1: int
    canny2: int
    blur_ksize: int
    skeleton_mode: bool
    simplify_eps: float
    min_poly_len: int


@dataclass(frozen=True)
class ArcadeOutputSettings:
    kpps: int
    ppf_ratio: float
    max_points_per_frame: Optional[int]
    fill_ratio: float
    invert_y: bool


@dataclass(frozen=True)
class IldaClassicSettings:
    fit_axis: str
    fill_ratio: float
    min_rel_size: float


@dataclass(frozen=True)
class IldaSettings:
    mode: str
    classic: IldaClassicSettings
    arcade_opencv: ArcadeOpenCVSettings
    arcade_output: ArcadeOutputSettings
    swap_rb: bool


@dataclass(frozen=True)
class PreviewSettings:
    palette: str


@dataclass(frozen=True)
class PipelineSettings:
    general: GeneralSettings
    bitmap: BitmapSettings
    ilda: IldaSettings
    preview: PreviewSettings
