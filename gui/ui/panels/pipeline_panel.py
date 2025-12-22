from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.preview_widgets import RasterPreview, SvgPreview


class PipelinePanel(QWidget):
    """UI panel containing general params + pipeline controls + previews.

    MainWindow owns the behavior and connects signals.
    This panel only builds widgets and exposes references.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        main_layout = QVBoxLayout(self)

        # ---------------- Paramètres généraux ----------------
        general_group = QGroupBox("Paramètres généraux", self)
        gen_layout = QVBoxLayout(general_group)

        row_video = QHBoxLayout()
        row_video.addWidget(QLabel("Vidéo source :"))
        self.edit_video_path = QLineEdit()
        row_video.addWidget(self.edit_video_path)
        self.btn_browse = QPushButton("Parcourir…")
        row_video.addWidget(self.btn_browse)
        gen_layout.addLayout(row_video)

        row_project = QHBoxLayout()
        row_project.addWidget(QLabel("Nom du projet :"))
        self.edit_project = QLineEdit("projet_demo")
        row_project.addWidget(self.edit_project)
        gen_layout.addLayout(row_project)

        row_fps = QHBoxLayout()
        row_fps.addWidget(QLabel("FPS :"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 200)
        self.spin_fps.setValue(25)
        row_fps.addWidget(self.spin_fps)
        gen_layout.addLayout(row_fps)

        self.btn_test = QPushButton("Tester les paramètres")
        gen_layout.addWidget(self.btn_test)

        main_layout.addWidget(general_group)

        # ---------------- Pipeline group ----------------
        pipeline_group = QGroupBox("Pipeline vidéo → ILDA", self)
        pipe_layout = QVBoxLayout(pipeline_group)

        row_frame = QHBoxLayout()
        row_frame.addWidget(QLabel("Frame :"))
        self.spin_frame = QSpinBox()
        self.spin_frame.setRange(1, 999999)
        self.spin_frame.setValue(1)
        row_frame.addWidget(self.spin_frame)

        self.btn_preview_frame = QPushButton("Prévisualiser frame")
        row_frame.addWidget(self.btn_preview_frame)
        row_frame.addStretch()
        pipe_layout.addLayout(row_frame)

        row_task = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        row_task.addWidget(self.progress_bar)

        self.btn_run_all = QPushButton("Exécuter les 4 étapes du pipeline")
        row_task.addWidget(self.btn_run_all)

        self.btn_cancel = QPushButton("Annuler la tâche en cours")
        self.btn_cancel.setEnabled(False)
        row_task.addWidget(self.btn_cancel)
        pipe_layout.addLayout(row_task)

        cols_layout = QHBoxLayout()

        # Col 1
        col1 = QVBoxLayout()
        step1_group = QGroupBox("1. FFmpeg → PNG")
        s1_layout = QVBoxLayout(step1_group)
        self.btn_ffmpeg = QPushButton("Lancer FFmpeg")
        s1_layout.addWidget(self.btn_ffmpeg)
        s1_layout.addStretch()
        col1.addWidget(step1_group)

        prev1_group = QGroupBox("Prévisualisation PNG")
        p1_layout = QVBoxLayout(prev1_group)
        self.preview_png = RasterPreview()
        p1_layout.addWidget(self.preview_png)
        col1.addWidget(prev1_group)

        col1_widget = QWidget()
        col1_widget.setLayout(col1)
        col1_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cols_layout.addWidget(col1_widget)

        # Col 2
        col2 = QVBoxLayout()
        step2_group = QGroupBox("2. PNG → BMP (seuil)")
        s2_layout = QVBoxLayout(step2_group)

        row_thr = QHBoxLayout()
        row_thr.addWidget(QLabel("Seuil (%) :"))
        self.spin_bmp_threshold = QSpinBox()
        self.spin_bmp_threshold.setRange(0, 100)
        self.spin_bmp_threshold.setValue(60)
        row_thr.addWidget(self.spin_bmp_threshold)
        s2_layout.addLayout(row_thr)

        self.check_bmp_thinning = QCheckBox("Amincissement (thinning)")
        self.check_bmp_thinning.setChecked(False)
        s2_layout.addWidget(self.check_bmp_thinning)

        row_max = QHBoxLayout()
        row_max.addWidget(QLabel("Max frames (0 = toutes) :"))
        self.spin_bmp_max_frames = QSpinBox()
        self.spin_bmp_max_frames.setRange(0, 999999)
        self.spin_bmp_max_frames.setValue(0)
        row_max.addWidget(self.spin_bmp_max_frames)
        s2_layout.addLayout(row_max)

        self.btn_bmp = QPushButton("Lancer conversion BMP")
        s2_layout.addWidget(self.btn_bmp)
        s2_layout.addStretch()
        col2.addWidget(step2_group)

        prev2_group = QGroupBox("Prévisualisation BMP")
        p2_layout = QVBoxLayout(prev2_group)
        self.preview_bmp = RasterPreview()
        p2_layout.addWidget(self.preview_bmp)
        col2.addWidget(prev2_group)

        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        col2_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cols_layout.addWidget(col2_widget)

        # Col 3
        col3 = QVBoxLayout()
        step3_group = QGroupBox("3. Vectorisation (Potrace)")
        s3_layout = QVBoxLayout(step3_group)
        self.btn_potrace = QPushButton("Lancer Potrace")
        s3_layout.addWidget(self.btn_potrace)
        s3_layout.addStretch()
        col3.addWidget(step3_group)

        prev3_group = QGroupBox("Prévisualisation SVG")
        p3_layout = QVBoxLayout(prev3_group)
        self.preview_svg = SvgPreview()
        p3_layout.addWidget(self.preview_svg)
        col3.addWidget(prev3_group)

        col3_widget = QWidget()
        col3_widget.setLayout(col3)
        col3_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cols_layout.addWidget(col3_widget)

        # Col 4
        col4 = QVBoxLayout()
        step4_group = QGroupBox("4. ILDA (export)")
        s4_layout = QVBoxLayout(step4_group)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Profil :"))
        self.combo_ilda_mode = QComboBox()
        self.combo_ilda_mode.addItem("Classique (noir & blanc)", "classic")
        self.combo_ilda_mode.addItem("Arcade (expérimental)", "arcade")
        self.combo_ilda_mode.setCurrentIndex(0)
        row_mode.addWidget(self.combo_ilda_mode)
        s4_layout.addLayout(row_mode)

        self.btn_ilda = QPushButton("Exporter ILDA")
        s4_layout.addWidget(self.btn_ilda)
        s4_layout.addStretch()
        col4.addWidget(step4_group)

        prev4_group = QGroupBox("Prévisualisation ILDA")
        p4_layout = QVBoxLayout(prev4_group)

        palette_row = QHBoxLayout()
        palette_row.addWidget(QLabel("Palette preview :"))
        self.combo_ilda_palette = QComboBox()
        self.combo_ilda_palette.addItem("Auto", "auto")
        self.combo_ilda_palette.addItem("IDTF 14 (64)", "idtf14")
        self.combo_ilda_palette.addItem("ILDA 64", "ilda64")
        self.combo_ilda_palette.addItem("White 63", "white63")
        palette_row.addWidget(self.combo_ilda_palette, 1)
        p4_layout.addLayout(palette_row)

        self.preview_ilda = RasterPreview()
        p4_layout.addWidget(self.preview_ilda)
        col4.addWidget(prev4_group)

        col4_widget = QWidget()
        col4_widget.setLayout(col4)
        col4_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cols_layout.addWidget(col4_widget)

        for i in range(4):
            cols_layout.setStretch(i, 1)

        pipe_layout.addLayout(cols_layout)
        main_layout.addWidget(pipeline_group)
