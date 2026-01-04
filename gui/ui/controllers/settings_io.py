from __future__ import annotations

from typing import Any, Mapping

from gui.ui.controllers.preview_controller import PreviewController
from gui.ui.panels.general_panel import GeneralPanel
from gui.ui.panels.pipeline_panel import PipelinePanel


def collect_ui_state(
    *,
    general_panel: GeneralPanel,
    pipeline_panel: PipelinePanel,
    preview_controller: PreviewController,
) -> dict[str, Any]:
    return {
        "general": {
            "video_path": (general_panel.edit_video_path.text() or "").strip(),
            "project": (general_panel.edit_project.text() or "").strip(),
            "fps": int(general_panel.spin_fps.value()),
            "max_frames": int(general_panel.spin_max_frames.value()),
            "ilda_mode": _get_combo_value(general_panel.combo_ilda_mode),
        },
        "pipeline": {
            "bmp_threshold": int(pipeline_panel.spin_bmp_threshold.value()),
            "bmp_thinning": bool(pipeline_panel.check_bmp_thinning.isChecked()),
            "arcade_sample_color": bool(
                pipeline_panel.check_arcade_sample_color.isChecked()
            ),
            "arcade_canny1": int(pipeline_panel.spin_arcade_canny1.value()),
            "arcade_canny2": int(pipeline_panel.spin_arcade_canny2.value()),
            "arcade_blur_ksize": int(pipeline_panel.spin_arcade_blur_ksize.value()),
            "arcade_skeleton": bool(
                pipeline_panel.check_arcade_skeleton.isChecked()
            ),
            "arcade_simplify_eps": float(
                pipeline_panel.spin_arcade_simplify_eps.value()
            ),
            "arcade_min_poly_len": int(
                pipeline_panel.spin_arcade_min_poly_len.value()
            ),
            "arcade_kpps": int(pipeline_panel.spin_arcade_kpps.value()),
            "arcade_ppf_ratio": float(
                pipeline_panel.spin_arcade_ppf_ratio.value()
            ),
            "arcade_max_points": int(
                pipeline_panel.spin_arcade_max_points.value()
            ),
            "arcade_fill_ratio": float(
                pipeline_panel.spin_arcade_fill_ratio.value()
            ),
            "arcade_invert_y": bool(
                pipeline_panel.check_arcade_invert_y.isChecked()
            ),
            "ilda_fit_axis": _get_combo_value(
                pipeline_panel.combo_ilda_fit_axis
            ),
            "ilda_fill_ratio": float(
                pipeline_panel.spin_ilda_fill_ratio.value()
            ),
            "ilda_min_rel_size": float(
                pipeline_panel.spin_ilda_min_rel_size.value()
            ),
            "ilda_swap_rb": bool(
                pipeline_panel.check_ilda_swap_rb.isChecked()
            ),
            "arcade_advanced": bool(
                pipeline_panel.check_arcade_advanced.isChecked()
            ),
            "output_toggle": bool(pipeline_panel.output_toggle.isChecked()),
        },
        "preview": {
            "palette": _get_combo_value(pipeline_panel.combo_ilda_palette),
            "show_grid": bool(pipeline_panel.check_ilda_grid.isChecked()),
            "fit_height": bool(pipeline_panel.check_ilda_fit_height.isChecked()),
        },
        "playback": {
            "frame": int(pipeline_panel.spin_frame.value()),
            "play_start": int(pipeline_panel.spin_play_start.value()),
            "play_end": int(pipeline_panel.spin_play_end.value()),
            "play_speed": float(pipeline_panel.spin_play_speed.value()),
            "loop": bool(pipeline_panel.check_loop.isChecked()),
        },
        "meta": {
            "schema": 1,
            "palette_resolved": preview_controller.get_palette_name(),
        },
    }


def apply_ui_state(
    state: Mapping[str, Any],
    *,
    general_panel: GeneralPanel,
    pipeline_panel: PipelinePanel,
    preview_controller: PreviewController,
    ignore_project_name: bool = False,
) -> None:
    if not isinstance(state, Mapping):
        return

    general = state.get("general") or {}
    pipeline = state.get("pipeline") or {}
    preview = state.get("preview") or {}
    playback = state.get("playback") or {}

    video_path = _as_str(general.get("video_path"))
    if video_path:
        general_panel.edit_video_path.setText(video_path)

    project = _as_str(general.get("project"))
    if project and not ignore_project_name:
        general_panel.edit_project.setText(project)

    fps = _as_int(general.get("fps"))
    if fps is not None:
        general_panel.spin_fps.setValue(fps)

    max_frames = _as_int(general.get("max_frames"))
    if max_frames is not None:
        general_panel.spin_max_frames.setValue(max_frames)

    _set_combo_value(general_panel.combo_ilda_mode, general.get("ilda_mode"))

    _set_spin_value(
        pipeline_panel.spin_bmp_threshold, _as_int(pipeline.get("bmp_threshold"))
    )
    _set_check_value(
        pipeline_panel.check_bmp_thinning, _as_bool(pipeline.get("bmp_thinning"))
    )
    _set_check_value(
        pipeline_panel.check_arcade_sample_color,
        _as_bool(pipeline.get("arcade_sample_color")),
    )
    _set_spin_value(
        pipeline_panel.spin_arcade_canny1, _as_int(pipeline.get("arcade_canny1"))
    )
    _set_spin_value(
        pipeline_panel.spin_arcade_canny2, _as_int(pipeline.get("arcade_canny2"))
    )
    _set_spin_value(
        pipeline_panel.spin_arcade_blur_ksize,
        _as_int(pipeline.get("arcade_blur_ksize")),
    )
    _set_check_value(
        pipeline_panel.check_arcade_skeleton,
        _as_bool(pipeline.get("arcade_skeleton")),
    )
    _set_double_value(
        pipeline_panel.spin_arcade_simplify_eps,
        _as_float(pipeline.get("arcade_simplify_eps")),
    )
    _set_spin_value(
        pipeline_panel.spin_arcade_min_poly_len,
        _as_int(pipeline.get("arcade_min_poly_len")),
    )
    _set_spin_value(
        pipeline_panel.spin_arcade_kpps, _as_int(pipeline.get("arcade_kpps"))
    )
    _set_double_value(
        pipeline_panel.spin_arcade_ppf_ratio,
        _as_float(pipeline.get("arcade_ppf_ratio")),
    )
    _set_spin_value(
        pipeline_panel.spin_arcade_max_points,
        _as_int(pipeline.get("arcade_max_points")),
    )
    _set_double_value(
        pipeline_panel.spin_arcade_fill_ratio,
        _as_float(pipeline.get("arcade_fill_ratio")),
    )
    _set_check_value(
        pipeline_panel.check_arcade_invert_y,
        _as_bool(pipeline.get("arcade_invert_y")),
    )
    _set_combo_value(pipeline_panel.combo_ilda_fit_axis, pipeline.get("ilda_fit_axis"))
    _set_double_value(
        pipeline_panel.spin_ilda_fill_ratio,
        _as_float(pipeline.get("ilda_fill_ratio")),
    )
    _set_double_value(
        pipeline_panel.spin_ilda_min_rel_size,
        _as_float(pipeline.get("ilda_min_rel_size")),
    )
    _set_check_value(
        pipeline_panel.check_ilda_swap_rb,
        _as_bool(pipeline.get("ilda_swap_rb")),
    )
    _set_check_value(
        pipeline_panel.check_arcade_advanced,
        _as_bool(pipeline.get("arcade_advanced")),
    )
    _set_check_value(
        pipeline_panel.output_toggle,
        _as_bool(pipeline.get("output_toggle")),
    )

    _set_combo_value(pipeline_panel.combo_ilda_palette, preview.get("palette"))
    _set_check_value(
        pipeline_panel.check_ilda_grid, _as_bool(preview.get("show_grid"))
    )
    _set_check_value(
        pipeline_panel.check_ilda_fit_height, _as_bool(preview.get("fit_height"))
    )

    _set_spin_value(
        pipeline_panel.spin_frame, _as_int(playback.get("frame"))
    )
    _set_spin_value(
        pipeline_panel.spin_play_start, _as_int(playback.get("play_start"))
    )
    _set_spin_value(
        pipeline_panel.spin_play_end, _as_int(playback.get("play_end"))
    )
    _set_double_value(
        pipeline_panel.spin_play_speed, _as_float(playback.get("play_speed"))
    )
    _set_check_value(
        pipeline_panel.check_loop, _as_bool(playback.get("loop"))
    )

    _ = preview_controller


def _get_combo_value(combo: Any) -> str:
    try:
        data = combo.currentData()
        if isinstance(data, str) and data.strip():
            return data.strip()
        text = combo.currentText()
        if isinstance(text, str) and text.strip():
            return text.strip()
    except Exception:
        pass
    return ""


def _set_combo_value(combo: Any, value: Any) -> None:
    if value is None:
        return
    try:
        idx = combo.findData(value)
        if idx < 0 and isinstance(value, str):
            idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    except Exception:
        pass


def _set_spin_value(spin: Any, value: int | None) -> None:
    if value is None:
        return
    try:
        spin.setValue(int(value))
    except Exception:
        pass


def _set_double_value(spin: Any, value: float | None) -> None:
    if value is None:
        return
    try:
        spin.setValue(float(value))
    except Exception:
        pass


def _set_check_value(check: Any, value: bool | None) -> None:
    if value is None:
        return
    try:
        check.setChecked(bool(value))
    except Exception:
        pass


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on"):
            return True
        if lowered in ("0", "false", "no", "off"):
            return False
    return None


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
