from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuggestionStats:
    frames: int
    median: float
    std: float
    edge: float
    otsu: float


@dataclass(frozen=True)
class SuggestedParams:
    threshold: int
    thinning: bool
    canny1: int
    canny2: int
    blur_ksize: int
    skeleton_mode: bool
    simplify_eps: float
    min_poly_len: int
    kpps: int
    ppf_ratio: float
    max_points_per_frame: int


@dataclass(frozen=True)
class SuggestionResult:
    params: SuggestedParams
    stats: SuggestionStats
