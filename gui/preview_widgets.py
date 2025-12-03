# gui/preview_widgets.py

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QStackedLayout,
    QSizePolicy,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QSize
from PySide6.QtSvgWidgets import QSvgWidget


PREVIEW_MIN_SIZE = QSize(320, 240)


class RasterPreview(QWidget):
    """
    Prévisualisation raster (PNG / BMP).

    - Même taille mini pour tous les previews.
    - Texte "Aucune image" tant qu'aucune image n'est chargée.
    - Image redimensionnée en conservant le ratio.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._stack = QStackedLayout(self)

        self._placeholder = QLabel("Aucune image")
        self._placeholder.setAlignment(Qt.AlignCenter)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setScaledContents(False)

        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._image_label)

        self.setMinimumSize(PREVIEW_MIN_SIZE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def clear(self):
        self._image_label.clear()
        self._stack.setCurrentWidget(self._placeholder)

    def show_image(self, path: str):
        if not path or not Path(path).is_file():
            self.clear()
            return

        pix = QPixmap(path)
        if pix.isNull():
            self.clear()
            return

        target_size = self.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            target_size = PREVIEW_MIN_SIZE

        scaled = pix.scaled(
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)
        self._stack.setCurrentWidget(self._image_label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Si une image est affichée, on la rescale pour garder le ratio
        if self._stack.currentWidget() is self._image_label:
            pix = self._image_label.pixmap()
            if pix is not None:
                target_size = self.size()
                scaled = pix.scaled(
                    target_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self._image_label.setPixmap(scaled)


class SvgPreview(QWidget):
    """
    Prévisualisation SVG.

    Même logique que RasterPreview : placeholder "Aucune image",
    même taille mini, et widget SVG qui remplit la zone.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._stack = QStackedLayout(self)

        self._placeholder = QLabel("Aucune image")
        self._placeholder.setAlignment(Qt.AlignCenter)

        self._svg_widget = QSvgWidget()
        self._svg_widget.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._svg_widget)

        self.setMinimumSize(PREVIEW_MIN_SIZE)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def clear(self):
        self._svg_widget.load(b"")
        self._stack.setCurrentWidget(self._placeholder)

    def show_svg(self, path: str):
        if not path or not Path(path).is_file():
            self.clear()
            return

        # QSvgWidget sait se redessiner à la taille du widget
        self._svg_widget.load(path)
        self._stack.setCurrentWidget(self._svg_widget)
        self._svg_widget.repaint()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # On redimensionne le widget SVG à la nouvelle taille
        if self._stack.currentWidget() is self._svg_widget:
            self._svg_widget.resize(self.size())
