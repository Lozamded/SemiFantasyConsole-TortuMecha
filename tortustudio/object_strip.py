"""Horizontal object prefab strip for the scene editor."""

from __future__ import annotations

import math
from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from tortuengine.object import TortuObject, load_object
from tortuengine.palette import load_palette, palette_path
from tortuengine.sprite import Sprite, load_sprite


class ObjectStripCanvas(QWidget):
    """Clickable strip of object prefab thumbnails."""

    SELECTION_COLOR = (255, 220, 80)
    GRID_COLOR = (36, 36, 50)
    EMPTY_BG = (48, 48, 60)

    object_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not pygame.get_init():
            pygame.init()
        self.project_root: Path | None = None
        self.prefab_paths: list[str] = []
        self._thumbnails: list[QImage | None] = []
        self.selected_index = 0
        self.cell_size = 48
        self._columns_per_row = 8
        self._cols = 1
        self._rows = 0
        self.setMinimumHeight(self.cell_size + 8)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_project(self, project_root: Path | None, prefab_paths: list[str]) -> None:
        self.project_root = project_root
        self.prefab_paths = list(prefab_paths)
        self._thumbnails = [self._build_thumbnail(rel) for rel in self.prefab_paths]
        if self.prefab_paths:
            self.selected_index = min(self.selected_index, len(self.prefab_paths) - 1)
        else:
            self.selected_index = 0
        self._update_layout()

    def set_selected_index(self, index: int) -> None:
        if not self.prefab_paths:
            self.selected_index = 0
        else:
            self.selected_index = max(0, min(index, len(self.prefab_paths) - 1))
        self.update()

    def selected_prefab(self) -> str:
        if not self.prefab_paths:
            return ""
        return self.prefab_paths[self.selected_index]

    def _build_thumbnail(self, prefab_path: str) -> QImage | None:
        if not self.project_root:
            return None
        path = (self.project_root / prefab_path).resolve()
        if not path.is_file():
            return None
        try:
            tortu_object = load_object(path)
            sprite_path = tortu_object.default_sprite
            if not sprite_path:
                return None
            sprite_file = (self.project_root / sprite_path).resolve()
            sprite = load_sprite(sprite_file)
            pal_file = palette_path(self.project_root, sprite.palette)
            palette = load_palette(pal_file)
            return self._sprite_thumbnail(sprite, palette)
        except (FileNotFoundError, ValueError, OSError):
            return None

    def _sprite_thumbnail(self, sprite: Sprite, palette: list[tuple[int, int, int]]) -> QImage:
        size = max(sprite.pixel_width, sprite.pixel_height, 1)
        thumb = pygame.Surface((size, size), pygame.SRCALPHA)
        thumb.fill((*self.EMPTY_BG, 255))
        frame = sprite.to_surface(palette, frame_index=0)
        ox = (size - sprite.pixel_width) // 2
        oy = (size - sprite.pixel_height) // 2
        thumb.blit(frame, (ox, oy))
        data = pygame.image.tobytes(thumb, "RGBA")
        return QImage(data, size, size, size * 4, QImage.Format.Format_RGBA8888)

    def _update_layout(self) -> None:
        if self.prefab_paths:
            self._cols = max(1, self._columns_per_row)
            self._rows = max(1, math.ceil(len(self.prefab_paths) / self._cols))
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

    def _display_offset(self) -> tuple[int, int, int, int]:
        disp_w = self._cols * self.cell_size
        disp_h = self._rows * self.cell_size
        ox = max(4, (self.width() - disp_w) // 2)
        oy = max(4, (self.height() - disp_h) // 2)
        return ox, oy, disp_w, disp_h

    def _index_at(self, event: QMouseEvent) -> int | None:
        if not self.prefab_paths:
            return None
        ox, oy, disp_w, disp_h = self._display_offset()
        local_x = event.position().x() - ox
        local_y = event.position().y() - oy
        if local_x < 0 or local_y < 0 or local_x >= disp_w or local_y >= disp_h:
            return None
        tx = int(local_x // self.cell_size)
        ty = int(local_y // self.cell_size)
        index = ty * self._cols + tx
        if index >= len(self.prefab_paths):
            return None
        return index

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if not self.prefab_paths:
            painter.setPen(QColor(160, 160, 170))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No objects in project")
            painter.end()
            return

        ox, oy, disp_w, disp_h = self._display_offset()

        for i, thumb in enumerate(self._thumbnails):
            tx = i % self._cols
            ty = i // self._cols
            cell_x = ox + tx * self.cell_size
            cell_y = oy + ty * self.cell_size
            if thumb is not None:
                scaled = thumb.scaled(
                    self.cell_size,
                    self.cell_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                ix = cell_x + (self.cell_size - scaled.width()) // 2
                iy = cell_y + (self.cell_size - scaled.height()) // 2
                painter.drawImage(ix, iy, scaled)
            else:
                painter.fillRect(
                    cell_x + 2,
                    cell_y + 2,
                    self.cell_size - 4,
                    self.cell_size - 4,
                    QColor(*self.EMPTY_BG),
                )

            if i == self.selected_index:
                pen = QPen(QColor(*self.SELECTION_COLOR))
                pen.setWidth(2)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(cell_x, cell_y, self.cell_size, self.cell_size)

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

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self._index_at(event)
        if index is not None:
            self.selected_index = index
            self.update()
            self.object_clicked.emit(index)
