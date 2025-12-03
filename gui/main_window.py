# gui/main_window.py


import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit,
    QSpinBox, QComboBox,
)


from pathlib import Path

from core.step_ffmpeg import extract_frames
from core.step_bitmap import convert_project_frames_to_bmp
from core.step_potrace import bitmap_to_svg_folder
from core.config import PROJECTS_ROOT
from .preview_widgets import RasterPreview


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Laser Pipeline - Prototype GUI")

        central = QWidget()
        layout = QVBoxLayout(central)

        # --- Ligne 1 : vidéo source + bouton Parcourir ---
        row_video = QHBoxLayout()
        self.edit_video = QLineEdit()
        btn_browse = QPushButton("Parcourir…")
        btn_browse.clicked.connect(self.choose_video)

        row_video.addWidget(QLabel("Vidéo source :"))
        row_video.addWidget(self.edit_video)
        row_video.addWidget(btn_browse)
        layout.addLayout(row_video)

        # --- Ligne 2 : nom de projet ---
        row_project = QHBoxLayout()
        self.edit_project = QLineEdit("projet_demo")
        row_project.addWidget(QLabel("Nom du projet :"))
        row_project.addWidget(self.edit_project)
        layout.addLayout(row_project)

        # --- Ligne 3 : FPS ---
        row_fps = QHBoxLayout()
        self.edit_fps = QLineEdit("25")
        row_fps.addWidget(QLabel("FPS :"))
        row_fps.addWidget(self.edit_fps)
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

        # Nouveau : choix de la source (PNG ou BMP)
        row_preview.addWidget(QLabel("Source :"))
        self.combo_source = QComboBox()
        self.combo_source.addItems(["PNG (frames)", "BMP (bitmap)"])
        row_preview.addWidget(self.combo_source)

        self.btn_preview = QPushButton("Prévisualiser frame")
        self.btn_preview.clicked.connect(self.on_preview_frame)
        row_preview.addWidget(self.btn_preview)

        layout.addLayout(row_preview)


        # --- Zone de prévisualisation ---
        self.preview = RasterPreview()
        self.preview.setMinimumHeight(200)
        layout.addWidget(self.preview)

        # --- Zone de log ---
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        self.setCentralWidget(central)


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
            self.edit_video.setText(path)
            self.log(f"Vidéo sélectionnée : {path}")

    def on_test_click(self):
        """Vérifie les paramètres entrés et les affiche dans le log."""
        video = (self.edit_video.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps_text = (self.edit_fps.text() or "").strip()

        # Validation simple
        if not video:
            self.log("Erreur : aucune vidéo sélectionnée.")
            return
        if not project:
            self.log("Erreur : nom de projet vide.")
            return

        try:
            fps = int(fps_text)
        except ValueError:
            self.log(f"Erreur : FPS invalide ({fps_text}), utiliser un entier.")
            return

        self.log("=== Paramètres actuels ===")
        self.log(f"Vidéo : {video}")
        self.log(f"Projet : {project}")
        self.log(f"FPS : {fps}")
        self.log("==========================")

    def on_ffmpeg_click(self):
        """Lance l'extraction des frames via FFmpeg."""
        video = (self.edit_video.text() or "").strip()
        project = (self.edit_project.text() or "").strip()
        fps_text = (self.edit_fps.text() or "").strip()

        # Validation basique (identique à on_test_click)
        if not video:
            self.log("Erreur FFmpeg : aucune vidéo sélectionnée.")
            return
        if not project:
            self.log("Erreur FFmpeg : nom de projet vide.")
            return

        try:
            fps = int(fps_text)
        except ValueError:
            self.log(f"Erreur FFmpeg : FPS invalide ({fps_text}).")
            return

        self.log(f"[FFmpeg] Démarrage extraction frames…")
        self.log(f"  Vidéo   : {video}")
        self.log(f"  Projet  : {project}")
        self.log(f"  FPS     : {fps}")

        try:
            frames_dir = extract_frames(video, project, fps)
        except Exception as e:
            self.log(f"[FFmpeg] ERREUR : {e}")
            return

        self.log(f"[FFmpeg] Terminé. Frames dans : {frames_dir}")
    def on_bmp_click(self):
        """Convertit les frames PNG du projet en BMP via ImageMagick."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur BMP : nom de projet vide.")
            return

        self.log(f"[BMP] Conversion PNG -> BMP pour le projet '{project}'...")

        try:
            bmp_dir = convert_project_frames_to_bmp(project)
        except Exception as e:
            self.log(f"[BMP] ERREUR : {e}")
            return

        self.log(f"[BMP] Terminé. BMP dans : {bmp_dir}")

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

        try:
            svg_out = bitmap_to_svg_folder(str(bmp_dir), str(svg_dir))
        except Exception as e:
            self.log(f"[Potrace] ERREUR : {e}")
            return

        self.log(f"[Potrace] Terminé. SVG dans : {svg_out}")

    def on_preview_frame(self):
        """Affiche une frame (PNG ou BMP) du projet dans le widget de prévisualisation."""
        project = (self.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur prévisualisation : nom de projet vide.")
            return

        frame_index = self.spin_frame.value()
        source_mode = self.combo_source.currentText()

        if source_mode.startswith("PNG"):
            base_dir = PROJECTS_ROOT / project / "frames"
            ext = ".png"
            src_label = "frames (PNG)"
        else:
            base_dir = PROJECTS_ROOT / project / "bmp"
            ext = ".bmp"
            src_label = "bitmap (BMP)"

        filename = f"frame_{frame_index:04d}{ext}"
        path = base_dir / filename

        self.log(f"[Preview] Frame {frame_index} ({src_label}) → {path}")
        self.preview.show_image(str(path))



def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(600, 400)
    win.show()
    sys.exit(app.exec())