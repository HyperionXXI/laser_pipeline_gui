from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel


@dataclass(frozen=True)
class PreviewResult:
    """Small helper that can be used by services/controllers if needed."""
    path: Path
    kind: str  # "raster" | "svg"


class _BasePreview(QLabel):
    def __init__(self, placeholder: str = "Aucune image") -> None:
        super().__init__()
        self._placeholder = placeholder
        self._pixmap: Optional[QPixmap] = None

        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(QSize(120, 120))
        self.setStyleSheet(
            "QLabel { background: black; color: #B0B0B0; border: 1px solid #B0B0B0; }"
        )
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        self._pixmap = None
        self.setText(self._placeholder)
        self.setPixmap(QPixmap())

    def clear(self) -> None:  # noqa: A003 (Qt API name)
        self._show_placeholder()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._pixmap is not None:
            self._apply_scaled_pixmap()

    def _apply_scaled_pixmap(self) -> None:
        assert self._pixmap is not None
        scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setPixmap(scaled)
        self.setText("")


class RasterPreview(_BasePreview):
    def __init__(self, placeholder: str = "Aucune image") -> None:
        super().__init__(placeholder=placeholder)

    def show_image(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            self._show_placeholder()
            return

        pix = QPixmap(str(p))
        if pix.isNull():
            self._show_placeholder()
            return

        self._pixmap = pix
        self._apply_scaled_pixmap()


class SvgPreview(_BasePreview):
    def __init__(self, placeholder: str = "Aucun SVG") -> None:
        super().__init__(placeholder=placeholder)

    def show_svg(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            self._show_placeholder()
            return

        renderer = QSvgRenderer(str(p))
        if not renderer.isValid():
            self._show_placeholder()
            return

        # Render into an image with the widget size (or a sensible default)
        w = max(1, self.width())
        h = max(1, self.height())
        img = QImage(w, h, QImage.Format_ARGB32)
        img.fill(Qt.black)

        painter = QPainter(img)
        try:
            renderer.render(painter)
        finally:
            painter.end()

        pix = QPixmap.fromImage(img)
        self._pixmap = pix
        self._apply_scaled_pixmap()
