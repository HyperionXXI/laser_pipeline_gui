from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Callable
from gui.pipeline_controller import PipelineController
from gui.services.pipeline_service import PipelineService
from gui.services.suggestion_service import SuggestionError, SuggestionService
from gui.ui.controllers.pipeline_settings_mapper import collect_settings
from gui.ui.controllers.pipeline_ui_actions import PipelineUiActions
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
        projects_root: Path,
        log_fn: Callable[[str], None],
    ) -> None:
        self._general_panel = general_panel
        self._pipeline_panel = pipeline_panel
        self._preview_controller = preview_controller
        self._pipeline_service = pipeline_service
        self._pipeline_controller = pipeline_controller
        self._projects_root = projects_root
        self._suggestion_service = SuggestionService(projects_root)
        self._log = log_fn
        self._last_suggested_mode: str | None = None
        self._last_suggested_project: str | None = None
        self._suggested_params: dict[str, object] = {}
        self._actions = PipelineUiActions(
            general_panel=general_panel,
            pipeline_panel=pipeline_panel,
            preview_controller=preview_controller,
            pipeline_service=pipeline_service,
            pipeline_controller=pipeline_controller,
            log_fn=log_fn,
            set_busy_fn=self.set_busy,
        )

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
        self._general_panel.combo_ilda_mode.setEnabled(run_enabled)
        self._general_panel.btn_apply_mode_suggestion.setEnabled(
            run_enabled
            and (
                self._general_panel.get_suggested_mode_key() is not None
                or self._general_panel.get_suggested_project_name() is not None
                or bool(self._suggested_params)
            )
        )

        self._pipeline_panel.set_busy(busy)

    def on_step_started(self, step_name: str) -> None:
        self._actions.on_step_started(step_name)

    def on_step_finished(self, step_name: str, result: object) -> None:
        self._actions.on_step_finished(step_name, result)

    def on_step_error(self, step_name: str, message: str) -> None:
        self._actions.on_step_error(step_name, message)

    def on_step_progress(self, step_name: str, payload: object) -> None:
        self._actions.on_step_progress(step_name, payload)

    def on_test_click(self) -> None:
        settings = collect_settings(
            general_panel=self._general_panel,
            pipeline_panel=self._pipeline_panel,
            preview_controller=self._preview_controller,
        )

        self._log("=== Current settings ===")
        self._log(f"Video: {settings.general.video_path or '<none>'}")
        self._log(f"Project: {settings.general.project or '<none>'}")
        self._log(f"FPS    : {settings.general.fps}")
        self._log("================================")
        self._suggest_mode(settings.general.video_path)
        self._suggest_project(settings.general.video_path)
        self._suggest_params(settings)

    def on_video_path_changed(self) -> None:
        path = (self._general_panel.edit_video_path.text() or "").strip()
        self._suggest_mode(path)
        self._suggest_project(path)
        self._preview_controller.set_preview_aspect_ratio_from_video(path)

    def on_apply_mode_suggestion(self) -> None:
        suggested = self._general_panel.get_suggested_mode_key()
        if suggested:
            label = self._general_panel.combo_ilda_mode.itemText(
                self._general_panel.combo_ilda_mode.findData(suggested)
            )
            self._log(f"[UI] Applied suggested mode: {label}")
        project_name = self._general_panel.get_suggested_project_name()
        if project_name:
            current = (self._general_panel.edit_project.text() or "").strip()
            if current and current != project_name:
                self._log(
                    f"[UI] Applied suggested project: {project_name} (replaced {current})"
                )
            else:
                self._log(f"[UI] Applied suggested project: {project_name}")
        if self._suggested_params:
            self._apply_suggested_params()
            summary = ", ".join(
                f"{key}={value}" for key, value in self._suggested_params.items()
            )
            self._log(f"[UI] Applied suggested params: {summary}")
        self._general_panel.apply_suggested_mode()

    def on_mode_changed(self) -> None:
        mode_key = str(self._general_panel.combo_ilda_mode.currentData() or "classic")
        mode_label = self._general_panel.combo_ilda_mode.currentText()
        self._pipeline_panel.set_mode_key(mode_key)
        self._log(f"[UI] Mode set to: {mode_label}")

    def on_ffmpeg_click(self) -> None:
        self._actions.on_ffmpeg_click()

    def on_bmp_click(self) -> None:
        self._actions.on_bmp_click()

    def on_arcade_click(self) -> None:
        self._actions.on_arcade_click()

    def on_potrace_click(self) -> None:
        self._actions.on_potrace_click()

    def on_export_ilda_click(self) -> None:
        self._actions.on_export_ilda_click()

    def on_cancel_task(self) -> None:
        self._actions.on_cancel_task()

    def on_execute_all_task(self) -> None:
        self._actions.on_execute_all_task()

    def on_play_click(self) -> None:
        self._actions.on_play_click()

    def on_stop_click(self) -> None:
        self._actions.on_stop_click()

    def on_play_speed_changed(self) -> None:
        self._actions.on_play_speed_changed()

    def on_play_range_changed(self) -> None:
        self._actions.on_play_range_changed()

    def on_preview_frame(self) -> None:
        self._actions.on_preview_frame()

    def _suggest_mode(self, video_path: str) -> None:
        if not video_path:
            self._general_panel.clear_mode_suggestion()
            if self._last_suggested_mode is not None:
                self._log("[UI] Suggested mode cleared (no video selected).")
            self._last_suggested_mode = None
            return
        name = str(video_path).lower()
        if "arcade" in name:
            suggested = "arcade"
            reason = "filename"
        else:
            suggested = "classic"
            reason = "filename"
        self._general_panel.set_mode_suggestion(suggested, reason)
        current_mode = str(self._general_panel.combo_ilda_mode.currentData() or "")
        if suggested != self._last_suggested_mode:
            label = self._general_panel.combo_ilda_mode.itemText(
                self._general_panel.combo_ilda_mode.findData(suggested)
            )
            if suggested != current_mode:
                self._log(f"[UI] Suggested mode: {label} ({reason})")
            self._last_suggested_mode = suggested

    def _suggest_project(self, video_path: str) -> None:
        if not video_path:
            self._general_panel.clear_project_suggestion()
            if self._last_suggested_project is not None:
                self._log("[UI] Suggested project cleared (no video selected).")
            self._last_suggested_project = None
            return
        current_text = (self._general_panel.edit_project.text() or "").strip()
        stem = Path(video_path).stem
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").lower()
        if not cleaned:
            self._general_panel.clear_project_suggestion()
            return
        if len(cleaned) > 50:
            cleaned = cleaned[:50]
        if current_text and current_text != "project_demo":
            last_auto = self._last_suggested_project or ""
            if current_text != cleaned and current_text != last_auto:
                self._general_panel.clear_project_suggestion()
                self._last_suggested_project = None
                return
        suggested = self._dedupe_project_name(cleaned)
        self._general_panel.set_project_suggestion(suggested)
        current = (self._general_panel.edit_project.text() or "").strip().lower()
        if suggested != self._last_suggested_project and suggested != current:
            reason = "filename"
            if suggested != cleaned:
                reason = "filename+dedup"
            self._log(f"[UI] Suggested project: {suggested} ({reason})")
            self._last_suggested_project = suggested

    def _dedupe_project_name(self, base: str) -> str:
        candidate = base
        suffix = 2
        while (self._projects_root / candidate).exists():
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _clear_param_suggestions(self, reason: str) -> None:
        if self._suggested_params:
            self._suggested_params = {}
            self._log(f"[UI] Suggested params cleared ({reason}).")
        if (
            self._general_panel.get_suggested_mode_key() is None
            and self._general_panel.get_suggested_project_name() is None
        ):
            self._general_panel.btn_apply_mode_suggestion.setEnabled(False)

    def _suggest_params(self, settings: PipelineSettings) -> None:
        video_path = settings.general.video_path
        project = settings.general.project
        if not video_path or not project:
            self._clear_param_suggestions("missing video/project")
            return
        try:
            result = self._suggestion_service.suggest_params(
                video_path=video_path,
                project=project,
                fps=settings.general.fps,
            )
        except SuggestionError as exc:
            self._clear_param_suggestions(str(exc))
            return

        stats = result.stats
        self._log(
            "[UI] Suggest stats: "
            f"frames={stats.frames}, "
            f"median={stats.median:.1f}, "
            f"std={stats.std:.1f}, "
            f"edge={stats.edge:.3f}, "
            f"otsu={stats.otsu:.1f}"
        )

        self._suggested_params = asdict(result.params)
        threshold_pct = int(result.params.threshold)
        thinning = bool(result.params.thinning)
        c1 = int(result.params.canny1)
        c2 = int(result.params.canny2)
        blur_ksize = int(result.params.blur_ksize)
        simplify_eps = float(result.params.simplify_eps)
        min_poly_len = int(result.params.min_poly_len)
        skeleton_mode = bool(result.params.skeleton_mode)
        kpps = int(result.params.kpps)
        ppf_ratio = float(result.params.ppf_ratio)
        max_points = int(result.params.max_points_per_frame)
        mode_key = str(self._general_panel.combo_ilda_mode.currentData() or "classic")
        bmp_summary = f"threshold={threshold_pct}, thinning={thinning}"
        arcade_summary = (
            f"canny1={c1}, canny2={c2}, blur_ksize={blur_ksize}, "
            f"simplify_eps={simplify_eps}, min_poly_len={min_poly_len}, "
            f"skeleton={skeleton_mode}, kpps={kpps}, "
            f"ppf_ratio={ppf_ratio}, max_points={max_points}"
        )
        if mode_key.lower() == "arcade":
            self._log(f"[UI] Suggested params (arcade): {arcade_summary}")
            self._log(
                f"[UI] Suggested params (bmp, ignored in arcade): {bmp_summary}"
            )
        else:
            self._log(f"[UI] Suggested params (bmp): {bmp_summary}")
            self._log(
                f"[UI] Suggested params (arcade, ignored in classic): {arcade_summary}"
            )
        self._general_panel.btn_apply_mode_suggestion.setEnabled(True)

    def _apply_suggested_params(self) -> None:
        params = self._suggested_params
        if not params:
            return
        self._pipeline_panel.spin_bmp_threshold.setValue(int(params["threshold"]))
        self._pipeline_panel.check_bmp_thinning.setChecked(bool(params["thinning"]))
        self._pipeline_panel.spin_arcade_canny1.setValue(int(params["canny1"]))
        self._pipeline_panel.spin_arcade_canny2.setValue(int(params["canny2"]))
        self._pipeline_panel.spin_arcade_blur_ksize.setValue(int(params["blur_ksize"]))
        self._pipeline_panel.check_arcade_skeleton.setChecked(
            bool(params["skeleton_mode"])
        )
        self._pipeline_panel.spin_arcade_simplify_eps.setValue(
            float(params["simplify_eps"])
        )
        self._pipeline_panel.spin_arcade_min_poly_len.setValue(
            int(params["min_poly_len"])
        )
        self._pipeline_panel.spin_arcade_kpps.setValue(int(params["kpps"]))
        self._pipeline_panel.spin_arcade_ppf_ratio.setValue(
            float(params["ppf_ratio"])
        )
        self._pipeline_panel.spin_arcade_max_points.setValue(
            int(params["max_points_per_frame"])
        )
