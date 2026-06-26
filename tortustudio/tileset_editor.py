"""Tileset editor: import sheet → edit one tile → save to stack."""

from __future__ import annotations

from enum import Enum
import math
from pathlib import Path

import pygame
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QImage, QMouseEvent, QPainter, QPen, QPolygonF, QWheelEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tortuengine.image import load_image
from tortustudio.color_key_widget import ColorKeyWidget
from tortuengine.palette import (
    PAINTABLE_INDICES,
    TRANSPARENT_INDEX,
    list_palette_names,
    load_palette,
    palette_path,
)
from tortuengine.tileset import (
    COLLISION_NONE,
    COLLISION_POLYGON,
    COLLISION_SOLID,
    COLLISION_TYPES,
    ONE_WAY_DOWN,
    ONE_WAY_LEFT,
    ONE_WAY_NONE,
    ONE_WAY_RIGHT,
    ONE_WAY_TYPES,
    ONE_WAY_UP,
    Tileset,
    STACK_PREVIEW_EMPTY_BG,
    existing_stack_preview_path,
    load_tileset,
    save_tileset,
    stack_sidecar_path,
    surface_tile_to_pixels,
)


class Tool(str, Enum):
    PENCIL = "pencil"
    ERASER = "eraser"
    EYEDROPPER = "eyedropper"


_ONE_WAY_ARROW_COLOR = QColor(255, 230, 80, 230)
_ONE_WAY_ARROW_BG = QColor(20, 20, 30, 160)


def _one_way_direction(one_way: str) -> tuple[float, float] | None:
    if one_way == ONE_WAY_UP:
        return 0.0, -1.0
    if one_way == ONE_WAY_DOWN:
        return 0.0, 1.0
    if one_way == ONE_WAY_LEFT:
        return -1.0, 0.0
    if one_way == ONE_WAY_RIGHT:
        return 1.0, 0.0
    return None


def _draw_one_way_arrow(
    painter: QPainter,
    x: float,
    y: float,
    w: float,
    h: float,
    one_way: str,
    *,
    line_width: int = 2,
) -> None:
    direction = _one_way_direction(one_way)
    if direction is None:
        return

    dx, dy = direction
    cx = x + w / 2
    cy = y + h / 2
    length = min(w, h) * 0.34
    head = length * 0.38
    bg_radius = min(w, h) * 0.22

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(_ONE_WAY_ARROW_BG))
    painter.drawEllipse(QPointF(cx, cy), bg_radius, bg_radius)

    tip_x = cx + dx * length
    tip_y = cy + dy * length
    tail_x = cx - dx * length * 0.45
    tail_y = cy - dy * length * 0.45
    px, py = -dy, dx
    head_w = head * 0.55

    pen = QPen(_ONE_WAY_ARROW_COLOR)
    pen.setWidth(line_width)
    pen.setCosmetic(True)
    painter.setPen(pen)
    painter.setBrush(QBrush(_ONE_WAY_ARROW_COLOR))
    painter.drawLine(QPointF(tail_x, tail_y), QPointF(tip_x, tip_y))
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(tip_x, tip_y),
                QPointF(tip_x - dx * head + px * head_w, tip_y - dy * head + py * head_w),
                QPointF(tip_x - dx * head - px * head_w, tip_y - dy * head - py * head_w),
            ]
        )
    )


class ImportImageCanvas(QWidget):
    """Source sheet — click a tile to select the import region."""

    PIXEL_GRID_COLOR = (72, 72, 92)
    TILE_GRID_COLOR = (36, 36, 50)
    TILE_GRID_WIDTH = 2
    SELECTION_COLOR = (255, 220, 80)

    tile_clicked = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.zoom = 8
        self.tile_size = 8
        self.show_pixel_grid = False
        self.show_tile_grid = True
        self.selected_tile_x = 0
        self.selected_tile_y = 0
        self._frame: QImage | None = None
        self._image_w = 0
        self._image_h = 0
        self.setMinimumSize(160, 160)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_image(self, surface: pygame.Surface | None) -> None:
        if surface is None:
            self._frame = None
            self._image_w = 0
            self._image_h = 0
            self.update()
            return
        w, h = surface.get_width(), surface.get_height()
        data = pygame.image.tobytes(surface, "RGBA")
        self._frame = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        self._image_w, self._image_h = w, h
        self.setMinimumSize(w * self.zoom, h * self.zoom)
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(2, min(32, zoom))
        if self._image_w:
            self.setMinimumSize(self._image_w * self.zoom, self._image_h * self.zoom)
        self.update()

    def set_tile_size(self, size: int) -> None:
        self.tile_size = max(1, size)
        self.update()

    def set_selected_tile(self, tx: int, ty: int) -> None:
        self.selected_tile_x = tx
        self.selected_tile_y = ty
        self.update()

    def _image_offset(self) -> tuple[int, int]:
        sw = self._image_w * self.zoom
        sh = self._image_h * self.zoom
        return (self.width() - sw) // 2, (self.height() - sh) // 2

    def _event_to_pixel(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None:
            return None
        ox, oy = self._image_offset()
        px = int((event.position().x() - ox) // self.zoom)
        py = int((event.position().y() - oy) // self.zoom)
        if 0 <= px < self._image_w and 0 <= py < self._image_h:
            return px, py
        return None

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None:
            painter.end()
            return

        scaled = self._frame.scaled(
            self._image_w * self.zoom,
            self._image_h * self.zoom,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        ox, oy = self._image_offset()
        painter.drawImage(ox, oy, scaled)

        tiles_w = self._image_w // self.tile_size if self.tile_size else 0
        tiles_h = self._image_h // self.tile_size if self.tile_size else 0
        if self.selected_tile_x < tiles_w and self.selected_tile_y < tiles_h:
            tx = self.selected_tile_x * self.tile_size * self.zoom
            ty = self.selected_tile_y * self.tile_size * self.zoom
            size = self.tile_size * self.zoom
            pen = QPen(QColor(*self.SELECTION_COLOR))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(ox + tx, oy + ty, size, size)

        pw, ph = self._image_w, self._image_h
        sw, sh = pw * self.zoom, ph * self.zoom
        if self.show_pixel_grid:
            pen = QPen(QColor(*self.PIXEL_GRID_COLOR))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(1, pw):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for py in range(1, ph):
                ly = oy + py * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)
        if self.show_tile_grid and self.tile_size:
            pen = QPen(QColor(*self.TILE_GRID_COLOR))
            pen.setWidth(self.TILE_GRID_WIDTH)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(self.tile_size, pw, self.tile_size):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for py in range(self.tile_size, ph, self.tile_size):
                ly = oy + py * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = self._event_to_pixel(event)
        if not pos:
            return
        tx = pos[0] // self.tile_size
        ty = pos[1] // self.tile_size
        if tx >= self._image_w // self.tile_size or ty >= self._image_h // self.tile_size:
            return
        self.set_selected_tile(tx, ty)
        self.tile_clicked.emit(tx, ty)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_zoom(self.zoom + 2)
        elif delta < 0:
            self.set_zoom(self.zoom - 2)


class SingleTileCanvas(QWidget):
    """Editable buffer for one tile before it is saved to the stack."""

    PIXEL_GRID_COLOR = (72, 72, 92)

    changed = pyqtSignal()
    tool_cycled = pyqtSignal(object)

    _TOOL_CYCLE = [Tool.PENCIL, Tool.ERASER, Tool.EYEDROPPER]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not pygame.get_init():
            pygame.init()

        self.palette: list[tuple[int, int, int]] = []
        self.pixels: list[int] = []
        self.tool = Tool.PENCIL
        self.current_index = 0
        self.zoom = 16
        self.show_pixel_grid = True
        self._drawing = False
        self._frame: QImage | None = None
        self._tile_size = 8

        self.setMinimumSize(128, 128)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_tile(self, pixels: list[int], tile_size: int, palette: list[tuple[int, int, int]]) -> None:
        self._tile_size = tile_size
        self.pixels = pixels.copy()
        self.palette = palette
        self._refresh()

    def get_pixels(self) -> list[int]:
        return self.pixels.copy()

    def clear_tile(self, tile_size: int) -> None:
        self.set_tile([TRANSPARENT_INDEX] * (tile_size * tile_size), tile_size, self.palette)

    def set_tool(self, tool: Tool) -> None:
        self.tool = tool

    def set_color_index(self, index: int) -> None:
        if index in PAINTABLE_INDICES:
            self.current_index = index

    def set_show_pixel_grid(self, visible: bool) -> None:
        self.show_pixel_grid = visible
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(4, min(48, zoom))
        self.setMinimumSize(self._tile_size * self.zoom, self._tile_size * self.zoom)
        self.update()

    def _pixel_at(self, x: int, y: int) -> int:
        if 0 <= x < self._tile_size and 0 <= y < self._tile_size:
            return self.pixels[y * self._tile_size + x]
        return TRANSPARENT_INDEX

    def _set_pixel(self, x: int, y: int, index: int) -> None:
        if 0 <= x < self._tile_size and 0 <= y < self._tile_size:
            self.pixels[y * self._tile_size + x] = index

    def _refresh(self) -> None:
        size = self._tile_size
        if not self.pixels or size < 1:
            self._frame = None
            self.update()
            return

        composite = pygame.Surface((size, size), pygame.SRCALPHA)
        for y in range(size):
            for x in range(size):
                index = self._pixel_at(x, y)
                if index == TRANSPARENT_INDEX:
                    continue
                rgb = self.palette[index]
                composite.set_at((x, y), (*rgb, 255))

        data = pygame.image.tobytes(composite, "RGBA")
        self._frame = QImage(data, size, size, size * 4, QImage.Format.Format_RGBA8888)
        self.setMinimumSize(size * self.zoom, size * self.zoom)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None:
            painter.end()
            return

        scaled = self._frame.scaled(
            self._tile_size * self.zoom,
            self._tile_size * self.zoom,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        sw = self._tile_size * self.zoom
        sh = self._tile_size * self.zoom
        ox = (self.width() - sw) // 2
        oy = (self.height() - sh) // 2
        painter.drawImage(ox, oy, scaled)

        if self.show_pixel_grid and self._tile_size > 1:
            pen = QPen(QColor(*self.PIXEL_GRID_COLOR))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(1, self._tile_size):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for py in range(1, self._tile_size):
                ly = oy + py * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)
        painter.end()

    def _event_to_pixel(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None:
            return None
        sw = self._tile_size * self.zoom
        sh = self._tile_size * self.zoom
        ox = (self.width() - sw) // 2
        oy = (self.height() - sh) // 2
        px = int((event.position().x() - ox) // self.zoom)
        py = int((event.position().y() - oy) // self.zoom)
        if 0 <= px < self._tile_size and 0 <= py < self._tile_size:
            return px, py
        return None

    def _apply_tool(self, x: int, y: int) -> None:
        if self.tool == Tool.PENCIL:
            self._set_pixel(x, y, self.current_index)
        elif self.tool == Tool.ERASER:
            self._set_pixel(x, y, TRANSPARENT_INDEX)
        elif self.tool == Tool.EYEDROPPER:
            index = self._pixel_at(x, y)
            if index != TRANSPARENT_INDEX:
                self.current_index = index
                self.changed.emit()
        self._refresh()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_to_pixel(event)
            if pos:
                self._drawing = True
                self._apply_tool(*pos)
        elif event.button() == Qt.MouseButton.RightButton:
            idx = self._TOOL_CYCLE.index(self.tool)
            self.tool_cycled.emit(self._TOOL_CYCLE[(idx + 1) % len(self._TOOL_CYCLE)])

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drawing and event.buttons() & Qt.MouseButton.LeftButton:
            pos = self._event_to_pixel(event)
            if pos:
                self._apply_tool(*pos)
                self.changed.emit()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            self.changed.emit()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_zoom(self.zoom + 2)
        elif delta < 0:
            self.set_zoom(self.zoom - 2)


class CollisionShapeCanvas(QWidget):
    """Paint collision cells over the tile art (polygon mode)."""

    PIXEL_GRID_COLOR = (72, 72, 92)
    COLLISION_FILL = (220, 60, 60, 110)
    COLLISION_SOLID_FILL = (80, 180, 255, 100)

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.palette: list[tuple[int, int, int]] = []
        self.tile_pixels: list[int] = []
        self.mask: list[int] = []
        self.collision_type = COLLISION_NONE
        self.one_way = ONE_WAY_NONE
        self.zoom = 16
        self.show_pixel_grid = True
        self._drawing = False
        self._paint_collision = True
        self._frame: QImage | None = None
        self._tile_size = 8

        self.setMinimumSize(128, 128)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @property
    def editable(self) -> bool:
        return self.collision_type == COLLISION_POLYGON

    def set_context(
        self,
        tile_pixels: list[int],
        mask: list[int],
        tile_size: int,
        palette: list[tuple[int, int, int]],
        collision_type: str,
        one_way: str = ONE_WAY_NONE,
    ) -> None:
        self._tile_size = tile_size
        self.tile_pixels = tile_pixels.copy()
        self.mask = mask.copy()
        self.palette = palette
        self.collision_type = collision_type
        self.one_way = one_way
        self._refresh()

    def set_one_way(self, one_way: str) -> None:
        self.one_way = one_way
        self.update()

    def get_mask(self) -> list[int]:
        return self.mask.copy()

    def set_paint_mode(self, paint: bool) -> None:
        self._paint_collision = paint

    def set_show_pixel_grid(self, visible: bool) -> None:
        self.show_pixel_grid = visible
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(4, min(48, zoom))
        self.setMinimumSize(self._tile_size * self.zoom, self._tile_size * self.zoom)
        self.update()

    def _effective_mask(self) -> list[int]:
        if self.collision_type == COLLISION_SOLID:
            return [1] * (self._tile_size * self._tile_size)
        if self.collision_type == COLLISION_NONE:
            return [0] * (self._tile_size * self._tile_size)
        return self.mask

    def _refresh(self) -> None:
        size = self._tile_size
        if size < 1:
            self._frame = None
            self.update()
            return

        tile_layer = pygame.Surface((size, size), pygame.SRCALPHA)
        overlay = pygame.Surface((size, size), pygame.SRCALPHA)
        effective = self._effective_mask()
        for y in range(size):
            for x in range(size):
                idx = y * size + x
                pixel_index = (
                    self.tile_pixels[idx]
                    if idx < len(self.tile_pixels)
                    else TRANSPARENT_INDEX
                )
                if pixel_index != TRANSPARENT_INDEX:
                    rgb = self.palette[pixel_index]
                    tile_layer.set_at((x, y), (*rgb, 255))
                if effective[idx]:
                    fill = (
                        self.COLLISION_SOLID_FILL
                        if self.collision_type == COLLISION_SOLID
                        else self.COLLISION_FILL
                    )
                    overlay.set_at((x, y), fill)

        composite = tile_layer.copy()
        composite.blit(overlay, (0, 0))

        data = pygame.image.tobytes(composite, "RGBA")
        self._frame = QImage(data, size, size, size * 4, QImage.Format.Format_RGBA8888)
        self.setMinimumSize(size * self.zoom, size * self.zoom)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None:
            painter.end()
            return

        scaled = self._frame.scaled(
            self._tile_size * self.zoom,
            self._tile_size * self.zoom,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        sw = self._tile_size * self.zoom
        sh = self._tile_size * self.zoom
        ox = (self.width() - sw) // 2
        oy = (self.height() - sh) // 2
        painter.drawImage(ox, oy, scaled)

        if self.show_pixel_grid and self._tile_size > 1:
            pen = QPen(QColor(*self.PIXEL_GRID_COLOR))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(1, self._tile_size):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for py in range(1, self._tile_size):
                ly = oy + py * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)

        _draw_one_way_arrow(
            painter,
            ox,
            oy,
            sw,
            sh,
            self.one_way,
            line_width=max(2, self.zoom // 5),
        )
        painter.end()

    def _event_to_cell(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None:
            return None
        sw = self._tile_size * self.zoom
        sh = self._tile_size * self.zoom
        ox = (self.width() - sw) // 2
        oy = (self.height() - sh) // 2
        px = int((event.position().x() - ox) // self.zoom)
        py = int((event.position().y() - oy) // self.zoom)
        if 0 <= px < self._tile_size and 0 <= py < self._tile_size:
            return px, py
        return None

    def _apply_cell(self, x: int, y: int) -> None:
        if not self.editable:
            return
        value = 1 if self._paint_collision else 0
        self.mask[y * self._tile_size + x] = value
        self._refresh()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.editable:
            pos = self._event_to_cell(event)
            if pos:
                self._drawing = True
                self._apply_cell(*pos)
                self.changed.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drawing and event.buttons() & Qt.MouseButton.LeftButton and self.editable:
            pos = self._event_to_cell(event)
            if pos:
                self._apply_cell(*pos)
                self.changed.emit()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            self.changed.emit()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_zoom(self.zoom + 2)
        elif delta < 0:
            self.set_zoom(self.zoom - 2)


class TilesetStripCanvas(QWidget):
    """Horizontal tile stack preview — click to load a tile into the editor."""

    SELECTION_COLOR = (255, 220, 80)
    GRID_COLOR = (36, 36, 50)
    EMPTY_BG = (48, 48, 60)
    COLLISION_FILL = (220, 60, 60, 110)
    COLLISION_SOLID_FILL = (80, 180, 255, 100)

    tile_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tileset: Tileset | None = None
        self.palette: list[tuple[int, int, int]] = []
        self.selected_index = 0
        self.cell_size = 32
        self.show_collision = False
        self.show_one_way = False
        self._columns_per_row = 8
        self._cols = 1
        self._rows = 0
        self.setMinimumHeight(self.cell_size + 8)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_columns_per_row(self, cols: int) -> None:
        self._columns_per_row = max(1, cols)
        self._update_layout()

    def set_show_collision(self, visible: bool) -> None:
        self.show_collision = visible
        self.update()

    def set_show_one_way(self, visible: bool) -> None:
        self.show_one_way = visible
        self.update()

    def _build_tile_image(self, index: int, tile: list[int], size: int) -> QImage:
        tile_img = pygame.Surface((size, size), pygame.SRCALPHA)
        for ly in range(size):
            for lx in range(size):
                pixel_index = tile[ly * size + lx]
                if pixel_index == TRANSPARENT_INDEX:
                    tile_img.set_at((lx, ly), (*self.EMPTY_BG, 255))
                else:
                    rgb = self.palette[pixel_index]
                    tile_img.set_at((lx, ly), (*rgb, 255))

        if self.show_collision and self.tileset:
            collision = self.tileset.get_collision(index)
            if collision != COLLISION_NONE:
                mask = self.tileset.get_collision_shape(index)
                overlay = pygame.Surface((size, size), pygame.SRCALPHA)
                fill = (
                    self.COLLISION_SOLID_FILL
                    if collision == COLLISION_SOLID
                    else self.COLLISION_FILL
                )
                for ly in range(size):
                    for lx in range(size):
                        if mask[ly * size + lx]:
                            overlay.set_at((lx, ly), fill)
                tile_img.blit(overlay, (0, 0))

        data = pygame.image.tobytes(tile_img, "RGBA")
        return QImage(data, size, size, size * 4, QImage.Format.Format_RGBA8888)

    def set_tileset(self, tileset: Tileset | None, palette: list[tuple[int, int, int]]) -> None:
        self.tileset = tileset
        self.palette = palette
        self._update_layout()

    def _update_layout(self) -> None:
        if self.tileset and self.tileset.tiles:
            self._cols = max(1, self._columns_per_row)
            self._rows = max(1, math.ceil(self.tileset.tile_count / self._cols))
            disp_w = self._cols * self.cell_size + 8
            disp_h = self._rows * self.cell_size + 8
            self.setMinimumSize(disp_w, disp_h)
            self.resize(disp_w, disp_h)
        else:
            self._cols = 1
            self._rows = 0
            self.setMinimumSize(0, self.cell_size + 8)
            self.resize(self.cell_size + 8, self.cell_size + 8)
        self.updateGeometry()
        self.update()

    def set_selected_index(self, index: int) -> None:
        self.selected_index = index
        self.update()

    def _display_offset(self) -> tuple[int, int, int, int]:
        disp_w = self._cols * self.cell_size
        disp_h = self._rows * self.cell_size
        ox = max(4, (self.width() - disp_w) // 2)
        oy = max(4, (self.height() - disp_h) // 2)
        return ox, oy, disp_w, disp_h

    def _index_at(self, event: QMouseEvent) -> int | None:
        if not self.tileset:
            return None
        ox, oy, disp_w, disp_h = self._display_offset()
        local_x = event.position().x() - ox
        local_y = event.position().y() - oy
        if local_x < 0 or local_y < 0 or local_x >= disp_w or local_y >= disp_h:
            return None
        tx = int(local_x // self.cell_size)
        ty = int(local_y // self.cell_size)
        index = ty * self._cols + tx
        if index >= self.tileset.tile_count:
            return None
        return index

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if not self.tileset:
            painter.end()
            return

        ox, oy, disp_w, disp_h = self._display_offset()
        size = self.tileset.tile_size

        for i, tile in enumerate(self.tileset.tiles):
            tx = i % self._cols
            ty = i // self._cols
            cell_x = ox + tx * self.cell_size
            cell_y = oy + ty * self.cell_size

            qimg = self._build_tile_image(i, tile, size)
            scaled = qimg.scaled(
                self.cell_size,
                self.cell_size,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            painter.drawImage(cell_x, cell_y, scaled)

            if self.show_one_way:
                one_way = self.tileset.get_one_way(i)
                if one_way != ONE_WAY_NONE:
                    _draw_one_way_arrow(
                        painter,
                        cell_x,
                        cell_y,
                        self.cell_size,
                        self.cell_size,
                        one_way,
                        line_width=2,
                    )

        pen = QPen(QColor(*self.GRID_COLOR))
        pen.setWidth(1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        for col in range(1, self._cols):
            lx = ox + col * self.cell_size
            painter.drawLine(lx, oy, lx, oy + disp_h)
        for row in range(1, self._rows):
            ly = oy + row * self.cell_size
            painter.drawLine(ox, ly, ox + disp_w, ly)

        if 0 <= self.selected_index < self.tileset.tile_count:
            tx = self.selected_index % self._cols
            ty = self.selected_index // self._cols
            sx = ox + tx * self.cell_size
            sy = oy + ty * self.cell_size
            pen = QPen(QColor(*self.SELECTION_COLOR))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sx, sy, self.cell_size, self.cell_size)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self._index_at(event)
        if index is not None:
            self.selected_index = index
            self.tile_clicked.emit(index)
            self.update()


class TilesetEditorWidget(QWidget):
    """Import sheet → edit buffer → save tiles to a growing stack."""

    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_tileset_requested = pyqtSignal()
    open_tileset_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.tileset: Tileset | None = None
        self._import_image: pygame.Surface | None = None
        self._palette_colors: list[tuple[int, int, int]] = []
        self._dirty = False
        self._buffer_dirty = False
        self._stack_index = 0
        self._pending_collision = COLLISION_NONE
        self._pending_one_way = ONE_WAY_NONE
        self._pending_collision_shape: list[int] = []

        self.import_canvas = ImportImageCanvas()
        self.import_canvas.tile_clicked.connect(self._on_import_tile_clicked)

        self.edit_canvas = SingleTileCanvas()
        self.edit_canvas.changed.connect(self._on_edit_canvas_changed)
        self.edit_canvas.tool_cycled.connect(self._set_tool)

        self.collision_canvas = CollisionShapeCanvas()
        self.collision_canvas.changed.connect(self._on_collision_canvas_changed)

        self.edit_tabs = QTabWidget()
        pencil_page = QWidget()
        pencil_layout = QVBoxLayout(pencil_page)
        pencil_layout.setContentsMargins(0, 0, 0, 0)
        pencil_scroll = QScrollArea()
        pencil_scroll.setWidgetResizable(True)
        pencil_scroll.setWidget(self.edit_canvas)
        pencil_layout.addWidget(pencil_scroll)
        self.edit_tabs.addTab(pencil_page, "Pencil")

        collision_page = QWidget()
        collision_layout = QVBoxLayout(collision_page)
        collision_layout.setContentsMargins(0, 0, 0, 0)
        collision_scroll = QScrollArea()
        collision_scroll.setWidgetResizable(True)
        collision_scroll.setWidget(self.collision_canvas)
        collision_layout.addWidget(collision_scroll)
        self.edit_tabs.addTab(collision_page, "Collision")
        self.edit_tabs.currentChanged.connect(self._on_edit_tab_changed)

        self.strip_canvas = TilesetStripCanvas()
        self.strip_canvas.tile_clicked.connect(self._on_strip_tile_clicked)

        self.tile_size = QSpinBox()
        self.tile_size.setRange(4, 64)
        self.tile_size.setValue(8)
        self.tile_size.setSuffix(" px")

        self.stack_index = QSpinBox()
        self.stack_index.setRange(0, 0)
        self.stack_index.valueChanged.connect(self._on_stack_index_spin_changed)

        self.btn_stack_prev = QPushButton("◀")
        self.btn_stack_prev.setFixedWidth(32)
        self.btn_stack_prev.clicked.connect(self._prev_stack_tile)
        self.btn_stack_next = QPushButton("▶")
        self.btn_stack_next.setFixedWidth(32)
        self.btn_stack_next.clicked.connect(self._next_stack_tile)

        self.stack_label = QLabel("0 tiles")
        self.editor_status_label = QLabel("New tile")

        self.show_import_pixel_grid = QCheckBox("Import: 1×1 grid")
        self.show_import_pixel_grid.toggled.connect(self._toggle_import_pixel_grid)
        self.show_import_tile_grid = QCheckBox("Import: tile grid")
        self.show_import_tile_grid.setChecked(True)
        self.show_import_tile_grid.toggled.connect(self._toggle_import_tile_grid)
        self.show_edit_pixel_grid = QCheckBox("Edit: 1×1 grid")
        self.show_edit_pixel_grid.setChecked(True)
        self.show_edit_pixel_grid.toggled.connect(self._toggle_edit_pixel_grid)

        self.show_strip_collision = QCheckBox("Stack: collision")
        self.show_strip_collision.toggled.connect(self._toggle_strip_collision)
        self.show_strip_one_way = QCheckBox("Stack: one-way")
        self.show_strip_one_way.toggled.connect(self._toggle_strip_one_way)

        self.strip_columns_per_row = QSpinBox()
        self.strip_columns_per_row.setRange(1, 64)
        self.strip_columns_per_row.setValue(8)
        self.strip_columns_per_row.setToolTip("Tiles per row in the stack preview (visual only)")
        self.strip_columns_per_row.valueChanged.connect(self._on_strip_columns_changed)

        self.palette_combo = QComboBox()
        self.palette_combo.currentTextChanged.connect(self._on_palette_changed)

        self.collision_combobox = QComboBox()
        self.collision_combobox.addItems(list(COLLISION_TYPES))
        self.collision_combobox.currentTextChanged.connect(self._on_collision_changed)

        self.one_way_combobox = QComboBox()
        self.one_way_combobox.addItems(list(ONE_WAY_TYPES))
        self.one_way_combobox.currentTextChanged.connect(self._on_one_way_changed)

        self.btn_pencil = QPushButton("Pencil")
        self.btn_eraser = QPushButton("Eraser")
        self.btn_dropper = QPushButton("Eyedropper")
        self.btn_pencil.setCheckable(True)
        self.btn_eraser.setCheckable(True)
        self.btn_dropper.setCheckable(True)
        self.btn_pencil.setChecked(True)
        self.btn_pencil.clicked.connect(lambda: self._set_tool(Tool.PENCIL))
        self.btn_eraser.clicked.connect(lambda: self._set_tool(Tool.ERASER))
        self.btn_dropper.clicked.connect(lambda: self._set_tool(Tool.EYEDROPPER))

        self.btn_collision_paint = QPushButton("Paint collision")
        self.btn_collision_erase = QPushButton("Erase collision")
        self.btn_collision_paint.setCheckable(True)
        self.btn_collision_erase.setCheckable(True)
        self.btn_collision_paint.setChecked(True)
        self.btn_collision_paint.clicked.connect(self._set_collision_paint)
        self.btn_collision_erase.clicked.connect(self._set_collision_erase)

        self.btn_save = QPushButton("Save tileset")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_tileset)
        self.btn_new = QPushButton("New Tileset…")
        self.btn_new.clicked.connect(self.new_tileset_requested.emit)
        self.btn_open = QPushButton("Open Tileset…")
        self.btn_open.clicked.connect(self.open_tileset_requested.emit)
        self.color_key = ColorKeyWidget()
        self.btn_load_import = QPushButton("Load Import Image…")
        self.btn_load_import.clicked.connect(self._load_import_image)
        self.btn_save_all = QPushButton("Save all from image")
        self.btn_save_all.setToolTip("Convert every import tile and append them to the stack")
        self.btn_save_all.clicked.connect(self._save_all_from_image)

        self.btn_load_to_editor = QPushButton("Load to editor")
        self.btn_load_to_editor.setToolTip(
            "Palette-convert the selected import tile into the edit canvas"
        )
        self.btn_load_to_editor.clicked.connect(self._load_import_to_editor)
        self.btn_save_to_stack = QPushButton("Save to stack")
        self.btn_save_to_stack.setToolTip(
            "Save tile pixels and collision mask to the stack, or replace the selected slot"
        )
        self.btn_save_to_stack.clicked.connect(self._save_to_stack)
        self.btn_clear_editor = QPushButton("Clear editor")
        self.btn_clear_editor.clicked.connect(self._clear_editor)

        self.swatches_area = QScrollArea()
        self.swatches_area.setWidgetResizable(True)
        self.swatches_widget = QWidget()
        self.swatches_grid = QGridLayout(self.swatches_widget)
        self.swatches_area.setWidget(self.swatches_widget)
        self.swatches_area.setMaximumHeight(160)

        self._build_layout()
        self._reload_palette_names()
        self._on_edit_tab_changed(0)

    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        file_row = QHBoxLayout()
        file_row.addWidget(self.btn_new)
        file_row.addWidget(self.btn_open)
        file_row.addWidget(self.btn_save)
        file_row.addWidget(self.btn_rename)
        file_row.addStretch()
        outer.addLayout(file_row)

        canvases = QHBoxLayout()
        outer.addLayout(canvases, stretch=1)

        import_group = QGroupBox("Import image")
        import_layout = QVBoxLayout(import_group)
        import_scroll = QScrollArea()
        import_scroll.setWidgetResizable(True)
        import_scroll.setWidget(self.import_canvas)
        import_layout.addWidget(import_scroll)
        import_layout.addWidget(self.btn_load_import)
        import_layout.addWidget(self.color_key)
        import_layout.addWidget(self.btn_save_all)
        canvases.addWidget(import_group, stretch=1)

        edit_group = QGroupBox("Edit tile")
        edit_layout = QVBoxLayout(edit_group)
        edit_layout.addWidget(self.edit_tabs)
        edit_row = QHBoxLayout()
        edit_row.addWidget(self.btn_load_to_editor)
        edit_row.addWidget(self.btn_save_to_stack)
        edit_row.addWidget(self.btn_clear_editor)
        edit_layout.addLayout(edit_row)
        canvases.addWidget(edit_group, stretch=1)

        side = QVBoxLayout()
        side.addWidget(QLabel("<b>Tileset Editor</b>"))

        form = QFormLayout()
        form.addRow("Tile size:", self.tile_size)
        form.addRow("Palette:", self.palette_combo)
        form.addRow("Stack:", self.stack_label)

        stack_row = QHBoxLayout()
        stack_row.addWidget(QLabel("#"))
        stack_row.addWidget(self.stack_index)
        stack_row.addWidget(self.btn_stack_prev)
        stack_row.addWidget(self.btn_stack_next)
        
        form.addRow("Tile slot:", stack_row)
        form.addRow("Editing:", self.editor_status_label)

        form.addRow(self.show_import_pixel_grid)
        form.addRow(self.show_import_tile_grid)
        form.addRow(self.show_edit_pixel_grid)

        form.addRow("Collision:", self.collision_combobox)
        form.addRow("One way:", self.one_way_combobox)

        side.addLayout(form)

        self.tile_size.valueChanged.connect(self._on_tile_size_changed)

        self.pencil_tools = QHBoxLayout()
        self.pencil_tools.addWidget(self.btn_pencil)
        self.pencil_tools.addWidget(self.btn_eraser)
        self.pencil_tools.addWidget(self.btn_dropper)
        side.addLayout(self.pencil_tools)

        self.collision_tools = QHBoxLayout()
        self.collision_tools.addWidget(self.btn_collision_paint)
        self.collision_tools.addWidget(self.btn_collision_erase)
        side.addLayout(self.collision_tools)
        self._set_collision_tool_row_visible(False)

        side.addWidget(QLabel("Palette colors (0–62):"))
        side.addWidget(self.swatches_area)
        side.addStretch()
        canvases.addLayout(side)

        strip_group = QGroupBox("Tile stack")
        strip_layout = QVBoxLayout(strip_group)
        strip_opts = QHBoxLayout()
        strip_opts.addWidget(self.show_strip_collision)
        strip_opts.addWidget(self.show_strip_one_way)
        strip_opts.addWidget(QLabel("Per row:"))
        strip_opts.addWidget(self.strip_columns_per_row)
        strip_opts.addStretch()
        strip_layout.addLayout(strip_opts)
        strip_scroll = QScrollArea()
        strip_scroll.setWidgetResizable(True)
        strip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        strip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        strip_scroll.setMaximumHeight(140)
        strip_scroll.setWidget(self.strip_canvas)
        strip_layout.addWidget(strip_scroll)
        outer.addWidget(strip_group)

    def _toggle_import_pixel_grid(self, visible: bool) -> None:
        self.import_canvas.show_pixel_grid = visible
        self.import_canvas.update()

    def _toggle_import_tile_grid(self, visible: bool) -> None:
        self.import_canvas.show_tile_grid = visible
        self.import_canvas.update()

    def _toggle_edit_pixel_grid(self, visible: bool) -> None:
        self.edit_canvas.set_show_pixel_grid(visible)
        self.collision_canvas.set_show_pixel_grid(visible)

    def _toggle_strip_collision(self, visible: bool) -> None:
        self.strip_canvas.set_show_collision(visible)

    def _toggle_strip_one_way(self, visible: bool) -> None:
        self.strip_canvas.set_show_one_way(visible)

    def _on_strip_columns_changed(self, value: int) -> None:
        self.strip_canvas.set_columns_per_row(value)

    def _update_strip_columns_limits(self) -> None:
        max_cols = max(1, self.tileset.tile_count) if self.tileset else 1
        self.strip_columns_per_row.setMaximum(max(1, max_cols))

    def _reset_strip_columns_per_row(self) -> None:
        if not self.tileset:
            return
        default = max(1, self.tileset.strip_columns)
        self.strip_columns_per_row.blockSignals(True)
        self._update_strip_columns_limits()
        self.strip_columns_per_row.setValue(min(default, self.strip_columns_per_row.maximum()))
        self.strip_columns_per_row.blockSignals(False)
        self.strip_canvas.set_columns_per_row(self.strip_columns_per_row.value())

    def _set_collision_tool_row_visible(self, visible: bool) -> None:
        for i in range(self.collision_tools.count()):
            item = self.collision_tools.itemAt(i)
            if item and item.widget():
                item.widget().setVisible(visible)

    def _set_pencil_tool_row_visible(self, visible: bool) -> None:
        for i in range(self.pencil_tools.count()):
            item = self.pencil_tools.itemAt(i)
            if item and item.widget():
                item.widget().setVisible(visible)
        self.swatches_area.setVisible(visible)

    def _on_edit_tab_changed(self, index: int) -> None:
        is_collision = index == 1
        self._set_collision_tool_row_visible(is_collision)
        self._set_pencil_tool_row_visible(not is_collision)
        if is_collision:
            self._refresh_collision_canvas()

    def _set_collision_paint(self) -> None:
        self.btn_collision_paint.setChecked(True)
        self.btn_collision_erase.setChecked(False)
        self.collision_canvas.set_paint_mode(True)

    def _set_collision_erase(self) -> None:
        self.btn_collision_paint.setChecked(False)
        self.btn_collision_erase.setChecked(True)
        self.collision_canvas.set_paint_mode(False)

    def _current_collision_type(self) -> str:
        return self.collision_combobox.currentText() or COLLISION_NONE

    def _current_one_way(self) -> str:
        return self.one_way_combobox.currentText() or ONE_WAY_NONE

    def _refresh_collision_canvas(self) -> None:
        if not self.tileset:
            return
        collision_type = self._current_collision_type()
        expected = self.tileset.tile_size * self.tileset.tile_size
        if collision_type == COLLISION_POLYGON:
            mask = self._pending_collision_shape
            if len(mask) != expected:
                if self._stack_index < self.tileset.tile_count:
                    mask = self.tileset.get_collision_shape(self._stack_index)
                else:
                    mask = self.tileset.collision_mask_for_type(COLLISION_NONE)
                self._pending_collision_shape = mask
        else:
            mask = self.tileset.collision_mask_for_type(collision_type)
        self.collision_canvas.set_context(
            self.edit_canvas.get_pixels(),
            mask,
            self.tileset.tile_size,
            self._palette_colors,
            collision_type,
            self._current_one_way(),
        )

    def _sync_tile_size_to_import(self) -> None:
        self.import_canvas.set_tile_size(self.tile_size.value())

    def _on_edit_canvas_changed(self) -> None:
        self._buffer_dirty = True
        self._update_editor_status()

    def _on_collision_canvas_changed(self) -> None:
        if self.collision_canvas.editable:
            self._pending_collision_shape = self.collision_canvas.get_mask()
        if (
            self.tileset
            and self._stack_index < self.tileset.tile_count
            and self._current_collision_type() == COLLISION_POLYGON
        ):
            self.tileset.set_collision_shape(self._stack_index, self._pending_collision_shape)
            self._dirty = True
            self.strip_canvas.update()
        else:
            self._buffer_dirty = True
        self._update_editor_status()

    def _sync_meta_controls(self) -> None:
        if not self.tileset:
            return
        self.collision_combobox.blockSignals(True)
        self.one_way_combobox.blockSignals(True)
        if self._stack_index < self.tileset.tile_count:
            collision = self.tileset.get_collision(self._stack_index)
            one_way = self.tileset.get_one_way(self._stack_index)
        else:
            collision = self._pending_collision
            one_way = self._pending_one_way
        idx = self.collision_combobox.findText(collision)
        if idx >= 0:
            self.collision_combobox.setCurrentIndex(idx)
        idx = self.one_way_combobox.findText(one_way)
        if idx >= 0:
            self.one_way_combobox.setCurrentIndex(idx)
        self.collision_combobox.blockSignals(False)
        self.one_way_combobox.blockSignals(False)

    def _on_collision_changed(self, value: str) -> None:
        if not self.tileset or not value:
            return
        if self._stack_index < self.tileset.tile_count:
            self.tileset.set_collision(self._stack_index, value)
            self._mark_dirty()
        else:
            self._pending_collision = value
        if value == COLLISION_POLYGON:
            if self._stack_index < self.tileset.tile_count:
                self._pending_collision_shape = self.tileset.get_collision_shape(
                    self._stack_index
                )
            elif len(self._pending_collision_shape) != self.tileset.tile_size ** 2:
                self._pending_collision_shape = self.tileset.collision_mask_for_type(
                    COLLISION_NONE
                )
        else:
            self._pending_collision_shape = self.tileset.collision_mask_for_type(value)
        self._refresh_collision_canvas()
        self.strip_canvas.update()

    def _on_one_way_changed(self, value: str) -> None:
        if not self.tileset or not value:
            return
        if self._stack_index < self.tileset.tile_count:
            self.tileset.set_one_way(self._stack_index, value)
            self._mark_dirty()
        else:
            self._pending_one_way = value
        self.collision_canvas.set_one_way(value)
        self.strip_canvas.update()

    def _update_stack_label(self) -> None:
        if not self.tileset:
            self.stack_label.setText("0 tiles")
            return
        self.stack_label.setText(f"{self.tileset.tile_count} tile(s)")

    def _update_save_button_label(self) -> None:
        if not self.tileset:
            return
        if self._stack_index < self.tileset.tile_count:
            self.btn_save_to_stack.setText("Replace in stack")
        else:
            self.btn_save_to_stack.setText("Save to stack")

    def _update_editor_status(self) -> None:
        if not self.tileset:
            self.editor_status_label.setText("No tileset")
            return
        if self._stack_index < self.tileset.tile_count:
            state = "edited" if self._buffer_dirty else "loaded"
            self.editor_status_label.setText(f"Tile #{self._stack_index} ({state})")
        else:
            self.editor_status_label.setText("New tile (unsaved)" if self._buffer_dirty else "New tile")

    def _update_stack_index_limits(self) -> None:
        if not self.tileset:
            self.stack_index.setMaximum(0)
            return
        self.stack_index.setMaximum(self.tileset.tile_count)

    def _confirm_discard_buffer(self) -> bool:
        if not self._buffer_dirty:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved Tile Edits",
            "Save changes before leaving this tile?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._flush_buffer_to_stack()
            return True
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        return True

    def _load_buffer_from_stack(self, index: int) -> None:
        if not self.tileset:
            return
        if index < self.tileset.tile_count:
            pixels = self.tileset.get_tile(index)
        else:
            pixels = self.tileset.blank_tile()
        self.edit_canvas.set_tile(pixels, self.tileset.tile_size, self._palette_colors)
        collision_type = (
            self.tileset.get_collision(index)
            if index < self.tileset.tile_count
            else self._pending_collision
        )
        if collision_type == COLLISION_POLYGON and index < self.tileset.tile_count:
            self._pending_collision_shape = self.tileset.get_collision_shape(index)
        else:
            self._pending_collision_shape = self.tileset.collision_mask_for_type(
                collision_type
            )
        self._buffer_dirty = False
        self._update_editor_status()
        self._update_save_button_label()

    def _set_stack_index(self, index: int) -> None:
        if not self.tileset:
            return
        index = max(0, min(index, self.tileset.tile_count))
        self._stack_index = index
        self.stack_index.blockSignals(True)
        self.stack_index.setValue(index)
        self.stack_index.blockSignals(False)
        self._load_buffer_from_stack(index)
        self._refresh_strip()
        self._sync_meta_controls()
        self._refresh_collision_canvas()
        self._update_save_button_label()

    def _on_stack_index_spin_changed(self, value: int) -> None:
        if not self._confirm_discard_buffer():
            self.stack_index.blockSignals(True)
            self.stack_index.setValue(self._stack_index)
            self.stack_index.blockSignals(False)
            return
        self._set_stack_index(value)

    def _on_strip_tile_clicked(self, index: int) -> None:
        if not self._confirm_discard_buffer():
            return
        self._set_stack_index(index)

    def _prev_stack_tile(self) -> None:
        if self._stack_index > 0:
            if not self._confirm_discard_buffer():
                return
            self._set_stack_index(self._stack_index - 1)

    def _next_stack_tile(self) -> None:
        if not self.tileset:
            return
        if self._stack_index < self.tileset.tile_count:
            if not self._confirm_discard_buffer():
                return
            self._set_stack_index(self._stack_index + 1)

    def _on_import_tile_clicked(self, _tx: int, _ty: int) -> None:
        pass

    def _reload_palette_names(self) -> None:
        current = self.palette_combo.currentText()
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        names = list_palette_names(self.project_root)
        if not names:
            names = ["default"]
        self.palette_combo.addItems(names)
        if current in names:
            self.palette_combo.setCurrentText(current)
        self.palette_combo.blockSignals(False)

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _set_tool(self, tool: Tool) -> None:
        self.btn_pencil.setChecked(tool == Tool.PENCIL)
        self.btn_eraser.setChecked(tool == Tool.ERASER)
        self.btn_dropper.setChecked(tool == Tool.EYEDROPPER)
        self.edit_canvas.set_tool(tool)

    def _refresh_strip(self) -> None:
        if self.tileset:
            self._update_strip_columns_limits()
            self.strip_canvas.set_columns_per_row(self.strip_columns_per_row.value())
            self.strip_canvas.set_tileset(self.tileset, self._palette_colors)
            self.strip_canvas.set_selected_index(self._stack_index)
            self._update_stack_label()
            self._update_stack_index_limits()

    def _refresh_editor(self) -> None:
        if self.tileset:
            self._load_buffer_from_stack(self._stack_index)
            self._refresh_strip()
            self._sync_meta_controls()
            self._refresh_collision_canvas()

    def _on_tile_size_changed(self, value: int) -> None:
        if not self.tileset:
            self._sync_tile_size_to_import()
            return
        if value == self.tileset.tile_size:
            return
        if self.tileset.has_pixels():
            reply = QMessageBox.question(
                self,
                "Change Tile Size",
                "Resample all stacked tiles to the new square size?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.tile_size.blockSignals(True)
                self.tile_size.setValue(self.tileset.tile_size)
                self.tile_size.blockSignals(False)
                return
        self.tileset.set_tile_size(value)
        self._dirty = True
        self._sync_tile_size_to_import()
        self._refresh_editor()
        self._save_stack_sidecar()

    def _on_palette_changed(self, name: str) -> None:
        if not self.tileset or not name:
            return
        if self.tileset.palette != name and self.tileset.has_pixels():
            reply = QMessageBox.question(
                self,
                "Change Palette",
                "Change palette? Indices stay the same but colors will change.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.palette_combo.blockSignals(True)
                self.palette_combo.setCurrentText(self.tileset.palette)
                self.palette_combo.blockSignals(False)
                return
        self.tileset.palette = name
        self._load_palette_colors()
        self._dirty = True
        self._refresh_editor()
        self._save_stack_sidecar()

    def _load_palette_colors(self) -> None:
        if not self.tileset:
            return
        path = palette_path(self.project_root, self.tileset.palette)
        if not path.is_file():
            raise FileNotFoundError(f"Palette not found: {path}")
        self._palette_colors = load_palette(path)
        self._build_swatches()

    def _build_swatches(self) -> None:
        while self.swatches_grid.count():
            item = self.swatches_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 8
        for n, index in enumerate(PAINTABLE_INDICES):
            r, g, b = self._palette_colors[index]
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #444;")
            btn.setToolTip(f"Index {index}")
            btn.clicked.connect(lambda _checked, i=index: self._pick_color(i))
            self.swatches_grid.addWidget(btn, n // cols, n % cols)

    def _pick_color(self, index: int) -> None:
        self.edit_canvas.set_color_index(index)
        self._set_tool(Tool.PENCIL)

    def _load_import_to_editor(self) -> None:
        if not self.tileset or self._import_image is None:
            QMessageBox.information(
                self, "Load to Editor", "Load an import image and open a tileset first."
            )
            return
        import_tx = self.import_canvas.selected_tile_x
        import_ty = self.import_canvas.selected_tile_y
        size = self.tile_size.value()
        pixels = surface_tile_to_pixels(
            self._import_image,
            import_tx,
            import_ty,
            self.tileset.tile_size,
            self._palette_colors,
            src_tile_size=size,
        )
        self.edit_canvas.set_tile(pixels, self.tileset.tile_size, self._palette_colors)
        self._refresh_collision_canvas()
        self._buffer_dirty = True
        self._update_editor_status()

    def _flush_buffer_to_stack(self) -> int:
        if not self.tileset:
            return self._stack_index
        pixels = self.edit_canvas.get_pixels()
        collision_type = self._current_collision_type()
        if collision_type == COLLISION_POLYGON:
            collision_shape = self._pending_collision_shape or self.collision_canvas.get_mask()
        else:
            collision_shape = self.tileset.collision_mask_for_type(collision_type)
        index = self.tileset.save_tile(
            self._stack_index,
            pixels,
            collision=collision_type,
            one_way=self.one_way_combobox.currentText(),
            collision_shape=collision_shape,
        )
        self._pending_collision = COLLISION_NONE
        self._pending_one_way = ONE_WAY_NONE
        self._pending_collision_shape = []
        self._dirty = True
        self._buffer_dirty = False
        self._save_stack_sidecar()
        return index

    def _save_to_stack(self) -> None:
        if not self.tileset:
            return
        index = self._flush_buffer_to_stack()
        self._set_stack_index(index)

    def _save_all_from_image(self) -> None:
        if not self.tileset or self._import_image is None:
            QMessageBox.information(
                self, "Save All", "Load an import image and open a tileset first."
            )
            return
        size = self.tile_size.value()
        import_tiles_w = self._import_image.get_width() // size
        import_tiles_h = self._import_image.get_height() // size
        if import_tiles_w == 0 or import_tiles_h == 0:
            return
        total = import_tiles_w * import_tiles_h
        if self.tileset.tile_count > 0:
            reply = QMessageBox.question(
                self,
                "Save All from Image",
                f"Append {total} converted tiles to the stack?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        for ty in range(import_tiles_h):
            for tx in range(import_tiles_w):
                pixels = surface_tile_to_pixels(
                    self._import_image,
                    tx,
                    ty,
                    self.tileset.tile_size,
                    self._palette_colors,
                    src_tile_size=size,
                )
                self.tileset.append_tile(pixels)
        self._dirty = True
        self._set_stack_index(self.tileset.tile_count - 1)
        self._save_stack_sidecar()

    def _clear_editor(self) -> None:
        if not self.tileset:
            return
        self.edit_canvas.clear_tile(self.tileset.tile_size)
        self._refresh_collision_canvas()
        self._buffer_dirty = True
        self._update_editor_status()

    def open_tileset(self, path: Path) -> None:
        self.file_path = path.resolve()
        self.tileset = load_tileset(self.file_path)
        self._dirty = False
        self._buffer_dirty = False
        self._pending_collision = COLLISION_NONE
        self._pending_one_way = ONE_WAY_NONE
        self._pending_collision_shape = []

        self.tile_size.blockSignals(True)
        self.tile_size.setValue(self.tileset.tile_size)
        self.tile_size.blockSignals(False)

        self._reload_palette_names()
        self.palette_combo.setCurrentText(self.tileset.palette)
        self._load_palette_colors()
        self._sync_tile_size_to_import()
        self._try_load_stack_sidecar()
        self._reset_strip_columns_per_row()
        self._set_stack_index(0)

    def new_tileset(self, path: Path, palette: str, tile_size: int = 8) -> None:
        self.file_path = path.resolve()
        self.tileset = Tileset.create(palette, tile_size=tile_size)
        self._dirty = True
        self._buffer_dirty = False
        self._pending_collision = COLLISION_NONE
        self._pending_one_way = ONE_WAY_NONE
        self._pending_collision_shape = []
        self._import_image = None
        self.import_canvas.set_image(None)

        self.tile_size.blockSignals(True)
        self.tile_size.setValue(tile_size)
        self.tile_size.blockSignals(False)

        self._reload_palette_names()
        self.palette_combo.setCurrentText(palette)
        self._load_palette_colors()
        self._sync_tile_size_to_import()
        self._reset_strip_columns_per_row()
        self._set_stack_index(0)

    def save(self) -> None:
        if not self.tileset or not self.file_path:
            return
        save_tileset(self.tileset, self.file_path)
        self._save_stack_sidecar()
        self._dirty = False
        self.saved.emit(self.file_path)

    def _rename_tileset(self) -> None:
        if not self.tileset or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename Tileset", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename Tileset",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortutileset"
        if new_path.exists():
            QMessageBox.warning(self, "Rename Tileset", f"{new_path.name} already exists.")
            return
        for sidecar in sorted(old_path.parent.glob(f"{old_path.stem}.*")):
            if sidecar == old_path:
                continue
            sidecar.rename(sidecar.parent / sidecar.name.replace(old_path.stem, new_stem, 1))
        old_path.rename(new_path)
        self.file_path = new_path
        self.renamed.emit(old_path, new_path)

    def _try_load_stack_sidecar(self) -> None:
        if not self.file_path or not self.tileset:
            return
        if self.tileset.tiles:
            self._save_stack_sidecar()
            return
        sidecar = existing_stack_preview_path(self.file_path)
        if sidecar is not None:
            self._set_import_image(load_image(sidecar))

    def _save_stack_sidecar(self) -> None:
        if not self.tileset or not self.file_path or not self.tileset.tiles:
            return
        surface = self.tileset.to_surface(
            self._palette_colors,
            empty_color=STACK_PREVIEW_EMPTY_BG,
        )
        pygame.image.save(surface, str(stack_sidecar_path(self.file_path)))
        self._set_import_image(surface)

    def _set_import_image(self, surface: pygame.Surface) -> None:
        self._import_image = surface
        self.import_canvas.set_image(surface)

    def _load_import_image(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Import Image",
            str(self.project_root),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if not path:
            return
        self._set_import_image(self.color_key.apply_to(load_image(path)))

    def has_unsaved_changes(self) -> bool:
        return self._dirty or self._buffer_dirty
