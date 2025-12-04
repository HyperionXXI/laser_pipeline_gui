# gui/main_window.py

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal, Slot, QThread
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QSpinBox,
    QCheckBox,
    QGroupBox,
    QSizePolicy,
    QProgressBar,
    
)

from core.step_ffmpeg import extract_frames
from core.step_bitmap import convert_project_frames_to_bmp
from core.step_potrace import bitmap_to_svg_folder
from core.step_ilda import export_project_to_ilda
from core.ilda_writer import write_ilda_file, IldaPoint
from core.config import PROJECTS_ROOT
from .preview_widgets import RasterPreview, SvgPreview


# ---------------------------------------------------------------------------
# Worker générique pour exécuter une fonction lourde dans un QThread.
# ---------------------------------------------------------------------------

class Worker(QObject):
    """
    Worker générique pour exécuter une fonction lourde dans un QThread.
    """
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        try:
            # IMPORTANT : on n'injecte PAS self dans les arguments
            result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.error.emit(str(e))
        else:
            self.finished.emit(result)




# ---------------------------------------------------------------------------
# Fenêtre principale
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Laser Pipeline - Prototype GUI")

        central = QWidget()
        main_layout = QVBoxLayout(central)

        # ================================================================
        # 1) GROUPE : PARAMÈTRES GÉNÉRAUX (en haut, pleine largeur)
        # ================================================================
        group_general = QGroupBox("Paramètres généraux")
        general_layout = QVBoxLayout(group_general)

        # Ligne vidéo
        row_video = QHBoxLayout()
        row_video.addWidget(QLabel("Vidéo source :"))
        self.edit_video_path = QLineEdit()
        row_video.addWidget(self.edit_video_path)

        self.btn_browse = QPushButton("Parcourir…")
        self.btn_browse.clicked.connect(self.choose_video)
        row_video.addWidget(self.btn_browse)
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

        # Bouton de test des paramètres
        self.btn_test = QPushButton("Tester les paramètres")
        self.btn_test.clicked.connect(self.on_test_click)
        general_layout.addWidget(self.btn_test)

        main_layout.addWidget(group_general)

        # ================================================================
        # 2) GROUPE : PIPELINE VIDÉO → VECTEUR
        #    → 3 colonnes : (1) FFmpeg, (2) Bitmap, (3) Vectorisation
        # ================================================================
        group_pipeline = QGroupBox("Pipeline vidéo → vecteur")
        pipeline_layout = QVBoxLayout(group_pipeline)

        # ---- Ligne : sélection de frame + bouton Prévisualiser ----
        row_frame = QHBoxLayout()
        row_frame.addWidget(QLabel("Frame :"))

        self.spin_frame = QSpinBox()
        self.spin_frame.setMinimum(1)
        self.spin_frame.setMaximum(99999)
        row_frame.addWidget(self.spin_frame)

        # On met le bouton juste après le spin, sans gros espace au milieu
        self.btn_preview = QPushButton("Prévisualiser frame")
        self.btn_preview.clicked.connect(self.on_preview_frame)
        row_frame.addWidget(self.btn_preview)

        row_frame.addStretch()


        pipeline_layout.addLayout(row_frame)
                # ---- Ligne : état de la tâche (progression + annulation) ----
        row_task = QHBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)

        self.btn_cancel_task = QPushButton("Annuler la tâche en cours")
        self.btn_cancel_task.setEnabled(False)
        self.btn_cancel_task.clicked.connect(self.on_cancel_task)

        row_task.addWidget(self.progress_bar)
        row_task.addWidget(self.btn_cancel_task)

        pipeline_layout.addLayout(row_task)


        # ---- Ligne : 4 colonnes (paramètres + preview) ----
        cols_layout = QHBoxLayout()

        # ------------------------------------------------------------
        # Colonne 1 : FFmpeg → PNG (frames)
        # ------------------------------------------------------------
        col1_layout = QVBoxLayout()

        group_step1_params = QGroupBox("1. FFmpeg → PNG (frames)")
        step1_layout = QVBoxLayout(group_step1_params)

        self.btn_ffmpeg = QPushButton("Lancer FFmpeg")
        self.btn_ffmpeg.clicked.connect(self.on_ffmpeg_click)
        step1_layout.addWidget(self.btn_ffmpeg)
        step1_layout.addStretch()

        col1_layout.addWidget(group_step1_params)

        group_step1_preview = QGroupBox("Prévisualisation PNG (frames)")
        step1_prev_layout = QVBoxLayout(group_step1_preview)

        self.preview_png = RasterPreview()
        self.preview_png.setMinimumSize(240, 180)
        step1_prev_layout.addWidget(self.preview_png)

        col1_layout.addWidget(group_step1_preview)

        col1_widget = QWidget()
        col1_widget.setLayout(col1_layout)

        # ------------------------------------------------------------
        # Colonne 2 : Bitmap (ImageMagick)
        # ------------------------------------------------------------
        col2_layout = QVBoxLayout()

        group_step2_params = QGroupBox("2. Bitmap (ImageMagick)")
        step2_layout = QVBoxLayout(group_step2_params)

        row_bmp_params = QHBoxLayout()
        row_bmp_params.addWidget(QLabel("Seuil (%):"))

        self.spin_bmp_threshold = QSpinBox()
        self.spin_bmp_threshold.setRange(0, 100)
        self.spin_bmp_threshold.setValue(60)
        row_bmp_params.addWidget(self.spin_bmp_threshold)

        self.check_bmp_thinning = QCheckBox("Thinning")
        self.check_bmp_thinning.setChecked(False)
        row_bmp_params.addWidget(self.check_bmp_thinning)

        row_bmp_params.addWidget(QLabel("Max frames (0 = toutes) :"))
        self.spin_bmp_max_frames = QSpinBox()
        self.spin_bmp_max_frames.setRange(0, 100000)
        self.spin_bmp_max_frames.setValue(0)
        row_bmp_params.addWidget(self.spin_bmp_max_frames)

        row_bmp_params.addStretch()
        step2_layout.addLayout(row_bmp_params)

        self.btn_bmp = QPushButton("Lancer Bitmap")
        self.btn_bmp.clicked.connect(self.on_bmp_click)
        step2_layout.addWidget(self.btn_bmp)
        step2_layout.addStretch()

        col2_layout.addWidget(group_step2_params)

        group_step2_preview = QGroupBox("Prévisualisation BMP (bitmap)")
        step2_prev_layout = QVBoxLayout(group_step2_preview)

        self.preview_bmp = RasterPreview()
        self.preview_bmp.setMinimumSize(240, 180)
        step2_prev_layout.addWidget(self.preview_bmp)

        col2_layout.addWidget(group_step2_preview)

        col2_widget = QWidget()
        col2_widget.setLayout(col2_layout)

        # ------------------------------------------------------------
        # Colonne 3 : Vectorisation (Potrace / SVG)
        # ------------------------------------------------------------
        col3_layout = QVBoxLayout()

        group_step3_params = QGroupBox("3. Vectorisation (Potrace)")
        step3_layout = QVBoxLayout(group_step3_params)

        self.btn_potrace = QPushButton("Lancer Potrace")
        self.btn_potrace.clicked.connect(self.on_potrace_click)
        step3_layout.addWidget(self.btn_potrace)
        step3_layout.addStretch()

        col3_layout.addWidget(group_step3_params)

        group_step3_preview = QGroupBox("Prévisualisation SVG (vectorisé)")
        step3_prev_layout = QVBoxLayout(group_step3_preview)

        self.preview_svg = SvgPreview()
        self.preview_svg.setMinimumSize(240, 180)
        step3_prev_layout.addWidget(self.preview_svg)

        col3_layout.addWidget(group_step3_preview)

        col3_widget = QWidget()
        col3_widget.setLayout(col3_layout)

        # ------------------------------------------------------------
        # Colonne 4 : ILDA (export)
        # ------------------------------------------------------------
        col4_layout = QVBoxLayout()

        group_step4_params = QGroupBox("4. ILDA (export)")
        step4_layout = QVBoxLayout(group_step4_params)

        self.btn_ilda = QPushButton("Exporter ILDA")
        self.btn_ilda.clicked.connect(self.on_export_ilda_click)
        step4_layout.addWidget(self.btn_ilda)
        step4_layout.addStretch()

        col4_layout.addWidget(group_step4_params)

        group_step4_preview = QGroupBox("Prévisualisation ILDA")
        step4_prev_layout = QVBoxLayout(group_step4_preview)

        self.preview_ilda = RasterPreview()
        self.preview_ilda.setMinimumSize(240, 180)
        step4_prev_layout.addWidget(self.preview_ilda)

        col4_layout.addWidget(group_step4_preview)

        col4_widget = QWidget()
        col4_widget.setLayout(col4_layout)

        # ---- Ajout des 4 colonnes dans le layout horizontal ----
        for w in (col1_widget, col2_widget, col3_widget, col4_widget):
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            cols_layout.addWidget(w, 1)  # stretch = 1 pour chacun

        pipeline_layout.addLayout(cols_layout)


        main_layout.addWidget(group_pipeline)

        # ================================================================
        # 3) ZONE DE LOG (en bas, pleine largeur)
        # ================================================================
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        main_layout.addWidget(self.log_view)

        self.setCentralWidget(central)

        # Pour garder les threads vivants (et pouvoir les arrêter proprement)
        self._threads = []

    # ------------------------------------------------------------------
    # Utilitaires UI / threads
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool):
        widgets = [
            getattr(self, "btn_test", None),
            getattr(self, "btn_ffmpeg", None),
            getattr(self, "btn_bmp", None),
            getattr(self, "btn_potrace", None),
            getattr(self, "btn_preview", None),
            getattr(self, "btn_browse", None),
        ]

        for w in widgets:
            if w is not None:
                w.setEnabled(not busy)

        if busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.progress_bar.setVisible(True)
            self.btn_cancel_task.setEnabled(True)
        else:
            QApplication.restoreOverrideCursor()
            self.btn_cancel_task.setEnabled(False)

        QApplication.processEvents()


    def start_worker(self, func, finished_cb, step_label, *args, **kwargs):
        """
        Lance func(*args, **kwargs) dans un QThread.
        """
        self.set_busy(True)

        thread = QThread(self)
        worker = Worker(func, *args, **kwargs)
        worker.moveToThread(thread)

        def on_finished(result):
            try:
                finished_cb(result)
            finally:
                self.set_busy(False)
                thread.quit()
                thread.wait()
                worker.deleteLater()
                thread.deleteLater()

        def on_error(message: str):
            self.log(f"[{step_label}] ERREUR : {message}")
            self.set_busy(False)
            thread.quit()
            thread.wait()
            worker.deleteLater()
            thread.deleteLater()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.start()

        self._current_thread = thread
        self._current_worker = worker


    def on_worker_progress(self, value: int):
        self.progress_bar.setValue(value)



    # ------------------------------------------------------------------
    # Callbacks & logique métier
    # ------------------------------------------------------------------

    def log(self, text: str):
        """Ajoute une ligne dans la zone de log."""
        self.log_view.append(text)

    def choose_video(self):
        """Ouvre une boîte de dialogue pour choisir un fichier vidéo."""
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

    def stop_all_threads(self):
        """
        Demande à tous les QThread encore actifs de s'arrêter proprement,
        puis attend leur fin.
        """
        for thread in self._threads:
            if thread.isRunning():
                thread.quit()
                thread.wait()  # bloque jusqu'à arrêt du thread
        self._threads.clear()

    def closeEvent(self, event):
        thread = getattr(self, "_current_thread", None)
        worker = getattr(self, "_current_worker", None)

        if thread is not None and thread.isRunning():
            if worker is not None:
                worker.cancel()
            thread.quit()
            thread.wait(3000)  # timeout raisonnable

        super().closeEvent(event)

    def on_test_click(self):
        """Vérifie les paramètres entrés et les affiche dans le log."""
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

    def on_ffmpeg_click(self):
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        if not video:
            self.log("Erreur FFmpeg : aucun fichier vidéo sélectionné.")
            return
        if not project:
            self.log("Erreur FFmpeg : nom de projet vide.")
            return

        self.log("[FFmpeg] Démarrage extraction frames...")
        self.log(f"  Vidéo  : {video}")
        self.log(f"  Projet : {project}")
        self.log(f"  FPS    : {fps}")

        def job(worker: Worker):
            # étape 1 : on signale 0%
            worker.report_progress(0)
            out_dir = extract_frames(video, project, fps=fps)
            # étape 2 : fin -> 100%
            worker.report_progress(100)
            return out_dir

        def on_finished(out_dir):
            self.log(f"[FFmpeg] Terminé. Frames dans : {out_dir}")

        self.start_worker(job, on_finished, "FFmpeg")


    def on_bmp_click(self):
        """Convertit les frames PNG du projet en BMP via ImageMagick."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur BMP : nom de projet vide.")
            return

        threshold = self.spin_bmp_threshold.value()
        use_thinning = self.check_bmp_thinning.isChecked()
        max_frames_value = self.spin_bmp_max_frames.value()
        max_frames = max_frames_value if max_frames_value > 0 else None

        def job(worker: Worker):
            worker.report_progress(0)
            bmp_dir = convert_project_frames_to_bmp(
                project,
                threshold=threshold,
                use_thinning=use_thinning,
                max_frames=max_frames,
            )
            worker.report_progress(100)            
            return bmp_dir

        self.log(
            f"[BMP] Conversion PNG -> BMP pour le projet '{project}' "
            f"(threshold={threshold}%, thinning={use_thinning}, "
            f"max_frames={max_frames or 'toutes'})..."
        )

        def on_finished(bmp_dir):
            self.log(f"[BMP] Terminé. BMP dans : {bmp_dir}")

        self.start_worker(
            convert_project_frames_to_bmp,
            on_finished,
            "BMP",
            project,
            threshold=threshold,
            use_thinning=use_thinning,
            max_frames=max_frames,
        )

    def on_potrace_click(self):
        """Vectorise les BMP du projet en SVG via Potrace."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur Potrace : nom de projet vide.")
            return

        project_root = PROJECTS_ROOT / project
        bmp_dir = project_root / "bmp"
        svg_dir = project_root / "svg"

        self.log(f"[Potrace] Vectorisation BMP -> SVG pour le projet '{project}'...")
        self.log(f"  Entrée : {bmp_dir}")
        self.log(f"  Sortie : {svg_dir}")

        def job(worker: Worker):
            worker.report_progress(0)
            svg_out = bitmap_to_svg_folder(str(bmp_dir), str(svg_dir))
            worker.report_progress(100)
            return svg_out

        def on_finished(svg_out):
            self.log(f"[Potrace] Terminé. SVG dans : {svg_out}")

        self.start_worker(
            bitmap_to_svg_folder,
            on_finished,
            "Potrace",
            str(bmp_dir),
            str(svg_dir),
        )

    def on_preview_frame(self):
        """Affiche la frame sélectionnée en PNG, BMP et SVG, côte à côte."""
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

        self.log(f"[Preview] Frame {frame_index} (PNG) → {png_path}")
        self.preview_png.show_image(str(png_path))

        self.log(f"[Preview] Frame {frame_index} (BMP) → {bmp_path}")
        self.preview_bmp.show_image(str(bmp_path))

        self.log(f"[Preview] Frame {frame_index} (SVG) → {svg_path}")
        self.preview_svg.show_svg(str(svg_path))


    def on_export_ilda_click(self):
        """Export ILDA du projet courant."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur ILDA : nom de projet vide.")
            return

        self.log(f"[ILDA] Export du projet '{project}'...")

        def job():
            # Pas encore de cancellation/progress avancée → simple appel
            return export_project_to_ilda(project)

        def on_finished(out_path):
            self.log(f"[ILDA] Terminé. Fichier ILDA généré : {out_path}")

        self.start_worker(job, on_finished, "ILDA")


    def on_cancel_task(self):
        worker = getattr(self, "_current_worker", None)
        if worker is not None:
            self.log("[UI] Annulation demandée…")
            worker.cancel()
            self.btn_cancel_task.setEnabled(False)

def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    sys.exit(app.exec())
