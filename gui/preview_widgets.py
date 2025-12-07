from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QImage
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

        self.setMinimumSize(240, 180)

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
    Widget pour afficher un SVG via QSvgRenderer avec :

      - fond noir (cohérent avec trait blanc),
      - zoom sur la zone réellement dessinée (bounding box du contenu),
      - centrage dans le widget.

    NOTE : Cette logique n'affecte QUE la prévisualisation GUI.
           Les coordonnées utilisées pour l'ILDA restent celles du SVG original.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(self)
        self._svg_path: str | None = None

        # Bounding box du contenu en coordonnées SVG
        # (None => on utilise la viewBox complète)
        self._content_box: QRectF | None = None

        self.setMinimumSize(240, 180)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def show_svg(self, path: str | Path) -> None:
        """
        Charge et affiche un SVG à partir d'un chemin.
        """
        path_str = str(path)
        self._svg_path = path_str
        self._renderer.load(path_str)
        self._content_box = self._compute_content_box()
        self.update()

    # ------------------------------------------------------------------
    # Calcul de la zone réellement dessinée
    # ------------------------------------------------------------------

    def _compute_content_box(self) -> QRectF | None:
        """
        Estime la zone réellement dessinée dans le SVG en rasterisant
        l'image dans une petite QImage et en cherchant les pixels non noirs.

        Retourne un QRectF en coordonnées SVG (viewBox), ou None si
        on ne trouve aucun contenu significatif.
        """
        if not self._renderer.isValid():
            return None

        view_box: QRectF = self._renderer.viewBoxF()
        if view_box.isEmpty():
            return None

        # Taille de l'image pour le calcul de bounding box
        img_w, img_h = 256, 256

        image = QImage(img_w, img_h, QImage.Format_ARGB32)
        image.fill(Qt.black)

        painter = QPainter(image)

        # Même principe que pour l'affichage : on fait tenir le viewBox
        # dans l'image en conservant le ratio, centré.
        scale = min(
            img_w / view_box.width(),
            img_h / view_box.height(),
        )

        painter.translate(img_w / 2.0, img_h / 2.0)
        painter.scale(scale, scale)
        painter.translate(-view_box.center())

        self._renderer.render(painter)
        painter.end()

        # Recherche des pixels non noirs
        min_x = img_w
        max_x = -1
        min_y = img_h
        max_y = -1

        for y in range(img_h):
            scanline = image.scanLine(y)
            # On lit les pixels via QImage.pixel pour rester simple
            for x in range(img_w):
                if image.pixel(x, y) != 0xFF000000:  # ARGB : opaque noir
                    if x < min_x:
                        min_x = x
                    if x > max_x:
                        max_x = x
                    if y < min_y:
                        min_y = y
                    if y > max_y:
                        max_y = y

        if max_x < min_x or max_y < min_y:
            # Aucun contenu détecté
            return None

        # Conversion de la bounding box image -> coordonnées viewBox
        cx = view_box.center().x()
        cy = view_box.center().y()

        # Inversion de la transform appliquée plus haut :
        # x_img = (x_svg - cx) * scale + img_w/2
        # => x_svg = (x_img - img_w/2) / scale + cx
        def img_to_svg(x_img: float, y_img: float) -> tuple[float, float]:
            x_svg = (x_img - img_w / 2.0) / scale + cx
            y_svg = (y_img - img_h / 2.0) / scale + cy
            return x_svg, y_svg

        x0_svg, y0_svg = img_to_svg(min_x, min_y)
        x1_svg, y1_svg = img_to_svg(max_x, max_y)

        return QRectF(
            min(x0_svg, x1_svg),
            min(y0_svg, y1_svg),
            abs(x1_svg - x0_svg),
            abs(y1_svg - y0_svg),
        )

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)

        # Fond noir pour que les traits blancs soient visibles
        painter.fillRect(self.rect(), Qt.black)

        if not self._renderer.isValid():
            return

        view_box: QRectF = self._renderer.viewBoxF()
        if view_box.isEmpty():
            self._renderer.render(painter)
            return

        # Si on a réussi à estimer une zone de contenu, on l'utilise,
        # sinon on se rabat sur la viewBox complète.
        box = self._content_box if self._content_box is not None else view_box

        scale = min(
            self.width() / box.width(),
            self.height() / box.height(),
        )

        # On centre la zone de contenu dans le wid
