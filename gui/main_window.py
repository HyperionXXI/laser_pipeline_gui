# gui/main_window.py
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtCore import Slot
from PySide6.QtGui import QTextCursor, QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QTextEdit,
    QLineEdit,
    QLabel,
    QFileDialog,
    QHBoxLayout,
    QVBoxLayout,
    QGroupBox,
    QCheckBox,
    QSizePolicy,
    QProgressBar,
    QInputDialog,
    QMessageBox,
)


from core.config import PROJECTS_ROOT
from core.pipeline.base import FrameProgress
from core.ilda_preview import render_ilda_preview
from .preview_widgets import RasterPreview, SvgPreview
from .pipeline_controller import PipelineController
from gui.ui.menu import setup_menus, MenuCallbacks

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Laser Pipeline GUI")

        setup_menus(
            self,
            MenuCallbacks(
                on_new_project=self.on_new_project,
                on_open_project=self.open_project,
                on_open_video=self.choose_video,
                on_clear_outputs=self.clear_project_outputs,
                on_reveal_project=self.reveal_project_in_explorer,
                on_refresh_previews=self.refresh_previews,
                on_toggle_fullscreen=self.toggle_fullscreen,
                on_about=self.on_about,
                on_exit=self.close,
            ),
        )

        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ----------------------------------------------------------
        # General settings
        # ----------------------------------------------------------
        general_group = QGroupBox("General settings", self)
        gen_layout = QVBoxLayout(general_group)

        # Video row
        row_video = QHBoxLayout()
        row_video.addWidget(QLabel("Video source:"))
        self.edit_video_path = QLineEdit()
        row_video.addWidget(self.edit_video_path)
        self.btn_browse_video = QPushButton("Browse...")
        self.btn_browse_video.clicked.connect(self.choose_video)
        row_video.addWidget(self.btn_browse_video)
        gen_layout.addLayout(row_video)

        # Project row
        row_project = QHBoxLayout()
        row_project.addWidget(QLabel("Project name:"))
        self.edit_project = QLineEdit("project_demo")
        row_project.addWidget(self.edit_project)
        gen_layout.addLayout(row_project)

        # Ligne FPS
        row_fps = QHBoxLayout()
        row_fps.addWidget(QLabel("FPS:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 200)
        self.spin_fps.setValue(25)
        row_fps.addWidget(self.spin_fps)
        gen_layout.addLayout(row_fps)

        # Max frames row (global)
        row_max = QHBoxLayout()
        row_max.addWidget(QLabel("Max frames (0 = all):"))
        self.spin_max_frames = QSpinBox()
        self.spin_max_frames.setRange(0, 999999)
        self.spin_max_frames.setValue(0)
        row_max.addWidget(self.spin_max_frames)
        gen_layout.addLayout(row_max)


        # Test button
        self.btn_test = QPushButton("Test settings")
        self.btn_test.clicked.connect(self.on_test_click)
        gen_layout.addWidget(self.btn_test)

        main_layout.addWidget(general_group)

        # ----------------------------------------------------------
        # Pipeline
        # ----------------------------------------------------------
        pipeline_group = QGroupBox("Video pipeline -> ILDA", self)
        pipe_layout = QVBoxLayout(pipeline_group)

        # Ligne frame + bouton preview
        row_frame = QHBoxLayout()
        row_frame.addWidget(QLabel("Frame:"))
        self.spin_frame = QSpinBox()
        self.spin_frame.setRange(1, 999999)
        self.spin_frame.setValue(1)
        row_frame.addWidget(self.spin_frame)

        self.btn_preview_frame = QPushButton("Preview frame")
        self.btn_preview_frame.clicked.connect(self.on_preview_frame)
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
        self.btn_run_all.clicked.connect(self.on_execute_all_task)
        row_task.addWidget(self.btn_run_all)

        self.btn_cancel = QPushButton("Cancel current task")
        self.btn_cancel.clicked.connect(self.on_cancel_task)
        self.btn_cancel.setEnabled(False)
        row_task.addWidget(self.btn_cancel)

        pipe_layout.addLayout(row_task)

        # ---- Colonnes des steps + previews ----
        cols_layout = QHBoxLayout()

        # Colonne FFmpeg
        col1 = QVBoxLayout()
        step1_group = QGroupBox("1. FFmpeg -> PNG")
        s1_layout = QVBoxLayout(step1_group)
        self.btn_ffmpeg = QPushButton("Run FFmpeg")
        self.btn_ffmpeg.clicked.connect(self.on_ffmpeg_click)
        s1_layout.addWidget(self.btn_ffmpeg)
        s1_layout.addStretch()
        col1.addWidget(step1_group)

        prev1_group = QGroupBox("PNG preview")
        p1_layout = QVBoxLayout(prev1_group)
        self.preview_png = RasterPreview()
        self.preview_png.setMinimumSize(240, 180)
        p1_layout.addWidget(self.preview_png)
        col1.addWidget(prev1_group)

        col1_widget = QWidget()
        col1_widget.setLayout(col1)
        col1_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col1_widget)

        # Colonne Bitmap
        col2 = QVBoxLayout()
        self.step2_group = QGroupBox("2. PNG -> BMP (threshold)")
        s2_layout = QVBoxLayout(self.step2_group)

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

        self.btn_bmp = QPushButton("Run BMP conversion")
        self.btn_bmp.clicked.connect(self.on_bmp_click)
        s2_layout.addWidget(self.btn_bmp)
        s2_layout.addStretch()
        col2.addWidget(self.step2_group)

        prev2_group = QGroupBox("BMP preview")
        p2_layout = QVBoxLayout(prev2_group)
        self.preview_bmp = RasterPreview()
        self.preview_bmp.setMinimumSize(240, 180)
        p2_layout.addWidget(self.preview_bmp)
        col2.addWidget(prev2_group)

        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        col2_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col2_widget)

        # Arcade parameters (shown only in arcade mode)
        self.grp_arcade_params = QGroupBox("Arcade (OpenCV)")
        arcade_layout = QVBoxLayout(self.grp_arcade_params)

        row_kpps = QHBoxLayout()
        row_kpps.addWidget(QLabel("Kpps :"))
        self.spin_arcade_kpps = QSpinBox()
        self.spin_arcade_kpps.setRange(1, 200)
        self.spin_arcade_kpps.setValue(60)
        row_kpps.addWidget(self.spin_arcade_kpps)
        arcade_layout.addLayout(row_kpps)

        row_ppf = QHBoxLayout()
        row_ppf.addWidget(QLabel("Points per frame ratio :"))
        self.spin_arcade_ppf_ratio = QDoubleSpinBox()
        self.spin_arcade_ppf_ratio.setRange(0.05, 10.0)
        self.spin_arcade_ppf_ratio.setSingleStep(0.05)
        self.spin_arcade_ppf_ratio.setDecimals(3)
        self.spin_arcade_ppf_ratio.setValue(1.0)
        row_ppf.addWidget(self.spin_arcade_ppf_ratio)
        arcade_layout.addLayout(row_ppf)

        self.check_arcade_sample_color = QCheckBox("Sample color from image")
        self.check_arcade_sample_color.setChecked(True)
        arcade_layout.addWidget(self.check_arcade_sample_color)

        self.check_arcade_invert_y = QCheckBox("Invert Y axis")
        self.check_arcade_invert_y.setChecked(True)
        arcade_layout.addWidget(self.check_arcade_invert_y)

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

        row_simplify = QHBoxLayout()
        row_simplify.addWidget(QLabel("Simplify epsilon :"))
        self.spin_arcade_simplify_eps = QDoubleSpinBox()
        self.spin_arcade_simplify_eps.setRange(0.0, 50.0)
        self.spin_arcade_simplify_eps.setSingleStep(0.25)
        self.spin_arcade_simplify_eps.setDecimals(3)
        self.spin_arcade_simplify_eps.setValue(2.0)
        row_simplify.addWidget(self.spin_arcade_simplify_eps)
        arcade_layout.addLayout(row_simplify)

        row_min_poly = QHBoxLayout()
        row_min_poly.addWidget(QLabel("Min polygon length :"))
        self.spin_arcade_min_poly_len = QSpinBox()
        self.spin_arcade_min_poly_len.setRange(1, 1000)
        self.spin_arcade_min_poly_len.setValue(10)
        row_min_poly.addWidget(self.spin_arcade_min_poly_len)
        arcade_layout.addLayout(row_min_poly)

        row_max_points = QHBoxLayout()
        row_max_points.addWidget(QLabel("Max points per frame (0 = auto) :"))
        self.spin_arcade_max_points = QSpinBox()
        self.spin_arcade_max_points.setRange(0, 60000)
        self.spin_arcade_max_points.setValue(0)
        row_max_points.addWidget(self.spin_arcade_max_points)
        arcade_layout.addLayout(row_max_points)

        row_arcade_fill = QHBoxLayout()
        row_arcade_fill.addWidget(QLabel("ILDA fill ratio :"))
        self.spin_arcade_fill_ratio = QDoubleSpinBox()
        self.spin_arcade_fill_ratio.setRange(0.1, 1.0)
        self.spin_arcade_fill_ratio.setSingleStep(0.05)
        self.spin_arcade_fill_ratio.setDecimals(3)
        self.spin_arcade_fill_ratio.setValue(0.95)
        row_arcade_fill.addWidget(self.spin_arcade_fill_ratio)
        arcade_layout.addLayout(row_arcade_fill)

        cols_layout.addWidget(self.grp_arcade_params, 1)

        # Colonne SVG
        col3 = QVBoxLayout()
        self.step3_group = QGroupBox("3. Vectorization (Potrace)")
        s3_layout = QVBoxLayout(self.step3_group)
        self.btn_potrace = QPushButton("Run Potrace")
        self.btn_potrace.clicked.connect(self.on_potrace_click)
        s3_layout.addWidget(self.btn_potrace)
        s3_layout.addStretch()
        col3.addWidget(self.step3_group)

        prev3_group = QGroupBox("SVG preview")
        p3_layout = QVBoxLayout(prev3_group)
        self.preview_svg = SvgPreview()
        self.preview_svg.setMinimumSize(240, 180)
        p3_layout.addWidget(self.preview_svg)
        col3.addWidget(prev3_group)

        col3_widget = QWidget()
        col3_widget.setLayout(col3)
        col3_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col3_widget)

        # Colonne ILDA
        col4 = QVBoxLayout()
        step4_group = QGroupBox("4. ILDA (export)")
        s4_layout = QVBoxLayout(step4_group)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Profile:"))
        self.combo_ilda_mode = QComboBox()
        self.combo_ilda_mode.addItem("Classic (B/W)", "classic")
        self.combo_ilda_mode.addItem("Arcade (experimental)", "arcade")
        self.combo_ilda_mode.setCurrentIndex(0)
        row_mode.addWidget(self.combo_ilda_mode)
        s4_layout.addLayout(row_mode)

        self.btn_ilda = QPushButton("Export ILDA")
        self.btn_ilda.clicked.connect(self.on_export_ilda_click)
        s4_layout.addWidget(self.btn_ilda)
        s4_layout.addStretch()
        col4.addWidget(step4_group)

        # Classic ILDA parameters (advanced)
        self.grp_ilda_advanced = QGroupBox("ILDA Parameters (classic)")
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


        self.prev4_group = QGroupBox("ILDA preview")
        p4_layout = QVBoxLayout(self.prev4_group)
        # Preview settings (does NOT affect export)
        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("Preview palette:"))

        self.combo_ilda_palette = QComboBox()
        self.combo_ilda_palette.addItem("Auto", "auto")          # auto: default palette from core
        self.combo_ilda_palette.addItem("IDTF 14 (64)", "idtf14")
        self.combo_ilda_palette.addItem("ILDA 64", "ilda64")
        self.combo_ilda_palette.addItem("White 63", "white63")
        self.combo_ilda_palette.setToolTip(
            "Palette used only for previewing indexed formats (ILDA 0/1). "
            "Ignored for ILDA 5 (true-color)."
        )
        self.combo_ilda_palette.currentIndexChanged.connect(self._on_ilda_preview_palette_changed)
        self.combo_ilda_mode.currentIndexChanged.connect(self._on_ilda_mode_changed)

        palette_row.addWidget(self.combo_ilda_palette, 1)
        p4_layout.addLayout(palette_row)

        self.preview_ilda = RasterPreview()
        self.preview_ilda.setMinimumSize(240, 180)
        p4_layout.addWidget(self.preview_ilda)
        col4.addWidget(self.prev4_group)

        col4_widget = QWidget()
        col4_widget.setLayout(col4)
        col4_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col4_widget)

        pipe_layout.addLayout(cols_layout)
        main_layout.addWidget(pipeline_group)

        # ----------------------------------------------------------
        # Log
        # ----------------------------------------------------------
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        main_layout.addWidget(self.log_view)

        # Pipeline controller
        self.pipeline = PipelineController(parent=self, log_fn=self.log)
        self.pipeline.step_started.connect(self.on_step_started)
        self.pipeline.step_finished.connect(self.on_step_finished)
        self.pipeline.step_error.connect(self.on_step_error)
        self.pipeline.step_progress.connect(self.on_step_progress)

        self._ui_busy = False
        self._on_ilda_mode_changed(self.combo_ilda_mode.currentIndex())

    # ---------------- Utilitaires log / busy ---------------------

    def log(self, text: str) -> None:
        ts = datetime.now().strftime("[%H:%M:%S]")
        self.log_view.append(f"{ts} {text}")
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.ensureCursorVisible()


    def set_busy(self, busy: bool) -> None:
        """Enable/disable the UI during pipeline execution."""
        self._ui_busy = busy
        if busy:
            self.progress_bar.setVisible(True)
            # Indeterminate until total_frames/progress is known.
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

        self.btn_test.setEnabled(run_enabled)
        self.combo_ilda_palette.setEnabled(run_enabled)
        self.btn_browse_video.setEnabled(run_enabled)

        # Boutons pipeline
        self.btn_run_all.setEnabled(run_enabled)
        self.btn_ffmpeg.setEnabled(run_enabled)
        self.btn_bmp.setEnabled(run_enabled)
        self.btn_potrace.setEnabled(run_enabled)
        self.btn_ilda.setEnabled(run_enabled)
        self.btn_preview_frame.setEnabled(run_enabled)

        # Settings
        self.edit_video_path.setEnabled(run_enabled)
        self.edit_project.setEnabled(run_enabled)
        self.spin_fps.setEnabled(run_enabled)
        self.spin_frame.setEnabled(run_enabled)
        self.spin_bmp_threshold.setEnabled(run_enabled)
        self.check_bmp_thinning.setEnabled(run_enabled)
        self.spin_max_frames.setEnabled(run_enabled)
        self.combo_ilda_mode.setEnabled(run_enabled)
        self.grp_arcade_params.setEnabled(run_enabled)
        self.grp_ilda_advanced.setEnabled(run_enabled)
        self._on_ilda_mode_changed(self.combo_ilda_mode.currentIndex())

    @Slot(str)
    def on_step_started(self, step_name: str) -> None:
        self.set_busy(True)
        self.log(f"[{step_name}] starting...")
        if step_name == "arcade_lines":
            self.prev4_group.setTitle("ILDA preview (live)")

    @Slot(str, object)
    def on_step_finished(self, step_name: str, result: object) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.set_busy(False)
        msg = getattr(result, "message", "")
        if msg:
            self.log(f"[{step_name}] {msg}")

        if step_name in ("arcade_lines", "ilda", "full_pipeline"):
            self.prev4_group.setTitle("ILDA preview")

        if step_name in ("arcade_lines", "ilda", "full_pipeline") and getattr(result, "success", False):
            project = (self.edit_project.text() or "").strip()
            if project:
                self._update_ilda_preview(project)

    @Slot(str, str)
    def on_step_error(self, step_name: str, message: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.set_busy(False)
        self.log(f"[{step_name}] ERREUR : {message}")
        if step_name in ("arcade_lines", "ilda", "full_pipeline"):
            self.prev4_group.setTitle("ILDA preview")

    @Slot(str, object)
    def on_step_progress(self, step_name: str, payload: object) -> None:
        if not isinstance(payload, FrameProgress):
            return
        fp: FrameProgress = payload

        if fp.total_frames is not None and fp.total_frames > 0:
            self.progress_bar.setRange(0, 100)

            total = int(fp.total_frames)
            idx = int(fp.frame_index)

            if idx < 0:
                idx = 0

            # Supporte 0-based (0..total-1) et 1-based (1..total)
            if idx < total:
                processed = idx + 1
            else:
                processed = idx

            if processed > total:
                processed = total

            pct = int(processed * 100 / total)
            self.progress_bar.setValue(pct)
        else:
            self.progress_bar.setRange(0, 0)

        if not fp.frame_path:
            return
        path = str(fp.frame_path)

        if step_name == "ffmpeg":
            self.preview_png.show_image(path)
        elif step_name == "bitmap":
            self.preview_bmp.show_image(path)
        elif step_name == "potrace":
            self.preview_svg.show_svg(path)
        elif step_name == "ilda":
            self.preview_ilda.show_image(path)
        elif step_name == "arcade_lines":
            self.preview_ilda.show_image(path)

    # ---------------- Callbacks UI -------------------------------

    def choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose a video",
            "",
            "Videos (*.mp4 *.mov *.avi);;All files (*)",
        )
        if path:
            self.edit_video_path.setText(path)
            self.edit_video_path.setFocus()
            self.log(f"Selected video: {path}")

    def on_new_project(self) -> None:
        """Create a new project directory structure under `PROJECTS_ROOT`."""
        name, ok = QInputDialog.getText(self, "Create a project", "Project name:")
        if not ok:
            return
        project = (name or "").strip()
        if not project:
            self.log("Error: project name is empty.")
            return

        project_root = PROJECTS_ROOT / project
        subdirs = ["frames", "bmp", "svg", "ilda", "preview"]
        try:
            for d in subdirs:
                (project_root / d).mkdir(parents=True, exist_ok=True)
            self.edit_project.setText(project)
            self.log(f"Project created: {project_root}")
        except Exception as e:
            self.log(f"Project creation error: {e}")

    def on_about(self) -> None:
        readme_text = ""
        try:
            readme_path = Path(__file__).resolve().parent.parent / "README.md"
            if readme_path.exists():
                readme_text = readme_path.read_text(encoding="utf-8")
        except Exception as e:
            readme_text = f"(Could not load README.md: {e})"

        msg = QMessageBox(self)
        msg.setWindowTitle("About Laser Pipeline GUI")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Laser Pipeline GUI\n\nExperimental video -> ILDA pipeline.")
        if readme_text:
            msg.setDetailedText(readme_text)
        msg.exec()

    def on_test_click(self) -> None:
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        self.log("=== Current settings ===")
        self.log(f"Video: {video or '<none>'}")
        self.log(f"Project: {project or '<none>'}")
        self.log(f"FPS    : {fps}")
        self.log("================================")

    def on_ffmpeg_click(self) -> None:
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        if not video:
            self.log("FFmpeg error: no video file selected.")
            return
        if not project:
            self.log("FFmpeg error: project name is empty.")
            return

        self.log("[FFmpeg] Starting frame extraction...")
        self.pipeline.start_ffmpeg(video, project, fps)

    def on_bmp_click(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("BMP error: project name is empty.")
            return

        threshold = self.spin_bmp_threshold.value()
        thinning = self.check_bmp_thinning.isChecked()
        max_frames_val = self.spin_max_frames.value()
        max_frames = max_frames_val if max_frames_val > 0 else None

        self.log(
            f"[BMP] Converting PNG -> BMP (threshold={threshold}%, "
            f"thinning={thinning}, max_frames={max_frames or 'all'})..."
        )
        self.pipeline.start_bitmap(project, threshold, thinning, max_frames)

    def on_potrace_click(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Potrace error: project name is empty.")
            return
        self.log(f"[Potrace] Vectorizing BMP -> SVG for '{project}'...")
        self.pipeline.start_potrace(project)

    def on_export_ilda_click(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("ILDA error: project name is empty.")
            return

        mode_key = self.combo_ilda_mode.currentData() or "classic"
        mode_label = self.combo_ilda_mode.currentText()
        if str(mode_key).lower() == "arcade":
            max_frames_val = self.spin_max_frames.value()
            max_frames = max_frames_val if max_frames_val > 0 else None
            arcade_params = self._get_arcade_params()
            self.log(f"[Arcade] Export ILDA from PNG frames (profile={mode_label})...")
            self.pipeline.start_arcade_lines(
                project,
                fps=self.spin_fps.value(),
                max_frames=max_frames,
                arcade_params=arcade_params,
            )
            return

        ilda_params = self._get_ilda_params()
        self.log(f"[ILDA] Export ILDA (profile={mode_label})...")
        self.pipeline.start_ilda(
            project,
            ilda_mode=mode_key,
            fit_axis=ilda_params["fit_axis"],
            fill_ratio=ilda_params["fill_ratio"],
            min_rel_size=ilda_params["min_rel_size"],
        )

    def on_cancel_task(self) -> None:
        if not self.btn_cancel.isEnabled():
            return
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("Canceling...")
        self.log("[UI] Cancel requested... (waiting for step to stop)")
        self.pipeline.cancel_current_step()

    # ---------------- Preview helpers ----------------------------

    def _resolve_ilda_path(self, project_root: Path, project: str) -> Path | None:
        # Arcade v2 writes: projects/<project>/<project>.ild
        # Classic (or future layout) could be: projects/<project>/ilda/<project>.ild
        candidates = [
            project_root / f"{project}.ild",
            project_root / "ilda" / f"{project}.ild",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def _update_ilda_preview(self, project: str) -> None:
        project_root = PROJECTS_ROOT / project

        # (SVG preview can remain, but arcade mode has no SVG output)
        svg_dir = project_root / "svg"
        svg_files = sorted(svg_dir.glob("frame_*.svg"))
        if svg_files:
            self.preview_svg.show_svg(str(svg_files[0]))
            self.log(f"[Preview] SVG: {svg_files[0]}")

        preview_dir = project_root / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)

        ilda_path = self._resolve_ilda_path(project_root, project)  # <- IMPORTANT
        if ilda_path is not None:
            out_png = preview_dir / "ilda_preview.png"
            try:
                render_ilda_preview(ilda_path, out_png, frame_index=0, palette_name=self._get_ilda_preview_palette_name())
                self.preview_ilda.show_image(str(out_png))
                self.log(f"[Preview] ILDA: {out_png}")
            except Exception as e:
                self.log(f"[Preview] Failed to generate ILDA preview: {e}")


    def _get_ilda_preview_palette_name(self) -> str:
        """Return the palette key to use for ILDA previews.

        Priority:
          1) The UI dropdown (if present)
          2) Environment variable ILDA_PREVIEW_PALETTE
          3) Fallback default ("ilda64")
        """
        try:
            combo = getattr(self, "combo_ilda_palette", None)
            if combo is not None:
                key = combo.currentData()
                if isinstance(key, str) and key.strip():
                    return key.strip()
                txt = combo.currentText()
                if isinstance(txt, str) and txt.strip():
                    return txt.strip()
        except Exception:
            pass

        import os
        return os.getenv("ILDA_PREVIEW_PALETTE", "ilda64")

    def _on_ilda_preview_palette_changed(self, _index: int) -> None:
        """Re-render the currently selected ILDA preview frame when palette changes."""
        # Reuse the existing preview refresh path; it already logs errors cleanly.
        try:
            self.on_preview_frame()
        except Exception:
            # Never let a palette change crash the GUI.
            pass

    def _on_ilda_mode_changed(self, _index: int) -> None:
        mode = self.combo_ilda_mode.currentData() or "classic"
        is_arcade = str(mode).lower() == "arcade"
        self.grp_arcade_params.setVisible(is_arcade)
        self.grp_ilda_advanced.setVisible(not is_arcade)

        self.btn_ilda.setText("Re-export from frames" if is_arcade else "Export ILDA")

        run_enabled = not self._ui_busy
        self.step2_group.setEnabled(run_enabled and not is_arcade)
        self.step3_group.setEnabled(run_enabled and not is_arcade)
        self.grp_ilda_advanced.setEnabled(run_enabled and not is_arcade)

    def _force_blur_odd(self, v: int) -> None:
        if v % 2 == 0:
            self.spin_arcade_blur_ksize.setValue(
                v + 1 if v < self.spin_arcade_blur_ksize.maximum() else v - 1
            )

    def _get_ilda_params(self) -> dict[str, object]:
        return {
            "fit_axis": str(self.combo_ilda_fit_axis.currentData() or "max"),
            "fill_ratio": float(self.spin_ilda_fill_ratio.value()),
            "min_rel_size": float(self.spin_ilda_min_rel_size.value()),
        }

    def _get_arcade_params(self) -> dict[str, object]:
        blur_ksize = int(self.spin_arcade_blur_ksize.value()) | 1
        return {
            "kpps": int(self.spin_arcade_kpps.value()),
            "ppf_ratio": float(self.spin_arcade_ppf_ratio.value()),
            "sample_color": bool(self.check_arcade_sample_color.isChecked()),
            "invert_y": bool(self.check_arcade_invert_y.isChecked()),
            "canny1": int(self.spin_arcade_canny1.value()),
            "canny2": int(self.spin_arcade_canny2.value()),
            "blur_ksize": blur_ksize,
            "simplify_eps": float(self.spin_arcade_simplify_eps.value()),
            "min_poly_len": int(self.spin_arcade_min_poly_len.value()),
            "max_points_per_frame": (None if self.spin_arcade_max_points.value() == 0 else int(self.spin_arcade_max_points.value())),
            "fill_ratio": float(self.spin_arcade_fill_ratio.value()),
        }
    def on_preview_frame(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Preview error: project name is empty.")
            return

        ui_frame = self.spin_frame.value()
        project_root = PROJECTS_ROOT / project
        png = project_root / "frames" / f"frame_{ui_frame:04d}.png"
        bmp = project_root / "bmp" / f"frame_{ui_frame:04d}.bmp"
        svg = project_root / "svg" / f"frame_{ui_frame:04d}.svg"

        if png.exists():
            self.preview_png.show_image(str(png))
            self.log(f"[Preview] PNG: {png}")
        if bmp.exists():
            self.preview_bmp.show_image(str(bmp))
            self.log(f"[Preview] BMP: {bmp}")
        if svg.exists():
            self.preview_svg.show_svg(str(svg))
            self.log(f"[Preview] SVG: {svg}")

        ilda_path = self._resolve_ilda_path(project_root, project)
        if ilda_path is not None:
            preview_dir = project_root / "preview"
            preview_dir.mkdir(parents=True, exist_ok=True)
            out_png = preview_dir / f"ilda_preview_{ui_frame:04d}.png"
            try:
                render_ilda_preview(ilda_path, out_png, frame_index=max(0, ui_frame - 1), palette_name=self._get_ilda_preview_palette_name())
                self.preview_ilda.show_image(str(out_png))
                self.log(f"[Preview] ILDA frame {ui_frame} : {out_png}")
            except Exception as e:
                self.log(f"[Preview] Failed to generate ILDA preview for frame {ui_frame}: {e}")
        else:
            self.log("[Preview] No ILDA file found for this frame.")

    def refresh_previews(self) -> None:
        self.on_preview_frame()

    # ---------------- Full pipeline ------------------------------

    def on_execute_all_task(self) -> None:
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        if not video:
            self.log("Error: no video file selected.")
            return
        if not project:
            self.log("Error: project name is empty.")
            return

        threshold = self.spin_bmp_threshold.value()
        thinning = self.check_bmp_thinning.isChecked()
        max_frames_val = self.spin_max_frames.value()
        max_frames = max_frames_val if max_frames_val > 0 else None
        mode_key = self.combo_ilda_mode.currentData() or "classic"
        mode_label = self.combo_ilda_mode.currentText()
        ilda_params = self._get_ilda_params()
        arcade_params = self._get_arcade_params() if str(mode_key).lower() == "arcade" else None

        self.log("Starting full pipeline (4 steps)...")
        self.log(f"  Video   : {video}")
        self.log(f"  Project : {project}")
        self.log(f"  FPS     : {fps}")
        self.log(
            f"  Bitmap  : threshold={threshold}%, thinning={thinning}, "
            f"max_frames={max_frames or 'all'}"
        )
        self.log(f"  ILDA    : profile={mode_label} ({mode_key})")

        self.pipeline.start_full_pipeline(
            video_path=video,
            project=project,
            fps=fps,
            threshold=threshold,
            use_thinning=thinning,
            max_frames=max_frames,
            ilda_mode=mode_key,
            fit_axis=ilda_params["fit_axis"],
            fill_ratio=ilda_params["fill_ratio"],
            min_rel_size=ilda_params["min_rel_size"],
            arcade_params=arcade_params,
        )

    def open_project(self) -> None:
        root = str(PROJECTS_ROOT)
        folder = QFileDialog.getExistingDirectory(self, "Open a project", root)
        if not folder:
            return

        try:
            folder_path = Path(folder).resolve()
            project_root = Path(PROJECTS_ROOT).resolve()
            project_name = folder_path.name

            # If the user picked PROJECTS_ROOT directly, refuse.
            if folder_path == project_root:
                self.log("[UI] Invalid selection: choose a subfolder of projects/.")
                return

            self.edit_project.setText(project_name)
            self.log(f"[UI] Project opened: {project_name}")
            self.refresh_previews()
        except Exception as e:
            self.log(f"[UI] Open Project error: {e}")


    def clear_project_outputs(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("[UI] Clear outputs: project name is empty.")
            return

        root = PROJECTS_ROOT / project
        if not root.exists():
            self.log(f"[UI] Clear outputs: missing folder: {root}")
            return

        reply = QMessageBox.question(
            self,
            "Clear outputs",
            f"Delete generated outputs in:\n{root}\n\n(Frames/BMP/SVG/preview/ilda)\n",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        deleted = 0
        for sub in ("frames", "bmp", "svg", "preview", "ilda"):
            d = root / sub
            if not d.exists():
                continue
            for p in d.glob("*"):
                try:
                    if p.is_file():
                        p.unlink()
                        deleted += 1
                except Exception:
                    pass

        self.log(f"[UI] Clear outputs: {deleted} files deleted.")
        self.refresh_previews()

        
    def reveal_project_in_explorer(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("[UI] Reveal: project name is empty.")
            return
        path = PROJECTS_ROOT / project
        if not path.exists():
            self.log(f"[UI] Reveal: missing folder: {path}")
            return
        try:
            import os
            os.startfile(str(path))
        except Exception as e:
            self.log(f"[UI] Reveal error: {e}")

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

def run() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    sys.exit(app.exec())

