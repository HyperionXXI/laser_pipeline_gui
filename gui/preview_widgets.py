# gui/preview_widgets.py

from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


class RasterPreview(QWidget):
    """Widget simple pour afficher une image raster (PNG, JPG, etc.)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.label = QLabel("Aucune image")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.label)

    def show_image(self, path: str):
        p = Path(path)
        if not p.is_file():
            self.label.setText(f"Introuvable :\n{p}")
            return

        pix = QPixmap(str(p))
        if pix.isNull():
            self.label.setText(f"Impossible de charger :\n{p}")
            return

        self._set_scaled_pixmap(pix)

    def _set_scaled_pixmap(self, pix: QPixmap):
        if pix.isNull():
            return
        self.label.setPixmap(
            pix.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def resizeEvent(self, event):
        """Quand on redimensionne la fenêtre, on rescaille l'image si nécessaire."""
        pix = self.label.pixmap()
        if pix:
            self._set_scaled_pixmap(pix)
        super().resizeEvent(event)
