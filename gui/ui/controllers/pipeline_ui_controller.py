from __future__ import annotations

from typing import Callable

from core.pipeline.base import FrameProgress
from gui.models.pipeline_settings import (
    ArcadeOpenCVSettings,
    ArcadeOutputSettings,
    BitmapSettings,
    GeneralSettings,
    IldaClassicSettings,
    IldaSettings,
    PipelineSettings,
    PreviewSettings,
)
from gui.pipeline_controller import PipelineController
from gui.services.pipeline_service import PipelineService
from gui.ui.controllers.preview_controller import PreviewController
from gui.ui.panels.general_panel import GeneralPanel
from gui.ui.panels.pipeline_panel import PipelinePanel


class PipelineUiController:
    def __init__(
        self,
        *,
        general_panel: GeneralPanel,
        pipeline_panel: PipelinePanel,
        preview_controller: PreviewController,
        pipeline_service: PipelineService,
        pipeline_controller: PipelineController,
        log_fn: Callable[[str], None],
    ) -> None:
        self._general_panel = general_panel
        self._pipeline_panel = pipeline_panel
        self._preview_controller = preview_controller
        self._pipeline_service = pipeline_service
        self._pipeline_controller = pipeline_controller
        self._log = log_fn

    def set_busy(self, busy: bool) -> None:
        run_enabled = not busy

        if busy:
            self._preview_controller.stop_play()

        self._general_panel.btn_test.setEnabled(run_enabled)
        self._general_panel.btn_browse_video.setEnabled(run_enabled)
        self._preview_controller.set_palette_enabled(run_enabled)

        self._general_panel.edit_video_path.setEnabled(run_enabled)
        self._general_panel.edit_project.setEnabled(run_enabled)
        self._general_panel.spin_fps.setEnabled(run_enabled)
        self._general_panel.spin_max_frames.setEnabled(run_enabled)

        self._pipeline_panel.set_busy(busy)

    def on_step_started(self, step_name: str) -> None:
        self.set_busy(True)
        self._log(f"[{step_name}] starting...")
        if step_name == "arcade_lines":
            self._preview_controller.set_ilda_title_live(True)

    def on_step_finished(self, step_name: str, result: object) -> None:
        self.set_busy(False)
        msg = getattr(result, "message", "")
        if msg:
            self._log(f"[{step_name}] {msg}")

        if step_name in ("arcade_lines", "ilda", "full_pipeline"):
            self._preview_controller.set_ilda_title_live(False)

        if step_name in ("arcade_lines", "ilda", "full_pipeline") and getattr(
            result, "success", False
        ):
            project = (self._general_panel.edit_project.text() or "").strip()
            if project:
                self._preview_controller.update_ilda_preview(project)

    def on_step_error(self, step_name: str, message: str) -> None:
        self._pipeline_panel.progress_bar.setRange(0, 100)
        self._pipeline_panel.progress_bar.setValue(100)
        self.set_busy(False)
        self._log(f"[{step_name}] ERREUR : {message}")
        if step_name in ("arcade_lines", "ilda", "full_pipeline"):
            self._preview_controller.set_ilda_title_live(False)

    def on_step_progress(self, step_name: str, payload: object) -> None:
        if not isinstance(payload, FrameProgress):
            return
        frame_progress: FrameProgress = payload

        if frame_progress.total_frames is not None and frame_progress.total_frames > 0:
            self._pipeline_panel.progress_bar.setRange(0, 100)

            total = int(frame_progress.total_frames)
            idx = int(frame_progress.frame_index)

            if idx < 0:
                idx = 0

            if idx < total:
                processed = idx + 1
            else:
                processed = idx

            if processed > total:
                processed = total

            pct = int(processed * 100 / total)
            self._pipeline_panel.progress_bar.setValue(pct)
        else:
            self._pipeline_panel.progress_bar.setRange(0, 0)

        if not frame_progress.frame_path:
            return
        self._preview_controller.show_progress_frame(
            step_name,
            str(frame_progress.frame_path),
        )

    def on_test_click(self) -> None:
        settings = self._collect_settings()

        self._log("=== Current settings ===")
        self._log(f"Video: {settings.general.video_path or '<none>'}")
        self._log(f"Project: {settings.general.project or '<none>'}")
        self._log(f"FPS    : {settings.general.fps}")
        self._log("================================")

    def on_ffmpeg_click(self) -> None:
        settings = self._collect_settings()
        if not settings.general.video_path:
            self._log("FFmpeg error: no video file selected.")
            return
        if not settings.general.project:
            self._log("FFmpeg error: project name is empty.")
            return

        self._log("[FFmpeg] Computing frame extraction...")
        self._pipeline_service.start_ffmpeg(settings.general)

    def on_bmp_click(self) -> None:
        settings = self._collect_settings()
        if not settings.general.project:
            self._log("BMP error: project name is empty.")
            return

        threshold = settings.bitmap.threshold
        thinning = settings.bitmap.thinning
        max_frames = settings.general.max_frames

        self._log(
            f"[BMP] Computing PNG -> BMP (threshold={threshold}%, "
            f"thinning={thinning}, max_frames={max_frames or 'all'})..."
        )
        self._pipeline_service.start_bitmap(settings.general, threshold, thinning)

    def on_arcade_click(self) -> None:
        settings = self._collect_settings()
        if not settings.general.project:
            self._log("Arcade error: project name is empty.")
            return
        mode_key = settings.ilda.mode
        if str(mode_key).lower() != "arcade":
            self._log("Arcade error: current profile is not arcade.")
            return
        mode_label = self._pipeline_panel.combo_ilda_mode.currentText()
        self._log(f"[Arcade] Computing ILDA from PNG frames (profile={mode_label})...")
        self._pipeline_service.start_arcade_reexport(settings.general, settings.ilda)

    def on_potrace_click(self) -> None:
        project = (self._general_panel.edit_project.text() or "").strip()
        if not project:
            self._log("Potrace error: project name is empty.")
            return
        self._log(f"[Potrace] Computing BMP -> SVG for '{project}'...")
        self._pipeline_service.start_potrace(project)

    def on_export_ilda_click(self) -> None:
        settings = self._collect_settings()
        if not settings.general.project:
            self._log("ILDA error: project name is empty.")
            return

        mode_key = settings.ilda.mode
        mode_label = self._pipeline_panel.combo_ilda_mode.currentText()
        if str(mode_key).lower() == "arcade":
            self._log(
                f"[Arcade] Computing ILDA from PNG frames (profile={mode_label})..."
            )
            self._pipeline_service.start_arcade_reexport(settings.general, settings.ilda)
            return

        self._log(f"[ILDA] Computing ILDA (profile={mode_label})...")
        self._pipeline_service.start_ilda_export(
            settings.general.project,
            settings.ilda.classic,
            mode_key,
        )

    def on_cancel_task(self) -> None:
        if not self._pipeline_panel.btn_cancel.isEnabled():
            return
        self._pipeline_panel.btn_cancel.setEnabled(False)
        self._pipeline_panel.btn_cancel.setText("Canceling...")
        self._log("[UI] Cancel requested... (waiting for step to stop)")
        self._pipeline_controller.cancel_current_step()

    def on_execute_all_task(self) -> None:
        settings = self._collect_settings()
        if not settings.general.video_path:
            self._log("Error: no video file selected.")
            return
        if not settings.general.project:
            self._log("Error: project name is empty.")
            return

        threshold = settings.bitmap.threshold
        thinning = settings.bitmap.thinning
        max_frames = settings.general.max_frames
        mode_key = settings.ilda.mode
        mode_label = self._pipeline_panel.combo_ilda_mode.currentText()

        self._log("Computing full pipeline...")
        self._log(f"  Video   : {settings.general.video_path}")
        self._log(f"  Project : {settings.general.project}")
        self._log(f"  FPS     : {settings.general.fps}")
        self._log(
            f"  Bitmap  : threshold={threshold}%, thinning={thinning}, "
            f"max_frames={max_frames or 'all'}"
        )
        self._log(f"  ILDA    : profile={mode_label} ({mode_key})")

        self._pipeline_service.start_full_pipeline(settings)

    def on_play_click(self) -> None:
        self._preview_controller.toggle_play()

    def on_stop_click(self) -> None:
        self._preview_controller.stop_play()

    def on_preview_frame(self) -> None:
        self._preview_controller.show_current_frame()

    def _collect_settings(self) -> PipelineSettings:
        max_frames_val = self._general_panel.spin_max_frames.value()
        max_frames = max_frames_val if max_frames_val > 0 else None
        mode_key = str(self._pipeline_panel.combo_ilda_mode.currentData() or "classic")

        general = GeneralSettings(
            video_path=(self._general_panel.edit_video_path.text() or "").strip(),
            project=(self._general_panel.edit_project.text() or "").strip(),
            fps=int(self._general_panel.spin_fps.value()),
            max_frames=max_frames,
        )
        bitmap = BitmapSettings(
            threshold=int(self._pipeline_panel.spin_bmp_threshold.value()),
            thinning=bool(self._pipeline_panel.check_bmp_thinning.isChecked()),
            max_frames=max_frames,
        )
        arcade_opencv = ArcadeOpenCVSettings(
            sample_color=bool(
                self._pipeline_panel.check_arcade_sample_color.isChecked()
            ),
            canny1=int(self._pipeline_panel.spin_arcade_canny1.value()),
            canny2=int(self._pipeline_panel.spin_arcade_canny2.value()),
            blur_ksize=int(self._pipeline_panel.spin_arcade_blur_ksize.value()),
            simplify_eps=float(self._pipeline_panel.spin_arcade_simplify_eps.value()),
            min_poly_len=int(self._pipeline_panel.spin_arcade_min_poly_len.value()),
        )
        arcade_output = ArcadeOutputSettings(
            kpps=int(self._pipeline_panel.spin_arcade_kpps.value()),
            ppf_ratio=float(self._pipeline_panel.spin_arcade_ppf_ratio.value()),
            max_points_per_frame=(
                None
                if self._pipeline_panel.spin_arcade_max_points.value() == 0
                else int(self._pipeline_panel.spin_arcade_max_points.value())
            ),
            fill_ratio=float(self._pipeline_panel.spin_arcade_fill_ratio.value()),
            invert_y=bool(self._pipeline_panel.check_arcade_invert_y.isChecked()),
        )
        ilda_classic = IldaClassicSettings(
            fit_axis=str(self._pipeline_panel.combo_ilda_fit_axis.currentData() or "max"),
            fill_ratio=float(self._pipeline_panel.spin_ilda_fill_ratio.value()),
            min_rel_size=float(self._pipeline_panel.spin_ilda_min_rel_size.value()),
        )
        ilda = IldaSettings(
            mode=mode_key,
            classic=ilda_classic,
            arcade_opencv=arcade_opencv,
            arcade_output=arcade_output,
        )
        preview = PreviewSettings(palette=str(self._preview_controller.get_palette_name()))
        return PipelineSettings(
            general=general,
            bitmap=bitmap,
            ilda=ilda,
            preview=preview,
        )
