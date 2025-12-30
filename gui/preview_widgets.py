# gui/preview_widgets.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPixmapCache
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


PathLike = Union[str, Path]


@dataclass
class PreviewState:
    path: Optional[Path] = None


class RasterPreview(QWidget):
    """
    Raster preview widget (PNG/BMP/ILDA preview rendered to PNG, etc.).
    - Always expandable (layout-friendly)
    - Shows a black background even when no image is loaded
    - Scales on resize (KeepAspectRatio)
    """

    def __init__(
        self,
        *,
        min_size: QSize = QSize(180, 120),
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._state = PreviewState()
        self._pixmap_src: Optional[QPixmap] = None
        self._aspect_ratio: Optional[float] = None
        self._grid_enabled = False

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("background: #000; border: 1px solid #333;")
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._label.setMinimumSize(min_size)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        size_policy.setHeightForWidth(True)
        self.setSizePolicy(size_policy)
        self.setMinimumSize(min_size)

        self.clear()

        # --- API expected by main_window.py ---
    # --- Compat API (older main_window code) ---
    def show_image(self, path: str) -> None:
        self.set_path(path)

    def clear_preview(self) -> None:
        """Compat alias: some callers use clear_preview()."""
        self.clear()

    def clear_image(self) -> None:
        """Compat alias: some callers use clear_image()."""
        self.clear_preview()

    def set_aspect_ratio(self, ratio: Optional[float]) -> None:
        if ratio is None or ratio <= 0:
            self._aspect_ratio = None
        else:
            self._aspect_ratio = float(ratio)
        self.updateGeometry()
        self._apply_scaled_pixmap()

    def set_grid_enabled(self, enabled: bool) -> None:
        self._grid_enabled = bool(enabled)
        self._apply_scaled_pixmap()

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return self._aspect_ratio is not None

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        if self._aspect_ratio is None or width <= 0:
            return super().heightForWidth(width)
        return max(1, int(round(width / self._aspect_ratio)))

    def sizeHint(self) -> QSize:  # noqa: N802
        base = self.minimumSize()
        if self._aspect_ratio is None:
            return base
        return QSize(base.width(), max(base.height(), self.heightForWidth(base.width())))



    def set_path(self, path: Optional[PathLike]) -> None:
        if path is None:
            self.clear()
            return

        p = Path(path)
        self._state.path = p

        if not p.exists():
            self._pixmap_src = None
            self._label.setToolTip(f"File not found: {p}")
            self._label.setPixmap(QPixmap())  # null pixmap, black background remains
            return

        QPixmapCache.remove(str(p))
        pm = QPixmap(str(p))
        if pm.isNull():
            self._pixmap_src = None
            self._label.setToolTip(f"Failed to load image: {p}")
            self._label.setPixmap(QPixmap())
            return

        self._pixmap_src = pm
        self._label.setToolTip(str(p))
        self._apply_scaled_pixmap()

    def clear(self) -> None:
        self._state.path = None
        self._pixmap_src = None
        self._label.setToolTip("")
        self._label.setPixmap(QPixmap())  # black background via stylesheet

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_scaled_pixmap()

    def _apply_scaled_pixmap(self) -> None:
        target = self._label.size()
        if target.width() <= 2 or target.height() <= 2:
            return

        if self._pixmap_src is None or self._pixmap_src.isNull():
            if self._grid_enabled:
                pm = QPixmap(target)
                pm.fill(Qt.black)
                painter = QPainter(pm)
                try:
                    self._draw_grid(painter, target)
                finally:
                    painter.end()
                self._label.setPixmap(pm)
            else:
                self._label.setPixmap(QPixmap())
            return

        scaled = self._pixmap_src.scaled(
            target, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        if not self._grid_enabled:
            self._label.setPixmap(scaled)
            return

        pm = QPixmap(target)
        pm.fill(Qt.black)
        painter = QPainter(pm)
        try:
            x = int((target.width() - scaled.width()) / 2)
            y = int((target.height() - scaled.height()) / 2)
            painter.drawPixmap(x, y, scaled)
            self._draw_grid(painter, target)
        finally:
            painter.end()
        self._label.setPixmap(pm)

    def _draw_grid(self, painter: QPainter, target: QSize) -> None:
        size = min(target.width(), target.height())
        left = int((target.width() - size) / 2)
        top = int((target.height() - size) / 2)
        rect = (left, top, size, size)

        grid_pen = QPen(QColor(180, 180, 180, 120), 1)
        grid_pen.setCosmetic(True)
        painter.setPen(grid_pen)

        divisions = 10
        step = size / divisions
        for i in range(1, divisions):
            x = int(left + i * step)
            y = int(top + i * step)
            painter.drawLine(x, top, x, top + size)
            painter.drawLine(left, y, left + size, y)

        border_pen = QPen(QColor(220, 220, 220, 160), 1)
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        painter.drawRect(left, top, size, size)

        painter.drawEllipse(left, top, size, size)


class SvgPreview(QWidget):
    """
    SVG preview (rasterized in the QLabel) with resize scaling.
    """

    def __init__(
        self,
        *,
        min_size: QSize = QSize(180, 120),
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._state = PreviewState()
        self._renderer: Optional[QSvgRenderer] = None
        self._aspect_ratio: Optional[float] = None

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("background: #000; border: 1px solid #333;")
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._label.setMinimumSize(min_size)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

        size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        size_policy.setHeightForWidth(True)
        self.setSizePolicy(size_policy)
        self.setMinimumSize(min_size)

        self.clear()

    def show_image(self, path: PathLike) -> None:
        self.set_path(path)

    def set_path(self, path: Optional[PathLike]) -> None:
        if path is None:
            self.clear()
            return

        p = Path(path)
        self._state.path = p

        if not p.exists():
            self._renderer = None
            self._label.setToolTip(f"Fichier introuvable: {p}")
            self._label.setPixmap(QPixmap())
            return

        r = QSvgRenderer(str(p))
        if not r.isValid():
            self._renderer = None
            self._label.setToolTip(f"SVG invalide: {p}")
            self._label.setPixmap(QPixmap())
            return

        self._renderer = r
        self._label.setToolTip(str(p))
        self._rerender()

    def clear(self) -> None:
        self._state.path = None
        self._renderer = None
        self._label.setToolTip("")
        self._label.setPixmap(QPixmap())

    def show_svg(self, path: PathLike) -> None:
        """Compat alias: MainWindow calls show_svg()."""
        self.set_path(path)

    def clear_preview(self) -> None:
        """Compat alias."""
        self.clear()

    def clear_image(self) -> None:
        self.clear()

    def set_aspect_ratio(self, ratio: Optional[float]) -> None:
        if ratio is None or ratio <= 0:
            self._aspect_ratio = None
        else:
            self._aspect_ratio = float(ratio)
        self.updateGeometry()
        self._rerender()

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return self._aspect_ratio is not None

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        if self._aspect_ratio is None or width <= 0:
            return super().heightForWidth(width)
        return max(1, int(round(width / self._aspect_ratio)))

    def sizeHint(self) -> QSize:  # noqa: N802
        base = self.minimumSize()
        if self._aspect_ratio is None:
            return base
        return QSize(base.width(), max(base.height(), self.heightForWidth(base.width())))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rerender()

    def _rerender(self) -> None:
        if self._renderer is None:
            return

        target = self._label.size()
        if target.width() <= 2 or target.height() <= 2:
            return

        img = QImage(target, QImage.Format_ARGB32)
        img.fill(0x00000000)  # transparent; fond noir vient du stylesheet

        painter = QPainter(img)
        try:
            self._renderer.render(painter)
        finally:
            painter.end()

        pm = QPixmap.fromImage(img)
        self._label.setPixmap(pm)

    
