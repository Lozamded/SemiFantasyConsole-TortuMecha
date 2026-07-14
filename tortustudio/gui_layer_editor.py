"""GUI layer editor — size a .tortuguilayer canvas and place a tile layer, objects, and text labels."""

from __future__ import annotations

import subprocess
from enum import Enum
from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_BLOCK
from tortuengine.gui_layer import (
    DEFAULT_GUI_LAYER_HEIGHT,
    DEFAULT_GUI_LAYER_WIDTH,
    EMPTY_TILE,
    FILL_BOTTOM_TO_TOP,
    FILL_LEFT_TO_RIGHT,
    FILL_RIGHT_TO_LEFT,
    FILL_TOP_TO_BOTTOM,
    REPEAT_HORIZONTAL,
    REPEAT_VERTICAL,
    GuiLayer,
    GuiObject,
    GuiRepeatSprite,
    GuiTextLabel,
    GuiTiledRect,
    load_gui_layer,
    save_gui_layer,
)
from tortuengine.object import TortuObject, load_object
from tortuengine.palette import TRANSPARENT_INDEX, load_palette, palette_path
from tortuengine.pip_bar import PipBar, load_pip_bar
from tortuengine.progress_bar import ProgressBar, load_progress_bar
from tortuengine.project import load_project
from tortuengine.sprite import Sprite, load_sprite
from tortuengine.sprite_font import TortuSpriteFont, load_sprite_font, render_sprite_text_line
from tortuengine.text_font import TortuFont, load_tortu_font, render_text_line
from tortuengine.tileset import Tileset, load_tileset
from tortustudio.collapsible import CollapsibleSection
from tortustudio.object_strip import ObjectStripCanvas
from tortustudio.pip_bar_strip import PipBarStripCanvas
from tortustudio.progress_bar_strip import ProgressBarStripCanvas
from tortustudio.scene_assets import (
    list_object_paths,
    list_pip_bar_paths,
    list_progress_bar_paths,
    list_sprite_font_paths,
    list_text_font_paths,
    list_tileset_paths,
)
from tortustudio.scene_editor import Tool
from tortustudio.tileset_editor import TilesetStripCanvas


class GuiLayerTarget(str, Enum):
    TILES = "tiles"
    OBJECTS = "objects"
    TEXT = "text"
    TILED_RECT = "tiled_rect"
    REPEAT_SPRITE = "repeat_sprite"


class GuiLayerCanvas(QWidget):
    """Editable GUI layer canvas — paints the tile layer, places objects and text labels."""

    TILE_GRID_COLOR = (48, 48, 64)
    CANVAS_BG = (30, 30, 40)
    SELECTION_COLOR = (255, 220, 0)

    changed = pyqtSignal()
    object_selected = pyqtSignal(int)
    text_label_selected = pyqtSignal(int)
    tiled_rect_selected = pyqtSignal(int)
    repeat_sprite_selected = pyqtSignal(int)
    tool_cycled = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not pygame.get_init():
            pygame.init()

        self.gui_layer: GuiLayer | None = None
        self.project_root: Path | None = None
        self.tileset: Tileset | None = None
        self.palette: list[tuple[int, int, int]] = []

        self.tortu_objects: dict[str, TortuObject] = {}
        self.object_sprites: dict[str, Sprite] = {}
        self.object_sprite_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self.text_fonts: dict[str, TortuFont] = {}
        self.sprite_fonts: dict[str, TortuSpriteFont] = {}
        self.font_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self.progress_bars: dict[str, ProgressBar] = {}
        self.pip_bars: dict[str, PipBar] = {}

        self.target = GuiLayerTarget.TILES
        self.tool = Tool.PAINT
        self.edit_mode = False
        self.selected_tile = 0
        self.selected_object_prefab = ""
        self.pending_text = ""
        self.pending_font = ""
        self.pending_progress_bar_prefab = ""
        self.pending_pip_bar_prefab = ""
        self.selected_object_index = -1
        self.selected_text_index = -1
        self.selected_tiled_rect_index = -1
        self.selected_repeat_sprite_index = -1
        self._dragging_object_index = -1
        self._dragging_text_index = -1
        self._dragging_tiled_rect_index = -1
        self._dragging_repeat_sprite_index = -1

        self.show_grid = True
        self.zoom = 2
        self._drawing = False
        self._frame: QImage | None = None
        self.resize(200, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_context(
        self,
        gui_layer: GuiLayer | None,
        project_root: Path | None,
        tileset: Tileset | None,
        palette: list[tuple[int, int, int]],
        *,
        target: GuiLayerTarget,
        tool: Tool,
        edit_mode: bool,
        selected_tile: int,
        selected_object_prefab: str,
        pending_text: str,
        pending_font: str,
        selected_object_index: int,
        selected_text_index: int,
        show_grid: bool = True,
        pending_progress_bar_prefab: str = "",
        pending_pip_bar_prefab: str = "",
        selected_tiled_rect_index: int = -1,
        selected_repeat_sprite_index: int = -1,
    ) -> None:
        self.gui_layer = gui_layer
        self.project_root = project_root
        self.tileset = tileset
        self.palette = palette
        self.target = target
        self.tool = tool
        self.edit_mode = edit_mode
        self.selected_tile = selected_tile
        self.selected_object_prefab = selected_object_prefab
        self.pending_text = pending_text
        self.pending_font = pending_font
        self.pending_progress_bar_prefab = pending_progress_bar_prefab
        self.pending_pip_bar_prefab = pending_pip_bar_prefab
        self.selected_object_index = selected_object_index
        self.selected_text_index = selected_text_index
        self.selected_tiled_rect_index = selected_tiled_rect_index
        self.selected_repeat_sprite_index = selected_repeat_sprite_index
        self.show_grid = show_grid
        self._refresh()

    def set_tool(self, tool: Tool) -> None:
        self.tool = tool

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(1, min(16, zoom))
        if self.gui_layer:
            self.resize(self.gui_layer.width * self.zoom, self.gui_layer.height * self.zoom)
        self.update()

    def set_show_grid(self, visible: bool) -> None:
        self.show_grid = visible
        self.update()

    def clear_caches(self) -> None:
        self.tortu_objects.clear()
        self.object_sprites.clear()
        self.object_sprite_palettes.clear()
        self.text_fonts.clear()
        self.sprite_fonts.clear()
        self.font_palettes.clear()
        self.progress_bars.clear()
        self.pip_bars.clear()

    # -- asset lookups -----------------------------------------------------

    def _tile_surface(self, tile_index: int) -> pygame.Surface | None:
        if not self.tileset or tile_index < 0 or tile_index >= self.tileset.tile_count:
            return None
        size = self.tileset.tile_size
        tile = self.tileset.get_tile(tile_index)
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        for ly in range(size):
            for lx in range(size):
                index = tile[ly * size + lx]
                if index == TRANSPARENT_INDEX:
                    continue
                rgb = self.palette[index]
                surface.set_at((lx, ly), (*rgb, 255))
        return surface

    def _get_tortu_object(self, prefab_path: str) -> TortuObject | None:
        if not prefab_path:
            return None
        if prefab_path in self.tortu_objects:
            return self.tortu_objects[prefab_path]
        if self.project_root is None:
            return None
        path = (self.project_root / prefab_path).resolve()
        if not path.is_file():
            return None
        loaded = load_object(path)
        self.tortu_objects[prefab_path] = loaded
        return loaded

    def _get_object_sprite(self, sprite_path: str) -> Sprite | None:
        if not sprite_path:
            return None
        if sprite_path in self.object_sprites:
            return self.object_sprites[sprite_path]
        if self.project_root is None:
            return None
        path = (self.project_root / sprite_path).resolve()
        if not path.is_file():
            return None
        loaded = load_sprite(path)
        self.object_sprites[sprite_path] = loaded
        return loaded

    def _sprite_palette(self, palette_name: str) -> list[tuple[int, int, int]] | None:
        if palette_name in self.object_sprite_palettes:
            return self.object_sprite_palettes[palette_name]
        if self.project_root is None:
            return None
        path = palette_path(self.project_root, palette_name)
        if not path.is_file():
            return None
        colors = load_palette(path)
        self.object_sprite_palettes[palette_name] = colors
        return colors

    def _object_instance_surface(self, inst: GuiObject) -> pygame.Surface | None:
        tortu_object = self._get_tortu_object(inst.prefab)
        if tortu_object is None:
            return None
        anim = inst.animation or tortu_object.default_animation
        sprite_path = tortu_object.sprite_for(anim) or tortu_object.default_sprite
        sprite = self._get_object_sprite(sprite_path)
        if sprite is None:
            return None
        palette = self._sprite_palette(sprite.palette)
        if palette is None:
            return None
        surface = sprite.to_surface(palette, frame_index=0)
        if inst.scale != 1.0:
            width = max(1, round(surface.get_width() * inst.scale))
            height = max(1, round(surface.get_height() * inst.scale))
            surface = pygame.transform.scale(surface, (width, height))
        return surface

    def _get_progress_bar(self, prefab_path: str) -> ProgressBar | None:
        if not prefab_path:
            return None
        if prefab_path in self.progress_bars:
            return self.progress_bars[prefab_path]
        if self.project_root is None:
            return None
        path = (self.project_root / prefab_path).resolve()
        if not path.is_file():
            return None
        loaded = load_progress_bar(path)
        self.progress_bars[prefab_path] = loaded
        return loaded

    def _get_pip_bar(self, prefab_path: str) -> PipBar | None:
        if not prefab_path:
            return None
        if prefab_path in self.pip_bars:
            return self.pip_bars[prefab_path]
        if self.project_root is None:
            return None
        path = (self.project_root / prefab_path).resolve()
        if not path.is_file():
            return None
        loaded = load_pip_bar(path)
        self.pip_bars[prefab_path] = loaded
        return loaded

    def _tiled_rect_base_surface(self, rect: GuiTiledRect) -> pygame.Surface | None:
        bar = self._get_progress_bar(rect.prefab)
        if bar is None:
            return None
        sprite = self._get_object_sprite(bar.texture_for(rect.number))
        if sprite is None:
            return None
        palette = self._sprite_palette(sprite.palette)
        if palette is None:
            return None
        return sprite.to_surface(palette, frame_index=0)

    def _tiled_rect_surface(self, rect: GuiTiledRect) -> pygame.Surface | None:
        """Full width×height preview, tiled from the texture (no fill cropping)."""
        if rect.width <= 0 or rect.height <= 0:
            return None
        base = self._tiled_rect_base_surface(rect)
        if base is None or base.get_width() < 1 or base.get_height() < 1:
            return None
        bw, bh = base.get_width(), base.get_height()
        tiled = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        for ty in range(0, rect.height, bh):
            for tx in range(0, rect.width, bw):
                tiled.blit(base, (tx, ty))
        return tiled

    def _tiled_rect_fill_rect(self, rect: GuiTiledRect) -> pygame.Rect:
        """Local (unclipped to rect.x/y) crop rect of the currently-filled portion."""
        bar = self._get_progress_bar(rect.prefab)
        fill_direction = bar.fill_direction if bar else FILL_LEFT_TO_RIGHT
        value = rect.fill_fraction
        if fill_direction == FILL_RIGHT_TO_LEFT:
            visible_w = round(rect.width * value)
            return pygame.Rect(rect.width - visible_w, 0, visible_w, rect.height)
        if fill_direction == FILL_TOP_TO_BOTTOM:
            visible_h = round(rect.height * value)
            return pygame.Rect(0, 0, rect.width, visible_h)
        if fill_direction == FILL_BOTTOM_TO_TOP:
            visible_h = round(rect.height * value)
            return pygame.Rect(0, rect.height - visible_h, rect.width, visible_h)
        visible_w = round(rect.width * value)
        return pygame.Rect(0, 0, visible_w, rect.height)

    def _repeat_sprite_icon_size(self, rep: GuiRepeatSprite) -> tuple[int, int, int]:
        """(step, icon_w, icon_h) for one icon slot, or (0, 0, 0) if unresolvable."""
        pip_bar = self._get_pip_bar(rep.prefab)
        if pip_bar is None:
            return 0, 0, 0
        sprite = self._get_object_sprite(pip_bar.full_sprite_for(rep.number))
        if sprite is None:
            return 0, 0, 0
        icon_w, icon_h = sprite.pixel_width, sprite.pixel_height
        icon_size = icon_h if pip_bar.direction == REPEAT_VERTICAL else icon_w
        step = round(icon_size * pip_bar.scale) + pip_bar.spacing
        return step, round(icon_w * pip_bar.scale), round(icon_h * pip_bar.scale)

    def _repeat_sprite_icon_surface(
        self, rep: GuiRepeatSprite, filled: bool
    ) -> pygame.Surface | None:
        pip_bar = self._get_pip_bar(rep.prefab)
        if pip_bar is None:
            return None
        sprite_path = pip_bar.full_sprite_for(rep.number) if filled else pip_bar.empty_sprite
        if not sprite_path:
            return None
        sprite = self._get_object_sprite(sprite_path)
        if sprite is None:
            return None
        palette = self._sprite_palette(sprite.palette)
        if palette is None:
            return None
        surface = sprite.to_surface(palette, frame_index=0)
        if pip_bar.scale != 1.0:
            width = max(1, round(surface.get_width() * pip_bar.scale))
            height = max(1, round(surface.get_height() * pip_bar.scale))
            surface = pygame.transform.scale(surface, (width, height))
        return surface

    def _repeat_sprite_bounds(self, rep: GuiRepeatSprite) -> tuple[int, int, int, int]:
        """(x0, y0, x1, y1) bounding box covering every icon slot."""
        step, icon_w, icon_h = self._repeat_sprite_icon_size(rep)
        pip_bar = self._get_pip_bar(rep.prefab)
        total = max(rep.max_number, rep.number, 1)
        direction = pip_bar.direction if pip_bar else REPEAT_HORIZONTAL
        if direction == REPEAT_VERTICAL:
            x0, y0 = rep.x, rep.y
            x1, y1 = x0 + icon_w, y0 + icon_h + step * (total - 1)
        else:
            x0, y0 = rep.x, rep.y
            x1, y1 = x0 + icon_w + step * (total - 1), y0 + icon_h
        return round(x0), round(y0), round(x1), round(y1)

    def _get_text_font(self, rel_path: str) -> TortuFont | None:
        if not rel_path:
            return None
        if rel_path in self.text_fonts:
            return self.text_fonts[rel_path]
        if self.project_root is None:
            return None
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_tortu_font(path)
        self.text_fonts[rel_path] = loaded
        return loaded

    def _get_sprite_font(self, rel_path: str) -> TortuSpriteFont | None:
        if not rel_path:
            return None
        if rel_path in self.sprite_fonts:
            return self.sprite_fonts[rel_path]
        if self.project_root is None:
            return None
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_sprite_font(path)
        self.sprite_fonts[rel_path] = loaded
        return loaded

    def _font_palette(self, palette_name: str) -> list[tuple[int, int, int]] | None:
        if palette_name in self.font_palettes:
            return self.font_palettes[palette_name]
        if self.project_root is None:
            return None
        path = palette_path(self.project_root, palette_name)
        if not path.is_file():
            return None
        colors = load_palette(path)
        self.font_palettes[palette_name] = colors
        return colors

    def _label_surface(self, label: GuiTextLabel) -> pygame.Surface | None:
        if not label.text or not label.font:
            return None
        if label.font.endswith(".tortuspritefont"):
            font = self._get_sprite_font(label.font)
            if font is None:
                return None
            colors = self._font_palette(font.palette)
            if colors is None:
                return None
            return render_sprite_text_line(font, label.text, colors)
        font = self._get_text_font(label.font)
        if font is None:
            return None
        colors = self._font_palette(font.palette)
        if colors is None:
            return None
        return render_text_line(font, label.text, colors)

    # -- rendering -----------------------------------------------------

    def _refresh(self) -> None:
        if not self.gui_layer:
            self._frame = None
            self.update()
            return

        w, h = self.gui_layer.width, self.gui_layer.height
        composite = pygame.Surface((w, h))
        composite.fill(self.CANVAS_BG)

        if self.gui_layer.tile_layer_visible and self.gui_layer.tileset and self.tileset:
            ts = self.tileset.tile_size
            cols = self.gui_layer.grid_columns(ts)
            rows = self.gui_layer.grid_rows(ts)
            for ty in range(rows):
                for tx in range(cols):
                    px, py = tx * ts, ty * ts
                    if px >= w or py >= h:
                        continue
                    tile_index = self.gui_layer.tiles[ty * cols + tx]
                    if tile_index == EMPTY_TILE:
                        continue
                    tile_surface = self._tile_surface(tile_index)
                    if tile_surface is not None:
                        composite.blit(tile_surface, (px, py))

        for inst in self.gui_layer.objects:
            surface = self._object_instance_surface(inst)
            if surface is None:
                continue
            tortu_object = self._get_tortu_object(inst.prefab)
            if tortu_object is None:
                continue
            draw_x = inst.x - tortu_object.origin.x * inst.scale
            draw_y = inst.y - tortu_object.origin.y * inst.scale
            composite.blit(surface, (round(draw_x), round(draw_y)))

        for rect in self.gui_layer.tiled_rects:
            tiled = self._tiled_rect_surface(rect)
            if tiled is None:
                continue
            src = self._tiled_rect_fill_rect(rect)
            if src.width > 0 and src.height > 0:
                composite.blit(tiled, (rect.x + src.x, rect.y + src.y), src)

        for rep in self.gui_layer.repeat_sprites:
            step, icon_w, icon_h = self._repeat_sprite_icon_size(rep)
            if step <= 0:
                continue
            pip_bar = self._get_pip_bar(rep.prefab)
            direction = pip_bar.direction if pip_bar else REPEAT_HORIZONTAL
            total = rep.max_number if rep.max_number > 0 else rep.number
            for i in range(total):
                filled = i < rep.number
                surface = self._repeat_sprite_icon_surface(rep, filled)
                if surface is None:
                    continue
                if direction == REPEAT_VERTICAL:
                    draw_x, draw_y = rep.x, rep.y + i * step
                else:
                    draw_x, draw_y = rep.x + i * step, rep.y
                composite.blit(surface, (round(draw_x), round(draw_y)))

        for label in self.gui_layer.text_labels:
            surface = self._label_surface(label)
            if surface is not None:
                composite.blit(surface, (label.x, label.y))

        data = pygame.image.tobytes(composite, "RGBA")
        self._frame = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        self.resize(w * self.zoom, h * self.zoom)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None or not self.gui_layer:
            painter.end()
            return

        w, h = self.gui_layer.width, self.gui_layer.height
        sw, sh = w * self.zoom, h * self.zoom
        scaled = self._frame.scaled(
            sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation
        )
        painter.drawImage(0, 0, scaled)

        if self.show_grid and self.target == GuiLayerTarget.TILES:
            ts = self.tileset.tile_size if self.tileset else TILE_BLOCK
            pen = QPen(QColor(*self.TILE_GRID_COLOR))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(ts, w, ts):
                lx = px * self.zoom
                painter.drawLine(lx, 0, lx, sh)
            for py in range(ts, h, ts):
                ly = py * self.zoom
                painter.drawLine(0, ly, sw, ly)

        if self.selected_object_index >= 0:
            objects = self.gui_layer.objects
            if self.selected_object_index < len(objects):
                inst = objects[self.selected_object_index]
                tortu_object = self.tortu_objects.get(inst.prefab)
                sprite = None
                if tortu_object:
                    anim = inst.animation or tortu_object.default_animation
                    sprite_path = tortu_object.sprite_for(anim) or tortu_object.default_sprite
                    sprite = self.object_sprites.get(sprite_path or "")
                pen = QPen(QColor(*self.SELECTION_COLOR, 230))
                pen.setWidth(2)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                if sprite and tortu_object:
                    rx = (inst.x - tortu_object.origin.x * inst.scale) * self.zoom
                    ry = (inst.y - tortu_object.origin.y * inst.scale) * self.zoom
                    painter.drawRect(
                        int(rx), int(ry), int(sprite.pixel_width * inst.scale * self.zoom),
                        int(sprite.pixel_height * inst.scale * self.zoom),
                    )
                else:
                    lx, ly = inst.x * self.zoom, inst.y * self.zoom
                    painter.drawLine(int(lx - 8), int(ly), int(lx + 8), int(ly))
                    painter.drawLine(int(lx), int(ly - 8), int(lx), int(ly + 8))

        if self.selected_text_index >= 0:
            labels = self.gui_layer.text_labels
            if self.selected_text_index < len(labels):
                label = labels[self.selected_text_index]
                surface = self._label_surface(label)
                lw = surface.get_width() if surface else 8
                lh = surface.get_height() if surface else 8
                pen = QPen(QColor(*self.SELECTION_COLOR, 230))
                pen.setWidth(2)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(
                    int(label.x * self.zoom), int(label.y * self.zoom),
                    int(lw * self.zoom), int(lh * self.zoom),
                )

        if self.selected_tiled_rect_index >= 0:
            rects = self.gui_layer.tiled_rects
            if self.selected_tiled_rect_index < len(rects):
                rect = rects[self.selected_tiled_rect_index]
                pen = QPen(QColor(*self.SELECTION_COLOR, 230))
                pen.setWidth(2)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(
                    int(rect.x * self.zoom), int(rect.y * self.zoom),
                    int(rect.width * self.zoom), int(rect.height * self.zoom),
                )

        if self.selected_repeat_sprite_index >= 0:
            reps = self.gui_layer.repeat_sprites
            if self.selected_repeat_sprite_index < len(reps):
                rep = reps[self.selected_repeat_sprite_index]
                x0, y0, x1, y1 = self._repeat_sprite_bounds(rep)
                pen = QPen(QColor(*self.SELECTION_COLOR, 230))
                pen.setWidth(2)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(
                    int(x0 * self.zoom), int(y0 * self.zoom),
                    int((x1 - x0) * self.zoom), int((y1 - y0) * self.zoom),
                )

        painter.end()

    # -- interaction -----------------------------------------------------

    def _event_to_pixel(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None or not self.gui_layer:
            return None
        px = event.position().x() / self.zoom
        py = event.position().y() / self.zoom
        if px < 0 or py < 0 or px >= self.gui_layer.width or py >= self.gui_layer.height:
            return None
        return int(px), int(py)

    def _event_to_tile(self, event: QMouseEvent) -> tuple[int, int] | None:
        pos = self._event_to_pixel(event)
        if pos is None or not self.tileset or not self.gui_layer:
            return None
        ts = self.tileset.tile_size
        tx, ty = pos[0] // ts, pos[1] // ts
        cols = self.gui_layer.grid_columns(ts)
        rows = self.gui_layer.grid_rows(ts)
        if 0 <= tx < cols and 0 <= ty < rows:
            return tx, ty
        return None

    def _apply_tile_tool(self, x: int, y: int) -> None:
        if not self.gui_layer or not self.tileset:
            return
        ts = self.tileset.tile_size
        if self.tool == Tool.PAINT:
            self.gui_layer.set_tile(x, y, self.selected_tile, ts)
        elif self.tool == Tool.ERASE:
            self.gui_layer.set_tile(x, y, EMPTY_TILE, ts)
        elif self.tool == Tool.EYEDROPPER:
            picked = self.gui_layer.get_tile(x, y, ts)
            if picked != EMPTY_TILE:
                self.selected_tile = picked
                self.changed.emit()
        self._refresh()

    def _find_object_at_pixel(self, px: int, py: int) -> int | None:
        if not self.gui_layer:
            return None
        best_index: int | None = None
        best_dist = float("inf")
        for index, inst in enumerate(self.gui_layer.objects):
            tortu_object = self._get_tortu_object(inst.prefab)
            if tortu_object is None:
                continue
            anim = inst.animation or tortu_object.default_animation
            sprite_path = tortu_object.sprite_for(anim) or tortu_object.default_sprite
            sprite = self._get_object_sprite(sprite_path)
            if sprite is None:
                continue
            x0 = inst.x - tortu_object.origin.x * inst.scale
            y0 = inst.y - tortu_object.origin.y * inst.scale
            x1, y1 = x0 + sprite.pixel_width * inst.scale, y0 + sprite.pixel_height * inst.scale
            if x0 <= px < x1 and y0 <= py < y1:
                dist = (inst.x - px) ** 2 + (inst.y - py) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best_index = index
        return best_index

    def _apply_object_tool(self, px: int, py: int) -> None:
        if not self.gui_layer:
            return
        if self.tool == Tool.ERASE:
            index = self.gui_layer.find_object_near(px, py)
            if index is not None:
                self.gui_layer.remove_object(index)
        elif self.tool == Tool.PAINT and self.selected_object_prefab:
            try:
                self.gui_layer.add_object(self.selected_object_prefab, px, py)
            except ValueError:
                pass
        self._refresh()

    def _find_text_at_pixel(self, px: int, py: int) -> int | None:
        if not self.gui_layer:
            return None
        for index, label in enumerate(self.gui_layer.text_labels):
            surface = self._label_surface(label)
            w = surface.get_width() if surface else 8
            h = surface.get_height() if surface else 8
            if label.x <= px < label.x + w and label.y <= py < label.y + h:
                return index
        return None

    def _apply_text_tool(self, px: int, py: int) -> None:
        if not self.gui_layer:
            return
        if self.tool == Tool.ERASE:
            index = self.gui_layer.find_text_label_near(px, py)
            if index is not None:
                self.gui_layer.remove_text_label(index)
        elif self.tool == Tool.PAINT and self.pending_text:
            try:
                self.gui_layer.add_text_label(self.pending_text, px, py, font=self.pending_font)
            except ValueError:
                pass
        self._refresh()

    DEFAULT_TILED_RECT_WIDTH = 40
    DEFAULT_TILED_RECT_HEIGHT = 8

    def _find_tiled_rect_at_pixel(self, px: int, py: int) -> int | None:
        if not self.gui_layer:
            return None
        for index, rect in enumerate(self.gui_layer.tiled_rects):
            if rect.x <= px < rect.x + rect.width and rect.y <= py < rect.y + rect.height:
                return index
        return None

    def _apply_tiled_rect_tool(self, px: int, py: int) -> None:
        if not self.gui_layer:
            return
        if self.tool == Tool.ERASE:
            index = self.gui_layer.find_tiled_rect_near(px, py)
            if index is not None:
                self.gui_layer.remove_tiled_rect(index)
        elif self.tool == Tool.PAINT and self.pending_progress_bar_prefab:
            bar = self._get_progress_bar(self.pending_progress_bar_prefab)
            width = bar.width if bar else self.DEFAULT_TILED_RECT_WIDTH
            height = bar.height if bar else self.DEFAULT_TILED_RECT_HEIGHT
            try:
                self.gui_layer.add_tiled_rect(
                    self.pending_progress_bar_prefab, px, py, width, height,
                )
            except ValueError:
                pass
        self._refresh()

    def _find_repeat_sprite_at_pixel(self, px: int, py: int) -> int | None:
        if not self.gui_layer:
            return None
        for index, rep in enumerate(self.gui_layer.repeat_sprites):
            x0, y0, x1, y1 = self._repeat_sprite_bounds(rep)
            if x0 <= px < x1 and y0 <= py < y1:
                return index
        return None

    def _apply_repeat_sprite_tool(self, px: int, py: int) -> None:
        if not self.gui_layer:
            return
        if self.tool == Tool.ERASE:
            index = self.gui_layer.find_repeat_sprite_near(px, py)
            if index is not None:
                self.gui_layer.remove_repeat_sprite(index)
        elif self.tool == Tool.PAINT and self.pending_pip_bar_prefab:
            try:
                self.gui_layer.add_repeat_sprite(
                    self.pending_pip_bar_prefab, px, py, number=1, max_number=1,
                )
            except ValueError:
                pass
        self._refresh()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            if not self.edit_mode:
                cycle = [Tool.PAINT, Tool.ERASE, Tool.EYEDROPPER]
                next_tool = cycle[(cycle.index(self.tool) + 1) % len(cycle)]
                self.tool_cycled.emit(next_tool)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.edit_mode:
            pos = self._event_to_pixel(event)
            if not pos:
                return
            obj_index = self._find_object_at_pixel(*pos)
            if obj_index is not None:
                self._dragging_object_index = obj_index
                self._dragging_text_index = -1
                self._dragging_tiled_rect_index = -1
                self._dragging_repeat_sprite_index = -1
                self.object_selected.emit(obj_index)
                return
            text_index = self._find_text_at_pixel(*pos)
            if text_index is not None:
                self._dragging_text_index = text_index
                self._dragging_object_index = -1
                self._dragging_tiled_rect_index = -1
                self._dragging_repeat_sprite_index = -1
                self.text_label_selected.emit(text_index)
                return
            rect_index = self._find_tiled_rect_at_pixel(*pos)
            if rect_index is not None:
                self._dragging_tiled_rect_index = rect_index
                self._dragging_object_index = -1
                self._dragging_text_index = -1
                self._dragging_repeat_sprite_index = -1
                self.tiled_rect_selected.emit(rect_index)
                return
            rep_index = self._find_repeat_sprite_at_pixel(*pos)
            if rep_index is not None:
                self._dragging_repeat_sprite_index = rep_index
                self._dragging_object_index = -1
                self._dragging_text_index = -1
                self._dragging_tiled_rect_index = -1
                self.repeat_sprite_selected.emit(rep_index)
                return
            self._dragging_object_index = -1
            self._dragging_text_index = -1
            self._dragging_tiled_rect_index = -1
            self._dragging_repeat_sprite_index = -1
            self.object_selected.emit(-1)
            self.text_label_selected.emit(-1)
            self.tiled_rect_selected.emit(-1)
            self.repeat_sprite_selected.emit(-1)
            return

        if self.target == GuiLayerTarget.TILES:
            pos = self._event_to_tile(event)
            if pos:
                self._drawing = True
                self._apply_tile_tool(*pos)
                self.changed.emit()
            return

        pos = self._event_to_pixel(event)
        if pos:
            self._drawing = True
            if self.target == GuiLayerTarget.OBJECTS:
                self._apply_object_tool(*pos)
            elif self.target == GuiLayerTarget.TILED_RECT:
                self._apply_tiled_rect_tool(*pos)
            elif self.target == GuiLayerTarget.REPEAT_SPRITE:
                self._apply_repeat_sprite_tool(*pos)
            else:
                self._apply_text_tool(*pos)
            self.changed.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.edit_mode:
            if event.buttons() & Qt.MouseButton.LeftButton and self.gui_layer:
                pos = self._event_to_pixel(event)
                if not pos:
                    return
                if 0 <= self._dragging_object_index < len(self.gui_layer.objects):
                    inst = self.gui_layer.objects[self._dragging_object_index]
                    inst.x, inst.y = pos
                    self._refresh()
                    self.changed.emit()
                elif 0 <= self._dragging_text_index < len(self.gui_layer.text_labels):
                    label = self.gui_layer.text_labels[self._dragging_text_index]
                    label.x, label.y = pos
                    self._refresh()
                    self.changed.emit()
                elif 0 <= self._dragging_tiled_rect_index < len(self.gui_layer.tiled_rects):
                    rect = self.gui_layer.tiled_rects[self._dragging_tiled_rect_index]
                    rect.x, rect.y = pos
                    self._refresh()
                    self.changed.emit()
                elif 0 <= self._dragging_repeat_sprite_index < len(self.gui_layer.repeat_sprites):
                    rep = self.gui_layer.repeat_sprites[self._dragging_repeat_sprite_index]
                    rep.x, rep.y = pos
                    self._refresh()
                    self.changed.emit()
            return
        if self._drawing and event.buttons() & Qt.MouseButton.LeftButton:
            if self.target == GuiLayerTarget.TILES:
                pos = self._event_to_tile(event)
                if pos:
                    self._apply_tile_tool(*pos)
                    self.changed.emit()
            elif self.tool == Tool.ERASE:
                pos = self._event_to_pixel(event)
                if pos:
                    if self.target == GuiLayerTarget.OBJECTS:
                        self._apply_object_tool(*pos)
                    elif self.target == GuiLayerTarget.TILED_RECT:
                        self._apply_tiled_rect_tool(*pos)
                    elif self.target == GuiLayerTarget.REPEAT_SPRITE:
                        self._apply_repeat_sprite_tool(*pos)
                    else:
                        self._apply_text_tool(*pos)
                    self.changed.emit()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.edit_mode:
            self._dragging_object_index = -1
            self._dragging_text_index = -1
            self._dragging_tiled_rect_index = -1
            self._dragging_repeat_sprite_index = -1
            return
        if self._drawing:
            self._drawing = False
            self.changed.emit()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_zoom(self.zoom + 1)
        elif delta < 0:
            self.set_zoom(self.zoom - 1)


class _GuiObjectCard(QWidget):
    """Collapsible editor for one placed object instance in a GUI layer."""

    changed = pyqtSignal()
    remove_requested = pyqtSignal()
    picked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suspend = False

        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: 600; padding: 4px; text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 24); }"
        )
        self.toggle.clicked.connect(self._on_toggle_clicked)

        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedWidth(22)
        self.btn_remove.setToolTip("Remove this object")
        self.btn_remove.clicked.connect(self.remove_requested.emit)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.toggle, stretch=1)
        header.addWidget(self.btn_remove)

        self.x_spin = QSpinBox()
        self.x_spin.setRange(-9999, 9999)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-9999, 9999)
        self.anim_combo = QComboBox()
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 10.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setToolTip("Uniform size multiplier for this object instance")
        self.visible_check = QCheckBox("Visible at play")
        self.visible_check.setChecked(True)
        self.visible_check.setToolTip("Whether this object instance is drawn when the scene runs")
        self.enabled_check = QCheckBox("Enabled at scene start")
        self.enabled_check.setChecked(True)
        self.enabled_check.setToolTip("Unchecked: the instance starts off entirely and isn't drawn")

        form = QFormLayout()
        form.setContentsMargins(20, 2, 0, 6)
        form.addRow("X:", self.x_spin)
        form.addRow("Y:", self.y_spin)
        form.addRow("Scale:", self.scale_spin)
        form.addRow("Animation:", self.anim_combo)
        form.addRow("", self.visible_check)
        form.addRow("", self.enabled_check)

        self.content = QWidget()
        self.content.setLayout(form)
        self.content.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(header)
        outer.addWidget(self.content)

        self.x_spin.valueChanged.connect(self._emit_changed)
        self.y_spin.valueChanged.connect(self._emit_changed)
        self.scale_spin.valueChanged.connect(self._emit_changed)
        self.anim_combo.currentIndexChanged.connect(self._emit_changed)
        self.visible_check.toggled.connect(self._emit_changed)
        self.enabled_check.toggled.connect(self._emit_changed)

    def _on_toggle_clicked(self) -> None:
        self.set_expanded(self.toggle.isChecked())
        self.picked.emit()

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(expanded)
        self.content.setVisible(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def set_header_text(self, text: str) -> None:
        self.toggle.setText(text)

    def set_highlighted(self, on: bool) -> None:
        weight = "700" if on else "600"
        color = " color: #4da3ff;" if on else ""
        self.toggle.setStyleSheet(
            f"QToolButton {{ border: none; font-weight: {weight};{color} padding: 4px;"
            " text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 24); }"
        )

    def _emit_changed(self) -> None:
        if not self._suspend:
            self.changed.emit()

    def sync(self, inst: GuiObject, tortu_object: TortuObject | None) -> None:
        widgets = (
            self.x_spin, self.y_spin, self.scale_spin, self.anim_combo,
            self.visible_check, self.enabled_check,
        )
        self._suspend = True
        for widget in widgets:
            widget.blockSignals(True)
        self.x_spin.setValue(inst.x)
        self.y_spin.setValue(inst.y)
        self.scale_spin.setValue(inst.scale)
        self.visible_check.setChecked(inst.visible)
        self.enabled_check.setChecked(inst.enabled)
        self.anim_combo.clear()
        self.anim_combo.addItem("(default)", "")
        if tortu_object is not None:
            for anim in tortu_object.animations:
                self.anim_combo.addItem(anim.name, anim.name)
        found = self.anim_combo.findData(inst.animation)
        self.anim_combo.setCurrentIndex(found if found >= 0 else 0)
        for widget in widgets:
            widget.blockSignals(False)
        self._suspend = False

    def read_into(self, inst: GuiObject) -> None:
        inst.x = self.x_spin.value()
        inst.y = self.y_spin.value()
        inst.scale = self.scale_spin.value()
        inst.animation = self.anim_combo.currentData() or ""
        inst.visible = self.visible_check.isChecked()
        inst.enabled = self.enabled_check.isChecked()


class _GuiTextLabelCard(QWidget):
    """Collapsible editor for one placed text label instance in a GUI layer."""

    changed = pyqtSignal()
    remove_requested = pyqtSignal()
    picked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suspend = False

        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: 600; padding: 4px; text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 24); }"
        )
        self.toggle.clicked.connect(self._on_toggle_clicked)

        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedWidth(22)
        self.btn_remove.setToolTip("Remove this label")
        self.btn_remove.clicked.connect(self.remove_requested.emit)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.toggle, stretch=1)
        header.addWidget(self.btn_remove)

        self.text_edit = QLineEdit()
        self.font_combo = QComboBox()
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("(none — not addressable from scripts)")
        self.id_edit.setToolTip(
            "Optional name so instance scripts can find and update this label's text\n"
            "at runtime via instance_api.set_gui_text_label_text(gui_layer_path, id, text)"
        )
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-9999, 9999)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-9999, 9999)
        self.visible_check = QCheckBox("Visible at play")
        self.visible_check.setChecked(True)
        self.visible_check.setToolTip("Whether this label is drawn when the scene runs")
        self.enabled_check = QCheckBox("Enabled at scene start")
        self.enabled_check.setChecked(True)
        self.enabled_check.setToolTip("Unchecked: the label starts off entirely and isn't drawn")

        form = QFormLayout()
        form.setContentsMargins(20, 2, 0, 6)
        form.addRow("Text:", self.text_edit)
        form.addRow("Font:", self.font_combo)
        form.addRow("Name/ID:", self.id_edit)
        form.addRow("X:", self.x_spin)
        form.addRow("Y:", self.y_spin)
        form.addRow("", self.visible_check)
        form.addRow("", self.enabled_check)

        self.content = QWidget()
        self.content.setLayout(form)
        self.content.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(header)
        outer.addWidget(self.content)

        self.text_edit.textChanged.connect(self._emit_changed)
        self.font_combo.currentIndexChanged.connect(self._emit_changed)
        self.id_edit.textChanged.connect(self._emit_changed)
        self.x_spin.valueChanged.connect(self._emit_changed)
        self.y_spin.valueChanged.connect(self._emit_changed)
        self.visible_check.toggled.connect(self._emit_changed)
        self.enabled_check.toggled.connect(self._emit_changed)

    def _on_toggle_clicked(self) -> None:
        self.set_expanded(self.toggle.isChecked())
        self.picked.emit()

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(expanded)
        self.content.setVisible(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def set_header_text(self, text: str) -> None:
        self.toggle.setText(text)

    def set_highlighted(self, on: bool) -> None:
        weight = "700" if on else "600"
        color = " color: #4da3ff;" if on else ""
        self.toggle.setStyleSheet(
            f"QToolButton {{ border: none; font-weight: {weight};{color} padding: 4px;"
            " text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 24); }"
        )

    def _emit_changed(self) -> None:
        if not self._suspend:
            self.changed.emit()

    def sync(self, label: GuiTextLabel, font_choices: list[str]) -> None:
        widgets = (
            self.text_edit, self.font_combo, self.id_edit, self.x_spin, self.y_spin,
            self.visible_check, self.enabled_check,
        )
        self._suspend = True
        for widget in widgets:
            widget.blockSignals(True)
        if self.text_edit.text() != label.text:
            self.text_edit.setText(label.text)
        self.font_combo.clear()
        self.font_combo.addItem("(none)", "")
        for rel in font_choices:
            self.font_combo.addItem(rel, rel)
        found = self.font_combo.findData(label.font)
        self.font_combo.setCurrentIndex(found if found >= 0 else 0)
        if self.id_edit.text() != label.id:
            self.id_edit.setText(label.id)
        self.x_spin.setValue(label.x)
        self.y_spin.setValue(label.y)
        self.visible_check.setChecked(label.visible)
        self.enabled_check.setChecked(label.enabled)
        for widget in widgets:
            widget.blockSignals(False)
        self._suspend = False

    def read_into(self, label: GuiTextLabel) -> None:
        label.text = self.text_edit.text()
        label.font = self.font_combo.currentData() or ""
        label.id = self.id_edit.text().strip()
        label.x = self.x_spin.value()
        label.y = self.y_spin.value()
        label.visible = self.visible_check.isChecked()
        label.enabled = self.enabled_check.isChecked()


class _GuiTiledRectCard(QWidget):
    """Collapsible editor for one tiled-rect (progress bar) instance in a GUI layer."""

    changed = pyqtSignal()
    remove_requested = pyqtSignal()
    picked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suspend = False

        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: 600; padding: 4px; text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 24); }"
        )
        self.toggle.clicked.connect(self._on_toggle_clicked)

        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedWidth(22)
        self.btn_remove.setToolTip("Remove this tiled rect")
        self.btn_remove.clicked.connect(self.remove_requested.emit)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.toggle, stretch=1)
        header.addWidget(self.btn_remove)

        self.prefab_combo = QComboBox()
        self.prefab_combo.setToolTip("Reusable .tortuprogressbar prefab (texture + fill direction)")
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-9999, 9999)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-9999, 9999)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 2048)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 2048)
        self.number_spin = QDoubleSpinBox()
        self.number_spin.setRange(0.0, 999999.0)
        self.number_spin.setValue(1.0)
        self.number_spin.setToolTip("Current value — e.g. current HP")
        self.max_number_spin = QDoubleSpinBox()
        self.max_number_spin.setRange(0.0, 999999.0)
        self.max_number_spin.setValue(1.0)
        self.max_number_spin.setToolTip("Max value — e.g. max HP. Fill % is number / max_number")
        self.visible_check = QCheckBox("Visible at play")
        self.visible_check.setChecked(True)
        self.visible_check.setToolTip("Whether this rect is drawn when the scene runs")
        self.enabled_check = QCheckBox("Enabled at scene start")
        self.enabled_check.setChecked(True)
        self.enabled_check.setToolTip("Unchecked: the rect starts off entirely and isn't drawn")

        form = QFormLayout()
        form.setContentsMargins(20, 2, 0, 6)
        form.addRow("Prefab:", self.prefab_combo)
        form.addRow("X:", self.x_spin)
        form.addRow("Y:", self.y_spin)
        form.addRow("Width:", self.width_spin)
        form.addRow("Height:", self.height_spin)
        form.addRow("Number:", self.number_spin)
        form.addRow("Max number:", self.max_number_spin)
        form.addRow("", self.visible_check)
        form.addRow("", self.enabled_check)

        self.content = QWidget()
        self.content.setLayout(form)
        self.content.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(header)
        outer.addWidget(self.content)

        self.prefab_combo.currentIndexChanged.connect(self._emit_changed)
        self.x_spin.valueChanged.connect(self._emit_changed)
        self.y_spin.valueChanged.connect(self._emit_changed)
        self.width_spin.valueChanged.connect(self._emit_changed)
        self.height_spin.valueChanged.connect(self._emit_changed)
        self.number_spin.valueChanged.connect(self._emit_changed)
        self.max_number_spin.valueChanged.connect(self._emit_changed)
        self.visible_check.toggled.connect(self._emit_changed)
        self.enabled_check.toggled.connect(self._emit_changed)

    def _on_toggle_clicked(self) -> None:
        self.set_expanded(self.toggle.isChecked())
        self.picked.emit()

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(expanded)
        self.content.setVisible(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def set_header_text(self, text: str) -> None:
        self.toggle.setText(text)

    def set_highlighted(self, on: bool) -> None:
        weight = "700" if on else "600"
        color = " color: #4da3ff;" if on else ""
        self.toggle.setStyleSheet(
            f"QToolButton {{ border: none; font-weight: {weight};{color} padding: 4px;"
            " text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 24); }"
        )

    def _emit_changed(self) -> None:
        if not self._suspend:
            self.changed.emit()

    def sync(self, rect: GuiTiledRect, prefab_choices: list[str]) -> None:
        widgets = (
            self.prefab_combo, self.x_spin, self.y_spin, self.width_spin, self.height_spin,
            self.number_spin, self.max_number_spin, self.visible_check, self.enabled_check,
        )
        self._suspend = True
        for widget in widgets:
            widget.blockSignals(True)
        self.prefab_combo.clear()
        for rel in prefab_choices:
            self.prefab_combo.addItem(rel, rel)
        found = self.prefab_combo.findData(rect.prefab)
        self.prefab_combo.setCurrentIndex(found if found >= 0 else 0)
        self.x_spin.setValue(rect.x)
        self.y_spin.setValue(rect.y)
        self.width_spin.setValue(rect.width)
        self.height_spin.setValue(rect.height)
        self.number_spin.setValue(rect.number)
        self.max_number_spin.setValue(rect.max_number)
        self.visible_check.setChecked(rect.visible)
        self.enabled_check.setChecked(rect.enabled)
        for widget in widgets:
            widget.blockSignals(False)
        self._suspend = False

    def read_into(self, rect: GuiTiledRect) -> None:
        rect.prefab = self.prefab_combo.currentData() or rect.prefab
        rect.x = self.x_spin.value()
        rect.y = self.y_spin.value()
        rect.width = self.width_spin.value()
        rect.height = self.height_spin.value()
        rect.number = self.number_spin.value()
        rect.max_number = self.max_number_spin.value()
        rect.visible = self.visible_check.isChecked()
        rect.enabled = self.enabled_check.isChecked()


class _GuiRepeatSpriteCard(QWidget):
    """Collapsible editor for one repeat-sprite (life pips) instance in a GUI layer."""

    changed = pyqtSignal()
    remove_requested = pyqtSignal()
    picked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._suspend = False

        self.toggle = QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: 600; padding: 4px; text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 24); }"
        )
        self.toggle.clicked.connect(self._on_toggle_clicked)

        self.btn_remove = QPushButton("✕")
        self.btn_remove.setFixedWidth(22)
        self.btn_remove.setToolTip("Remove this repeat sprite")
        self.btn_remove.clicked.connect(self.remove_requested.emit)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.toggle, stretch=1)
        header.addWidget(self.btn_remove)

        self.prefab_combo = QComboBox()
        self.prefab_combo.setToolTip(
            "Reusable .tortupipbar prefab (full/empty sprites, direction, spacing, scale)"
        )
        self.x_spin = QSpinBox()
        self.x_spin.setRange(-9999, 9999)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(-9999, 9999)
        self.number_spin = QSpinBox()
        self.number_spin.setRange(0, 999999)
        self.number_spin.setToolTip("Currently filled slots — e.g. remaining life")
        self.max_number_spin = QSpinBox()
        self.max_number_spin.setRange(0, 999999)
        self.max_number_spin.setToolTip("Total slots — e.g. max life")
        self.visible_check = QCheckBox("Visible at play")
        self.visible_check.setChecked(True)
        self.visible_check.setToolTip("Whether these icons are drawn when the scene runs")
        self.enabled_check = QCheckBox("Enabled at scene start")
        self.enabled_check.setChecked(True)
        self.enabled_check.setToolTip("Unchecked: the icons start off entirely and aren't drawn")

        form = QFormLayout()
        form.setContentsMargins(20, 2, 0, 6)
        form.addRow("Prefab:", self.prefab_combo)
        form.addRow("X:", self.x_spin)
        form.addRow("Y:", self.y_spin)
        form.addRow("Number:", self.number_spin)
        form.addRow("Max number:", self.max_number_spin)
        form.addRow("", self.visible_check)
        form.addRow("", self.enabled_check)

        self.content = QWidget()
        self.content.setLayout(form)
        self.content.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(header)
        outer.addWidget(self.content)

        self.prefab_combo.currentIndexChanged.connect(self._emit_changed)
        self.x_spin.valueChanged.connect(self._emit_changed)
        self.y_spin.valueChanged.connect(self._emit_changed)
        self.number_spin.valueChanged.connect(self._emit_changed)
        self.max_number_spin.valueChanged.connect(self._emit_changed)
        self.visible_check.toggled.connect(self._emit_changed)
        self.enabled_check.toggled.connect(self._emit_changed)

    def _on_toggle_clicked(self) -> None:
        self.set_expanded(self.toggle.isChecked())
        self.picked.emit()

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(expanded)
        self.content.setVisible(expanded)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def set_header_text(self, text: str) -> None:
        self.toggle.setText(text)

    def set_highlighted(self, on: bool) -> None:
        weight = "700" if on else "600"
        color = " color: #4da3ff;" if on else ""
        self.toggle.setStyleSheet(
            f"QToolButton {{ border: none; font-weight: {weight};{color} padding: 4px;"
            " text-align: left; }"
            "QToolButton:hover { background-color: rgba(255, 255, 255, 24); }"
        )

    def _emit_changed(self) -> None:
        if not self._suspend:
            self.changed.emit()

    def sync(self, rep: GuiRepeatSprite, prefab_choices: list[str]) -> None:
        widgets = (
            self.prefab_combo, self.x_spin, self.y_spin, self.number_spin,
            self.max_number_spin, self.visible_check, self.enabled_check,
        )
        self._suspend = True
        for widget in widgets:
            widget.blockSignals(True)
        self.prefab_combo.clear()
        for rel in prefab_choices:
            self.prefab_combo.addItem(rel, rel)
        found = self.prefab_combo.findData(rep.prefab)
        self.prefab_combo.setCurrentIndex(found if found >= 0 else 0)
        self.x_spin.setValue(rep.x)
        self.y_spin.setValue(rep.y)
        self.number_spin.setValue(rep.number)
        self.max_number_spin.setValue(rep.max_number)
        self.visible_check.setChecked(rep.visible)
        self.enabled_check.setChecked(rep.enabled)
        for widget in widgets:
            widget.blockSignals(False)
        self._suspend = False

    def read_into(self, rep: GuiRepeatSprite) -> None:
        rep.prefab = self.prefab_combo.currentData() or rep.prefab
        rep.x = self.x_spin.value()
        rep.y = self.y_spin.value()
        rep.number = self.number_spin.value()
        rep.max_number = self.max_number_spin.value()
        rep.visible = self.visible_check.isChecked()
        rep.enabled = self.enabled_check.isChecked()


class GuiLayerEditorWidget(QWidget):
    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_gui_layer_requested = pyqtSignal()
    open_gui_layer_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.gui_layer: GuiLayer | None = None
        self._dirty = False
        self._palette_colors: list[tuple[int, int, int]] = []
        self._active_tileset: Tileset | None = None
        self._tilesets_cache: dict[str, Tileset] = {}

        self.canvas = GuiLayerCanvas()
        self.canvas.changed.connect(self._on_canvas_changed)
        self.canvas.tool_cycled.connect(self._set_tool)
        self.canvas.object_selected.connect(self._on_canvas_object_selected)
        self.canvas.text_label_selected.connect(self._on_canvas_text_selected)
        self.canvas.tiled_rect_selected.connect(self._on_canvas_tiled_rect_selected)
        self.canvas.repeat_sprite_selected.connect(self._on_canvas_repeat_sprite_selected)

        self.strip_canvas = TilesetStripCanvas()
        self.strip_canvas.tile_clicked.connect(self._on_strip_tile_clicked)

        self.object_strip = ObjectStripCanvas()
        self.object_strip.object_clicked.connect(self._on_object_strip_clicked)

        self.progress_bar_strip = ProgressBarStripCanvas()
        self.progress_bar_strip.progress_bar_clicked.connect(self._on_progress_bar_strip_clicked)

        self.pip_bar_strip = PipBarStripCanvas()
        self.pip_bar_strip.pip_bar_clicked.connect(self._on_pip_bar_strip_clicked)

        self.btn_new = QPushButton("New GUI Layer…")
        self.btn_new.clicked.connect(self.new_gui_layer_requested.emit)
        self.btn_open = QPushButton("Open GUI Layer…")
        self.btn_open.clicked.connect(self.open_gui_layer_requested.emit)
        self.btn_save = QPushButton("Save GUI layer")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_gui_layer)

        self.status_label = QLabel("No GUI layer open")
        self.size_label = QLabel("—")

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 2048)
        self.width_spin.setValue(DEFAULT_GUI_LAYER_WIDTH)
        self.width_spin.setSuffix(" px")

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 2048)
        self.height_spin.setValue(DEFAULT_GUI_LAYER_HEIGHT)
        self.height_spin.setSuffix(" px")

        self.btn_resize = QPushButton("Resize")
        self.btn_resize.clicked.connect(self._resize_gui_layer)
        self.btn_reset_screen = QPushButton("Reset to screen")
        self.btn_reset_screen.setToolTip(f"Set size to {SCREEN_WIDTH}×{SCREEN_HEIGHT} (screen)")
        self.btn_reset_screen.clicked.connect(self._reset_to_screen_size)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 16)
        self.zoom_spin.setValue(2)
        self.zoom_spin.valueChanged.connect(self.canvas.set_zoom)

        self.show_grid = QCheckBox("Tile grid")
        self.show_grid.setChecked(True)
        self.show_grid.toggled.connect(self.canvas.set_show_grid)

        # -- script ---------------------------------------
        self.script_edit = QLineEdit()
        self.script_edit.setPlaceholderText("scripts/my_hud.py")
        self.script_edit.textChanged.connect(self._on_script_changed)
        self.script_edit.textChanged.connect(self._refresh_script_row)

        self.btn_browse_script = QPushButton("Browse…")
        self.btn_browse_script.clicked.connect(self._browse_script)
        self.btn_open_script = QPushButton("Open script")
        self.btn_open_script.clicked.connect(self._open_script_in_editor)

        self.btn_create_script = QPushButton("Create new")
        self.btn_create_script.clicked.connect(self._create_script)
        self.btn_assign_script = QPushButton("Assign existing…")
        self.btn_assign_script.clicked.connect(self._browse_script)

        self._script_container = QWidget()
        _script_vbox = QVBoxLayout(self._script_container)
        _script_vbox.setContentsMargins(0, 0, 0, 0)
        _script_vbox.setSpacing(2)
        self._script_empty_row = QWidget()
        _script_empty_inner = QHBoxLayout(self._script_empty_row)
        _script_empty_inner.setContentsMargins(0, 0, 0, 0)
        _script_empty_inner.addWidget(self.btn_create_script)
        _script_empty_inner.addWidget(self.btn_assign_script)
        _script_vbox.addWidget(self._script_empty_row)
        self._script_edit_row = QWidget()
        _script_edit_inner = QHBoxLayout(self._script_edit_row)
        _script_edit_inner.setContentsMargins(0, 0, 0, 0)
        _script_edit_inner.addWidget(self.script_edit, stretch=1)
        _script_edit_inner.addWidget(self.btn_browse_script)
        _script_edit_inner.addWidget(self.btn_open_script)
        _script_vbox.addWidget(self._script_edit_row)

        # -- target / mode / tool ---------------------------------------
        self.btn_target_tiles = QPushButton("Tiles")
        self.btn_target_objects = QPushButton("Objects")
        self.btn_target_text = QPushButton("Text")
        self.btn_target_tiled_rect = QPushButton("Tiled Rect")
        self.btn_target_repeat_sprite = QPushButton("Repeat Sprite")
        target_buttons = (
            self.btn_target_tiles, self.btn_target_objects, self.btn_target_text,
            self.btn_target_tiled_rect, self.btn_target_repeat_sprite,
        )
        for btn in target_buttons:
            btn.setCheckable(True)
        self.btn_target_tiles.setChecked(True)
        self.btn_target_tiles.clicked.connect(lambda: self._set_target(GuiLayerTarget.TILES))
        self.btn_target_objects.clicked.connect(lambda: self._set_target(GuiLayerTarget.OBJECTS))
        self.btn_target_text.clicked.connect(lambda: self._set_target(GuiLayerTarget.TEXT))
        self.btn_target_tiled_rect.clicked.connect(
            lambda: self._set_target(GuiLayerTarget.TILED_RECT)
        )
        self.btn_target_repeat_sprite.clicked.connect(
            lambda: self._set_target(GuiLayerTarget.REPEAT_SPRITE)
        )

        self.btn_draw_mode = QPushButton("Draw")
        self.btn_edit_mode = QPushButton("Edit")
        for btn in (self.btn_draw_mode, self.btn_edit_mode):
            btn.setCheckable(True)
        self.btn_draw_mode.setChecked(True)
        self.btn_draw_mode.clicked.connect(lambda: self._set_editor_mode(False))
        self.btn_edit_mode.clicked.connect(lambda: self._set_editor_mode(True))

        self.btn_paint = QPushButton("Paint")
        self.btn_erase = QPushButton("Erase")
        self.btn_dropper = QPushButton("Eyedropper")
        for btn in (self.btn_paint, self.btn_erase, self.btn_dropper):
            btn.setCheckable(True)
        self.btn_paint.setChecked(True)
        self.btn_paint.clicked.connect(lambda: self._set_tool(Tool.PAINT))
        self.btn_erase.clicked.connect(lambda: self._set_tool(Tool.ERASE))
        self.btn_dropper.clicked.connect(lambda: self._set_tool(Tool.EYEDROPPER))

        # -- tile layer panel ---------------------------------------
        self.tileset_combo = QComboBox()
        self.tileset_combo.currentIndexChanged.connect(self._on_tileset_changed)
        self.tile_layer_visible = QCheckBox("Tile layer visible")
        self.tile_layer_visible.setChecked(True)
        self.tile_layer_visible.toggled.connect(self._on_tile_layer_visible_toggled)

        # -- objects panel ---------------------------------------
        self.objects_search = QLineEdit()
        self.objects_search.setPlaceholderText("Filter objects…")
        self.objects_search.textChanged.connect(self._refresh_objects_list)

        self._objects_list_indices: list[int] = []
        self._object_cards: dict[int, _GuiObjectCard] = {}

        self.objects_container = QWidget()
        self.objects_container_layout = QVBoxLayout(self.objects_container)
        self.objects_container_layout.setContentsMargins(0, 0, 0, 0)
        self.objects_container_layout.setSpacing(2)
        self.objects_container_layout.addStretch(1)

        self.objects_scroll = QScrollArea()
        self.objects_scroll.setWidgetResizable(True)
        self.objects_scroll.setWidget(self.objects_container)
        self.objects_scroll.setMinimumHeight(160)

        # -- text labels panel ---------------------------------------
        self.text_content_edit = QLineEdit()
        self.text_content_edit.setPlaceholderText("New label text…")
        self.text_content_edit.textChanged.connect(self._on_text_fields_changed)
        self.text_content_edit.returnPressed.connect(self._add_text_label)

        self.text_font_combo = QComboBox()
        self.text_font_combo.currentIndexChanged.connect(self._on_text_fields_changed)

        self.btn_add_text_label = QPushButton("Add label")
        self.btn_add_text_label.setToolTip("Create a new text label using the text and font above")
        self.btn_add_text_label.clicked.connect(self._add_text_label)

        self.text_labels_search = QLineEdit()
        self.text_labels_search.setPlaceholderText("Filter labels…")
        self.text_labels_search.textChanged.connect(self._refresh_text_labels_list)

        self._text_labels_list_indices: list[int] = []
        self._text_label_cards: dict[int, _GuiTextLabelCard] = {}

        self.text_labels_container = QWidget()
        self.text_labels_container_layout = QVBoxLayout(self.text_labels_container)
        self.text_labels_container_layout.setContentsMargins(0, 0, 0, 0)
        self.text_labels_container_layout.setSpacing(2)
        self.text_labels_container_layout.addStretch(1)

        self.text_labels_scroll = QScrollArea()
        self.text_labels_scroll.setWidgetResizable(True)
        self.text_labels_scroll.setWidget(self.text_labels_container)
        self.text_labels_scroll.setMinimumHeight(160)

        # -- tiled rects panel ---------------------------------------
        self.btn_add_tiled_rect = QPushButton("Add tiled rect")
        self.btn_add_tiled_rect.setToolTip(
            "Create a new tiled rect (e.g. a health bar) using the texture selected\n"
            "in the Tiled Rects tab below"
        )
        self.btn_add_tiled_rect.clicked.connect(self._add_tiled_rect)

        self.tiled_rects_search = QLineEdit()
        self.tiled_rects_search.setPlaceholderText("Filter tiled rects…")
        self.tiled_rects_search.textChanged.connect(self._refresh_tiled_rects_list)

        self._tiled_rects_list_indices: list[int] = []
        self._tiled_rect_cards: dict[int, _GuiTiledRectCard] = {}

        self.tiled_rects_container = QWidget()
        self.tiled_rects_container_layout = QVBoxLayout(self.tiled_rects_container)
        self.tiled_rects_container_layout.setContentsMargins(0, 0, 0, 0)
        self.tiled_rects_container_layout.setSpacing(2)
        self.tiled_rects_container_layout.addStretch(1)

        self.tiled_rects_scroll = QScrollArea()
        self.tiled_rects_scroll.setWidgetResizable(True)
        self.tiled_rects_scroll.setWidget(self.tiled_rects_container)
        self.tiled_rects_scroll.setMinimumHeight(160)

        # -- repeat sprites panel ---------------------------------------
        self.repeat_sprites_search = QLineEdit()
        self.repeat_sprites_search.setPlaceholderText("Filter repeat sprites…")
        self.repeat_sprites_search.textChanged.connect(self._refresh_repeat_sprites_list)

        self._repeat_sprites_list_indices: list[int] = []
        self._repeat_sprite_cards: dict[int, _GuiRepeatSpriteCard] = {}

        self.repeat_sprites_container = QWidget()
        self.repeat_sprites_container_layout = QVBoxLayout(self.repeat_sprites_container)
        self.repeat_sprites_container_layout.setContentsMargins(0, 0, 0, 0)
        self.repeat_sprites_container_layout.setSpacing(2)
        self.repeat_sprites_container_layout.addStretch(1)

        self.repeat_sprites_scroll = QScrollArea()
        self.repeat_sprites_scroll.setWidgetResizable(True)
        self.repeat_sprites_scroll.setWidget(self.repeat_sprites_container)
        self.repeat_sprites_scroll.setMinimumHeight(160)

        self._selected_object_index = -1
        self._selected_text_index = -1
        self._selected_tiled_rect_index = -1
        self._selected_repeat_sprite_index = -1
        self._target = GuiLayerTarget.TILES
        self._edit_mode = False
        self._selected_tile = 0

        self._build_layout()
        self._set_editor_mode(True)

    # -- layout -----------------------------------------------------

    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        file_row = QHBoxLayout()
        file_row.addWidget(self.btn_new)
        file_row.addWidget(self.btn_open)
        file_row.addWidget(self.btn_save)
        file_row.addWidget(self.btn_rename)
        file_row.addWidget(self.status_label)
        file_row.addStretch()
        outer.addLayout(file_row)

        body = QHBoxLayout()
        outer.addLayout(body, stretch=1)

        self.canvas_group = QGroupBox("GUI Layer")
        canvas_layout = QVBoxLayout(self.canvas_group)
        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(False)
        canvas_scroll.setWidget(self.canvas)
        canvas_layout.addWidget(canvas_scroll)
        body.addWidget(self.canvas_group, stretch=1)

        side_widget = QWidget()
        side = QVBoxLayout(side_widget)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(6)

        size_section = CollapsibleSection("Size", expanded=False)
        size_form = QFormLayout()
        size_form.addRow("Size:", self.size_label)
        size_form.addRow("Width:", self.width_spin)
        size_form.addRow("Height:", self.height_spin)
        resize_row = QHBoxLayout()
        resize_row.addWidget(self.btn_resize)
        resize_row.addWidget(self.btn_reset_screen)
        size_form.addRow(resize_row)
        size_form.addRow("Zoom:", self.zoom_spin)
        size_form.addRow(self.show_grid)
        size_section.content_layout().addLayout(size_form)
        side.addWidget(size_section)

        script_section = CollapsibleSection("Script", expanded=False)
        script_form = QFormLayout()
        script_form.addRow("GUI layer script:", self._script_container)
        script_section.content_layout().addLayout(script_form)
        side.addWidget(script_section)

        tile_section = CollapsibleSection("Tile Layer", expanded=True)
        tile_form = QFormLayout()
        tile_form.addRow("Tileset:", self.tileset_combo)
        tile_form.addRow("", self.tile_layer_visible)
        tile_section.content_layout().addLayout(tile_form)
        side.addWidget(tile_section)

        objects_section = CollapsibleSection("Objects", expanded=True)
        objects_section.content_layout().addWidget(self.objects_search)
        objects_section.content_layout().addWidget(self.objects_scroll)
        side.addWidget(objects_section)

        text_section = CollapsibleSection("Text Labels", expanded=True)
        text_form = QFormLayout()
        text_form.addRow("New label text:", self.text_content_edit)
        text_form.addRow("New label font:", self.text_font_combo)
        text_section.content_layout().addLayout(text_form)
        text_section.content_layout().addWidget(self.btn_add_text_label)
        text_section.content_layout().addWidget(self.text_labels_search)
        text_section.content_layout().addWidget(self.text_labels_scroll)
        side.addWidget(text_section)

        tiled_rects_section = CollapsibleSection("Tiled Rects", expanded=True)
        tiled_rects_section.content_layout().addWidget(QLabel(
            "Pick a texture in the Tiled Rects tab below, then click the canvas\n"
            "in Tiled Rect mode to place a bar (e.g. a health bar)."
        ))
        tiled_rects_section.content_layout().addWidget(self.btn_add_tiled_rect)
        tiled_rects_section.content_layout().addWidget(self.tiled_rects_search)
        tiled_rects_section.content_layout().addWidget(self.tiled_rects_scroll)
        side.addWidget(tiled_rects_section)

        repeat_sprites_section = CollapsibleSection("Repeat Sprites", expanded=True)
        repeat_sprites_section.content_layout().addWidget(QLabel(
            "Pick a prefab in the Repeat Sprites tab below, then click the canvas\n"
            "in Repeat Sprite mode to place a pip/heart counter."
        ))
        repeat_sprites_section.content_layout().addWidget(self.repeat_sprites_search)
        repeat_sprites_section.content_layout().addWidget(self.repeat_sprites_scroll)
        side.addWidget(repeat_sprites_section)

        side.addStretch()

        side_scroll = QScrollArea()
        side_scroll.setWidgetResizable(True)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side_scroll.setWidget(side_widget)
        side_scroll.setMinimumWidth(260)
        body.addWidget(side_scroll)

        self.bottom_tabs = QTabWidget()
        tile_tab = QWidget()
        tile_tab_layout = QVBoxLayout(tile_tab)
        tile_tab_layout.setContentsMargins(0, 0, 0, 0)
        tile_strip_scroll = QScrollArea()
        tile_strip_scroll.setWidgetResizable(True)
        tile_strip_scroll.setMaximumHeight(140)
        tile_strip_scroll.setWidget(self.strip_canvas)
        tile_tab_layout.addWidget(tile_strip_scroll)
        self.bottom_tabs.addTab(tile_tab, "Tileset")

        object_tab = QWidget()
        object_tab_layout = QVBoxLayout(object_tab)
        object_tab_layout.setContentsMargins(0, 0, 0, 0)
        object_strip_scroll = QScrollArea()
        object_strip_scroll.setWidgetResizable(True)
        object_strip_scroll.setMaximumHeight(140)
        object_strip_scroll.setWidget(self.object_strip)
        object_tab_layout.addWidget(object_strip_scroll)
        self.bottom_tabs.addTab(object_tab, "Objects")

        tiled_rect_tab = QWidget()
        tiled_rect_tab_layout = QVBoxLayout(tiled_rect_tab)
        tiled_rect_tab_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_strip_scroll = QScrollArea()
        progress_bar_strip_scroll.setWidgetResizable(True)
        progress_bar_strip_scroll.setMaximumHeight(140)
        progress_bar_strip_scroll.setWidget(self.progress_bar_strip)
        tiled_rect_tab_layout.addWidget(progress_bar_strip_scroll)
        self.bottom_tabs.addTab(tiled_rect_tab, "Tiled Rects")

        repeat_sprite_tab = QWidget()
        repeat_sprite_tab_layout = QVBoxLayout(repeat_sprite_tab)
        repeat_sprite_tab_layout.setContentsMargins(0, 0, 0, 0)
        pip_bar_strip_scroll = QScrollArea()
        pip_bar_strip_scroll.setWidgetResizable(True)
        pip_bar_strip_scroll.setMaximumHeight(140)
        pip_bar_strip_scroll.setWidget(self.pip_bar_strip)
        repeat_sprite_tab_layout.addWidget(pip_bar_strip_scroll)
        self.bottom_tabs.addTab(repeat_sprite_tab, "Repeat Sprites")
        outer.addWidget(self.bottom_tabs)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self.btn_target_tiles)
        mode_row.addWidget(self.btn_target_objects)
        mode_row.addWidget(self.btn_target_text)
        mode_row.addWidget(self.btn_target_tiled_rect)
        mode_row.addWidget(self.btn_target_repeat_sprite)
        mode_row.addSpacing(12)
        mode_row.addWidget(self.btn_draw_mode)
        mode_row.addWidget(self.btn_edit_mode)
        mode_row.addSpacing(12)
        mode_row.addWidget(self.btn_paint)
        mode_row.addWidget(self.btn_erase)
        mode_row.addWidget(self.btn_dropper)
        mode_row.addStretch()
        outer.addLayout(mode_row)

    # -- mode / tool / target -----------------------------------------------------

    def _set_target(self, target: GuiLayerTarget) -> None:
        self._target = target
        self.btn_target_tiles.setChecked(target == GuiLayerTarget.TILES)
        self.btn_target_objects.setChecked(target == GuiLayerTarget.OBJECTS)
        self.btn_target_text.setChecked(target == GuiLayerTarget.TEXT)
        self.btn_target_tiled_rect.setChecked(target == GuiLayerTarget.TILED_RECT)
        self.btn_target_repeat_sprite.setChecked(target == GuiLayerTarget.REPEAT_SPRITE)
        self.btn_dropper.setEnabled(target == GuiLayerTarget.TILES)
        if target != GuiLayerTarget.TILES and self.canvas.tool == Tool.EYEDROPPER:
            self._set_tool(Tool.PAINT)
        self._refresh_canvas()

    def _gui_group_title(self) -> str:
        if self._edit_mode:
            return "GUI Layer — EDIT MODE"
        names = {Tool.PAINT: "Paint", Tool.ERASE: "Erase", Tool.EYEDROPPER: "Eyedropper"}
        return f"GUI Layer — DRAW MODE  ·  {names.get(self.canvas.tool, '')}"

    def _set_editor_mode(self, edit: bool) -> None:
        self._edit_mode = edit
        self.btn_draw_mode.setChecked(not edit)
        self.btn_edit_mode.setChecked(edit)
        for btn in (self.btn_paint, self.btn_erase, self.btn_dropper):
            btn.setEnabled(not edit)
        self.canvas_group.setTitle(self._gui_group_title())
        self._refresh_canvas()

    def _set_tool(self, tool: Tool) -> None:
        self.btn_paint.setChecked(tool == Tool.PAINT)
        self.btn_erase.setChecked(tool == Tool.ERASE)
        self.btn_dropper.setChecked(tool == Tool.EYEDROPPER)
        self.canvas.set_tool(tool)
        self.canvas_group.setTitle(self._gui_group_title())
        self._refresh_canvas()

    # -- dirty / status -----------------------------------------------------

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._update_status()

    def _update_status(self) -> None:
        if not self.gui_layer or not self.file_path:
            self.status_label.setText("No GUI layer open")
            return
        state = "edited" if self._dirty else "saved"
        self.status_label.setText(f"{self.file_path.name} ({state})")

    def _update_size_label(self) -> None:
        if not self.gui_layer:
            self.size_label.setText("—")
            return
        self.size_label.setText(f"{self.gui_layer.width}×{self.gui_layer.height} px")

    # -- asset caches -----------------------------------------------------

    def _get_tileset(self, rel_path: str) -> Tileset | None:
        if not rel_path:
            return None
        if rel_path in self._tilesets_cache:
            return self._tilesets_cache[rel_path]
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_tileset(path)
        self._tilesets_cache[rel_path] = loaded
        return loaded

    def _load_active_tileset(self) -> None:
        if not self.gui_layer:
            self._active_tileset = None
            return
        self._active_tileset = self._get_tileset(self.gui_layer.tileset)

    def _load_palette_colors(self) -> None:
        if not self.gui_layer:
            return
        path = palette_path(self.project_root, self.gui_layer.palette)
        if not path.is_file():
            raise FileNotFoundError(f"Palette not found: {path}")
        self._palette_colors = load_palette(path)

    def _active_tile_size(self) -> int:
        return self._active_tileset.tile_size if self._active_tileset else TILE_BLOCK

    # -- combos / strips -----------------------------------------------------

    def _sync_tileset_combo(self) -> None:
        self.tileset_combo.blockSignals(True)
        self.tileset_combo.clear()
        self.tileset_combo.addItem("(none)", "")
        for rel in list_tileset_paths(self.project_root):
            self.tileset_combo.addItem(rel, rel)
        if self.gui_layer:
            index = self.tileset_combo.findData(self.gui_layer.tileset)
            self.tileset_combo.setCurrentIndex(index if index >= 0 else 0)
        self.tileset_combo.blockSignals(False)

    def _sync_text_font_combo(self) -> None:
        self.text_font_combo.blockSignals(True)
        current = self.text_font_combo.currentData()
        self.text_font_combo.clear()
        self.text_font_combo.addItem("(none)", "")
        for rel in list_text_font_paths(self.project_root):
            self.text_font_combo.addItem(rel, rel)
        for rel in list_sprite_font_paths(self.project_root):
            self.text_font_combo.addItem(rel, rel)
        index = self.text_font_combo.findData(current) if current else 0
        self.text_font_combo.setCurrentIndex(index if index >= 0 else 0)
        self.text_font_combo.blockSignals(False)

    def _refresh_strip(self) -> None:
        if self._active_tileset:
            self.strip_canvas.set_tileset(self._active_tileset, self._palette_colors)
            self.strip_canvas.set_selected_index(self._selected_tile)
        else:
            self.strip_canvas.set_tileset(None, [])

    def _refresh_object_strip(self) -> None:
        paths = list_object_paths(self.project_root)
        self.object_strip.set_project(self.project_root, paths)

    def _refresh_progress_bar_strip(self) -> None:
        paths = list_progress_bar_paths(self.project_root)
        self.progress_bar_strip.set_project(self.project_root, paths)

    def _refresh_pip_bar_strip(self) -> None:
        paths = list_pip_bar_paths(self.project_root)
        self.pip_bar_strip.set_project(self.project_root, paths)

    def _refresh_objects_list(self) -> None:
        if not self.gui_layer:
            self._rebuild_object_cards([])
            self._objects_list_indices = []
            self._selected_object_index = -1
            return
        if self._selected_object_index >= len(self.gui_layer.objects):
            self._selected_object_index = -1
        query = self.objects_search.text().strip().lower()
        visible_indices: list[int] = []
        for i, inst in enumerate(self.gui_layer.objects):
            name = Path(inst.prefab).stem if inst.prefab else "(unassigned)"
            if query and query not in name.lower():
                continue
            visible_indices.append(i)
        if visible_indices != self._objects_list_indices:
            self._rebuild_object_cards(visible_indices)
            self._objects_list_indices = visible_indices
        for i in visible_indices:
            inst = self.gui_layer.objects[i]
            card = self._object_cards[i]
            tortu_object = self.canvas._get_tortu_object(inst.prefab)
            card.sync(inst, tortu_object)
            name = Path(inst.prefab).stem if inst.prefab else "(unassigned)"
            suffix = f"  scale={inst.scale:g}" if inst.scale != 1.0 else ""
            card.set_header_text(f"#{i}  {name}{suffix}")
            card.toggle.setToolTip(f"{name}{suffix}  @ ({inst.x}, {inst.y})")
            card.set_highlighted(i == self._selected_object_index)

    def _rebuild_object_cards(self, visible_indices: list[int]) -> None:
        for card in self._object_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._object_cards = {}
        for i in visible_indices:
            card = _GuiObjectCard()
            card.changed.connect(lambda idx=i: self._on_object_card_changed(idx))
            card.remove_requested.connect(lambda idx=i: self._remove_object(idx))
            card.picked.connect(lambda idx=i: self._on_object_card_picked(idx))
            self.objects_container_layout.insertWidget(
                self.objects_container_layout.count() - 1, card
            )
            self._object_cards[i] = card

    def _on_object_card_changed(self, obj_idx: int) -> None:
        if not self.gui_layer or not (0 <= obj_idx < len(self.gui_layer.objects)):
            return
        card = self._object_cards.get(obj_idx)
        if card is None:
            return
        card.read_into(self.gui_layer.objects[obj_idx])
        self._mark_dirty()
        self._refresh_canvas()
        self._refresh_objects_list()

    def _on_object_card_picked(self, obj_idx: int) -> None:
        self._selected_object_index = obj_idx
        self._selected_text_index = -1
        self._selected_tiled_rect_index = -1
        self._selected_repeat_sprite_index = -1
        self.canvas.selected_object_index = obj_idx
        self.canvas.selected_text_index = -1
        self.canvas.selected_tiled_rect_index = -1
        self.canvas.selected_repeat_sprite_index = -1
        self.canvas.update()
        self._refresh_text_labels_list()
        self._refresh_tiled_rects_list()
        self._refresh_repeat_sprites_list()
        for idx, card in self._object_cards.items():
            card.set_highlighted(idx == self._selected_object_index)

    def _remove_object(self, obj_idx: int) -> None:
        if not self.gui_layer or not (0 <= obj_idx < len(self.gui_layer.objects)):
            return
        self.gui_layer.remove_object(obj_idx)
        if self._selected_object_index == obj_idx:
            self._selected_object_index = -1
        elif self._selected_object_index > obj_idx:
            self._selected_object_index -= 1
        self._mark_dirty()
        self._refresh_objects_list()
        self._refresh_canvas()

    def _font_choices(self) -> list[str]:
        return list_text_font_paths(self.project_root) + list_sprite_font_paths(self.project_root)

    def _refresh_text_labels_list(self) -> None:
        if not self.gui_layer:
            self._rebuild_text_label_cards([])
            self._text_labels_list_indices = []
            self._selected_text_index = -1
            return
        if self._selected_text_index >= len(self.gui_layer.text_labels):
            self._selected_text_index = -1
        query = self.text_labels_search.text().strip().lower()
        visible_indices: list[int] = []
        for i, label in enumerate(self.gui_layer.text_labels):
            if query and query not in label.text.lower():
                continue
            visible_indices.append(i)
        if visible_indices != self._text_labels_list_indices:
            self._rebuild_text_label_cards(visible_indices)
            self._text_labels_list_indices = visible_indices
        font_choices = self._font_choices()
        for i in visible_indices:
            label = self.gui_layer.text_labels[i]
            card = self._text_label_cards[i]
            card.sync(label, font_choices)
            preview = label.text if len(label.text) <= 20 else label.text[:20] + "…"
            name_suffix = f"  [{label.id}]" if label.id else ""
            card.set_header_text(f'#{i}  "{preview}"{name_suffix}')
            card.toggle.setToolTip(f'"{preview}"  @ ({label.x}, {label.y})')
            card.set_highlighted(i == self._selected_text_index)

    def _rebuild_text_label_cards(self, visible_indices: list[int]) -> None:
        for card in self._text_label_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._text_label_cards = {}
        for i in visible_indices:
            card = _GuiTextLabelCard()
            card.changed.connect(lambda idx=i: self._on_text_label_card_changed(idx))
            card.remove_requested.connect(lambda idx=i: self._remove_text_label(idx))
            card.picked.connect(lambda idx=i: self._on_text_label_card_picked(idx))
            self.text_labels_container_layout.insertWidget(
                self.text_labels_container_layout.count() - 1, card
            )
            self._text_label_cards[i] = card

    def _on_text_label_card_changed(self, label_idx: int) -> None:
        if not self.gui_layer or not (0 <= label_idx < len(self.gui_layer.text_labels)):
            return
        card = self._text_label_cards.get(label_idx)
        if card is None:
            return
        label = self.gui_layer.text_labels[label_idx]
        card.read_into(label)
        if label.id and any(
            i != label_idx and other.id == label.id for i, other in enumerate(self.gui_layer.text_labels)
        ):
            QMessageBox.warning(
                self, "Duplicate Label Name",
                f'Another label already uses the name "{label.id}" — scripts would find '
                "only the first match. Pick a different name."
            )
            label.id = ""
        self._mark_dirty()
        self._refresh_canvas()
        self._refresh_text_labels_list()

    def _on_text_label_card_picked(self, label_idx: int) -> None:
        self._selected_text_index = label_idx
        self._selected_object_index = -1
        self._selected_tiled_rect_index = -1
        self._selected_repeat_sprite_index = -1
        self.canvas.selected_text_index = label_idx
        self.canvas.selected_object_index = -1
        self.canvas.selected_tiled_rect_index = -1
        self.canvas.selected_repeat_sprite_index = -1
        self.canvas.update()
        self._refresh_objects_list()
        self._refresh_tiled_rects_list()
        self._refresh_repeat_sprites_list()
        for idx, card in self._text_label_cards.items():
            card.set_highlighted(idx == self._selected_text_index)

    def _remove_text_label(self, label_idx: int) -> None:
        if not self.gui_layer or not (0 <= label_idx < len(self.gui_layer.text_labels)):
            return
        self.gui_layer.remove_text_label(label_idx)
        if self._selected_text_index == label_idx:
            self._selected_text_index = -1
        elif self._selected_text_index > label_idx:
            self._selected_text_index -= 1
        self._mark_dirty()
        self._refresh_text_labels_list()
        self._refresh_canvas()

    def _progress_bar_choices(self) -> list[str]:
        return list_progress_bar_paths(self.project_root)

    def _pip_bar_choices(self) -> list[str]:
        return list_pip_bar_paths(self.project_root)

    def _refresh_tiled_rects_list(self) -> None:
        if not self.gui_layer:
            self._rebuild_tiled_rect_cards([])
            self._tiled_rects_list_indices = []
            self._selected_tiled_rect_index = -1
            return
        if self._selected_tiled_rect_index >= len(self.gui_layer.tiled_rects):
            self._selected_tiled_rect_index = -1
        query = self.tiled_rects_search.text().strip().lower()
        visible_indices: list[int] = []
        for i, rect in enumerate(self.gui_layer.tiled_rects):
            if query and query not in rect.id.lower():
                continue
            visible_indices.append(i)
        if visible_indices != self._tiled_rects_list_indices:
            self._rebuild_tiled_rect_cards(visible_indices)
            self._tiled_rects_list_indices = visible_indices
        progress_bar_choices = self._progress_bar_choices()
        for i in visible_indices:
            rect = self.gui_layer.tiled_rects[i]
            card = self._tiled_rect_cards[i]
            card.sync(rect, progress_bar_choices)
            card.set_header_text(f"#{i}  {rect.id}")
            card.toggle.setToolTip(f"{rect.id}  @ ({rect.x}, {rect.y})")
            card.set_highlighted(i == self._selected_tiled_rect_index)

    def _rebuild_tiled_rect_cards(self, visible_indices: list[int]) -> None:
        for card in self._tiled_rect_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._tiled_rect_cards = {}
        for i in visible_indices:
            card = _GuiTiledRectCard()
            card.changed.connect(lambda idx=i: self._on_tiled_rect_card_changed(idx))
            card.remove_requested.connect(lambda idx=i: self._remove_tiled_rect(idx))
            card.picked.connect(lambda idx=i: self._on_tiled_rect_card_picked(idx))
            self.tiled_rects_container_layout.insertWidget(
                self.tiled_rects_container_layout.count() - 1, card
            )
            self._tiled_rect_cards[i] = card

    def _on_tiled_rect_card_changed(self, rect_idx: int) -> None:
        if not self.gui_layer or not (0 <= rect_idx < len(self.gui_layer.tiled_rects)):
            return
        card = self._tiled_rect_cards.get(rect_idx)
        if card is None:
            return
        card.read_into(self.gui_layer.tiled_rects[rect_idx])
        self._mark_dirty()
        self._refresh_canvas()
        self._refresh_tiled_rects_list()

    def _on_tiled_rect_card_picked(self, rect_idx: int) -> None:
        self._selected_tiled_rect_index = rect_idx
        self._selected_object_index = -1
        self._selected_text_index = -1
        self._selected_repeat_sprite_index = -1
        self.canvas.selected_tiled_rect_index = rect_idx
        self.canvas.selected_object_index = -1
        self.canvas.selected_text_index = -1
        self.canvas.selected_repeat_sprite_index = -1
        self.canvas.update()
        self._refresh_objects_list()
        self._refresh_text_labels_list()
        self._refresh_repeat_sprites_list()
        for idx, card in self._tiled_rect_cards.items():
            card.set_highlighted(idx == self._selected_tiled_rect_index)

    def _remove_tiled_rect(self, rect_idx: int) -> None:
        if not self.gui_layer or not (0 <= rect_idx < len(self.gui_layer.tiled_rects)):
            return
        self.gui_layer.remove_tiled_rect(rect_idx)
        if self._selected_tiled_rect_index == rect_idx:
            self._selected_tiled_rect_index = -1
        elif self._selected_tiled_rect_index > rect_idx:
            self._selected_tiled_rect_index -= 1
        self._mark_dirty()
        self._refresh_tiled_rects_list()
        self._refresh_canvas()

    def _add_tiled_rect(self) -> None:
        if not self.gui_layer:
            return
        prefab = self.progress_bar_strip.selected_prefab()
        if not prefab:
            QMessageBox.information(self, "Add Tiled Rect", "Choose a progress bar prefab first.")
            return
        x = min(8, max(0, self.gui_layer.width - 1))
        y = min(8, max(0, self.gui_layer.height - 1))
        bar = self.canvas._get_progress_bar(prefab)
        width = bar.width if bar else GuiLayerCanvas.DEFAULT_TILED_RECT_WIDTH
        height = bar.height if bar else GuiLayerCanvas.DEFAULT_TILED_RECT_HEIGHT
        try:
            index = self.gui_layer.add_tiled_rect(str(prefab), x, y, width, height)
        except ValueError as exc:
            QMessageBox.warning(self, "Add Tiled Rect", str(exc))
            return
        self._mark_dirty()
        self._selected_tiled_rect_index = index
        self._selected_object_index = -1
        self._selected_text_index = -1
        self._selected_repeat_sprite_index = -1
        self._refresh_objects_list()
        self._refresh_text_labels_list()
        self._refresh_repeat_sprites_list()
        self._refresh_tiled_rects_list()
        card = self._tiled_rect_cards.get(index)
        if card is not None:
            card.set_expanded(True)
            self.tiled_rects_scroll.ensureWidgetVisible(card)
        self._refresh_canvas()

    def _refresh_repeat_sprites_list(self) -> None:
        if not self.gui_layer:
            self._rebuild_repeat_sprite_cards([])
            self._repeat_sprites_list_indices = []
            self._selected_repeat_sprite_index = -1
            return
        if self._selected_repeat_sprite_index >= len(self.gui_layer.repeat_sprites):
            self._selected_repeat_sprite_index = -1
        query = self.repeat_sprites_search.text().strip().lower()
        visible_indices: list[int] = []
        for i, rep in enumerate(self.gui_layer.repeat_sprites):
            name = Path(rep.prefab).stem if rep.prefab else rep.id
            if query and query not in name.lower() and query not in rep.id.lower():
                continue
            visible_indices.append(i)
        if visible_indices != self._repeat_sprites_list_indices:
            self._rebuild_repeat_sprite_cards(visible_indices)
            self._repeat_sprites_list_indices = visible_indices
        pip_bar_choices = self._pip_bar_choices()
        for i in visible_indices:
            rep = self.gui_layer.repeat_sprites[i]
            card = self._repeat_sprite_cards[i]
            card.sync(rep, pip_bar_choices)
            name = Path(rep.prefab).stem if rep.prefab else "(unassigned)"
            card.set_header_text(f"#{i}  {name}  {rep.number}/{rep.max_number}")
            card.toggle.setToolTip(f"{name}  @ ({rep.x}, {rep.y})")
            card.set_highlighted(i == self._selected_repeat_sprite_index)

    def _rebuild_repeat_sprite_cards(self, visible_indices: list[int]) -> None:
        for card in self._repeat_sprite_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._repeat_sprite_cards = {}
        for i in visible_indices:
            card = _GuiRepeatSpriteCard()
            card.changed.connect(lambda idx=i: self._on_repeat_sprite_card_changed(idx))
            card.remove_requested.connect(lambda idx=i: self._remove_repeat_sprite(idx))
            card.picked.connect(lambda idx=i: self._on_repeat_sprite_card_picked(idx))
            self.repeat_sprites_container_layout.insertWidget(
                self.repeat_sprites_container_layout.count() - 1, card
            )
            self._repeat_sprite_cards[i] = card

    def _on_repeat_sprite_card_changed(self, rep_idx: int) -> None:
        if not self.gui_layer or not (0 <= rep_idx < len(self.gui_layer.repeat_sprites)):
            return
        card = self._repeat_sprite_cards.get(rep_idx)
        if card is None:
            return
        card.read_into(self.gui_layer.repeat_sprites[rep_idx])
        self._mark_dirty()
        self._refresh_canvas()
        self._refresh_repeat_sprites_list()

    def _on_repeat_sprite_card_picked(self, rep_idx: int) -> None:
        self._selected_repeat_sprite_index = rep_idx
        self._selected_object_index = -1
        self._selected_text_index = -1
        self._selected_tiled_rect_index = -1
        self.canvas.selected_repeat_sprite_index = rep_idx
        self.canvas.selected_object_index = -1
        self.canvas.selected_text_index = -1
        self.canvas.selected_tiled_rect_index = -1
        self.canvas.update()
        self._refresh_objects_list()
        self._refresh_text_labels_list()
        self._refresh_tiled_rects_list()
        for idx, card in self._repeat_sprite_cards.items():
            card.set_highlighted(idx == self._selected_repeat_sprite_index)

    def _remove_repeat_sprite(self, rep_idx: int) -> None:
        if not self.gui_layer or not (0 <= rep_idx < len(self.gui_layer.repeat_sprites)):
            return
        self.gui_layer.remove_repeat_sprite(rep_idx)
        if self._selected_repeat_sprite_index == rep_idx:
            self._selected_repeat_sprite_index = -1
        elif self._selected_repeat_sprite_index > rep_idx:
            self._selected_repeat_sprite_index -= 1
        self._mark_dirty()
        self._refresh_repeat_sprites_list()
        self._refresh_canvas()

    # -- canvas refresh -----------------------------------------------------

    def _refresh_canvas(self) -> None:
        pending_font = self.text_font_combo.currentData() or ""
        pending_progress_bar_prefab = self.progress_bar_strip.selected_prefab()
        pending_pip_bar_prefab = self.pip_bar_strip.selected_prefab()
        self.canvas.set_context(
            self.gui_layer,
            self.project_root,
            self._active_tileset,
            self._palette_colors,
            target=self._target,
            tool=self.canvas.tool,
            edit_mode=self._edit_mode,
            selected_tile=self._selected_tile,
            selected_object_prefab=self.object_strip.selected_prefab(),
            pending_text=self.text_content_edit.text(),
            pending_font=str(pending_font),
            selected_object_index=self._selected_object_index,
            selected_text_index=self._selected_text_index,
            show_grid=self.show_grid.isChecked(),
            pending_progress_bar_prefab=str(pending_progress_bar_prefab),
            pending_pip_bar_prefab=str(pending_pip_bar_prefab),
            selected_tiled_rect_index=self._selected_tiled_rect_index,
            selected_repeat_sprite_index=self._selected_repeat_sprite_index,
        )

    def _refresh_editor(self) -> None:
        if not self.gui_layer:
            return
        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)
        self.width_spin.setValue(self.gui_layer.width)
        self.height_spin.setValue(self.gui_layer.height)
        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)
        self._update_size_label()
        self.tile_layer_visible.blockSignals(True)
        self.tile_layer_visible.setChecked(self.gui_layer.tile_layer_visible)
        self.tile_layer_visible.blockSignals(False)
        self.script_edit.blockSignals(True)
        self.script_edit.setText(self.gui_layer.script)
        self.script_edit.blockSignals(False)
        self._refresh_script_row()
        self._sync_tileset_combo()
        self._sync_text_font_combo()
        self._load_active_tileset()
        self._refresh_strip()
        self._refresh_object_strip()
        self._refresh_progress_bar_strip()
        self._refresh_pip_bar_strip()
        self._refresh_objects_list()
        self._refresh_text_labels_list()
        self._refresh_tiled_rects_list()
        self._refresh_repeat_sprites_list()
        self._refresh_canvas()

    # -- canvas event handlers -----------------------------------------------------

    def _on_canvas_changed(self) -> None:
        if self.canvas.tool == Tool.EYEDROPPER and self.canvas.selected_tile != self._selected_tile:
            self._selected_tile = self.canvas.selected_tile
            self.strip_canvas.set_selected_index(self._selected_tile)
        self._mark_dirty()
        self._refresh_canvas()
        self._refresh_objects_list()
        self._refresh_text_labels_list()
        self._refresh_tiled_rects_list()
        self._refresh_repeat_sprites_list()

    def _on_strip_tile_clicked(self, index: int) -> None:
        self._selected_tile = index
        self.strip_canvas.set_selected_index(index)
        self._set_target(GuiLayerTarget.TILES)
        self._set_tool(Tool.PAINT)
        self.bottom_tabs.setCurrentIndex(0)
        self._refresh_canvas()

    def _on_object_strip_clicked(self, _index: int) -> None:
        self._set_target(GuiLayerTarget.OBJECTS)
        self._set_tool(Tool.PAINT)
        self._refresh_canvas()

    def _on_progress_bar_strip_clicked(self, _index: int) -> None:
        self._set_target(GuiLayerTarget.TILED_RECT)
        self._set_tool(Tool.PAINT)
        self._refresh_canvas()

    def _on_pip_bar_strip_clicked(self, _index: int) -> None:
        self._set_target(GuiLayerTarget.REPEAT_SPRITE)
        self._set_tool(Tool.PAINT)
        self._refresh_canvas()

    def _on_tileset_changed(self, index: int) -> None:
        if not self.gui_layer:
            return
        rel = self.tileset_combo.itemData(index)
        rel_path = str(rel) if rel else ""
        if self.gui_layer.tileset == rel_path:
            return
        self.gui_layer.tileset = rel_path
        self._load_active_tileset()
        self.gui_layer.ensure_tile_grid(self._active_tile_size())
        self._mark_dirty()
        self._refresh_strip()
        self._refresh_canvas()

    def _on_tile_layer_visible_toggled(self, visible: bool) -> None:
        if not self.gui_layer:
            return
        self.gui_layer.tile_layer_visible = visible
        self._mark_dirty()
        self._refresh_canvas()

    def _on_canvas_object_selected(self, index: int) -> None:
        self._selected_object_index = index
        if index >= 0:
            self._selected_text_index = -1
            self._selected_tiled_rect_index = -1
            self._selected_repeat_sprite_index = -1
            self._refresh_text_labels_list()
            self._refresh_tiled_rects_list()
            self._refresh_repeat_sprites_list()
        self._refresh_objects_list()
        card = self._object_cards.get(index)
        if card is not None:
            card.set_expanded(True)
            self.objects_scroll.ensureWidgetVisible(card)
        self._refresh_canvas()

    def _on_canvas_text_selected(self, index: int) -> None:
        self._selected_text_index = index
        if index >= 0:
            self._selected_object_index = -1
            self._selected_tiled_rect_index = -1
            self._selected_repeat_sprite_index = -1
            self._refresh_objects_list()
            self._refresh_tiled_rects_list()
            self._refresh_repeat_sprites_list()
        self._refresh_text_labels_list()
        card = self._text_label_cards.get(index)
        if card is not None:
            card.set_expanded(True)
            self.text_labels_scroll.ensureWidgetVisible(card)
        self._refresh_canvas()

    def _on_canvas_tiled_rect_selected(self, index: int) -> None:
        self._selected_tiled_rect_index = index
        if index >= 0:
            self._selected_object_index = -1
            self._selected_text_index = -1
            self._selected_repeat_sprite_index = -1
            self._refresh_objects_list()
            self._refresh_text_labels_list()
            self._refresh_repeat_sprites_list()
        self._refresh_tiled_rects_list()
        card = self._tiled_rect_cards.get(index)
        if card is not None:
            card.set_expanded(True)
            self.tiled_rects_scroll.ensureWidgetVisible(card)
        self._refresh_canvas()

    def _on_canvas_repeat_sprite_selected(self, index: int) -> None:
        self._selected_repeat_sprite_index = index
        if index >= 0:
            self._selected_object_index = -1
            self._selected_text_index = -1
            self._selected_tiled_rect_index = -1
            self._refresh_objects_list()
            self._refresh_text_labels_list()
            self._refresh_tiled_rects_list()
        self._refresh_repeat_sprites_list()
        card = self._repeat_sprite_cards.get(index)
        if card is not None:
            card.set_expanded(True)
            self.repeat_sprites_scroll.ensureWidgetVisible(card)
        self._refresh_canvas()

    def _on_text_fields_changed(self) -> None:
        self._refresh_canvas()

    def _add_text_label(self) -> None:
        if not self.gui_layer:
            return
        text = self.text_content_edit.text().strip()
        if not text:
            QMessageBox.information(self, "Add Label", "Enter text for the new label first.")
            return
        font = self.text_font_combo.currentData() or ""
        x = min(8, max(0, self.gui_layer.width - 1))
        y = min(8, max(0, self.gui_layer.height - 1))
        try:
            index = self.gui_layer.add_text_label(text, x, y, font=str(font))
        except ValueError as exc:
            QMessageBox.warning(self, "Add Label", str(exc))
            return
        self._mark_dirty()
        self.text_content_edit.clear()
        self._selected_text_index = index
        self._selected_object_index = -1
        self._refresh_objects_list()
        self._refresh_text_labels_list()
        card = self._text_label_cards.get(index)
        if card is not None:
            card.set_expanded(True)
            self.text_labels_scroll.ensureWidgetVisible(card)
        self._refresh_canvas()

    # -- resize -----------------------------------------------------

    def _resize_gui_layer(self) -> None:
        if not self.gui_layer:
            return
        new_w = self.width_spin.value()
        new_h = self.height_spin.value()
        if new_w == self.gui_layer.width and new_h == self.gui_layer.height:
            return
        self.gui_layer.resize(new_w, new_h, self._active_tile_size())
        self._mark_dirty()
        self._refresh_editor()

    def _reset_to_screen_size(self) -> None:
        self.width_spin.setValue(SCREEN_WIDTH)
        self.height_spin.setValue(SCREEN_HEIGHT)
        self._resize_gui_layer()

    # -- file operations -----------------------------------------------------

    def new_gui_layer(self, path: Path, width: int, height: int, palette: str = "default") -> None:
        self.file_path = path.resolve()
        try:
            self.gui_layer = GuiLayer.create(width, height)
            self.gui_layer.palette = palette
        except ValueError as exc:
            QMessageBox.warning(self, "New GUI Layer", str(exc))
            self.gui_layer = None
            self.file_path = None
            return
        self._dirty = True
        self._selected_object_index = -1
        self._selected_text_index = -1
        self._selected_tiled_rect_index = -1
        self._selected_repeat_sprite_index = -1
        self._selected_tile = 0
        self.canvas.clear_caches()
        self._tilesets_cache.clear()
        self._open_gui_layer_data()

    def open_gui_layer(self, path: Path) -> None:
        self.file_path = path.resolve()
        try:
            self.gui_layer = load_gui_layer(self.file_path, project_root=self.project_root)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Open GUI Layer", str(exc))
            self.gui_layer = None
            self.file_path = None
            return
        self._dirty = False
        self._selected_object_index = -1
        self._selected_text_index = -1
        self._selected_tiled_rect_index = -1
        self._selected_repeat_sprite_index = -1
        self._selected_tile = 0
        self.canvas.clear_caches()
        self._tilesets_cache.clear()
        self._open_gui_layer_data()

    def _open_gui_layer_data(self) -> None:
        if not self.gui_layer:
            return
        try:
            self._load_palette_colors()
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "Open GUI Layer", str(exc))
            self.gui_layer = None
            self.file_path = None
            return
        self._refresh_editor()
        self._update_status()

    def save(self) -> None:
        if not self.gui_layer or not self.file_path:
            return
        self.gui_layer.script = self.script_edit.text().strip()
        save_gui_layer(self.gui_layer, self.file_path)
        self._dirty = False
        self._update_status()
        self.saved.emit(self.file_path)

    def _on_script_changed(self) -> None:
        if self.gui_layer is not None:
            self.gui_layer.script = self.script_edit.text().strip()
            self._mark_dirty()

    def _refresh_script_row(self) -> None:
        has_script = bool(self.script_edit.text().strip())
        self._script_empty_row.setVisible(not has_script)
        self._script_edit_row.setVisible(has_script)

    def _create_script(self) -> None:
        if not self.file_path:
            return
        scripts_dir = self.project_root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_path = scripts_dir / f"{self.file_path.stem}.py"
        if script_path.exists():
            reply = QMessageBox.question(
                self,
                "Create Script",
                f"Script already exists:\n{script_path}\n\nLink and open it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        else:
            stem = self.file_path.stem
            template = (
                f'"""Script for GUI layer {stem}."""\n\n\n'
                "def init(engine):\n    pass\n\n\n"
                "def update(dt):\n    pass\n\n\n"
                "def draw(engine):\n    pass\n"
            )
            script_path.write_text(template, encoding="utf-8")
        rel = script_path.resolve().relative_to(self.project_root.resolve()).as_posix()
        self.script_edit.setText(rel)
        self._open_script_in_editor()

    def _browse_script(self) -> None:
        scripts_dir = self.project_root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Script",
            str(scripts_dir),
            "Python Scripts (*.py)",
        )
        if not path:
            return
        rel = Path(path).resolve().relative_to(self.project_root.resolve()).as_posix()
        self.script_edit.setText(rel)

    def _open_script_in_editor(self) -> None:
        script = self.script_edit.text().strip()
        if not script:
            QMessageBox.information(self, "Open Script", "Set a script path first.")
            return
        path = (self.project_root / script).resolve()
        if not path.is_file():
            QMessageBox.warning(self, "Open Script", f"Script not found: {path}")
            return
        try:
            project = load_project(self.project_root)
            cmd = project.editor_command.format(file=path, line=1)
            subprocess.Popen(cmd, shell=True)
        except OSError as exc:
            QMessageBox.warning(self, "Open Script", str(exc))

    def _rename_gui_layer(self) -> None:
        if not self.gui_layer or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename GUI Layer", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename GUI Layer",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortuguilayer"
        if new_path.exists():
            QMessageBox.warning(self, "Rename GUI Layer", f"{new_path.name} already exists.")
            return
        old_path.rename(new_path)
        self.file_path = new_path
        self._update_status()
        self.renamed.emit(old_path, new_path)

    def has_unsaved_changes(self) -> bool:
        return self._dirty
