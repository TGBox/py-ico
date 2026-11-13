from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

PreviewBgMode = Literal["dark", "light", "checker"]
SUPPORTED_IMAGE_SUFFIXES: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".ico"}
)


def pil_to_qimage(image: Image.Image) -> QImage:
    """Convert a Pillow Image into an independent RGBA QImage."""
    rgba = image.convert("RGBA")
    raw = rgba.tobytes("raw", "RGBA")
    qimage = QImage(
        raw,
        rgba.width,
        rgba.height,
        rgba.width * 4,
        QImage.Format.Format_RGBA8888,
    )
    return qimage.copy()


def qimage_to_pil(qimage: QImage) -> Image.Image:
    """Convert a QImage into a Pillow RGBA Image."""
    converted = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = converted.constBits()
    raw = bytes(ptr)[: converted.sizeInBytes()]
    return Image.frombytes(
        "RGBA",
        (converted.width(), converted.height()),
        raw,
        "raw",
        "RGBA",
        converted.bytesPerLine(),
    )


def _draw_background(
    painter: QPainter, rect: QRect, mode: PreviewBgMode, tile_size: int = 12
) -> None:
    if mode == "dark":
        painter.fillRect(rect, QColor("#18181B"))
        return
    if mode == "light":
        painter.fillRect(rect, QColor("#F4F4F5"))
        return

    light = QColor("#E4E4E7")
    dark = QColor("#D4D4D8")
    painter.fillRect(rect, light)
    start_x = rect.left()
    start_y = rect.top()
    for y in range(start_y, rect.bottom() + 1, tile_size):
        row_idx = (y - start_y) // tile_size
        for x in range(start_x, rect.right() + 1, tile_size):
            col_idx = (x - start_x) // tile_size
            if (row_idx + col_idx) % 2 == 1:
                w = min(tile_size, rect.right() - x + 1)
                h = min(tile_size, rect.bottom() - y + 1)
                painter.fillRect(x, y, w, h, dark)


class InteractivePreviewWidget(QWidget):
    """Canvas displaying the icon preview or original image with drag & drop and pipette."""

    file_dropped = Signal(Path)
    color_picked = Signal(int, int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._pil_image: Image.Image | None = None
        self._pixmap: QPixmap | None = None
        self._bg_mode: PreviewBgMode = "checker"
        self._pipette_active = False
        self._image_rect = QRect()

    def set_background_mode(self, mode: PreviewBgMode) -> None:
        """Set the canvas background style."""
        self._bg_mode = mode
        self.update()

    def set_pipette_active(self, active: bool) -> None:
        """Enable or disable color picking on click."""
        self._pipette_active = active
        self.setCursor(Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_image(self, image: Image.Image | None) -> None:
        """Update the displayed Pillow image."""
        self._pil_image = image
        if image is None:
            self._pixmap = None
        else:
            self._pixmap = QPixmap.fromImage(pil_to_qimage(image))
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES:
                        self.file_dropped.emit(path)
                        event.acceptProposedAction()
                        return
        event.ignore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self._pipette_active
            and event.button() == Qt.MouseButton.LeftButton
            and self._pil_image is not None
            and not self._image_rect.isEmpty()
        ):
            pos: QPoint = event.position().toPoint()
            if self._image_rect.contains(pos):
                rel_x = (pos.x() - self._image_rect.x()) / max(1, self._image_rect.width())
                rel_y = (pos.y() - self._image_rect.y()) / max(1, self._image_rect.height())
                px = min(self._pil_image.width - 1, max(0, int(rel_x * self._pil_image.width)))
                py = min(self._pil_image.height - 1, max(0, int(rel_y * self._pil_image.height)))
                rgb = self._pil_image.convert("RGB").getpixel((px, py))
                self.color_picked.emit(int(rgb[0]), int(rgb[1]), int(rgb[2]))
                return
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        canvas_rect = self.rect().adjusted(1, 1, -1, -1)
        _draw_background(painter, canvas_rect, self._bg_mode, tile_size=14)

        border_color = QColor("#38BDF8") if self._pipette_active else QColor("#3F3F46")
        painter.setPen(QPen(border_color, 2 if self._pipette_active else 1))
        painter.drawRect(canvas_rect)

        if self._pixmap is None or self._pixmap.isNull():
            self._image_rect = QRect()
            painter.setPen(QColor("#A1A1AA" if self._bg_mode == "dark" else "#3F3F46"))
            painter.drawText(
                canvas_rect.adjusted(24, 24, -24, -24),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Bild hierher ziehen,\nStrg+V drücken (Zwischenablage)\n"
                "oder oben auf „Bild öffnen…“ klicken.",
            )
            return

        padded = canvas_rect.adjusted(16, 16, -16, -16)
        scaled_size = self._pixmap.size().scaled(padded.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = padded.x() + (padded.width() - scaled_size.width()) // 2
        y = padded.y() + (padded.height() - scaled_size.height()) // 2
        self._image_rect = QRect(x, y, scaled_size.width(), scaled_size.height())
        painter.drawPixmap(self._image_rect, self._pixmap)


class _SizeTile(QWidget):
    """Single real-size icon preview tile."""

    def __init__(
        self,
        label_text: str,
        display_px: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._display_px = display_px
        self._bg_mode: PreviewBgMode = "dark"
        self._pixmap: QPixmap | None = None
        self._active = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._preview_box = QWidget(self)
        box_size = max(display_px + 12, 36)
        self._preview_box.setFixedSize(box_size, box_size)

        self._label = QLabel(label_text, self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("font-size: 11px; color: #A1A1AA;")

        layout.addWidget(self._preview_box, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_tile_data(
        self,
        image: Image.Image | None,
        bg_mode: PreviewBgMode,
        active: bool,
    ) -> None:
        self._bg_mode = bg_mode
        self._active = active
        self._pixmap = QPixmap.fromImage(pil_to_qimage(image)) if image is not None else None
        self._label.setStyleSheet(
            "font-size: 11px; color: #F4F4F5; font-weight: 600;"
            if active
            else "font-size: 11px; color: #71717A;"
        )
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        box_geo = self._preview_box.geometry()
        _draw_background(painter, box_geo, self._bg_mode, tile_size=8)
        painter.setPen(QPen(QColor("#3F3F46" if self._active else "#27272A"), 1))
        painter.drawRect(box_geo.adjusted(0, 0, -1, -1))

        if self._pixmap is not None and not self._pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target_w = min(self._display_px, box_geo.width() - 4)
            target_h = min(self._display_px, box_geo.height() - 4)
            x = box_geo.x() + (box_geo.width() - target_w) // 2
            y = box_geo.y() + (box_geo.height() - target_h) // 2
            painter.drawPixmap(QRect(x, y, target_w, target_h), self._pixmap)


class RealContextPreviewBar(QWidget):
    """Displays 16px..256px previews on toggleable dark, light, or checkerboard backgrounds."""

    background_changed = Signal(str)

    DISPLAY_SPECS: tuple[tuple[int, int, str], ...] = (
        (16, 16, "16×16"),
        (24, 24, "24×24"),
        (32, 32, "32×32"),
        (48, 48, "48×48"),
        (64, 64, "64×64"),
        (256, 72, "256×256"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bg_mode: PreviewBgMode = "dark"
        self._tiles: dict[int, _SizeTile] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Echtgrößen-Vorschau (Taskleiste & Explorer)", self)
        title.setStyleSheet("font-weight: 600; font-size: 12px;")
        header.addWidget(title)
        header.addStretch(1)

        self._bg_group = QButtonGroup(self)
        self._bg_group.setExclusive(True)
        for mode, text in (
            ("dark", "Dunkel"),
            ("light", "Hell"),
            ("checker", "Schachbrett"),
        ):
            btn = QPushButton(text, self)
            btn.setCheckable(True)
            btn.setChecked(mode == self._bg_mode)
            btn.setProperty("bgMode", mode)
            btn.clicked.connect(self._on_bg_button_clicked)
            self._bg_group.addButton(btn)
            header.addWidget(btn)

        root.addLayout(header)

        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(8)
        for icon_size, display_px, label in self.DISPLAY_SPECS:
            tile = _SizeTile(label, display_px, self)
            self._tiles[icon_size] = tile
            tiles_row.addWidget(tile)
        tiles_row.addStretch(1)
        root.addLayout(tiles_row)

    @property
    def background_mode(self) -> PreviewBgMode:
        return self._bg_mode

    def _on_bg_button_clicked(self) -> None:
        sender = self.sender()
        if isinstance(sender, QPushButton):
            mode = sender.property("bgMode")
            if mode in ("dark", "light", "checker"):
                self._bg_mode = mode
                self.background_changed.emit(mode)

    def update_frames(
        self,
        frames: Mapping[int, Image.Image],
        enabled_sizes: set[int],
    ) -> None:
        """Refresh each size tile with the current generated icon frames."""
        for icon_size, tile in self._tiles.items():
            tile.set_tile_data(
                image=frames.get(icon_size),
                bg_mode=self._bg_mode,
                active=icon_size in enabled_sizes,
            )

    def sizeHint(self) -> QSize:
        return QSize(560, 140)
