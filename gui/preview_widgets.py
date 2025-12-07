from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
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
        pm = QPixmap(str(path))
        self._pixmap = pm
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
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
    - Contenu centré et mis à l'échelle pour occuper au mieux la zone.
    - Aucune logique de "zoom" maison : on laisse le viewBox du SVG
      faire foi, ce qui évite les surprises et les déformations.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._renderer = QSvgRenderer(self)
        # Important : conserver le ratio du viewBox et centrer le rendu
        self._renderer.setAspectRatioMode(Qt.KeepAspectRatio)

        self._svg_path: str | None = None
        self.setMinimumSize(240, 180)

    def show_svg(self, path: str | Path) -> None:
        """Charge et affiche un SVG à partir d'un chemin."""
        path_str = str(path)
        self._svg_path = path_str
        self._renderer.load(path_str)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)

        # Fond noir pour voir correctement les traits
        painter.fillRect(self.rect(), Qt.black)

        if not self._renderer.isValid():
            return

        # Avec aspectRatioMode = KeepAspectRatio, QSvgRenderer :
        # - centre le contenu,
        # - le met à l'échelle au maximum dans "self.rect()",
        # - en conservant le ratio du viewBox.
        self._renderer.render(painter, self.rect())
