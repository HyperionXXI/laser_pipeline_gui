# gui/main_window.py

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit
)


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

def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(600, 400)
    win.show()
    sys.exit(app.exec())