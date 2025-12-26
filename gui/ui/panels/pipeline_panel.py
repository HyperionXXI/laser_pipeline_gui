from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.preview_widgets import RasterPreview, SvgPreview


class PipelinePanel(QWidget):
    """UI panel for the 4-step pipeline (FFmpeg -> BMP -> Potrace -> ILDA) + previews.

This file also exposes Arcade parameters in the UI when the ILDA profile
'Arcade (experimental)' is selected.
"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)

        # -------------------- frame preview controls --------------------
        row_frame = QHBoxLayout()
        row_frame.addWidget(QLabel("Frame:"))
        self.spin_frame = QSpinBox()
        self.spin_frame.setRange(1, 999999)
        self.spin_frame.setValue(1)
        row_frame.addWidget(self.spin_frame)
        self.btn_preview_frame = QPushButton("Preview frame")
        row_frame.addWidget(self.btn_preview_frame)
        row_frame.addStretch(1)
        root.addLayout(row_frame)

        # -------------------- pipeline run / cancel --------------------
        row_run = QHBoxLayout()
        self.btn_full_pipeline = QPushButton("Run all 4 pipeline steps")
        self.btn_cancel = QPushButton("Cancel current task")
        self.btn_cancel.setEnabled(False)
        row_run.addWidget(self.btn_full_pipeline)
        row_run.addWidget(self.btn_cancel)
        root.addLayout(row_run)

        # -------------------- 4 steps row --------------------
        steps_row = QHBoxLayout()
        root.addLayout(steps_row)

        # Step 1: FFmpeg -> PNG
        step1_group = QGroupBox("1. FFmpeg -> PNG")
        s1 = QVBoxLayout(step1_group)
        self.btn_ffmpeg = QPushButton("Lancer FFmpeg")
        s1.addWidget(self.btn_ffmpeg)
        s1.addStretch(1)
        steps_row.addWidget(step1_group, 1)

        # Step 2: PNG -> BMP (threshold)
        step2_group = QGroupBox("2. PNG -> BMP (threshold)")
        s2 = QVBoxLayout(step2_group)

        row_thr = QHBoxLayout()
        row_thr.addWidget(QLabel("Threshold (%):"))
        self.spin_threshold = QSpinBox()
        self.spin_threshold.setRange(0, 100)
        self.spin_threshold.setValue(60)
        row_thr.addWidget(self.spin_threshold)
        row_thr.addStretch(1)
        s2.addLayout(row_thr)

        self.check_thinning = QCheckBox("Thinning")
        self.check_thinning.setChecked(False)
        s2.addWidget(self.check_thinning)

        row_max = QHBoxLayout()
        row_max.addWidget(QLabel("Max frames (0 = all):"))
        self.spin_max_frames = QSpinBox()
        self.spin_max_frames.setRange(0, 999999)
        self.spin_max_frames.setValue(0)
        row_max.addWidget(self.spin_max_frames)
        row_max.addStretch(1)
        s2.addLayout(row_max)

        self.btn_bmp = QPushButton("Run BMP conversion")
        s2.addWidget(self.btn_bmp)
        s2.addStretch(1)
        steps_row.addWidget(step2_group, 1)

        # Step 3: Vectorization (Potrace)
        step3_group = QGroupBox("3. Vectorization (Potrace)")
        s3 = QVBoxLayout(step3_group)
        self.btn_potrace = QPushButton("Run Potrace")
        s3.addWidget(self.btn_potrace)
        s3.addStretch(1)
        steps_row.addWidget(step3_group, 1)

        # Step 4: ILDA (export)
        step4_group = QGroupBox("4. ILDA (export)")
        s4 = QVBoxLayout(step4_group)

        row_profile = QHBoxLayout()
        row_profile.addWidget(QLabel("Profile:"))
        self.combo_ilda_mode = QComboBox()
        self.combo_ilda_mode.addItem("Classic (B/W)", "classic")
        self.combo_ilda_mode.addItem("Arcade (experimental)", "arcade")
        row_profile.addWidget(self.combo_ilda_mode)
        s4.addLayout(row_profile)

        self.btn_ilda = QPushButton("Export ILDA")
        s4.addWidget(self.btn_ilda)

        # --- Arcade parameters (shown only when profile == 'arcade') ---
        self.grp_arcade_params = QGroupBox("Arcade parameters")
        grid = QGridLayout(self.grp_arcade_params)

        r = 0
        grid.addWidget(QLabel("Kpps :"), r, 0)
        self.spin_arcade_kpps = QSpinBox()
        self.spin_arcade_kpps.setRange(1, 200)
        self.spin_arcade_kpps.setValue(60)
        grid.addWidget(self.spin_arcade_kpps, r, 1)
        r += 1

        grid.addWidget(QLabel("Points per frame ratio :"), r, 0)
        self.spin_arcade_ppf_ratio = QDoubleSpinBox()
        self.spin_arcade_ppf_ratio.setRange(0.05, 10.0)
        self.spin_arcade_ppf_ratio.setSingleStep(0.05)
        self.spin_arcade_ppf_ratio.setDecimals(3)
        self.spin_arcade_ppf_ratio.setValue(1.0)
        grid.addWidget(self.spin_arcade_ppf_ratio, r, 1)
        r += 1

        self.check_arcade_sample_color = QCheckBox("Sample color from image")
        self.check_arcade_sample_color.setChecked(True)
        grid.addWidget(self.check_arcade_sample_color, r, 0, 1, 2)
        r += 1

        self.check_arcade_invert_y = QCheckBox("Invert Y axis")
        # NOTE: in arcade video sources, Y inversion is usually needed to match preview.
        self.check_arcade_invert_y.setChecked(True)
        grid.addWidget(self.check_arcade_invert_y, r, 0, 1, 2)
        r += 1

        grid.addWidget(QLabel("Canny threshold 1 :"), r, 0)
        self.spin_arcade_canny1 = QSpinBox()
        self.spin_arcade_canny1.setRange(1, 1000)
        self.spin_arcade_canny1.setValue(100)
        grid.addWidget(self.spin_arcade_canny1, r, 1)
        r += 1

        grid.addWidget(QLabel("Canny threshold 2 :"), r, 0)
        self.spin_arcade_canny2 = QSpinBox()
        self.spin_arcade_canny2.setRange(1, 1000)
        self.spin_arcade_canny2.setValue(200)
        grid.addWidget(self.spin_arcade_canny2, r, 1)
        r += 1

        grid.addWidget(QLabel("Blur kernel size :"), r, 0)
        self.spin_arcade_blur_ksize = QSpinBox()
        self.spin_arcade_blur_ksize.setRange(1, 31)
        self.spin_arcade_blur_ksize.setSingleStep(2)
        self.spin_arcade_blur_ksize.setValue(5)
        grid.addWidget(self.spin_arcade_blur_ksize, r, 1)
        r += 1

        grid.addWidget(QLabel("Simplify epsilon :"), r, 0)
        self.spin_arcade_simplify_eps = QDoubleSpinBox()
        self.spin_arcade_simplify_eps.setRange(0.0, 50.0)
        self.spin_arcade_simplify_eps.setSingleStep(0.25)
        self.spin_arcade_simplify_eps.setDecimals(3)
        self.spin_arcade_simplify_eps.setValue(2.0)
        grid.addWidget(self.spin_arcade_simplify_eps, r, 1)
        r += 1

        grid.addWidget(QLabel("Min polygon length :"), r, 0)
        self.spin_arcade_min_poly_len = QSpinBox()
        self.spin_arcade_min_poly_len.setRange(1, 1000)
        self.spin_arcade_min_poly_len.setValue(10)
        grid.addWidget(self.spin_arcade_min_poly_len, r, 1)
        r += 1

        # little spacer at bottom of the grid (prevents "cramped" look)
        grid.setRowStretch(r, 1)

        s4.addWidget(self.grp_arcade_params)
        s4.addStretch(1)
        steps_row.addWidget(step4_group, 1)

        # -------------------- previews row --------------------
        previews_row = QHBoxLayout()
        root.addLayout(previews_row)

        prev1_group = QGroupBox("PNG preview")
        p1 = QVBoxLayout(prev1_group)
        self.preview_png = RasterPreview()
        self.preview_png.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p1.addWidget(self.preview_png)
        previews_row.addWidget(prev1_group, 1)

        prev2_group = QGroupBox("BMP preview")
        p2 = QVBoxLayout(prev2_group)
        self.preview_bmp = RasterPreview()
        self.preview_bmp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p2.addWidget(self.preview_bmp)
        previews_row.addWidget(prev2_group, 1)

        prev3_group = QGroupBox("SVG preview")
        p3 = QVBoxLayout(prev3_group)
        self.preview_svg = SvgPreview()
        self.preview_svg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p3.addWidget(self.preview_svg)
        previews_row.addWidget(prev3_group, 1)

        prev4_group = QGroupBox("ILDA preview")
        p4 = QVBoxLayout(prev4_group)
        row_palette = QHBoxLayout()
        row_palette.addWidget(QLabel("Preview palette:"))
        self.combo_palette_preview = QComboBox()
        self.combo_palette_preview.addItem("Auto", "auto")
        self.combo_palette_preview.addItem("Red", "red")
        self.combo_palette_preview.addItem("Green", "green")
        self.combo_palette_preview.addItem("Blue", "blue")
        self.combo_palette_preview.addItem("White", "white")
        row_palette.addWidget(self.combo_palette_preview)
        p4.addLayout(row_palette)

        self.preview_ilda = RasterPreview()
        self.preview_ilda.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        p4.addWidget(self.preview_ilda)
        previews_row.addWidget(prev4_group, 1)

        # -------------------- mode-dependent UI --------------------
        self.combo_ilda_mode.currentIndexChanged.connect(self._update_mode_ui)
        self._update_mode_ui()

    # -------------------- arcade params --------------------
    def get_arcade_params(self) -> Dict[str, Any]:
        """
        Read the Arcade parameters from the panel.

        Returned keys match core/pipeline/arcade_lines_step.py expectations.
        """
        return {
            "kpps": int(self.spin_arcade_kpps.value()),
            "ppf_ratio": float(self.spin_arcade_ppf_ratio.value()),
            "sample_color": bool(self.check_arcade_sample_color.isChecked()),
            "invert_y": bool(self.check_arcade_invert_y.isChecked()),
            "canny1": int(self.spin_arcade_canny1.value()),
            "canny2": int(self.spin_arcade_canny2.value()),
            "blur_ksize": int(self.spin_arcade_blur_ksize.value()),
            "simplify_eps": float(self.spin_arcade_simplify_eps.value()),
            "min_poly_len": int(self.spin_arcade_min_poly_len.value()),
        }

    def _update_mode_ui(self) -> None:
        mode = self.combo_ilda_mode.currentData()
        is_arcade = mode == "arcade"

        # show/hide arcade params block
        self.grp_arcade_params.setVisible(bool(is_arcade))

        # optional UX: disable irrelevant classic-only controls when arcade is selected
        classic_only = not is_arcade
        self.spin_threshold.setEnabled(classic_only)
        self.check_thinning.setEnabled(classic_only)
        self.btn_bmp.setEnabled(classic_only)
        self.btn_potrace.setEnabled(classic_only)
