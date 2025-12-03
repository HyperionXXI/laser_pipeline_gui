# gui/main_window.py

import sys


from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
    QSpinBox, QCheckBox,
)


from pathlib import Path

from core.step_ffmpeg import extract_frames
from core.step_bitmap import convert_project_frames_to_bmp
from core.step_potrace import bitmap_to_svg_folder
from core.config import PROJECTS_ROOT
from .preview_widgets import RasterPreview, SvgPreview
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Laser Pipeline - Prototype GUI")

        central = QWidget()
        layout = QVBoxLayout(central)

        # --- Ligne 1 : vidéo source + bouton Parcourir ---
        row_video = QHBoxLayout()
        self.edit_video_path = QLineEdit()

        self.btn_browse = QPushButton("Parcourir…")
        self.btn_browse.clicked.connect(self.choose_video)

        row_video.addWidget(QLabel("Vidéo source :"))
        row_video.addWidget(self.edit_video_path)
        row_video.addWidget(self.btn_browse)
        layout.addLayout(row_video)

        # --- Ligne 2 : nom de projet ---
        row_project = QHBoxLayout()
        self.edit_project = QLineEdit("projet_demo")
        row_project.addWidget(QLabel("Nom du projet :"))
        row_project.addWidget(self.edit_project)
        layout.addLayout(row_project)

        # --- Ligne 3 : FPS ---
        row_fps = QHBoxLayout()
        row_fps.addWidget(QLabel("FPS :"))

        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 200)
        self.spin_fps.setValue(25)
        row_fps.addWidget(self.spin_fps)

        layout.addLayout(row_fps)

        # --- Bouton principal : test des paramètres ---
        self.btn_test = QPushButton("Tester les paramètres")
        self.btn_test.clicked.connect(self.on_test_click)
        layout.addWidget(self.btn_test)

        # --- Bouton FFmpeg ---
        self.btn_ffmpeg = QPushButton("1. Extraire frames (FFmpeg)")
        self.btn_ffmpeg.clicked.connect(self.on_ffmpeg_click)
        layout.addWidget(self.btn_ffmpeg)

        # --- Bouton BMP ---
        self.btn_bmp = QPushButton("2. Préparer BMP (ImageMagick)")
        self.btn_bmp.clicked.connect(self.on_bmp_click)
        layout.addWidget(self.btn_bmp)

        # --- Paramètres BMP ---
        row_bmp_params = QHBoxLayout()

        row_bmp_params.addWidget(QLabel("Seuil (%) :"))
        self.spin_bmp_threshold = QSpinBox()
        self.spin_bmp_threshold.setRange(0, 100)
        self.spin_bmp_threshold.setValue(60)  # valeur par défaut
        row_bmp_params.addWidget(self.spin_bmp_threshold)

        self.check_bmp_thinning = QCheckBox("Thinning")
        self.check_bmp_thinning.setChecked(False)
        row_bmp_params.addWidget(self.check_bmp_thinning)

        row_bmp_params.addWidget(QLabel("Max frames (0 = toutes) :"))
        self.spin_bmp_max_frames = QSpinBox()
        self.spin_bmp_max_frames.setRange(0, 100000)
        self.spin_bmp_max_frames.setValue(0)  # 0 => pas de limite
        row_bmp_params.addWidget(self.spin_bmp_max_frames)

        layout.addLayout(row_bmp_params)

        # --- Bouton Potrace ---
        self.btn_potrace = QPushButton("3. Vectoriser (Potrace)")
        self.btn_potrace.clicked.connect(self.on_potrace_click)
        layout.addWidget(self.btn_potrace)



        # --- Contrôles de prévisualisation ---
        row_preview = QHBoxLayout()
        row_preview.addWidget(QLabel("Frame :"))

        self.spin_frame = QSpinBox()
        self.spin_frame.setMinimum(1)
        self.spin_frame.setMaximum(99999)
        row_preview.addWidget(self.spin_frame)

        self.btn_preview = QPushButton("Prévisualiser frame")
        self.btn_preview.clicked.connect(self.on_preview_frame)
        row_preview.addWidget(self.btn_preview)

        layout.addLayout(row_preview)

        # --- Zones de prévisualisation (PNG, BMP, SVG) ---
        previews_row = QHBoxLayout()

        # Colonne PNG
        col_png = QVBoxLayout()
        label_png = QLabel("PNG (frames)")
        col_png.addWidget(label_png)

        self.preview_png = RasterPreview()
        self.preview_png.setMinimumSize(200, 200)
        col_png.addWidget(self.preview_png)

        previews_row.addLayout(col_png)

        # Colonne BMP
        col_bmp = QVBoxLayout()
        label_bmp = QLabel("BMP (bitmap)")
        col_bmp.addWidget(label_bmp)

        self.preview_bmp = RasterPreview()
        self.preview_bmp.setMinimumSize(200, 200)
        col_bmp.addWidget(self.preview_bmp)

        previews_row.addLayout(col_bmp)

        # Colonne SVG
        col_svg = QVBoxLayout()
        label_svg = QLabel("SVG (vectorisé)")
        col_svg.addWidget(label_svg)

        self.preview_svg = SvgPreview()
        self.preview_svg.setMinimumSize(200, 200)
        col_svg.addWidget(self.preview_svg)

        previews_row.addLayout(col_svg)

        layout.addLayout(previews_row)

        # --- Zone de log ---
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        self.setCentralWidget(central)

    def set_busy(self, busy: bool):
        """
        Active/désactive les boutons principaux et change le curseur.

        busy=True  -> désactive les actions, curseur 'attente'
        busy=False -> réactive les actions, curseur normal
        """
        # Liste des widgets à désactiver pendant un traitement
        widgets = [
            getattr(self, "btn_test", None),
            getattr(self, "btn_ffmpeg", None),
            getattr(self, "btn_bmp", None),
            getattr(self, "btn_potrace", None),
            getattr(self, "btn_preview", None),
            getattr(self, "btn_browse", None),  # si ce bouton existe
        ]

        for w in widgets:
            if w is not None:
                w.setEnabled(not busy)

        if busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()


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
            "Vidéos (*.mp4 *.mov *.avi);;Tous les fichiers (*)"
        )
        if path:
            self.edit_video_path.setText(path)
            self.log(f"Vidéo sélectionnée : {path}")

    def on_test_click(self):
        """Vérifie les paramètres entrés et les affiche dans le log."""
        video = (self.edit_video_path.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps = self.spin_fps.value()

        # Validation simple
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

        self.set_busy(True)
        try:
            out_dir = extract_frames(video, project, fps=fps)
        except Exception as e:
            self.log(f"[FFmpeg] ERREUR : {e}")
        else:
            self.log(f"[FFmpeg] Terminé. Frames dans : {out_dir}")
        finally:
            self.set_busy(False)


    def on_bmp_click(self):
        """Convertit les frames PNG du projet en BMP via ImageMagick (avec paramètres GUI)."""
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

        self.set_busy(True)
        try:
            bmp_dir = convert_project_frames_to_bmp(
                project,
                threshold=threshold,
                use_thinning=use_thinning,
                max_frames=max_frames,
            )
        except Exception as e:
            self.log(f"[BMP] ERREUR : {e}")
        else:
            self.log(f"[BMP] Terminé. BMP dans : {bmp_dir}")
        finally:
            self.set_busy(False)

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

        self.set_busy(True)
        try:
            svg_out = bitmap_to_svg_folder(str(bmp_dir), str(svg_dir))
        except Exception as e:
            self.log(f"[Potrace] ERREUR : {e}")
        else:
            self.log(f"[Potrace] Terminé. SVG dans : {svg_out}")
        finally:
            self.set_busy(False)


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

def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(600, 400)
    win.show()
    sys.exit(app.exec())