from __future__ import annotations

from PySide6.QtCore import Qt, QSize
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
    QStackedLayout,
    QSpinBox,
    QSizePolicy,
    QToolButton,
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

        self.btn_play = QPushButton("Play")
        self.btn_play.setObjectName("")
        row_frame.addWidget(self.btn_play)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("")
        self.btn_stop.setEnabled(False)
        row_frame.addWidget(self.btn_stop)

        self.check_loop = QCheckBox("Loop")
        self.check_loop.setChecked(True)
        row_frame.addWidget(self.check_loop)
        row_frame.addStretch()
        pipe_layout.addLayout(row_frame)

        # Play settings row
        row_play = QHBoxLayout()
        row_play.addWidget(QLabel("From:"))
        self.spin_play_start = QSpinBox()
        self.spin_play_start.setRange(1, 999999)
        self.spin_play_start.setValue(1)
        row_play.addWidget(self.spin_play_start)

        row_play.addWidget(QLabel("To (0=auto):"))
        self.spin_play_end = QSpinBox()
        self.spin_play_end.setRange(0, 999999)
        self.spin_play_end.setValue(0)
        row_play.addWidget(self.spin_play_end)

        row_play.addWidget(QLabel("Speed:"))
        self.spin_play_speed = QDoubleSpinBox()
        self.spin_play_speed.setRange(0.25, 4.0)
        self.spin_play_speed.setSingleStep(0.25)
        self.spin_play_speed.setDecimals(2)
        self.spin_play_speed.setValue(1.0)
        row_play.addWidget(self.spin_play_speed)

        self.label_play_status = QLabel("")
        row_play.addWidget(self.label_play_status, 1)
        row_play.addStretch()
        pipe_layout.addLayout(row_play)

        # Task status row
        row_task = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        row_task.addWidget(self.progress_bar)

        self.btn_run_all = QPushButton("Compute full pipeline")
        self.btn_run_all.setObjectName("")
        row_task.addWidget(self.btn_run_all)

        self.btn_cancel = QPushButton("Cancel current task")
        self.btn_cancel.setEnabled(False)
        row_task.addWidget(self.btn_cancel)

        pipe_layout.addLayout(row_task)

        # Pipeline flow hint
        self.label_flow = QLabel("Current pipeline flow: FFmpeg -> BMP -> Potrace -> ILDA")
        pipe_layout.addWidget(self.label_flow)

        # ---- Steps ----
        self.steps_group = QGroupBox("Processing steps")
        self.steps_group.setObjectName("")
        steps_layout = QGridLayout(self.steps_group)
        self.steps_layout = steps_layout
        steps_layout.setContentsMargins(6, 6, 6, 6)
        steps_layout.setHorizontalSpacing(6)
        steps_layout.setVerticalSpacing(6)
        steps_layout.setRowStretch(0, 0)
        for col in range(5):
            steps_layout.setColumnStretch(col, 1)

        preview_ratio = 4 / 3
        preview_width = 300
        preview_height = int(round(preview_width / preview_ratio))
        preview_size = QSize(preview_width, preview_height)
        preview_min_height = preview_height

        # Column 1: FFmpeg
        col1 = QVBoxLayout()
        col1.setAlignment(Qt.AlignTop)
        self.step1_group = QGroupBox("1. FFmpeg -> PNG")
        self.step1_group.setObjectName("")
        self.step1_group.setMinimumHeight(0)
        s1_layout = QVBoxLayout(self.step1_group)
        s1_layout.setAlignment(Qt.AlignTop)
        s1_layout.setSpacing(4)
        self.btn_ffmpeg = QPushButton("Compute FFmpeg")
        self.btn_ffmpeg.setObjectName("")
        s1_layout.addWidget(self.btn_ffmpeg)
        col1.addWidget(self.step1_group)

        col1_widget = QWidget()
        col1_widget.setLayout(col1)
        col1_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.step1_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.col1_widget = col1_widget

        # Column 2: Bitmap
        col2 = QVBoxLayout()
        col2.setAlignment(Qt.AlignTop)
        self.step2_group = QGroupBox("2. PNG -> BMP (threshold)")
        self.step2_group.setObjectName("")
        self.step2_group.setMinimumHeight(0)
        s2_layout = QVBoxLayout(self.step2_group)
        s2_layout.setAlignment(Qt.AlignTop)
        s2_layout.setSpacing(4)

        self.btn_bmp = QPushButton("Compute BMP conversion")
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

        col2.addWidget(self.step2_group)

        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        col2_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.step2_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.col2_widget = col2_widget

        # Column 2.5: Arcade OpenCV
        self.grp_arcade_opencv = QGroupBox("Arcade (OpenCV)")
        self.grp_arcade_opencv.setObjectName("")
        self.grp_arcade_opencv.setMinimumHeight(0)
        arcade_layout = QVBoxLayout(self.grp_arcade_opencv)
        arcade_layout.setAlignment(Qt.AlignTop)
        self.btn_arcade = QPushButton("Compute Arcade")
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

        self.check_arcade_skeleton = QCheckBox("Skeleton mode")
        self.check_arcade_skeleton.setChecked(False)
        arcade_layout.addWidget(self.check_arcade_skeleton)

        self.check_arcade_advanced = QCheckBox("Advanced")
        arcade_layout.addWidget(self.check_arcade_advanced)

        arcade_col = QVBoxLayout()
        arcade_col.setAlignment(Qt.AlignTop)
        arcade_col.addWidget(self.grp_arcade_opencv)

        arcade_widget = QWidget()
        arcade_widget.setLayout(arcade_col)
        arcade_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grp_arcade_opencv.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.arcade_widget = arcade_widget

        # Column 3: Potrace
        col3 = QVBoxLayout()
        col3.setAlignment(Qt.AlignTop)
        self.step3_group = QGroupBox("3. Vectorization (Potrace)")
        self.step3_group.setObjectName("")
        self.step3_group.setMinimumHeight(0)
        s3_layout = QVBoxLayout(self.step3_group)
        s3_layout.setAlignment(Qt.AlignTop)
        s3_layout.setSpacing(4)
        self.btn_potrace = QPushButton("Compute Potrace")
        self.btn_potrace.setObjectName("")
        s3_layout.addWidget(self.btn_potrace)
        col3.addWidget(self.step3_group)

        col3_widget = QWidget()
        col3_widget.setLayout(col3)
        col3_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.step3_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.col3_widget = col3_widget

        # Column 4: ILDA
        col4 = QVBoxLayout()
        col4.setAlignment(Qt.AlignTop)
        self.step4_group = QGroupBox("4. ILDA (compute)")
        self.step4_group.setObjectName("")
        self.step4_group.setMinimumHeight(0)
        s4_layout = QVBoxLayout(self.step4_group)
        s4_layout.setAlignment(Qt.AlignTop)
        s4_layout.setSpacing(4)

        self.btn_ilda = QPushButton("Compute ILDA")
        self.btn_ilda.setObjectName("")
        s4_layout.addWidget(self.btn_ilda)

        col4.addWidget(self.step4_group)

        # Arcade output parameters
        self.grp_arcade_output = QGroupBox("Arcade output")
        self.grp_arcade_output.setObjectName("")
        self.grp_arcade_output.setMinimumHeight(0)
        arcade_out_layout = QVBoxLayout(self.grp_arcade_output)
        arcade_out_layout.setAlignment(Qt.AlignTop)
        arcade_out_layout.setAlignment(Qt.AlignTop)

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

        # ILDA export options
        self.grp_ilda_export = QGroupBox("ILDA export")
        self.grp_ilda_export.setObjectName("")
        self.grp_ilda_export.setMinimumHeight(0)
        ilda_export_layout = QVBoxLayout(self.grp_ilda_export)
        ilda_export_layout.setAlignment(Qt.AlignTop)
        self.check_ilda_swap_rb = QCheckBox("Swap R/B for ILDA export")
        self.check_ilda_swap_rb.setChecked(False)
        ilda_export_layout.addWidget(self.check_ilda_swap_rb)

        # Classic ILDA parameters
        self.grp_ilda_advanced = QGroupBox("ILDA Parameters (classic)")
        self.grp_ilda_advanced.setObjectName("")
        self.grp_ilda_advanced.setMinimumHeight(0)
        ilda_adv_layout = QVBoxLayout(self.grp_ilda_advanced)
        ilda_adv_layout.setAlignment(Qt.AlignTop)

        # Arcade advanced parameters
        self.grp_arcade_advanced = QGroupBox("Arcade advanced")
        self.grp_arcade_advanced.setObjectName("")
        self.grp_arcade_advanced.setMinimumHeight(0)
        arcade_adv_layout = QVBoxLayout(self.grp_arcade_advanced)
        arcade_adv_layout.setAlignment(Qt.AlignTop)

        row_simplify = QHBoxLayout()
        row_simplify.addWidget(QLabel("Simplify epsilon :"))
        self.spin_arcade_simplify_eps = QDoubleSpinBox()
        self.spin_arcade_simplify_eps.setRange(0.0, 50.0)
        self.spin_arcade_simplify_eps.setSingleStep(0.25)
        self.spin_arcade_simplify_eps.setDecimals(3)
        self.spin_arcade_simplify_eps.setValue(2.0)
        row_simplify.addWidget(self.spin_arcade_simplify_eps)
        arcade_adv_layout.addLayout(row_simplify)

        row_min_poly = QHBoxLayout()
        row_min_poly.addWidget(QLabel("Min polygon length :"))
        self.spin_arcade_min_poly_len = QSpinBox()
        self.spin_arcade_min_poly_len.setRange(1, 1000)
        self.spin_arcade_min_poly_len.setValue(10)
        row_min_poly.addWidget(self.spin_arcade_min_poly_len)
        arcade_adv_layout.addLayout(row_min_poly)

        self.grp_arcade_advanced.setVisible(False)
        self.check_arcade_advanced.toggled.connect(
            self.grp_arcade_advanced.setVisible
        )
        arcade_layout.addWidget(self.grp_arcade_advanced)
        ilda_adv_layout.setAlignment(Qt.AlignTop)

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


        col4_widget = QWidget()
        col4_widget.setLayout(col4)
        col4_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.step4_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grp_arcade_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grp_ilda_advanced.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.grp_ilda_export.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.col4_widget = col4_widget

        # Previews row
        self.grp_preview_png = QGroupBox("PNG preview")
        self.grp_preview_png.setObjectName("")
        self.grp_preview_png.setMinimumHeight(preview_min_height)
        self.grp_preview_png.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p1_layout = QVBoxLayout(self.grp_preview_png)
        self.preview_png = RasterPreview(min_size=preview_size)
        self.preview_png.setMinimumSize(preview_size)
        self.preview_png.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p1_layout.addWidget(self.preview_png)

        self.grp_preview_bmp = QGroupBox("BMP preview")
        self.grp_preview_bmp.setObjectName("")
        self.grp_preview_bmp.setMinimumHeight(preview_min_height)
        self.grp_preview_bmp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p2_layout = QVBoxLayout(self.grp_preview_bmp)
        self.preview_bmp = RasterPreview(min_size=preview_size)
        self.preview_bmp.setMinimumSize(preview_size)
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
        self.arcade_preview_label.setMinimumSize(preview_size)
        self.arcade_preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview_arcade = RasterPreview(min_size=preview_size)
        self.preview_arcade.setMinimumSize(preview_size)
        self.preview_arcade.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.arcade_preview_stack.addWidget(self.arcade_preview_label)
        self.arcade_preview_stack.addWidget(self.preview_arcade)
        self.arcade_preview_stack.setCurrentWidget(self.arcade_preview_label)
        arcade_preview_container = QWidget()
        arcade_preview_container.setLayout(self.arcade_preview_stack)
        arcade_preview_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        arcade_prev_layout.addWidget(arcade_preview_container)

        self.grp_preview_svg = QGroupBox("SVG preview")
        self.grp_preview_svg.setObjectName("")
        self.grp_preview_svg.setMinimumHeight(preview_min_height)
        self.grp_preview_svg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p3_layout = QVBoxLayout(self.grp_preview_svg)
        self.preview_svg = SvgPreview(min_size=preview_size)
        self.preview_svg.setMinimumSize(preview_size)
        self.preview_svg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p3_layout.addWidget(self.preview_svg)

        self.grp_preview_ilda = QGroupBox("ILDA preview")
        self.grp_preview_ilda.setObjectName("")
        self.grp_preview_ilda.setMinimumHeight(preview_min_height)
        self.grp_preview_ilda.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p4_layout = QVBoxLayout(self.grp_preview_ilda)
        self.preview_ilda = RasterPreview(min_size=preview_size)
        self.preview_ilda.setMinimumSize(preview_size)
        self.preview_ilda.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p4_layout.addWidget(self.preview_ilda)

        steps_layout.addWidget(self.col1_widget, 0, 0)
        steps_layout.addWidget(self.col2_widget, 0, 1)
        steps_layout.addWidget(self.arcade_widget, 0, 2)
        steps_layout.addWidget(self.col3_widget, 0, 3)
        steps_layout.addWidget(self.col4_widget, 0, 4)

        # ---- ILDA preview controls (moved out of preview box) ----
        self.grp_ilda_preview_controls = QGroupBox("ILDA preview")
        self.grp_ilda_preview_controls.setObjectName("")
        ilda_preview_layout = QVBoxLayout(self.grp_ilda_preview_controls)
        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("Preview palette:"))
        self.combo_ilda_palette = QComboBox()
        self.combo_ilda_palette.addItem("Auto", "auto")
        self.combo_ilda_palette.addItem("IDTF 14 (64)", "idtf14")
        self.combo_ilda_palette.addItem("ILDA 64", "ilda64")
        self.combo_ilda_palette.addItem("White 63", "white63")
        palette_row.addWidget(self.combo_ilda_palette, 1)
        ilda_preview_layout.addLayout(palette_row)
        self.check_ilda_grid = QCheckBox("Show ILDA grid")
        self.check_ilda_grid.setChecked(False)
        ilda_preview_layout.addWidget(self.check_ilda_grid)
        self.check_ilda_fit_height = QCheckBox("Fit preview height")
        self.check_ilda_fit_height.setChecked(False)
        ilda_preview_layout.addWidget(self.check_ilda_fit_height)
        ilda_preview_layout.addStretch()
        self.check_ilda_grid.toggled.connect(self.preview_ilda.set_grid_enabled)

        # ---- Output parameters ----
        self.output_group = QGroupBox("Output parameters")
        self.output_group.setObjectName("")
        output_layout = QHBoxLayout(self.output_group)
        output_layout.setContentsMargins(6, 6, 6, 6)
        output_layout.setSpacing(6)
        output_layout.addWidget(self.grp_arcade_output, 1)
        output_layout.addWidget(self.grp_ilda_advanced, 1)
        output_layout.addWidget(self.grp_ilda_preview_controls, 0)
        output_layout.addWidget(self.grp_ilda_export, 0)

        # ---- Previews ----
        self.previews_group = QGroupBox("Previews")
        self.previews_group.setObjectName("")
        self.previews_container = QVBoxLayout(self.previews_group)
        self.previews_container.setContentsMargins(8, 8, 8, 8)
        self.previews_container.setSpacing(8)

        self.previews_grid = QGridLayout()
        self.previews_grid.setHorizontalSpacing(8)
        self.previews_grid.setVerticalSpacing(8)
        self.previews_grid.setRowStretch(0, 1)
        self.previews_grid_container = QWidget()
        previews_grid_layout = QVBoxLayout(self.previews_grid_container)
        previews_grid_layout.setContentsMargins(0, 0, 0, 0)
        previews_grid_layout.addLayout(self.previews_grid)
        self.previews_grid_container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.output_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.output_toggle = QToolButton()
        self.output_toggle.setText("Output parameters")
        self.output_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.output_toggle.setArrowType(Qt.RightArrow)
        self.output_toggle.setCheckable(True)
        self.output_toggle.setChecked(False)
        self.output_toggle.toggled.connect(self._toggle_output_group)

        output_toggle_row = QHBoxLayout()
        output_toggle_row.addWidget(self.output_toggle)
        output_toggle_row.addStretch()

        self.previews_container.addWidget(self.previews_grid_container, 1)
        self.previews_container.addLayout(output_toggle_row)
        self.previews_container.addWidget(self.output_group, 0)
        self.output_group.setVisible(False)

        pipe_layout.addWidget(self.steps_group)
        pipe_layout.addWidget(self.previews_group)

        self._mode_key = "classic"
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
        self.btn_play.setEnabled(run_enabled)
        self.btn_stop.setEnabled(run_enabled and self.btn_stop.isEnabled())
        self.check_loop.setEnabled(run_enabled)
        self.spin_play_start.setEnabled(run_enabled)
        self.spin_play_end.setEnabled(run_enabled)
        self.spin_play_speed.setEnabled(run_enabled)

        self.spin_frame.setEnabled(run_enabled)
        self.step2_group.setEnabled(run_enabled)
        self.spin_bmp_threshold.setEnabled(run_enabled)
        self.check_bmp_thinning.setEnabled(run_enabled)

        self.grp_arcade_opencv.setEnabled(run_enabled)
        self.grp_arcade_output.setEnabled(run_enabled)
        self.grp_ilda_advanced.setEnabled(run_enabled)
        self.grp_ilda_preview_controls.setEnabled(run_enabled)
        self.grp_ilda_export.setEnabled(run_enabled)
        self.grp_arcade_advanced.setEnabled(run_enabled)
        self.update_mode_ui()

    def update_mode_ui(self) -> None:
        mode = self._mode_key or "classic"
        is_arcade = str(mode).lower() == "arcade"

        self._apply_mode_layout(is_arcade)

        self.grp_arcade_output.setVisible(is_arcade)
        self.grp_ilda_advanced.setVisible(not is_arcade)
        self.grp_arcade_advanced.setVisible(is_arcade and self.check_arcade_advanced.isChecked())
        self.btn_ilda.setText(
            "Compute Arcade (from frames)" if is_arcade else "Compute ILDA"
        )

        if is_arcade:
            self.grp_arcade_opencv.setTitle("2. Arcade (OpenCV)")
            self.step4_group.setTitle("3. ILDA (compute)")
        else:
            self.grp_arcade_opencv.setTitle("Arcade (OpenCV)")
            self.step4_group.setTitle("4. ILDA (compute)")

        run_enabled = not self._ui_busy
        self.step2_group.setEnabled(run_enabled and not is_arcade)
        self.step3_group.setEnabled(run_enabled and not is_arcade)

    def _toggle_output_group(self, checked: bool) -> None:
        self.output_group.setVisible(checked)
        self.output_toggle.setArrowType(
            Qt.DownArrow if checked else Qt.RightArrow
        )

    def set_mode_key(self, mode_key: str) -> None:
        self._mode_key = mode_key
        self.update_mode_ui()

    def _apply_mode_layout(self, is_arcade: bool) -> None:
        self._configure_steps_layout(is_arcade)
        self._configure_previews_layout(is_arcade)

    def _clear_layout(self, layout: QGridLayout | QVBoxLayout | QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                continue
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)

    def _configure_steps_layout(self, is_arcade: bool) -> None:
        self._clear_layout(self.steps_layout)
        if is_arcade:
            self.steps_layout.addWidget(self.col1_widget, 0, 0)
            self.steps_layout.addWidget(self.arcade_widget, 0, 1)
            self.steps_layout.addWidget(self.col4_widget, 0, 2)
            for col in range(5):
                self.steps_layout.setColumnStretch(col, 1 if col < 3 else 0)
        else:
            self.steps_layout.addWidget(self.col1_widget, 0, 0)
            self.steps_layout.addWidget(self.col2_widget, 0, 1)
            self.steps_layout.addWidget(self.col3_widget, 0, 2)
            self.steps_layout.addWidget(self.col4_widget, 0, 3)
            for col in range(5):
                self.steps_layout.setColumnStretch(col, 1 if col < 4 else 0)

    def _configure_previews_layout(self, is_arcade: bool) -> None:
        self._clear_layout(self.previews_grid)
        if is_arcade:
            self.previews_grid.addWidget(self.grp_preview_png, 0, 0)
            self.previews_grid.addWidget(self.grp_preview_arcade, 0, 1)
            self.previews_grid.addWidget(self.grp_preview_ilda, 0, 2)
            for col in range(3):
                self.previews_grid.setColumnStretch(col, 1)
            for col in range(3, 5):
                self.previews_grid.setColumnStretch(col, 0)
        else:
            self.previews_grid.addWidget(self.grp_preview_png, 0, 0)
            self.previews_grid.addWidget(self.grp_preview_bmp, 0, 1)
            self.previews_grid.addWidget(self.grp_preview_svg, 0, 2)
            self.previews_grid.addWidget(self.grp_preview_ilda, 0, 3)
            for col in range(4):
                self.previews_grid.setColumnStretch(col, 1)
            self.previews_grid.setColumnStretch(4, 0)

    def set_preview_aspect_ratio(self, ratio: float | None) -> None:
        self.preview_png.set_aspect_ratio(ratio)
        self.preview_bmp.set_aspect_ratio(ratio)
        self.preview_svg.set_aspect_ratio(ratio)
        self.preview_arcade.set_aspect_ratio(ratio)
        self.preview_ilda.set_aspect_ratio(ratio)

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
