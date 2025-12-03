from pathlib import Path

from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvgWidgets import QSvgWidget


class RasterPreview(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("Aucune image")
        self.setMinimumSize(200, 200)

    def show_image(self, path: str):
        p = Path(path)
        if not p.is_file():
            self.setText(f"Introuvable :\n{p}")
            self.setPixmap(QPixmap())  # efface l'ancienne image
            return

        pix = QPixmap(str(p))
        if pix.isNull():
            self.setText(f"Erreur de chargement :\n{p}")
            self.setPixmap(QPixmap())
            return

        self.setPixmap(pix.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))
        self.setText("")

    def resizeEvent(self, event):
        # Re-scale quand on redimensionne la fenêtre
        if self.pixmap() is not None and not self.pixmap().isNull():
            self.setPixmap(self.pixmap().scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))
        super().resizeEvent(event)


class SvgPreview(QSvgWidget):
    """
    Widget simple pour afficher un fichier SVG.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._current_path = None

    def show_svg(self, path: str):
        p = Path(path)
        self._current_path = str(p)

        if not p.is_file():
            # On "efface" en chargeant un SVG vide
            self.renderer().load(QByteArray())
            self.setToolTip(f"Introuvable : {p}")
            return

        data = QByteArray(p.read_bytes())
        self.renderer().load(data)
        self.setToolTip(str(p))
        self.update()
