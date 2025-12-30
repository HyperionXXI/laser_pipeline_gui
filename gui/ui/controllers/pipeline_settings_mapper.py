from __future__ import annotations

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
from gui.ui.controllers.preview_controller import PreviewController
from gui.ui.panels.general_panel import GeneralPanel
from gui.ui.panels.pipeline_panel import PipelinePanel


def collect_settings(
    *,
    general_panel: GeneralPanel,
    pipeline_panel: PipelinePanel,
    preview_controller: PreviewController,
) -> PipelineSettings:
    max_frames_val = general_panel.spin_max_frames.value()
    max_frames = max_frames_val if max_frames_val > 0 else None
    mode_key = str(general_panel.combo_ilda_mode.currentData() or "classic")

    general = GeneralSettings(
        video_path=(general_panel.edit_video_path.text() or "").strip(),
        project=(general_panel.edit_project.text() or "").strip(),
        fps=int(general_panel.spin_fps.value()),
        max_frames=max_frames,
    )
    bitmap = BitmapSettings(
        threshold=int(pipeline_panel.spin_bmp_threshold.value()),
        thinning=bool(pipeline_panel.check_bmp_thinning.isChecked()),
        max_frames=max_frames,
    )
    arcade_opencv = ArcadeOpenCVSettings(
        sample_color=bool(pipeline_panel.check_arcade_sample_color.isChecked()),
        canny1=int(pipeline_panel.spin_arcade_canny1.value()),
        canny2=int(pipeline_panel.spin_arcade_canny2.value()),
        blur_ksize=int(pipeline_panel.spin_arcade_blur_ksize.value()),
        skeleton_mode=bool(pipeline_panel.check_arcade_skeleton.isChecked()),
        simplify_eps=float(pipeline_panel.spin_arcade_simplify_eps.value()),
        min_poly_len=int(pipeline_panel.spin_arcade_min_poly_len.value()),
    )
    arcade_output = ArcadeOutputSettings(
        kpps=int(pipeline_panel.spin_arcade_kpps.value()),
        ppf_ratio=float(pipeline_panel.spin_arcade_ppf_ratio.value()),
        max_points_per_frame=(
            None
            if pipeline_panel.spin_arcade_max_points.value() == 0
            else int(pipeline_panel.spin_arcade_max_points.value())
        ),
        fill_ratio=float(pipeline_panel.spin_arcade_fill_ratio.value()),
        invert_y=bool(pipeline_panel.check_arcade_invert_y.isChecked()),
    )
    ilda_classic = IldaClassicSettings(
        fit_axis=str(pipeline_panel.combo_ilda_fit_axis.currentData() or "max"),
        fill_ratio=float(pipeline_panel.spin_ilda_fill_ratio.value()),
        min_rel_size=float(pipeline_panel.spin_ilda_min_rel_size.value()),
    )
    ilda = IldaSettings(
        mode=mode_key,
        classic=ilda_classic,
        arcade_opencv=arcade_opencv,
        arcade_output=arcade_output,
        swap_rb=bool(pipeline_panel.check_ilda_swap_rb.isChecked()),
    )
    preview = PreviewSettings(palette=str(preview_controller.get_palette_name()))
    return PipelineSettings(
        general=general,
        bitmap=bitmap,
        ilda=ilda,
        preview=preview,
    )
