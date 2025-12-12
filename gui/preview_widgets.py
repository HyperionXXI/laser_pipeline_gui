from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QPaintEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget


class RasterPreview(QWidget):
    """
    Widget simple pour afficher une image raster (PNG, BMP, etc.)
    centrée et en conservant le ratio.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self.setMinimumSize(240, 180)

    def show_image(self, path: str | Path) -> None:
        """Charge et affiche une image raster à partir d'un chemin."""
        self._pixmap = QPixmap(str(path))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        painter = QPainter(self)

        # Fond noir pour bien contraster avec les traits clairs
        painter.fillRect(self.rect(), Qt.black)

        if self._pixmap.isNull():
            return

        # Mise à l'échelle en conservant le ratio, centrée
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class SvgPreview(QWidget):
    """
    Widget pour afficher un SVG via QSvgRenderer.

    - Fond noir (cohérent avec les traits blancs / colorés).
    - Rapport largeur/hauteur toujours respecté.
    - Contenu centré et mis à l'échelle pour occuper au mieux la zone,
      sans aucune déformation.

    Aucun traitement lourd : la preview reste très légère et ne
    ralentit pas Potrace / ILDA.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(self)
        self.setMinimumSize(240, 180)

    def show_svg(self, path: str | Path) -> None:
        """Charge et affiche un SVG à partir d'un chemin."""
        self._renderer.load(str(path))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        painter = QPainter(self)

        # Fond noir pour voir correctement les traits
        painter.fillRect(self.rect(), Qt.black)

        if not self._renderer.isValid():
            return

        widget_w = self.width()
        widget_h = self.height()
        if widget_w <= 0 or widget_h <= 0:
            return

        view_box: QRectF = self._renderer.viewBoxF()
        if view_box.isEmpty():
            # Rendu brut si le SVG n'a pas de viewBox exploitable
            self._renderer.render(painter)
            return

        vw = view_box.width()
        vh = view_box.height()
        if vw <= 0 or vh <= 0:
            self._renderer.render(painter)
            return

        aspect_view = vw / vh
        aspect_widget = widget_w / widget_h

        # Rectangle cible avec même ratio que la viewBox, centré.
        if aspect_widget > aspect_view:
            target_h = float(widget_h)
            target_w = target_h * aspect_view
            x = (widget_w - target_w) / 2.0
            y = 0.0
        else:
            target_w = float(widget_w)
            target_h = target_w / aspect_view
            x = 0.0
            y = (widget_h - target_h) / 2.0

        target_rect = QRectF(x, y, target_w, target_h)
        self._renderer.render(painter, target_rect)
