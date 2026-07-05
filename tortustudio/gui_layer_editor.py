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
    QVBoxLayout,
    QWidget,
)

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_BLOCK
from tortuengine.gui_layer import (
    DEFAULT_GUI_LAYER_HEIGHT,
    DEFAULT_GUI_LAYER_WIDTH,
    EMPTY_TILE,
    GuiLayer,
    GuiObject,
    GuiTextLabel,
    load_gui_layer,
    save_gui_layer,
)
from tortuengine.object import TortuObject, load_object
from tortuengine.palette import TRANSPARENT_INDEX, load_palette, palette_path
from tortuengine.project import load_project
from tortuengine.sprite import Sprite, load_sprite
from tortuengine.sprite_font import TortuSpriteFont, load_sprite_font, render_sprite_text_line
from tortuengine.text_font import TortuFont, load_tortu_font, render_text_line
from tortuengine.tileset import Tileset, load_tileset
from tortustudio.collapsible import CollapsibleSection
from tortustudio.object_strip import ObjectStripCanvas
from tortustudio.scene_assets import (
    list_object_paths,
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


class GuiLayerCanvas(QWidget):
    """Editable GUI layer canvas — paints the tile layer, places objects and text labels."""

    TILE_GRID_COLOR = (48, 48, 64)
    CANVAS_BG = (30, 30, 40)
    SELECTION_COLOR = (255, 220, 0)

    changed = pyqtSignal()
    object_selected = pyqtSignal(int)
    text_label_selected = pyqtSignal(int)
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

        self.target = GuiLayerTarget.TILES
        self.tool = Tool.PAINT
        self.edit_mode = False
        self.selected_tile = 0
        self.selected_object_prefab = ""
        self.pending_text = ""
        self.pending_font = ""
        self.selected_object_index = -1
        self.selected_text_index = -1
        self._dragging_object_index = -1
        self._dragging_text_index = -1

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
        self.selected_object_index = selected_object_index
        self.selected_text_index = selected_text_index
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
        return sprite.to_surface(palette, frame_index=0)

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
            composite.blit(surface, (inst.x - tortu_object.origin.x, inst.y - tortu_object.origin.y))

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

        if self.target == GuiLayerTarget.OBJECTS and self.selected_object_index >= 0:
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
                    rx = (inst.x - tortu_object.origin.x) * self.zoom
                    ry = (inst.y - tortu_object.origin.y) * self.zoom
                    painter.drawRect(
                        int(rx), int(ry), int(sprite.pixel_width * self.zoom),
                        int(sprite.pixel_height * self.zoom),
                    )
                else:
                    lx, ly = inst.x * self.zoom, inst.y * self.zoom
                    painter.drawLine(int(lx - 8), int(ly), int(lx + 8), int(ly))
                    painter.drawLine(int(lx), int(ly - 8), int(lx), int(ly + 8))

        if self.target == GuiLayerTarget.TEXT and self.selected_text_index >= 0:
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
            x0 = inst.x - tortu_object.origin.x
            y0 = inst.y - tortu_object.origin.y
            x1, y1 = x0 + sprite.pixel_width, y0 + sprite.pixel_height
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

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            if not self.edit_mode:
                cycle = [Tool.PAINT, Tool.ERASE, Tool.EYEDROPPER]
                next_tool = cycle[(cycle.index(self.tool) + 1) % len(cycle)]
                self.tool_cycled.emit(next_tool)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.target == GuiLayerTarget.TILES:
            pos = self._event_to_tile(event)
            if pos:
                self._drawing = True
                self._apply_tile_tool(*pos)
                self.changed.emit()
            return

        if self.edit_mode:
            pos = self._event_to_pixel(event)
            if not pos:
                return
            if self.target == GuiLayerTarget.OBJECTS:
                index = self._find_object_at_pixel(*pos)
                self._dragging_object_index = index if index is not None else -1
                self.object_selected.emit(self._dragging_object_index)
            else:
                index = self._find_text_at_pixel(*pos)
                self._dragging_text_index = index if index is not None else -1
                self.text_label_selected.emit(self._dragging_text_index)
            return

        pos = self._event_to_pixel(event)
        if pos:
            self._drawing = True
            if self.target == GuiLayerTarget.OBJECTS:
                self._apply_object_tool(*pos)
            else:
                self._apply_text_tool(*pos)
            self.changed.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.edit_mode:
            if event.buttons() & Qt.MouseButton.LeftButton and self.gui_layer:
                pos = self._event_to_pixel(event)
                if not pos:
                    return
                if self.target == GuiLayerTarget.OBJECTS and 0 <= self._dragging_object_index < len(self.gui_layer.objects):
                    inst = self.gui_layer.objects[self._dragging_object_index]
                    inst.x, inst.y = pos
                    self._refresh()
                    self.changed.emit()
                elif self.target == GuiLayerTarget.TEXT and 0 <= self._dragging_text_index < len(self.gui_layer.text_labels):
                    label = self.gui_layer.text_labels[self._dragging_text_index]
                    label.x, label.y = pos
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
                    else:
                        self._apply_text_tool(*pos)
                    self.changed.emit()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.edit_mode:
            self._dragging_object_index = -1
            self._dragging_text_index = -1
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

        self.strip_canvas = TilesetStripCanvas()
        self.strip_canvas.tile_clicked.connect(self._on_strip_tile_clicked)

        self.object_strip = ObjectStripCanvas()
        self.object_strip.object_clicked.connect(self._on_object_strip_clicked)

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
        for btn in (self.btn_target_tiles, self.btn_target_objects, self.btn_target_text):
            btn.setCheckable(True)
        self.btn_target_tiles.setChecked(True)
        self.btn_target_tiles.clicked.connect(lambda: self._set_target(GuiLayerTarget.TILES))
        self.btn_target_objects.clicked.connect(lambda: self._set_target(GuiLayerTarget.OBJECTS))
        self.btn_target_text.clicked.connect(lambda: self._set_target(GuiLayerTarget.TEXT))

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
        self.objects_list = QListWidget()
        self.objects_list.setMaximumHeight(120)
        self.objects_list.currentRowChanged.connect(self._on_objects_list_selection_changed)
        self.btn_remove_selected_object = QPushButton("Remove selected object")
        self.btn_remove_selected_object.setEnabled(False)
        self.btn_remove_selected_object.clicked.connect(self._remove_selected_object)

        # -- text labels panel ---------------------------------------
        self.text_content_edit = QLineEdit()
        self.text_content_edit.setPlaceholderText("Text to place / edit selected label…")
        self.text_content_edit.textChanged.connect(self._on_text_fields_changed)

        self.text_font_combo = QComboBox()
        self.text_font_combo.currentIndexChanged.connect(self._on_text_fields_changed)

        self.text_labels_list = QListWidget()
        self.text_labels_list.setMaximumHeight(120)
        self.text_labels_list.currentRowChanged.connect(self._on_text_labels_list_selection_changed)
        self.btn_remove_selected_text = QPushButton("Remove selected label")
        self.btn_remove_selected_text.setEnabled(False)
        self.btn_remove_selected_text.clicked.connect(self._remove_selected_text_label)

        self._selected_object_index = -1
        self._selected_text_index = -1
        self._target = GuiLayerTarget.TILES
        self._edit_mode = False
        self._selected_tile = 0

        self._build_layout()

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

        canvas_group = QGroupBox("GUI Layer")
        canvas_layout = QVBoxLayout(canvas_group)
        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(False)
        canvas_scroll.setWidget(self.canvas)
        canvas_layout.addWidget(canvas_scroll)
        body.addWidget(canvas_group, stretch=1)

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
        objects_section.content_layout().addWidget(self.objects_list)
        objects_section.content_layout().addWidget(self.btn_remove_selected_object)
        side.addWidget(objects_section)

        text_section = CollapsibleSection("Text Labels", expanded=True)
        text_form = QFormLayout()
        text_form.addRow("Text:", self.text_content_edit)
        text_form.addRow("Font:", self.text_font_combo)
        text_section.content_layout().addLayout(text_form)
        text_section.content_layout().addWidget(self.text_labels_list)
        text_section.content_layout().addWidget(self.btn_remove_selected_text)
        side.addWidget(text_section)

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
        outer.addWidget(self.bottom_tabs)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self.btn_target_tiles)
        mode_row.addWidget(self.btn_target_objects)
        mode_row.addWidget(self.btn_target_text)
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
        self.btn_dropper.setEnabled(target == GuiLayerTarget.TILES)
        if target != GuiLayerTarget.TILES and self.canvas.tool == Tool.EYEDROPPER:
            self._set_tool(Tool.PAINT)
        self._refresh_canvas()

    def _set_editor_mode(self, edit: bool) -> None:
        self._edit_mode = edit
        self.btn_draw_mode.setChecked(not edit)
        self.btn_edit_mode.setChecked(edit)
        self._refresh_canvas()

    def _set_tool(self, tool: Tool) -> None:
        self.btn_paint.setChecked(tool == Tool.PAINT)
        self.btn_erase.setChecked(tool == Tool.ERASE)
        self.btn_dropper.setChecked(tool == Tool.EYEDROPPER)
        self.canvas.set_tool(tool)
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

    def _refresh_objects_list(self) -> None:
        self.objects_list.blockSignals(True)
        self.objects_list.clear()
        if self.gui_layer:
            for i, inst in enumerate(self.gui_layer.objects):
                name = Path(inst.prefab).stem if inst.prefab else "(unassigned)"
                self.objects_list.addItem(f"{i}: {name} @ ({inst.x}, {inst.y})")
        if 0 <= self._selected_object_index < self.objects_list.count():
            self.objects_list.setCurrentRow(self._selected_object_index)
        self.objects_list.blockSignals(False)
        self.btn_remove_selected_object.setEnabled(self._selected_object_index >= 0)

    def _refresh_text_labels_list(self) -> None:
        self.text_labels_list.blockSignals(True)
        self.text_labels_list.clear()
        if self.gui_layer:
            for i, label in enumerate(self.gui_layer.text_labels):
                preview = label.text if len(label.text) <= 20 else label.text[:20] + "…"
                self.text_labels_list.addItem(f'{i}: "{preview}" @ ({label.x}, {label.y})')
        if 0 <= self._selected_text_index < self.text_labels_list.count():
            self.text_labels_list.setCurrentRow(self._selected_text_index)
        self.text_labels_list.blockSignals(False)
        self.btn_remove_selected_text.setEnabled(self._selected_text_index >= 0)

    # -- canvas refresh -----------------------------------------------------

    def _refresh_canvas(self) -> None:
        pending_font = self.text_font_combo.currentData() or ""
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
        self._refresh_objects_list()
        self._refresh_text_labels_list()
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
        self._refresh_objects_list()
        self._refresh_canvas()

    def _on_objects_list_selection_changed(self, row: int) -> None:
        self._selected_object_index = row
        self.btn_remove_selected_object.setEnabled(row >= 0)
        self._refresh_canvas()

    def _remove_selected_object(self) -> None:
        if not self.gui_layer or self._selected_object_index < 0:
            return
        try:
            self.gui_layer.remove_object(self._selected_object_index)
        except IndexError:
            return
        self._selected_object_index = -1
        self._mark_dirty()
        self._refresh_objects_list()
        self._refresh_canvas()

    def _on_canvas_text_selected(self, index: int) -> None:
        self._selected_text_index = index
        if self.gui_layer and 0 <= index < len(self.gui_layer.text_labels):
            label = self.gui_layer.text_labels[index]
            self.text_content_edit.blockSignals(True)
            self.text_content_edit.setText(label.text)
            self.text_content_edit.blockSignals(False)
            font_index = self.text_font_combo.findData(label.font)
            self.text_font_combo.blockSignals(True)
            self.text_font_combo.setCurrentIndex(font_index if font_index >= 0 else 0)
            self.text_font_combo.blockSignals(False)
        self._refresh_text_labels_list()
        self._refresh_canvas()

    def _on_text_labels_list_selection_changed(self, row: int) -> None:
        self._on_canvas_text_selected(row)
        self.btn_remove_selected_text.setEnabled(row >= 0)

    def _on_text_fields_changed(self) -> None:
        if self.gui_layer and self._edit_mode and 0 <= self._selected_text_index < len(self.gui_layer.text_labels):
            label = self.gui_layer.text_labels[self._selected_text_index]
            label.text = self.text_content_edit.text()
            font = self.text_font_combo.currentData()
            label.font = str(font) if font else ""
            self._mark_dirty()
            self._refresh_text_labels_list()
        self._refresh_canvas()

    def _remove_selected_text_label(self) -> None:
        if not self.gui_layer or self._selected_text_index < 0:
            return
        try:
            self.gui_layer.remove_text_label(self._selected_text_index)
        except IndexError:
            return
        self._selected_text_index = -1
        self._mark_dirty()
        self._refresh_text_labels_list()
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
