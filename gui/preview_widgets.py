# gui/preview_widgets.py

from pathlib import Path

from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtSvg import QSvgRenderer


class BasePreview(QWidget):
    """
    Widget de base : un QLabel centré qui affiche soit un texte,
    soit un QPixmap mis à l'échelle.
    """

    def __init__(self, placeholder: str = "Aucune image", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._label = QLabel(placeholder)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def _target_size(self) -> QSize:
        s = self.size()
        if not s.isValid() or s.width() <= 0 or s.height() <= 0:
            return QSize(320, 240)
        return s

    def clear(self):
        """Réinitialise la preview avec le texte de placeholder."""
        self._label.setPixmap(QPixmap())
        self._label.setText(self._placeholder)

    def _set_pixmap_scaled(self, pixmap: QPixmap):
        if pixmap.isNull():
            self.clear()
            return
        target = self._target_size()
        scaled = pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._label.setPixmap(scaled)
        self._label.setText("")


class RasterPreview(BasePreview):
    """
    Preview pour images raster (PNG, BMP, …).
    """

    def show_image(self, path: str):
        p = Path(path)
        if not p.is_file():
            self.clear()
            return

        pix = QPixmap(str(p))
        self._set_pixmap_scaled(pix)


class SvgPreview(BasePreview):
    """
    Preview pour SVG, en rasterisant le vecteur dans un QImage/QPixmap.
    Cela permet d'avoir le même comportement que RasterPreview
    (même taille de widget, scaling, etc.).
    """

    def show_svg(self, path: str):
        p = Path(path)
        if not p.is_file():
            self.clear()
            return

        renderer = QSvgRenderer(str(p))
        if not renderer.isValid():
            self.clear()
            return

        target = self._target_size()
        w = max(target.width(), 1)
        h = max(target.height(), 1)

        # Fond noir pour rester cohérent avec les BMP/PNG traités
        image = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.black)

        painter = QPainter(image)

        view_box = renderer.viewBox()
        if not view_box.isNull():
            # On adapte le viewBox au rectangle de rendu en conservant le ratio
            target_rect = QRectF(0, 0, w, h)

            sx = target_rect.width() / view_box.width()
            sy = target_rect.height() / view_box.height()
            s = min(sx, sy)

            tw = view_box.width() * s
            th = view_box.height() * s
            tx = (target_rect.width() - tw) / 2.0
            ty = (target_rect.height() - th) / 2.0

            painter.translate(tx, ty)
            painter.scale(s, s)
            renderer.render(painter, view_box)
        else:
            # Fallback : on laisse Qt gérer le cadrage
            renderer.render(painter, QRectF(0, 0, w, h))

        painter.end()

        pix = QPixmap.fromImage(image)
        self._set_pixmap_scaled(pix)
