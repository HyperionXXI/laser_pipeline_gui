from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget


class RasterPreview(QWidget):
    """
    Widget simple pour afficher une image raster (PNG, BMP, etc.)
    centrée et conservant le ratio.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()

        # Taille minimale confortable pour la GUI
        self.setMinimumSize(240, 180)
        # Le fond sera peint dans paintEvent (noir)

    def show_image(self, path: str | Path) -> None:
        """
        Charge et affiche une image raster à partir d'un chemin.
        """
        pm = QPixmap(str(path))
        self._pixmap = pm
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)

        # Fond noir pour bien contraster avec les images claires
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
    Widget pour afficher un SVG via QSvgRenderer, avec :
      - fond noir (cohérent avec le pipeline : trait blanc),
      - mise à l'échelle uniforme,
      - centrage du contenu.

    Utilisé pour :
      - la sortie Potrace (SVG),
      - la prévisualisation ILDA (approximation via SVG).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(self)
        self._svg_path: str | None = None

        self.setMinimumSize(240, 180)
        # Le fond sera peint en noir dans paintEvent

    def show_svg(self, path: str | Path) -> None:
        """
        Charge et affiche un SVG à partir d'un chemin.
        """
        path_str = str(path)
        self._svg_path = path_str
        self._renderer.load(path_str)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)

        # Fond noir pour que les traits blancs soient visibles
        painter.fillRect(self.rect(), Qt.black)

        if not self._renderer.isValid():
            return

        view_box: QRectF = self._renderer.viewBoxF()
        if view_box.isEmpty():
            # Rendu brut si le SVG n'a pas de viewBox exploitable
            self._renderer.render(painter)
            return

        # Facteur d'échelle uniforme pour faire tenir tout le SVG
        scale = min(
            self.width() / view_box.width(),
            self.height() / view_box.height(),
        )

        # On centre le contenu dans le widget
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.scale(scale, scale)
        painter.translate(-view_box.center())

        self._renderer.render(painter)
