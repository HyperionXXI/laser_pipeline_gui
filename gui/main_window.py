from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

from core.pipeline.base import FrameProgress
from core.config import PROJECTS_ROOT

from .preview_widgets import RasterPreview, SvgPreview
from .pipeline_controller import PipelineController

from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QProgressBar,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Laser Pipeline GUI")

        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ================================================================
        # 1) Paramètres généraux
        # ================================================================
        group_general = QGroupBox("Paramètres généraux", self)
        general_layout = QVBoxLayout(group_general)

        # Ligne vidéo
        row_video = QHBoxLayout()
        row_video.addWidget(QLabel("Vidéo source :"))
        self.edit_video_path = QLineEdit()
        row_video.addWidget(self.edit_video_path)
        btn_browse = QPushButton("Parcourir…")
        btn_browse.clicked.connect(self.choose_video)
        row_video.addWidget(btn_browse)
        general_layout.addLayout(row_video)

        # Ligne projet
        row_project = QHBoxLayout()
        row_project.addWidget(QLabel("Nom du projet :"))
        self.edit_project = QLineEdit("projet_demo")
        row_project.addWidget(self.edit_project)
        general_layout.addLayout(row_project)

        # Ligne FPS
        row_fps = QHBoxLayout()
        row_fps.addWidget(QLabel("FPS :"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 200)
        self.spin_fps.setValue(25)
        row_fps.addWidget(self.spin_fps)
        general_layout.addLayout(row_fps)

        # Bouton test
        btn_test = QPushButton("Tester les paramètres")
        btn_test.clicked.connect(self.on_test_click)
        general_layout.addWidget(btn_test)

        main_layout.addWidget(group_general)

        # ================================================================
        # 2) Pipeline vidéo → vecteur
        # ================================================================
        group_pipeline = QGroupBox("Pipeline vidéo → vecteur", self)
        pipeline_layout = QVBoxLayout(group_pipeline)

        # Ligne frame + bouton prévisualiser
        row_frame = QHBoxLayout()
        row_frame.addWidget(QLabel("Frame :"))
        self.spin_frame = QSpinBox()
        self.spin_frame.setRange(1, 99999)
        row_frame.addWidget(self.spin_frame)

        self.btn_preview = QPushButton("Prévisualiser frame")
        self.btn_preview.clicked.connect(self.on_preview_frame)
        row_frame.addWidget(self.btn_preview)

        row_frame.addStretch()
        pipeline_layout.addLayout(row_frame)

        # Ligne état de tâche (progress bar + annulation)
        row_task = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        row_task.addWidget(self.progress_bar)

        self.btn_cancel_task = QPushButton("Annuler la tâche en cours")
        self.btn_cancel_task.clicked.connect(self.on_cancel_task)
        self.btn_cancel_task.setEnabled(False)
        row_task.addWidget(self.btn_cancel_task)

        pipeline_layout.addLayout(row_task)

        # ---- 4 colonnes ----
        cols_layout = QHBoxLayout()

        # Colonne 1 : FFmpeg
        col1_layout = QVBoxLayout()
        group_step1 = QGroupBox("1. FFmpeg → PNG (frames)")
        step1_layout = QVBoxLayout(group_step1)
        self.btn_ffmpeg = QPushButton("Lancer FFmpeg")
        self.btn_ffmpeg.clicked.connect(self.on_ffmpeg_click)
        step1_layout.addWidget(self.btn_ffmpeg)
        step1_layout.addStretch()
        col1_layout.addWidget(group_step1)

        group_prev1 = QGroupBox("Prévisualisation PNG (frames)")
        prev1_layout = QVBoxLayout(group_prev1)
        self.preview_png = RasterPreview()
        self.preview_png.setMinimumSize(240, 180)
        prev1_layout.addWidget(self.preview_png)
        col1_layout.addWidget(group_prev1)

        col1_widget = QWidget()
        col1_widget.setLayout(col1_layout)
        col1_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col1_widget)

        # Colonne 2 : Bitmap
        col2_layout = QVBoxLayout()
        group_step2 = QGroupBox("2. Bitmap (ImageMagick)")
        step2_layout = QVBoxLayout(group_step2)

        row_bmp = QHBoxLayout()
        row_bmp.addWidget(QLabel("Seuil (%):"))
        self.spin_bmp_threshold = QSpinBox()
        self.spin_bmp_threshold.setRange(0, 100)
        self.spin_bmp_threshold.setValue(60)
        row_bmp.addWidget(self.spin_bmp_threshold)

        self.check_bmp_thinning = QCheckBox("Thinning")
        self.check_bmp_thinning.setChecked(False)
        row_bmp.addWidget(self.check_bmp_thinning)

        row_bmp.addWidget(QLabel("Max frames (0 = toutes) :"))
        self.spin_bmp_max_frames = QSpinBox()
        self.spin_bmp_max_frames.setRange(0, 100000)
        self.spin_bmp_max_frames.setValue(0)
        row_bmp.addWidget(self.spin_bmp_max_frames)

        row_bmp.addStretch()
        step2_layout.addLayout(row_bmp)

        self.btn_bmp = QPushButton("Lancer Bitmap")
        self.btn_bmp.clicked.connect(self.on_bmp_click)
        step2_layout.addWidget(self.btn_bmp)
        step2_layout.addStretch()
        col2_layout.addWidget(group_step2)

        group_prev2 = QGroupBox("Prévisualisation BMP (bitmap)")
        prev2_layout = QVBoxLayout(group_prev2)
        self.preview_bmp = RasterPreview()
        self.preview_bmp.setMinimumSize(240, 180)
        prev2_layout.addWidget(self.preview_bmp)
        col2_layout.addWidget(group_prev2)

        col2_widget = QWidget()
        col2_widget.setLayout(col2_layout)
        col2_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col2_widget)

        # Colonne 3 : Potrace / SVG
        col3_layout = QVBoxLayout()
        group_step3 = QGroupBox("3. Vectorisation (Potrace)")
        step3_layout = QVBoxLayout(group_step3)
        self.btn_potrace = QPushButton("Lancer Potrace")
        self.btn_potrace.clicked.connect(self.on_potrace_click)
        step3_layout.addWidget(self.btn_potrace)
        step3_layout.addStretch()
        col3_layout.addWidget(group_step3)

        group_prev3 = QGroupBox("Prévisualisation SVG (vectorisé)")
        prev3_layout = QVBoxLayout(group_prev3)
        self.preview_svg = SvgPreview()
        self.preview_svg.setMinimumSize(240, 180)
        prev3_layout.addWidget(self.preview_svg)
        col3_layout.addWidget(group_prev3)

        col3_widget = QWidget()
        col3_widget.setLayout(col3_layout)
        col3_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col3_widget)

        # Colonne 4 : ILDA
        col4_layout = QVBoxLayout()
        group_step4 = QGroupBox("4. ILDA (export)")
        step4_layout = QVBoxLayout(group_step4)
        self.btn_ilda = QPushButton("Exporter ILDA")
        self.btn_ilda.clicked.connect(self.on_export_ilda_click)
        step4_layout.addWidget(self.btn_ilda)
        step4_layout.addStretch()
        col4_layout.addWidget(group_step4)

        group_prev4 = QGroupBox("Prévisualisation ILDA (fichier .ild)")
        prev4_layout = QVBoxLayout(group_prev4)
        self.preview_ilda = RasterPreview()
        self.preview_ilda.setMinimumSize(240, 180)
        prev4_layout.addWidget(self.preview_ilda)
        col4_layout.addWidget(group_prev4)

        col4_widget = QWidget()
        col4_widget.setLayout(col4_layout)
        col4_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        cols_layout.addWidget(col4_widget)

        pipeline_layout.addLayout(cols_layout)
        main_layout.addWidget(group_pipeline)

        # ================================================================
        # 3) Log
        # ================================================================
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        main_layout.addWidget(self.log_view)

        # ------------------------------------------------------------
        # PipelineController
        # ------------------------------------------------------------
        self.pipeline = PipelineController(parent=self, log_fn=self.log)
        self.pipeline.step_started.connect(self.on_step_started)
        self.pipeline.step_finished.connect(self.on_step_finished)
        self.pipeline.step_error.connect(self.on_step_error)
        self.pipeline.step_progress.connect(self.on_step_progress)

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def log(self, text: str) -> None:
        ts = datetime.now().strftime("[%H:%M:%S]")
        self.log_view.append(f"{ts} {text}")
        # Auto-scroll vers la dernière ligne
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.ensureCursorVisible()


    def set_busy(self, busy: bool) -> None:
        if busy:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # indéterminé
            self.btn_cancel_task.setEnabled(True)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(False)
            self.btn_cancel_task.setEnabled(False)

    # ------------------------------------------------------------------
    # Slots liés au PipelineController
    # ------------------------------------------------------------------

    @Slot(str)
    def on_step_started(self, step_name: str) -> None:
        self.set_busy(True)

    @Slot(str, object)
    def on_step_finished(self, step_name: str, result) -> None:
        """
        Step terminé (succès).
        On arrête le mode busy et on log le message final.
        Les previews image par image sont déjà gérées par on_step_progress.
        """
        self.set_busy(False)

        msg = getattr(result, "message", "")
        if msg:
            self.log(f"[{step_name}] {msg}")

        # Mise à jour de la preview ILDA quand l'export est terminé
        if step_name == "ilda" and getattr(result, "success", False):
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

        # 1) Progress bar
        if fp.total_frames is not None and fp.total_frames > 0:
            self.progress_bar.setRange(0, 100)
            percent = int((fp.frame_index + 1) * 100 / fp.total_frames)
            self.progress_bar.setValue(percent)
        else:
            self.progress_bar.setRange(0, 0)  # indéterminé

        # 2) Preview progressive
        if not fp.frame_path:
            return

        path_str = str(fp.frame_path)

        if step_name == "ffmpeg":
            self.preview_png.show_image(path_str)
        elif step_name == "bitmap":
            self.preview_bmp.show_image(path_str)
        elif step_name == "potrace":
            self.preview_svg.show_svg(path_str)
        elif step_name == "ilda":
            # Désormais on reçoit un PNG généré depuis le fichier .ild
            self.preview_ilda.show_image(path_str)


    # ------------------------------------------------------------------
    # Callbacks UI
    # ------------------------------------------------------------------

    def choose_video(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une vidéo",
            "",
            "Vidéos (*.mp4 *.mov *.avi);;Tous les fichiers (*)",
        )
        if path:
            self.edit_video_path.setText(path)
            self.log(f"Vidéo sélectionnée : {path}")

    def on_test_click(self) -> None:
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        if not video:
            self.log("Erreur : aucune vidéo sélectionnée.")
            return
        if not project:
            self.log("Erreur : nom de projet vide.")
            return

        self.log("=== Paramètres actuels ===")
        self.log(f"Vidéo : {video}")
        self.log(f"Projet : {project}")
        self.log(f"FPS : {fps}")
        self.log("==========================")

    def on_ffmpeg_click(self) -> None:
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        if not video:
            self.log("Erreur FFmpeg : aucun fichier vidéo sélectionnée.")
            return
        if not project:
            self.log("Erreur FFmpeg : nom de projet vide.")
            return

        self.log("[FFmpeg] Démarrage extraction frames...")
        self.log(f"  Vidéo  : {video}")
        self.log(f"  Projet : {project}")
        self.log(f"  FPS    : {fps}")

        self.pipeline.start_ffmpeg(video, project, fps)

    def on_bmp_click(self) -> None:
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur BMP : nom de projet vide.")
            return

        threshold = self.spin_bmp_threshold.value()
        use_thinning = self.check_bmp_thinning.isChecked()
        max_frames_value = self.spin_bmp_max_frames.value()
        max_frames = max_frames_value if max_frames_value > 0 else None

        self.log(
            f"[BMP] Conversion PNG -> BMP pour le projet '{project}' "
            f"(threshold={threshold}%, thinning={use_thinning}, "
            f"max_frames={max_frames or 'toutes'})..."
        )

        self.pipeline.start_bitmap(
            project,
            threshold=threshold,
            use_thinning=use_thinning,
            max_frames=max_frames,
        )

    def on_potrace_click(self) -> None:
        """Lance la vectorisation BMP -> SVG via Potrace (pipeline)."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur Potrace : nom de projet vide.")
            return

        self.log(f"[Potrace] Vectorisation BMP -> SVG pour le projet '{project}'...")
        self.pipeline.start_potrace(project)

    def on_export_ilda_click(self) -> None:
        """
        Lance l'export ILDA via le pipeline (step 'ilda').
        """
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur ILDA : nom de projet vide.")
            return

        self.log(f"[ILDA] Export ILDA pour le projet '{project}' (pipeline)…")
        # Nécessite que PipelineController expose start_ilda(project)
        self.pipeline.start_ilda(project)

    # ------------------------------------------------------------------
    # Helpers et preview manuelle
    # ------------------------------------------------------------------

    def _update_ilda_preview(self, project: str) -> None:
        """
        Met à jour la prévisualisation ILDA après un export.

        On ne rasterise toujours pas directement le .ild, donc on affiche
        la première frame SVG comme approximation de la sortie ILDA.
        """
        project_root = PROJECTS_ROOT / project
        svg_dir = project_root / "svg"
        first_svg = self._find_first_frame(svg_dir, pattern="frame_*.svg")

        if first_svg:
            self.preview_svg.show_svg(str(first_svg))
            self.log(f"[Preview] SVG : {first_svg}")
        else:
            self.log("[Preview] Aucune frame SVG trouvée pour la preview.")

        # Preview ILDA seulement si une image a déjà été générée
        ilda_preview_png = project_root / "preview" / "ilda_preview.png"
        if ilda_preview_png.exists():
            self.preview_ilda.show_image(str(ilda_preview_png))
            self.log(f"[Preview] ILDA à partir de : {ilda_preview_png}")
        else:
            self.log("[Preview] Pas encore de preview ILDA (exportez d'abord).")


    def on_preview_frame(self) -> None:
        """
        Prévisualise une frame donnée (index dans self.spin_frame)
        pour les trois étapes intermédiaires : PNG, BMP, SVG.
        """
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur prévisualisation : nom de projet vide.")
            return

        frame_index = self.spin_frame.value()

        project_root = PROJECTS_ROOT / project
        png_dir = project_root / "frames"
        bmp_dir = project_root / "bmp"
        svg_dir = project_root / "svg"

        png_path = png_dir / f"frame_{frame_index:04d}.png"
        bmp_path = bmp_dir / f"frame_{frame_index:04d}.bmp"
        svg_path = svg_dir / f"frame_{frame_index:04d}.svg"

        # PNG
        self.log(f"[Preview] Frame {frame_index} (PNG) → {png_path}")
        self.preview_png.show_image(str(png_path))

        # BMP
        self.log(f"[Preview] Frame {frame_index} (BMP) → {bmp_path}")
        self.preview_bmp.show_image(str(bmp_path))

        # SVG
        self.log(f"[Preview] Frame {frame_index} (SVG) → {svg_path}")
        self.preview_svg.show_svg(str(svg_path))

    def on_cancel_task(self) -> None:
        """
        Demande l'annulation du step en cours au PipelineController.
        """
        self.pipeline.cancel_current_step()

    # ------------------------------------------------------------------
    # Helpers pour trouver la "dernière" ou "première" frame d'un dossier
    # ------------------------------------------------------------------

    def _find_last_frame(
        self, directory: Path, pattern: str = "frame_*.png"
    ) -> Path | None:
        if not directory.exists():
            return None
        files = sorted(directory.glob(pattern))
        return files[-1] if files else None

    def _find_first_frame(
        self, directory: Path, pattern: str = "frame_*.png"
    ) -> Path | None:
        if not directory.exists():
            return None
        files = sorted(directory.glob(pattern))
        return files[0] if files else None


def run() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    sys.exit(app.exec())
