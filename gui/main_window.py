# gui/main_window.py
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCursor, QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QPushButton,
    QSpinBox,
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Laser Pipeline GUI")

        # --- Menu bar ---
        menu = self.menuBar()

        # File menu
        file_menu = menu.addMenu("File")
        open_action = QAction("Open Video...", self)
        open_action.triggered.connect(self.choose_video)
        file_menu.addAction(open_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Project menu
        proj_menu = menu.addMenu("Project")
        new_proj_action = QAction("New Project...", self)
        new_proj_action.triggered.connect(self.on_new_project)
        proj_menu.addAction(new_proj_action)

        # Help menu
        help_menu = menu.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.on_about)
        help_menu.addAction(about_action)

        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ----------------------------------------------------------
        # Paramètres généraux
        # ----------------------------------------------------------
        general_group = QGroupBox("Paramètres généraux", self)
        gen_layout = QVBoxLayout(general_group)

        # Ligne vidéo
        row_video = QHBoxLayout()
        row_video.addWidget(QLabel("Vidéo source :"))
        self.edit_video_path = QLineEdit()
        row_video.addWidget(self.edit_video_path)
        btn_browse = QPushButton("Parcourir…")
        btn_browse.clicked.connect(self.choose_video)
        row_video.addWidget(btn_browse)
        gen_layout.addLayout(row_video)

        # Ligne projet
        row_project = QHBoxLayout()
        row_project.addWidget(QLabel("Nom du projet :"))
        self.edit_project = QLineEdit("projet_demo")
        row_project.addWidget(self.edit_project)
        gen_layout.addLayout(row_project)

        # Ligne FPS
        row_fps = QHBoxLayout()
        row_fps.addWidget(QLabel("FPS :"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 200)
        self.spin_fps.setValue(25)
        row_fps.addWidget(self.spin_fps)
        gen_layout.addLayout(row_fps)

        # Bouton test
        btn_test = QPushButton("Tester les paramètres")
        btn_test.clicked.connect(self.on_test_click)
        gen_layout.addWidget(btn_test)

        main_layout.addWidget(general_group)

        # ----------------------------------------------------------
        # Pipeline
        # ----------------------------------------------------------
        pipeline_group = QGroupBox("Pipeline vidéo → ILDA", self)
        pipe_layout = QVBoxLayout(pipeline_group)

        # Ligne frame + bouton preview
        row_frame = QHBoxLayout()
        row_frame.addWidget(QLabel("Frame :"))
        self.spin_frame = QSpinBox()
        self.spin_frame.setRange(1, 999999)
        self.spin_frame.setValue(1)
        row_frame.addWidget(self.spin_frame)

        self.btn_preview_frame = QPushButton("Prévisualiser frame")
        self.btn_preview_frame.clicked.connect(self.on_preview_frame)
        row_frame.addWidget(self.btn_preview_frame)
        row_frame.addStretch()
        pipe_layout.addLayout(row_frame)

        # Ligne état tâche
        row_task = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        row_task.addWidget(self.progress_bar)

        self.btn_run_all = QPushButton("Exécuter les 4 étapes du pipeline")
        self.btn_run_all.clicked.connect(self.on_execute_all_task)
        row_task.addWidget(self.btn_run_all)

        self.btn_cancel = QPushButton("Annuler la tâche en cours")
        self.btn_cancel.clicked.connect(self.on_cancel_task)
        self.btn_cancel.setEnabled(False)
        row_task.addWidget(self.btn_cancel)

        pipe_layout.addLayout(row_task)

        # ---- Colonnes des steps + previews ----
        cols_layout = QHBoxLayout()

        # Colonne FFmpeg
        col1 = QVBoxLayout()
        step1_group = QGroupBox("1. FFmpeg → PNG")
        s1_layout = QVBoxLayout(step1_group)
        self.btn_ffmpeg = QPushButton("Lancer FFmpeg")
        self.btn_ffmpeg.clicked.connect(self.on_ffmpeg_click)
        s1_layout.addWidget(self.btn_ffmpeg)
        s1_layout.addStretch()
        col1.addWidget(step1_group)

        prev1_group = QGroupBox("Prévisualisation PNG")
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
        self.btn_bmp.clicked.connect(self.on_bmp_click)
        s2_layout.addWidget(self.btn_bmp)
        s2_layout.addStretch()
        col2.addWidget(step2_group)

        prev2_group = QGroupBox("Prévisualisation BMP")
        p2_layout = QVBoxLayout(prev2_group)
        self.preview_bmp = RasterPreview()
        self.preview_bmp.setMinimumSize(240, 180)
        p2_layout.addWidget(self.preview_bmp)
        col2.addWidget(prev2_group)

        col2_widget = QWidget()
        col2_widget.setLayout(col2)
        col2_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col2_widget)

        # Colonne SVG
        col3 = QVBoxLayout()
        step3_group = QGroupBox("3. Vectorisation (Potrace)")
        s3_layout = QVBoxLayout(step3_group)
        self.btn_potrace = QPushButton("Lancer Potrace")
        self.btn_potrace.clicked.connect(self.on_potrace_click)
        s3_layout.addWidget(self.btn_potrace)
        s3_layout.addStretch()
        col3.addWidget(step3_group)

        prev3_group = QGroupBox("Prévisualisation SVG")
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
        row_mode.addWidget(QLabel("Profil :"))
        self.combo_ilda_mode = QComboBox()
        self.combo_ilda_mode.addItem("Classique (noir & blanc)", "classic")
        self.combo_ilda_mode.addItem("Arcade (expérimental)", "arcade")
        self.combo_ilda_mode.setCurrentIndex(0)
        row_mode.addWidget(self.combo_ilda_mode)
        s4_layout.addLayout(row_mode)

        self.btn_ilda = QPushButton("Exporter ILDA")
        self.btn_ilda.clicked.connect(self.on_export_ilda_click)
        s4_layout.addWidget(self.btn_ilda)
        s4_layout.addStretch()
        col4.addWidget(step4_group)

        prev4_group = QGroupBox("Prévisualisation ILDA")
        p4_layout = QVBoxLayout(prev4_group)
        self.preview_ilda = RasterPreview()
        self.preview_ilda.setMinimumSize(240, 180)
        p4_layout.addWidget(self.preview_ilda)
        col4.addWidget(prev4_group)

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

    # ---------------- Utilitaires log / busy ---------------------

    def log(self, text: str) -> None:
        ts = datetime.now().strftime("[%H:%M:%S]")
        self.log_view.append(f"{ts} {text}")
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.ensureCursorVisible()

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.btn_cancel.setEnabled(True)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(False)
            self.btn_cancel.setEnabled(False)

    # ---------------- Slots pipeline -----------------------------

    @Slot(str)
    def on_step_started(self, step_name: str) -> None:
        self.set_busy(True)

    @Slot(str, object)
    def on_step_finished(self, step_name: str, result: object) -> None:
        self.set_busy(False)
        msg = getattr(result, "message", "")
        if msg:
            self.log(f"[{step_name}] {msg}")

        if step_name in ("ilda", "full_pipeline") and getattr(result, "success", False):
            project = (self.edit_project.text() or "").strip()
            if project:
                self._update_ilda_preview(project)

    @Slot(str, str)
    def on_step_error(self, step_name: str, message: str) -> None:
        self.set_busy(False)
        self.log(f"[{step_name}] ERREUR : {message}")

    @Slot(str, object)
    def on_step_progress(self, step_name: str, payload: object) -> None:
        if not isinstance(payload, FrameProgress):
            return
        fp: FrameProgress = payload

        if fp.total_frames is not None and fp.total_frames > 0:
            self.progress_bar.setRange(0, 100)
            pct = int((fp.frame_index + 1) * 100 / fp.total_frames)
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

    # ---------------- Callbacks UI -------------------------------

    def choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une vidéo",
            "",
            "Vidéos (*.mp4 *.mov *.avi);;Tous les fichiers (*)",
        )
        if path:
            self.edit_video_path.setText(path)
            self.log(f"Vidéo sélectionnée : {path}")

    def on_new_project(self) -> None:
        """Create a new project directory structure under `PROJECTS_ROOT`.

        Prompts for a project name, creates subfolders and sets the project
        name in the UI if successful.
        """
        name, ok = QInputDialog.getText(self, "Créer un projet", "Nom du projet:")
        if not ok:
            return
        project = (name or "").strip()
        if not project:
            self.log("Erreur : nom de projet vide.")
            return

        project_root = PROJECTS_ROOT / project
        subdirs = ["frames", "bmp", "svg", "ilda", "preview"]
        try:
            for d in subdirs:
                (project_root / d).mkdir(parents=True, exist_ok=True)
            self.edit_project.setText(project)
            self.log(f"Projet créé : {project_root}")
        except Exception as e:
            self.log(f"Erreur création projet : {e}")

    def on_about(self) -> None:
        QMessageBox.about(
            self,
            "About Laser Pipeline GUI",
            "Laser Pipeline GUI\n\nExperimental video → ILDA pipeline. See README.md for details.",
        )

    def on_test_click(self) -> None:
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        self.log("=== Paramètres actuels ===")
        self.log(f"Vidéo : {video or '<aucune>'}")
        self.log(f"Projet : {project or '<vide>'}")
        self.log(f"FPS    : {fps}")
        self.log("================================")

    def on_ffmpeg_click(self) -> None:
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        if not video:
            self.log("Erreur FFmpeg : aucun fichier vidéo sélectionné.")
            return
        if not project:
            self.log("Erreur FFmpeg : nom de projet vide.")
            return

        self.log("[FFmpeg] Démarrage extraction frames…")
        self.pipeline.start_ffmpeg(video, project, fps)

    def on_bmp_click(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur BMP : nom de projet vide.")
            return

        threshold = self.spin_bmp_threshold.value()
        thinning = self.check_bmp_thinning.isChecked()
        max_frames_val = self.spin_bmp_max_frames.value()
        max_frames = max_frames_val if max_frames_val > 0 else None

        self.log(
            f"[BMP] Conversion PNG -> BMP (threshold={threshold}%, "
            f"thinning={thinning}, max_frames={max_frames or 'toutes'})…"
        )
        self.pipeline.start_bitmap(project, threshold, thinning, max_frames)

    def on_potrace_click(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur Potrace : nom de projet vide.")
            return
        self.log(f"[Potrace] Vectorisation BMP -> SVG pour '{project}'…")
        self.pipeline.start_potrace(project)

    def on_export_ilda_click(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur ILDA : nom de projet vide.")
            return

        mode_key = self.combo_ilda_mode.currentData() or "classic"
        mode_label = self.combo_ilda_mode.currentText()
        self.log(f"[ILDA] Export ILDA (profil={mode_label})…")
        self.pipeline.start_ilda(project, ilda_mode=mode_key)

    def on_cancel_task(self) -> None:
        self.btn_cancel.setEnabled(False)
        self.pipeline.cancel_current_step()

    # ---------------- Preview helpers ----------------------------

    def _update_ilda_preview(self, project: str) -> None:
        project_root = PROJECTS_ROOT / project
        svg_dir = project_root / "svg"
        svg_files = sorted(svg_dir.glob("frame_*.svg"))
        if svg_files:
            self.preview_svg.show_svg(str(svg_files[0]))
            self.log(f"[Preview] SVG : {svg_files[0]}")

        preview_dir = project_root / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        ilda_path = project_root / "ilda" / f"{project}.ild"
        if ilda_path.exists():
            out_png = preview_dir / "ilda_preview.png"
            try:
                render_ilda_preview(ilda_path, out_png, frame_index=0)
                self.preview_ilda.show_image(str(out_png))
                self.log(f"[Preview] ILDA : {out_png}")
            except Exception as e:
                self.log(f"[Preview] Impossible de générer la preview ILDA : {e}")

    def on_preview_frame(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur preview : nom de projet vide.")
            return

        frame_index = self.spin_frame.value()
        project_root = PROJECTS_ROOT / project
        png = project_root / "frames" / f"frame_{frame_index:04d}.png"
        bmp = project_root / "bmp" / f"frame_{frame_index:04d}.bmp"
        svg = project_root / "svg" / f"frame_{frame_index:04d}.svg"

        if png.exists():
            self.preview_png.show_image(str(png))
            self.log(f"[Preview] PNG : {png}")
        if bmp.exists():
            self.preview_bmp.show_image(str(bmp))
            self.log(f"[Preview] BMP : {bmp}")
        if svg.exists():
            self.preview_svg.show_svg(str(svg))
            self.log(f"[Preview] SVG : {svg}")

        ilda_path = project_root / "ilda" / f"{project}.ild"
        if ilda_path.exists():
            preview_dir = project_root / "preview"
            preview_dir.mkdir(parents=True, exist_ok=True)
            out_png = preview_dir / f"ilda_preview_{frame_index:04d}.png"
            try:
                render_ilda_preview(ilda_path, out_png, frame_index=max(frame_index - 1, 0))
                self.preview_ilda.show_image(str(out_png))
                self.log(f"[Preview] ILDA frame {frame_index} : {out_png}")
            except Exception as e:
                self.log(f"[Preview] Impossible de générer la preview ILDA frame {frame_index} : {e}")
        else:
            self.log("[Preview] Aucun fichier ILDA trouvé pour cette frame.")

    # ---------------- Full pipeline ------------------------------

    def on_execute_all_task(self) -> None:
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        if not video:
            self.log("Erreur : aucun fichier vidéo sélectionnée.")
            return
        if not project:
            self.log("Erreur : nom de projet vide.")
            return

        threshold = self.spin_bmp_threshold.value()
        thinning = self.check_bmp_thinning.isChecked()
        max_frames_val = self.spin_bmp_max_frames.value()
        max_frames = max_frames_val if max_frames_val > 0 else None
        mode_key = self.combo_ilda_mode.currentData() or "classic"
        mode_label = self.combo_ilda_mode.currentText()

        self.log("Démarrage du pipeline complet (4 steps)…")
        self.log(f"  Vidéo   : {video}")
        self.log(f"  Projet  : {project}")
        self.log(f"  FPS     : {fps}")
        self.log(
            f"  Bitmap  : threshold={threshold}%, thinning={thinning}, "
            f"max_frames={max_frames or 'toutes'}"
        )
        self.log(f"  ILDA    : profil={mode_label} ({mode_key})")

        self.pipeline.start_full_pipeline(
            video_path=video,
            project=project,
            fps=fps,
            threshold=threshold,
            use_thinning=thinning,
            max_frames=max_frames,
            ilda_mode=mode_key,
        )


def run() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    sys.exit(app.exec())
