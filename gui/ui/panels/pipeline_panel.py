from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QStackedLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.preview_widgets import RasterPreview, SvgPreview


class PipelinePanel(QGroupBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Video pipeline -> ILDA", parent)

        self._ui_busy = False

        pipe_layout = QVBoxLayout(self)

        # Frame row + preview button
        row_frame = QHBoxLayout()
        row_frame.addWidget(QLabel("Frame:"))
        self.spin_frame = QSpinBox()
        self.spin_frame.setRange(1, 999999)
        self.spin_frame.setValue(1)
        row_frame.addWidget(self.spin_frame)

        self.btn_preview_frame = QPushButton("Preview frame")
        row_frame.addWidget(self.btn_preview_frame)
        row_frame.addStretch()
        pipe_layout.addLayout(row_frame)

        # Task status row
        row_task = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        row_task.addWidget(self.progress_bar)

        self.btn_run_all = QPushButton("Run all 4 pipeline steps")
        self.btn_run_all.setObjectName("")
        row_task.addWidget(self.btn_run_all)

        self.btn_cancel = QPushButton("Cancel current task")
        self.btn_cancel.setEnabled(False)
        row_task.addWidget(self.btn_cancel)

        pipe_layout.addLayout(row_task)

        # Pipeline flow hint
        self.label_flow = QLabel("Pipeline flow: FFmpeg -> BMP -> Potrace -> ILDA")
        pipe_layout.addWidget(self.label_flow)

        # ---- Steps ----
        self.steps_group = QGroupBox("Processing steps")
        self.steps_group.setObjectName("")
        steps_layout = QGridLayout(self.steps_group)
        steps_layout.setContentsMargins(6, 6, 6, 6)
        steps_layout.setHorizontalSpacing(6)
        steps_layout.setVerticalSpacing(6)
        steps_layout.setRowStretch(0, 1)
        for col in range(5):
            steps_layout.setColumnStretch(col, 1)

        step_min_height = 140
        preview_min_height = 220

        # Column 1: FFmpeg
        col1 = QVBoxLayout()
        step1_group = QGroupBox("1. FFmpeg -> PNG")
        step1_group.setObjectName("")
        step1_group.setMinimumHeight(step_min_height)
        s1_layout = QVBoxLayout(step1_group)
        self.btn_ffmpeg = QPushButton("Run FFmpeg")
        self.btn_ffmpeg.setObjectName("")
        s1_layout.addWidget(self.btn_ffmpeg)
        s1_layout.addStretch()
        col1.addWidget(step1_group)

        col1_widget = QWidget()
        col1_widget.setLayout(col1)
        col1_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        step1_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.col1_widget = col1_widget

        # Column 2: Bitmap
        col2 = QVBoxLayout()
        self.step2_group = QGroupBox("2. PNG -> BMP (threshold)")
        self.step2_group.setObjectName("")
        self.step2_group.setMinimumHeight(step_min_height)
        s2_layout = QVBoxLayout(self.step2_group)

        self.btn_bmp = QPushButton("Run BMP conversion")
        self.btn_bmp.setObjectName("")
        s2_layout.addWidget(self.btn_bmp)

        row_thr = QHBoxLayout()
        row_thr.addWidget(QLabel("Threshold (%):"))
        self.spin_bmp_threshold = QSpinBox()
        self.spin_bmp_threshold.setRange(0, 100)
        self.spin_bmp_threshold.setValue(60)
        row_thr.addWidget(self.spin_bmp_threshold)
        s2_layout.addLayout(row_thr)

        self.check_bmp_thinning = QCheckBox("Thinning")
        self.check_bmp_thinning.setChecked(False)
        s2_layout.addWidget(self.check_bmp_thinning)

        s2_layout.addStretch()
        col2.addWidget(self.step2_group)

        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        col2_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.step2_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.col2_widget = col2_widget

        # Column 2.5: Arcade OpenCV
        self.grp_arcade_opencv = QGroupBox("Arcade (OpenCV)")
        self.grp_arcade_opencv.setObjectName("")
        self.grp_arcade_opencv.setMinimumHeight(step_min_height)
        arcade_layout = QVBoxLayout(self.grp_arcade_opencv)
        self.btn_arcade = QPushButton("Run Arcade")
        self.btn_arcade.setObjectName("")
        arcade_layout.addWidget(self.btn_arcade)
        arcade_layout.setContentsMargins(4, 4, 4, 4)
        arcade_layout.setSpacing(3)

        self.check_arcade_sample_color = QCheckBox("Sample color from image")
        self.check_arcade_sample_color.setChecked(True)
        arcade_layout.addWidget(self.check_arcade_sample_color)

        row_canny1 = QHBoxLayout()
        row_canny1.addWidget(QLabel("Canny threshold 1 :"))
        self.spin_arcade_canny1 = QSpinBox()
        self.spin_arcade_canny1.setRange(1, 1000)
        self.spin_arcade_canny1.setValue(100)
        row_canny1.addWidget(self.spin_arcade_canny1)
        arcade_layout.addLayout(row_canny1)

        row_canny2 = QHBoxLayout()
        row_canny2.addWidget(QLabel("Canny threshold 2 :"))
        self.spin_arcade_canny2 = QSpinBox()
        self.spin_arcade_canny2.setRange(1, 1000)
        self.spin_arcade_canny2.setValue(200)
        row_canny2.addWidget(self.spin_arcade_canny2)
        arcade_layout.addLayout(row_canny2)

        row_blur = QHBoxLayout()
        row_blur.addWidget(QLabel("Blur kernel size :"))
        self.spin_arcade_blur_ksize = QSpinBox()
        self.spin_arcade_blur_ksize.setRange(1, 31)
        self.spin_arcade_blur_ksize.setSingleStep(2)
        self.spin_arcade_blur_ksize.setValue(5)
        self.spin_arcade_blur_ksize.valueChanged.connect(self._force_blur_odd)
        row_blur.addWidget(self.spin_arcade_blur_ksize)
        arcade_layout.addLayout(row_blur)

        self.check_arcade_advanced = QCheckBox("Advanced")
        arcade_layout.addWidget(self.check_arcade_advanced)

        self.arcade_advanced_widget = QWidget()
        adv_layout = QVBoxLayout(self.arcade_advanced_widget)
        adv_layout.setContentsMargins(0, 0, 0, 0)
        adv_layout.setSpacing(3)

        row_simplify = QHBoxLayout()
        row_simplify.addWidget(QLabel("Simplify epsilon :"))
        self.spin_arcade_simplify_eps = QDoubleSpinBox()
        self.spin_arcade_simplify_eps.setRange(0.0, 50.0)
        self.spin_arcade_simplify_eps.setSingleStep(0.25)
        self.spin_arcade_simplify_eps.setDecimals(3)
        self.spin_arcade_simplify_eps.setValue(2.0)
        row_simplify.addWidget(self.spin_arcade_simplify_eps)
        adv_layout.addLayout(row_simplify)

        row_min_poly = QHBoxLayout()
        row_min_poly.addWidget(QLabel("Min polygon length :"))
        self.spin_arcade_min_poly_len = QSpinBox()
        self.spin_arcade_min_poly_len.setRange(1, 1000)
        self.spin_arcade_min_poly_len.setValue(10)
        row_min_poly.addWidget(self.spin_arcade_min_poly_len)
        adv_layout.addLayout(row_min_poly)

        self.arcade_advanced_widget.setVisible(False)
        self.check_arcade_advanced.toggled.connect(self.arcade_advanced_widget.setVisible)
        arcade_layout.addWidget(self.arcade_advanced_widget)
        arcade_layout.addStretch(1)

        arcade_col = QVBoxLayout()
        arcade_col.addWidget(self.grp_arcade_opencv)
        arcade_col.addStretch()

        arcade_widget = QWidget()
        arcade_widget.setLayout(arcade_col)
        arcade_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.grp_arcade_opencv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.arcade_widget = arcade_widget

        # Column 3: Potrace
        col3 = QVBoxLayout()
        self.step3_group = QGroupBox("3. Vectorization (Potrace)")
        self.step3_group.setObjectName("")
        self.step3_group.setMinimumHeight(step_min_height)
        s3_layout = QVBoxLayout(self.step3_group)
        self.btn_potrace = QPushButton("Run Potrace")
        self.btn_potrace.setObjectName("")
        s3_layout.addWidget(self.btn_potrace)
        s3_layout.addStretch()
        col3.addWidget(self.step3_group)

        col3_widget = QWidget()
        col3_widget.setLayout(col3)
        col3_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.step3_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.col3_widget = col3_widget

        # Column 4: ILDA
        col4 = QVBoxLayout()
        step4_group = QGroupBox("4. ILDA (export)")
        step4_group.setObjectName("")
        step4_group.setMinimumHeight(step_min_height)
        s4_layout = QVBoxLayout(step4_group)

        self.btn_ilda = QPushButton("Export ILDA")
        self.btn_ilda.setObjectName("")
        s4_layout.addWidget(self.btn_ilda)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Profile:"))
        self.combo_ilda_mode = QComboBox()
        self.combo_ilda_mode.addItem("Classic (B/W)", "classic")
        self.combo_ilda_mode.addItem("Arcade (experimental)", "arcade")
        self.combo_ilda_mode.setCurrentIndex(0)
        row_mode.addWidget(self.combo_ilda_mode)
        s4_layout.addLayout(row_mode)

        s4_layout.addStretch()
        col4.addWidget(step4_group)

        # Arcade output parameters
        self.grp_arcade_output = QGroupBox("Arcade output")
        self.grp_arcade_output.setObjectName("")
        self.grp_arcade_output.setMinimumHeight(step_min_height)
        arcade_out_layout = QVBoxLayout(self.grp_arcade_output)

        row_kpps = QHBoxLayout()
        row_kpps.addWidget(QLabel("Kpps :"))
        self.spin_arcade_kpps = QSpinBox()
        self.spin_arcade_kpps.setRange(1, 200)
        self.spin_arcade_kpps.setValue(60)
        row_kpps.addWidget(self.spin_arcade_kpps)
        arcade_out_layout.addLayout(row_kpps)

        row_ppf = QHBoxLayout()
        row_ppf.addWidget(QLabel("Points per frame ratio :"))
        self.spin_arcade_ppf_ratio = QDoubleSpinBox()
        self.spin_arcade_ppf_ratio.setRange(0.05, 10.0)
        self.spin_arcade_ppf_ratio.setSingleStep(0.05)
        self.spin_arcade_ppf_ratio.setDecimals(3)
        self.spin_arcade_ppf_ratio.setValue(1.0)
        row_ppf.addWidget(self.spin_arcade_ppf_ratio)
        arcade_out_layout.addLayout(row_ppf)

        self.check_arcade_invert_y = QCheckBox("Invert Y axis")
        self.check_arcade_invert_y.setChecked(True)
        arcade_out_layout.addWidget(self.check_arcade_invert_y)

        row_max_points = QHBoxLayout()
        row_max_points.addWidget(QLabel("Max points per frame (0 = auto) :"))
        self.spin_arcade_max_points = QSpinBox()
        self.spin_arcade_max_points.setRange(0, 60000)
        self.spin_arcade_max_points.setValue(0)
        row_max_points.addWidget(self.spin_arcade_max_points)
        arcade_out_layout.addLayout(row_max_points)

        row_arcade_fill = QHBoxLayout()
        row_arcade_fill.addWidget(QLabel("ILDA fill ratio :"))
        self.spin_arcade_fill_ratio = QDoubleSpinBox()
        self.spin_arcade_fill_ratio.setRange(0.1, 1.0)
        self.spin_arcade_fill_ratio.setSingleStep(0.05)
        self.spin_arcade_fill_ratio.setDecimals(3)
        self.spin_arcade_fill_ratio.setValue(0.95)
        row_arcade_fill.addWidget(self.spin_arcade_fill_ratio)
        arcade_out_layout.addLayout(row_arcade_fill)
        col4.addWidget(self.grp_arcade_output)

        # Classic ILDA parameters
        self.grp_ilda_advanced = QGroupBox("ILDA Parameters (classic)")
        self.grp_ilda_advanced.setObjectName("")
        self.grp_ilda_advanced.setMinimumHeight(step_min_height)
        ilda_adv_layout = QVBoxLayout(self.grp_ilda_advanced)

        row_fit = QHBoxLayout()
        row_fit.addWidget(QLabel("Fit axis :"))
        self.combo_ilda_fit_axis = QComboBox()
        self.combo_ilda_fit_axis.addItem("Max", "max")
        self.combo_ilda_fit_axis.addItem("X", "x")
        self.combo_ilda_fit_axis.addItem("Y", "y")
        row_fit.addWidget(self.combo_ilda_fit_axis)
        ilda_adv_layout.addLayout(row_fit)

        row_fill = QHBoxLayout()
        row_fill.addWidget(QLabel("Fill ratio :"))
        self.spin_ilda_fill_ratio = QDoubleSpinBox()
        self.spin_ilda_fill_ratio.setRange(0.1, 1.0)
        self.spin_ilda_fill_ratio.setSingleStep(0.05)
        self.spin_ilda_fill_ratio.setDecimals(3)
        self.spin_ilda_fill_ratio.setValue(0.95)
        row_fill.addWidget(self.spin_ilda_fill_ratio)
        ilda_adv_layout.addLayout(row_fill)

        row_min_rel = QHBoxLayout()
        row_min_rel.addWidget(QLabel("Min relative size :"))
        self.spin_ilda_min_rel_size = QDoubleSpinBox()
        self.spin_ilda_min_rel_size.setRange(0.0, 0.5)
        self.spin_ilda_min_rel_size.setSingleStep(0.005)
        self.spin_ilda_min_rel_size.setDecimals(3)
        self.spin_ilda_min_rel_size.setValue(0.01)
        row_min_rel.addWidget(self.spin_ilda_min_rel_size)
        ilda_adv_layout.addLayout(row_min_rel)

        col4.addWidget(self.grp_ilda_advanced)

        col4.addStretch()
        col4_widget = QWidget()
        col4_widget.setLayout(col4)
        col4_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        step4_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.grp_arcade_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.grp_ilda_advanced.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.col4_widget = col4_widget

        # Previews row
        self.grp_preview_png = QGroupBox("PNG preview")
        self.grp_preview_png.setObjectName("")
        self.grp_preview_png.setMinimumHeight(preview_min_height)
        self.grp_preview_png.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p1_layout = QVBoxLayout(self.grp_preview_png)
        self.preview_png = RasterPreview()
        self.preview_png.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p1_layout.addWidget(self.preview_png)

        self.grp_preview_bmp = QGroupBox("BMP preview")
        self.grp_preview_bmp.setObjectName("")
        self.grp_preview_bmp.setMinimumHeight(preview_min_height)
        self.grp_preview_bmp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p2_layout = QVBoxLayout(self.grp_preview_bmp)
        self.preview_bmp = RasterPreview()
        self.preview_bmp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p2_layout.addWidget(self.preview_bmp)

        self.grp_preview_arcade = QGroupBox("Arcade preview")
        self.grp_preview_arcade.setObjectName("")
        self.grp_preview_arcade.setMinimumHeight(preview_min_height)
        self.grp_preview_arcade.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        arcade_prev_layout = QVBoxLayout(self.grp_preview_arcade)
        self.arcade_preview_stack = QStackedLayout()
        self.arcade_preview_label = QLabel("No preview available")
        self.arcade_preview_label.setAlignment(Qt.AlignCenter)
        self.preview_arcade = RasterPreview()
        self.preview_arcade.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.arcade_preview_stack.addWidget(self.arcade_preview_label)
        self.arcade_preview_stack.addWidget(self.preview_arcade)
        self.arcade_preview_stack.setCurrentWidget(self.arcade_preview_label)
        arcade_preview_container = QWidget()
        arcade_preview_container.setLayout(self.arcade_preview_stack)
        arcade_prev_layout.addWidget(arcade_preview_container)

        self.grp_preview_svg = QGroupBox("SVG preview")
        self.grp_preview_svg.setObjectName("")
        self.grp_preview_svg.setMinimumHeight(preview_min_height)
        self.grp_preview_svg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p3_layout = QVBoxLayout(self.grp_preview_svg)
        self.preview_svg = SvgPreview()
        self.preview_svg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p3_layout.addWidget(self.preview_svg)

        self.grp_preview_ilda = QGroupBox("ILDA preview")
        self.grp_preview_ilda.setObjectName("")
        self.grp_preview_ilda.setMinimumHeight(preview_min_height)
        self.grp_preview_ilda.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p4_layout = QVBoxLayout(self.grp_preview_ilda)
        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("Preview palette:"))
        self.combo_ilda_palette = QComboBox()
        self.combo_ilda_palette.addItem("Auto", "auto")
        self.combo_ilda_palette.addItem("IDTF 14 (64)", "idtf14")
        self.combo_ilda_palette.addItem("ILDA 64", "ilda64")
        self.combo_ilda_palette.addItem("White 63", "white63")
        palette_row.addWidget(self.combo_ilda_palette, 1)
        p4_layout.addLayout(palette_row)
        self.preview_ilda = RasterPreview()
        self.preview_ilda.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p4_layout.addWidget(self.preview_ilda)

        steps_layout.addWidget(self.col1_widget, 0, 0)
        steps_layout.addWidget(self.col2_widget, 0, 1)
        steps_layout.addWidget(self.arcade_widget, 0, 2)
        steps_layout.addWidget(self.col3_widget, 0, 3)
        steps_layout.addWidget(self.col4_widget, 0, 4)

        # ---- Previews ----
        self.previews_group = QGroupBox("Previews")
        self.previews_group.setObjectName("")
        previews_layout = QGridLayout(self.previews_group)
        previews_layout.setContentsMargins(8, 8, 8, 8)
        previews_layout.setHorizontalSpacing(8)
        previews_layout.setVerticalSpacing(8)
        previews_layout.setRowStretch(0, 1)
        for col in range(5):
            previews_layout.setColumnStretch(col, 1)

        previews_layout.addWidget(self.grp_preview_png, 0, 0)
        previews_layout.addWidget(self.grp_preview_bmp, 0, 1)
        previews_layout.addWidget(self.grp_preview_arcade, 0, 2)
        previews_layout.addWidget(self.grp_preview_svg, 0, 3)
        previews_layout.addWidget(self.grp_preview_ilda, 0, 4)

        pipe_layout.addWidget(self.steps_group)
        pipe_layout.addWidget(self.previews_group)

        self.combo_ilda_mode.currentIndexChanged.connect(self.update_mode_ui)
        self.update_mode_ui()

    def set_busy(self, busy: bool) -> None:
        self._ui_busy = busy
        if busy:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.btn_cancel.setEnabled(True)
            self.btn_cancel.setText("Cancel current task")
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(False)
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setText("Cancel current task")

        run_enabled = not busy
        self.btn_run_all.setEnabled(run_enabled)
        self.btn_ffmpeg.setEnabled(run_enabled)
        self.btn_bmp.setEnabled(run_enabled)
        self.btn_potrace.setEnabled(run_enabled)
        self.btn_ilda.setEnabled(run_enabled)
        self.btn_arcade.setEnabled(run_enabled)
        self.btn_preview_frame.setEnabled(run_enabled)

        self.spin_frame.setEnabled(run_enabled)
        self.step2_group.setEnabled(run_enabled)
        self.spin_bmp_threshold.setEnabled(run_enabled)
        self.check_bmp_thinning.setEnabled(run_enabled)

        self.grp_arcade_opencv.setEnabled(run_enabled)
        self.grp_arcade_output.setEnabled(run_enabled)
        self.grp_ilda_advanced.setEnabled(run_enabled)
        self.update_mode_ui()

    def update_mode_ui(self) -> None:
        mode = self.combo_ilda_mode.currentData() or "classic"
        is_arcade = str(mode).lower() == "arcade"

        self.grp_arcade_output.setVisible(is_arcade)
        self.grp_ilda_advanced.setVisible(not is_arcade)
        self.btn_ilda.setText("Re-export from frames" if is_arcade else "Export ILDA")

        run_enabled = not self._ui_busy
        self.step2_group.setEnabled(run_enabled and not is_arcade)
        self.step3_group.setEnabled(run_enabled and not is_arcade)
        self.grp_ilda_advanced.setEnabled(run_enabled and not is_arcade)
        self.grp_arcade_opencv.setEnabled(run_enabled and is_arcade)
        self.btn_arcade.setEnabled(run_enabled and is_arcade)
        self.grp_preview_arcade.setEnabled(is_arcade)
        self.label_flow.setText(
            "Pipeline flow: FFmpeg -> Arcade -> ILDA"
            if is_arcade
            else "Pipeline flow: FFmpeg -> BMP -> Potrace -> ILDA"
        )
        if not is_arcade:
            self.clear_arcade_preview()

    def show_arcade_preview(self, path: str) -> None:
        self.preview_arcade.show_image(path)
        self.arcade_preview_stack.setCurrentWidget(self.preview_arcade)

    def clear_arcade_preview(self) -> None:
        self.preview_arcade.clear()
        self.arcade_preview_stack.setCurrentWidget(self.arcade_preview_label)

    def set_ilda_title_live(self, live: bool) -> None:
        self.grp_preview_ilda.setTitle("ILDA preview (live)" if live else "ILDA preview")

    def _force_blur_odd(self, v: int) -> None:
        if v % 2 == 0:
            self.spin_arcade_blur_ksize.setValue(
                v + 1 if v < self.spin_arcade_blur_ksize.maximum() else v - 1
            )
