from __future__ import annotations

from typing import Optional

from gui.models.pipeline_settings import (
    ArcadeOpenCVSettings,
    ArcadeOutputSettings,
    GeneralSettings,
    IldaClassicSettings,
    IldaSettings,
    PipelineSettings,
)
from gui.pipeline_controller import PipelineController


class PipelineService:
    def __init__(self, controller: PipelineController) -> None:
        self._controller = controller

    def start_ffmpeg(self, general: GeneralSettings) -> None:
        self._controller.start_ffmpeg(general.video_path, general.project, general.fps)

    def start_bitmap(self, general: GeneralSettings, threshold: int, thinning: bool) -> None:
        self._controller.start_bitmap(general.project, threshold, thinning, general.max_frames)

    def start_potrace(self, project: str) -> None:
        self._controller.start_potrace(project)

    def start_ilda_export(self, project: str, ilda_classic: IldaClassicSettings, mode: str) -> None:
        self._controller.start_ilda(
            project,
            ilda_mode=mode,
            fit_axis=ilda_classic.fit_axis,
            fill_ratio=ilda_classic.fill_ratio,
            min_rel_size=ilda_classic.min_rel_size,
        )

    def start_arcade_reexport(self, general: GeneralSettings, ilda: IldaSettings) -> None:
        arcade_params = self._build_arcade_params(ilda.arcade_opencv, ilda.arcade_output)
        self._controller.start_arcade_lines(
            general.project,
            fps=general.fps,
            max_frames=general.max_frames,
            arcade_params=arcade_params,
        )

    def start_full_pipeline(self, settings: PipelineSettings) -> None:
        arcade_params: Optional[dict[str, object]] = None
        if settings.ilda.mode.lower() == "arcade":
            arcade_params = self._build_arcade_params(
                settings.ilda.arcade_opencv,
                settings.ilda.arcade_output,
            )

        self._controller.start_full_pipeline(
            video_path=settings.general.video_path,
            project=settings.general.project,
            fps=settings.general.fps,
            threshold=settings.bitmap.threshold,
            use_thinning=settings.bitmap.thinning,
            max_frames=settings.general.max_frames,
            ilda_mode=settings.ilda.mode,
            fit_axis=settings.ilda.classic.fit_axis,
            fill_ratio=settings.ilda.classic.fill_ratio,
            min_rel_size=settings.ilda.classic.min_rel_size,
            arcade_params=arcade_params,
        )

    @staticmethod
    def _build_arcade_params(
        opencv: ArcadeOpenCVSettings,
        output: ArcadeOutputSettings,
    ) -> dict[str, object]:
        blur_ksize = int(opencv.blur_ksize) | 1
        return {
            "kpps": int(output.kpps),
            "ppf_ratio": float(output.ppf_ratio),
            "max_points_per_frame": output.max_points_per_frame,
            "fill_ratio": float(output.fill_ratio),
            "invert_y": bool(output.invert_y),
            "sample_color": bool(opencv.sample_color),
            "canny1": int(opencv.canny1),
            "canny2": int(opencv.canny2),
            "blur_ksize": blur_ksize,
            "simplify_eps": float(opencv.simplify_eps),
            "min_poly_len": int(opencv.min_poly_len),
        }
