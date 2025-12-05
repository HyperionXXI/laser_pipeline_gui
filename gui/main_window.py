# gui/main_window.py

import sys
import os
import re
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
    QComboBox,    
)

from core.ilda_preview import render_ilda_frame_to_png
from core.step_ffmpeg import extract_frames
from core.step_bitmap import convert_project_frames_to_bmp
from core.step_potrace import bitmap_to_svg_folder
from core.step_ilda import export_project_to_ilda
from core.config import PROJECTS_ROOT
from .preview_widgets import RasterPreview, SvgPreview


# ---------------------------------------------------------------------------
# Worker générique pour exécuter une fonction lourde dans un QThread.
# ---------------------------------------------------------------------------

class Worker(QObject):
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
            result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.error.emit(str(e))
        else:
            self.finished.emit(result)

    def cancel(self):
        """Placeholder pour un futur mécanisme d'annulation."""
        pass



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
        #    → 4 colonnes : (1) FFmpeg, (2) Bitmap, (3) Vectorisation, (4) ILDA
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

        # Ligne 1 : ajustement (fit axis)
        row_ilda_fit = QHBoxLayout()
        row_ilda_fit.addWidget(QLabel("Ajustement :"))
        self.combo_ilda_fit_axis = QComboBox()
        self.combo_ilda_fit_axis.addItems([
            "Max des deux axes",
            "Ajuster sur largeur (X)",
            "Ajuster sur hauteur (Y)",
        ])
        row_ilda_fit.addWidget(self.combo_ilda_fit_axis)
        step4_layout.addLayout(row_ilda_fit)

        # Ligne 2 : fill ratio
        row_ilda_fill = QHBoxLayout()
        row_ilda_fill.addWidget(QLabel("Fill (%) :"))
        self.spin_ilda_fill = QSpinBox()
        self.spin_ilda_fill.setRange(10, 100)
        self.spin_ilda_fill.setValue(95)
        row_ilda_fill.addWidget(self.spin_ilda_fill)
        step4_layout.addLayout(row_ilda_fill)

        # Ligne 3 : min size (anti-poussière)
        row_ilda_min = QHBoxLayout()
        row_ilda_min.addWidget(QLabel("Min taille (%) :"))
        self.spin_ilda_min_size = QSpinBox()
        self.spin_ilda_min_size.setRange(0, 50)
        self.spin_ilda_min_size.setValue(1)   # 1% par défaut
        row_ilda_min.addWidget(self.spin_ilda_min_size)
        step4_layout.addLayout(row_ilda_min)

        # Bouton Export
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

        # ICI il manque la création de col4_widget

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

        # Gestion du worker courant
        self._current_thread: QThread | None = None
        self._current_worker: Worker | None = None

    # ------------------------------------------------------------------
    # Utilitaires UI / threads
    # ------------------------------------------------------------------

    def set_busy(self, busy: bool):

        if busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)   # mode indéterminé
            self.btn_cancel_task.setEnabled(True)
        else:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(False)
            self.btn_cancel_task.setEnabled(False)

        QApplication.processEvents()


    def start_worker(self, func, finished_cb, step_label, *args, **kwargs):
        self.set_busy(True)

        thread = QThread(self)
        worker = Worker(func, *args, **kwargs)
        worker.moveToThread(thread)

        def cleanup():
            self.set_busy(False)
            thread.quit()
            worker.deleteLater()
            thread.deleteLater()
            self._current_thread = None
            self._current_worker = None

        def on_finished(result):
            try:
                finished_cb(result)
            finally:
                cleanup()

        def on_error(message: str):
            self.log(f"[{step_label}] ERREUR : {message}")
            cleanup()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)

        self._current_thread = thread
        self._current_worker = worker
        thread.start()


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

    def closeEvent(self, event):
        """
        On demande poliment l’arrêt du thread courant s’il existe,
        sans jamais bloquer avec wait().
        """
        thread = getattr(self, "_current_thread", None)
        worker = getattr(self, "_current_worker", None)

        try:
            if thread is not None and thread.isRunning():
                self.log("Fermeture : arrêt du traitement en cours…")

                if worker is not None and hasattr(worker, "cancel"):
                    worker.cancel()

                thread.quit()
        except RuntimeError:
            # QThread déjà détruit côté C++ -> on ignore
            pass

        event.accept()


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
        """Lance l'extraction des frames via FFmpeg."""
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()
        project_root = PROJECTS_ROOT / project

        self.log("[FFmpeg] Démarrage extraction frames...")

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

        def on_finished(out_dir):
            self.log(f"[FFmpeg] Terminé. Frames dans : {out_dir}")
            # on force la prévisualisation sur la DERNIÈRE frame PNG existante
            last_idx = self._find_last_frame_index(project_root / "frames", "png")
            if last_idx is not None:
                self.spin_frame.setValue(last_idx)
            self.update_previews_for_current_frame()

        self.start_worker(
            extract_frames,
            on_finished,
            "FFmpeg",
            video,
            project,
            fps=fps,
        )


    def on_bmp_click(self):
        """Convertit les frames PNG du projet en BMP via ImageMagick."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur BMP : nom de projet vide.")
            return
        project_root = PROJECTS_ROOT / project

        threshold = self.spin_bmp_threshold.value()
        use_thinning = self.check_bmp_thinning.isChecked()
        max_frames_value = self.spin_bmp_max_frames.value()
        max_frames = max_frames_value if max_frames_value > 0 else None

        self.log(
            f"[BMP] Conversion PNG -> BMP pour le projet '{project}' "
            f"(threshold={threshold}%, thinning={use_thinning}, "
            f"max_frames={max_frames or 'toutes'})..."
        )

        def on_finished(bmp_dir):
            self.log(f"[BMP] Terminé. BMP dans : {bmp_dir}")
            last_idx = self._find_last_frame_index(project_root / "bmp", "bmp")
            if last_idx is not None:
                self.spin_frame.setValue(last_idx)
            self.update_previews_for_current_frame()

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

        def on_finished(svg_out):
            self.log(f"[Potrace] Terminé. SVG dans : {svg_out}")
            last_idx = self._find_last_frame_index(svg_dir, "svg")
            if last_idx is not None:
                self.spin_frame.setValue(last_idx)
            self.update_previews_for_current_frame()

        self.start_worker(
            bitmap_to_svg_folder,
            on_finished,
            "Potrace",
            str(bmp_dir),
            str(svg_dir),
        )

    def _find_last_frame_index(self, dir_path: Path, suffix: str) -> int | None:
        """
        Cherche la plus grande valeur de N telle qu'un fichier
        frame_NNNN.<suffix> existe dans dir_path.
        Retourne None si rien n'est trouvé.
        """
        if not dir_path.exists():
            return None

        pattern = re.compile(r"^frame_(\d+)\." + re.escape(suffix) + r"$")
        max_idx = 0

        for entry in dir_path.iterdir():
            if not entry.is_file():
                continue
            m = pattern.match(entry.name)
            if not m:
                continue
            idx = int(m.group(1))
            if idx > max_idx:
                max_idx = idx

        return max_idx or None

    def update_previews_for_current_frame(self):
        """Affiche la frame sélectionnée en PNG, BMP, SVG (et placeholder ILDA)."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur prévisualisation : nom de projet vide.")
            return

        frame_index = self.spin_frame.value()
        project_root = PROJECTS_ROOT / project
        png_dir = project_root / "frames"
        bmp_dir = project_root / "bmp"
        svg_dir = project_root / "svg"
        ilda_dir = project_root / "ilda"

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

        # ILDA : pour l’instant on réutilise l’image PNG comme approximation
        self.log(f"[Preview] Frame {frame_index} (ILDA approx) → {png_path}")
        self.preview_ilda.show_image(str(png_path))


    def on_preview_frame(self):
        """Slot du bouton 'Prévisualiser frame'."""
        self.update_previews_for_current_frame()



    def on_export_ilda_click(self):
        """Export ILDA à partir des SVG du projet."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur ILDA : nom de projet vide.")
            return
        
        project_root = PROJECTS_ROOT / project   # <<< AJOUT

        # Récupère les paramètres GUI
        fit_text = self.combo_ilda_fit_axis.currentText()
        if "largeur" in fit_text:
            fit_axis = "x"
        elif "hauteur" in fit_text:
            fit_axis = "y"
        else:
            fit_axis = "max"

        fill_ratio = self.spin_ilda_fill.value() / 100.0
        min_rel_size = self.spin_ilda_min_size.value() / 100.0

        self.log(
            f"[ILDA] Export ILDA pour le projet '{project}' "
            f"(fit_axis={fit_axis}, fill={fill_ratio:.2f}, "
            f"min_size={min_rel_size:.3f})..."
        )

        def on_finished(out_path):
            # on garde la même frame que la dernière SVG,
            # ce sera aussi la dernière frame ILDA
            last_idx = self._find_last_frame_index(project_root / "svg", "svg")
            if last_idx is not None:
                self.spin_frame.setValue(last_idx)
            self.log(f"[ILDA] Terminé. Fichier : {out_path}")
            # met à jour toutes les prévisualisations sur la frame courante
            self.update_previews_for_current_frame()

        # Worker : on passe les paramètres supplémentaires
        self.start_worker(
            export_project_to_ilda,
            on_finished,
            "ILDA",
            project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
        )

    def on_cancel_task(self):
        """Demande l'annulation du traitement en cours (si supportée)."""
        thread = self._current_thread
        worker = self._current_worker

        if thread is None or not thread.isRunning():
            self.log("[Task] Aucun traitement en cours à annuler.")
            return

        if worker is not None and hasattr(worker, "cancel"):
            self.log("[Task] Annulation demandée…")
            worker.cancel()

        # On demande l’arrêt (le nettoyage sera fait dans on_thread_finished)
        thread.quit()

def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    sys.exit(app.exec())
