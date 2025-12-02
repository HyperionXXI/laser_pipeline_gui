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

        # Ligne simple : un champ texte + bouton
        row = QHBoxLayout()
        self.input_edit = QLineEdit()
        btn = QPushButton("Dire bonjour")
        btn.clicked.connect(self.on_click)

        row.addWidget(QLabel("Nom :"))
        row.addWidget(self.input_edit)
        row.addWidget(btn)
        layout.addLayout(row)

        # Zone de log / sortie
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        self.setCentralWidget(central)

    def on_click(self):
        name = self.input_edit.text().strip() or "inconnu"
        self.log_view.append(f"Bonjour, {name} !")


def run():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(600, 400)
    win.show()
    sys.exit(app.exec())