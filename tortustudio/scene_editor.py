"""Scene editor — paint tile layers on a map using a linked tileset."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tortuengine.palette import TRANSPARENT_INDEX, load_palette, palette_path
from tortuengine.scene import (
    EMPTY_TILE,
    MAX_SCENE_LAYERS,
    MIN_SCENE_LAYERS,
    Scene,
    load_scene,
    save_scene,
)
from tortuengine.tileset import Tileset, load_tileset
from tortustudio.tileset_editor import TilesetStripCanvas


class Tool(str, Enum):
    PAINT = "paint"
    ERASE = "erase"
    EYEDROPPER = "eyedropper"


class SceneMapCanvas(QWidget):
    """Scrollable tile map — composites visible layers, edits the active one."""

    TILE_GRID_COLOR = (48, 48, 64)
    MAP_BG = (30, 30, 40)

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scene: Scene | None = None
        self.tileset: Tileset | None = None
        self.palette: list[tuple[int, int, int]] = []
        self.active_layer = 0
        self.selected_tile = 0
        self.tool = Tool.PAINT
        self.show_grid = True
        self.zoom = 2
        self._drawing = False
        self._frame: QImage | None = None
        self.setMinimumSize(200, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_context(
        self,
        scene: Scene | None,
        tileset: Tileset | None,
        palette: list[tuple[int, int, int]],
        active_layer: int,
        selected_tile: int,
    ) -> None:
        self.scene = scene
        self.tileset = tileset
        self.palette = palette
        self.active_layer = active_layer
        self.selected_tile = selected_tile
        self._refresh()

    def set_tool(self, tool: Tool) -> None:
        self.tool = tool

    def set_show_grid(self, visible: bool) -> None:
        self.show_grid = visible
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(1, min(16, zoom))
        if self.scene and self.tileset:
            tw = self.scene.width_tiles * self.tileset.tile_size * self.zoom
            th = self.scene.height_tiles * self.tileset.tile_size * self.zoom
            self.setMinimumSize(tw, th)
        self.update()

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

    def _refresh(self) -> None:
        if not self.scene or not self.tileset:
            self._frame = None
            self.update()
            return

        tile_size = self.tileset.tile_size
        map_w = self.scene.width_tiles * tile_size
        map_h = self.scene.height_tiles * tile_size
        composite = pygame.Surface((map_w, map_h))
        composite.fill(self.MAP_BG)

        for layer_index, layer in enumerate(self.scene.layers):
            if not layer.visible:
                continue
            for ty in range(self.scene.height_tiles):
                for tx in range(self.scene.width_tiles):
                    tile_index = layer.tiles[ty * self.scene.width_tiles + tx]
                    if tile_index == EMPTY_TILE:
                        continue
                    tile_surface = self._tile_surface(tile_index)
                    if tile_surface is None:
                        continue
                    composite.blit(tile_surface, (tx * tile_size, ty * tile_size))

        data = pygame.image.tobytes(composite, "RGBA")
        self._frame = QImage(data, map_w, map_h, map_w * 4, QImage.Format.Format_RGBA8888)
        self.setMinimumSize(map_w * self.zoom, map_h * self.zoom)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None or not self.scene or not self.tileset:
            painter.end()
            return

        tile_size = self.tileset.tile_size
        sw = self.scene.width_tiles * tile_size * self.zoom
        sh = self.scene.height_tiles * tile_size * self.zoom
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)

        scaled = self._frame.scaled(
            sw,
            sh,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        painter.drawImage(ox, oy, scaled)

        if self.show_grid:
            pen = QPen(QColor(*self.TILE_GRID_COLOR))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for tx in range(1, self.scene.width_tiles):
                lx = ox + tx * tile_size * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for ty in range(1, self.scene.height_tiles):
                ly = oy + ty * tile_size * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)

        if self.scene.collision_layer == self.active_layer:
            pen = QPen(QColor(255, 220, 80, 180))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(ox, oy, sw, sh)

        painter.end()

    def _event_to_tile(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None or not self.scene or not self.tileset:
            return None
        tile_size = self.tileset.tile_size
        sw = self.scene.width_tiles * tile_size * self.zoom
        sh = self.scene.height_tiles * tile_size * self.zoom
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)
        tx = int((event.position().x() - ox) // (tile_size * self.zoom))
        ty = int((event.position().y() - oy) // (tile_size * self.zoom))
        if 0 <= tx < self.scene.width_tiles and 0 <= ty < self.scene.height_tiles:
            return tx, ty
        return None

    def _apply_tool(self, x: int, y: int) -> None:
        if not self.scene:
            return
        if self.tool == Tool.PAINT:
            self.scene.set_tile(self.active_layer, x, y, self.selected_tile)
        elif self.tool == Tool.ERASE:
            self.scene.set_tile(self.active_layer, x, y, EMPTY_TILE)
        elif self.tool == Tool.EYEDROPPER:
            picked = self.scene.get_tile(self.active_layer, x, y)
            if picked != EMPTY_TILE:
                self.selected_tile = picked
                self.changed.emit()
        self._refresh()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_to_tile(event)
            if pos:
                self._drawing = True
                self._apply_tool(*pos)
                self.changed.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drawing and event.buttons() & Qt.MouseButton.LeftButton:
            pos = self._event_to_tile(event)
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
            self.set_zoom(self.zoom + 1)
        elif delta < 0:
            self.set_zoom(self.zoom - 1)


class SceneEditorWidget(QWidget):
    saved = pyqtSignal(Path)
    new_scene_requested = pyqtSignal()
    open_scene_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.scene: Scene | None = None
        self.tileset: Tileset | None = None
        self._palette_colors: list[tuple[int, int, int]] = []
        self._dirty = False
        self._selected_tile = 0

        self.map_canvas = SceneMapCanvas()
        self.map_canvas.changed.connect(self._on_map_changed)

        self.strip_canvas = TilesetStripCanvas()
        self.strip_canvas.tile_clicked.connect(self._on_strip_tile_clicked)

        self.btn_save = QPushButton("Save scene")
        self.btn_save.clicked.connect(self.save)
        self.btn_new = QPushButton("New Scene…")
        self.btn_new.clicked.connect(self.new_scene_requested.emit)
        self.btn_open = QPushButton("Open Scene…")
        self.btn_open.clicked.connect(self.open_scene_requested.emit)

        self.status_label = QLabel("No scene open")
        self.tileset_label = QLabel("—")

        self.layer_combo = QComboBox()
        self.layer_combo.currentIndexChanged.connect(self._on_layer_changed)

        self.layer_visible = QCheckBox("Layer visible")
        self.layer_visible.setChecked(True)
        self.layer_visible.toggled.connect(self._on_layer_visible_toggled)

        self.collision_layer_combo = QComboBox()
        self.collision_layer_combo.currentIndexChanged.connect(self._on_collision_layer_changed)

        self.btn_add_layer = QPushButton("Add layer")
        self.btn_add_layer.clicked.connect(self._add_layer)
        self.btn_remove_layer = QPushButton("Remove layer")
        self.btn_remove_layer.clicked.connect(self._remove_layer)

        self.map_width = QSpinBox()
        self.map_width.setRange(1, 256)
        self.map_height = QSpinBox()
        self.map_height.setRange(1, 256)
        self.btn_resize_map = QPushButton("Resize map")
        self.btn_resize_map.clicked.connect(self._resize_map)

        self.show_grid = QCheckBox("Tile grid")
        self.show_grid.setChecked(True)
        self.show_grid.toggled.connect(self.map_canvas.set_show_grid)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 16)
        self.zoom_spin.setValue(2)
        self.zoom_spin.valueChanged.connect(self.map_canvas.set_zoom)

        self.btn_paint = QPushButton("Paint")
        self.btn_erase = QPushButton("Erase")
        self.btn_dropper = QPushButton("Eyedropper")
        for btn in (self.btn_paint, self.btn_erase, self.btn_dropper):
            btn.setCheckable(True)
        self.btn_paint.setChecked(True)
        self.btn_paint.clicked.connect(lambda: self._set_tool(Tool.PAINT))
        self.btn_erase.clicked.connect(lambda: self._set_tool(Tool.ERASE))
        self.btn_dropper.clicked.connect(lambda: self._set_tool(Tool.EYEDROPPER))

        self._build_layout()

    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        file_row = QHBoxLayout()
        file_row.addWidget(self.btn_new)
        file_row.addWidget(self.btn_open)
        file_row.addWidget(self.btn_save)
        file_row.addWidget(self.status_label)
        file_row.addStretch()
        outer.addLayout(file_row)

        body = QHBoxLayout()
        outer.addLayout(body, stretch=1)

        map_group = QGroupBox("Map")
        map_layout = QVBoxLayout(map_group)
        map_scroll = QScrollArea()
        map_scroll.setWidgetResizable(True)
        map_scroll.setWidget(self.map_canvas)
        map_layout.addWidget(map_scroll)
        body.addWidget(map_group, stretch=1)

        side = QVBoxLayout()
        form = QFormLayout()
        form.addRow("Tileset:", self.tileset_label)
        form.addRow("Active layer:", self.layer_combo)
        form.addRow("", self.layer_visible)
        form.addRow("Collision layer:", self.collision_layer_combo)
        layer_btns = QHBoxLayout()
        layer_btns.addWidget(self.btn_add_layer)
        layer_btns.addWidget(self.btn_remove_layer)
        form.addRow(layer_btns)
        form.addRow("Map width:", self.map_width)
        form.addRow("Map height:", self.map_height)
        form.addRow(self.btn_resize_map)
        form.addRow("Zoom:", self.zoom_spin)
        form.addRow(self.show_grid)
        side.addLayout(form)

        tools = QHBoxLayout()
        tools.addWidget(self.btn_paint)
        tools.addWidget(self.btn_erase)
        tools.addWidget(self.btn_dropper)
        side.addLayout(tools)
        side.addStretch()
        body.addLayout(side)

        strip_group = QGroupBox("Tileset")
        strip_layout = QVBoxLayout(strip_group)
        strip_scroll = QScrollArea()
        strip_scroll.setWidgetResizable(True)
        strip_scroll.setMaximumHeight(140)
        strip_scroll.setWidget(self.strip_canvas)
        strip_layout.addWidget(strip_scroll)
        outer.addWidget(strip_group)

    def _set_tool(self, tool: Tool) -> None:
        self.btn_paint.setChecked(tool == Tool.PAINT)
        self.btn_erase.setChecked(tool == Tool.ERASE)
        self.btn_dropper.setChecked(tool == Tool.EYEDROPPER)
        self.map_canvas.set_tool(tool)

    def _on_map_changed(self) -> None:
        if self.map_canvas.tool == Tool.EYEDROPPER and self.map_canvas.selected_tile != self._selected_tile:
            self._selected_tile = self.map_canvas.selected_tile
            self.strip_canvas.set_selected_index(self._selected_tile)
        self._mark_dirty()
        self._refresh_map()

    def _on_strip_tile_clicked(self, index: int) -> None:
        self._selected_tile = index
        self._refresh_map()

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._update_status()

    def _update_status(self) -> None:
        if not self.scene or not self.file_path:
            self.status_label.setText("No scene open")
            return
        state = "edited" if self._dirty else "saved"
        self.status_label.setText(f"{self.file_path.name} ({state})")

    def _relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_root.resolve()).as_posix()

    def _load_tileset_for_scene(self) -> None:
        if not self.scene:
            self.tileset = None
            return
        tileset_path = self.scene.tileset_path(self.project_root)
        if not tileset_path.is_file():
            raise FileNotFoundError(f"Tileset not found: {tileset_path}")
        self.tileset = load_tileset(tileset_path)
        self.tileset_label.setText(self.scene.tileset)

    def _load_palette_for_scene(self) -> None:
        if not self.scene:
            return
        path = palette_path(self.project_root, self.scene.palette)
        if not path.is_file():
            raise FileNotFoundError(f"Palette not found: {path}")
        self._palette_colors = load_palette(path)

    def _sync_layer_controls(self) -> None:
        if not self.scene:
            return
        self.layer_combo.blockSignals(True)
        self.collision_layer_combo.blockSignals(True)
        self.layer_combo.clear()
        self.collision_layer_combo.clear()
        for i, layer in enumerate(self.scene.layers):
            label = f"{i}: {layer.name}"
            self.layer_combo.addItem(label, i)
            self.collision_layer_combo.addItem(label, i)
        active = min(self.map_canvas.active_layer, max(0, self.scene.layer_count - 1))
        self.layer_combo.setCurrentIndex(active)
        self.collision_layer_combo.setCurrentIndex(self.scene.collision_layer)
        self.layer_visible.setChecked(self.scene.layers[active].visible)
        self.layer_combo.blockSignals(False)
        self.collision_layer_combo.blockSignals(False)
        self.btn_remove_layer.setEnabled(self.scene.layer_count > MIN_SCENE_LAYERS)
        self.btn_add_layer.setEnabled(self.scene.layer_count < MAX_SCENE_LAYERS)

    def _refresh_map(self) -> None:
        if not self.scene:
            self.map_canvas.set_context(None, None, [], 0, 0)
            return
        active = self.layer_combo.currentIndex() if self.layer_combo.count() else 0
        self.map_canvas.set_context(
            self.scene,
            self.tileset,
            self._palette_colors,
            active,
            self._selected_tile,
        )

    def _refresh_strip(self) -> None:
        if self.tileset:
            self.strip_canvas.set_tileset(self.tileset, self._palette_colors)
            self.strip_canvas.set_selected_index(self._selected_tile)
        else:
            self.strip_canvas.set_tileset(None, [])

    def _refresh_editor(self) -> None:
        if not self.scene:
            return
        self.map_width.blockSignals(True)
        self.map_height.blockSignals(True)
        self.map_width.setValue(self.scene.width_tiles)
        self.map_height.setValue(self.scene.height_tiles)
        self.map_width.blockSignals(False)
        self.map_height.blockSignals(False)
        self._sync_layer_controls()
        self._refresh_map()
        self._refresh_strip()

    def _on_layer_changed(self, index: int) -> None:
        if not self.scene or index < 0:
            return
        self.layer_visible.blockSignals(True)
        self.layer_visible.setChecked(self.scene.layers[index].visible)
        self.layer_visible.blockSignals(False)
        self._refresh_map()

    def _on_layer_visible_toggled(self, visible: bool) -> None:
        if not self.scene:
            return
        index = self.layer_combo.currentIndex()
        if 0 <= index < self.scene.layer_count:
            self.scene.layers[index].visible = visible
            self._mark_dirty()
            self._refresh_map()

    def _on_collision_layer_changed(self, index: int) -> None:
        if not self.scene or index < 0:
            return
        self.scene.set_collision_layer(index)
        self._mark_dirty()
        self._refresh_map()

    def _add_layer(self) -> None:
        if not self.scene:
            return
        try:
            index = self.scene.add_layer()
        except ValueError as exc:
            QMessageBox.warning(self, "Add Layer", str(exc))
            return
        self._mark_dirty()
        self._sync_layer_controls()
        self.layer_combo.setCurrentIndex(index)
        self._refresh_map()

    def _remove_layer(self) -> None:
        if not self.scene:
            return
        index = self.layer_combo.currentIndex()
        try:
            self.scene.remove_layer(index)
        except ValueError as exc:
            QMessageBox.warning(self, "Remove Layer", str(exc))
            return
        self._mark_dirty()
        self._sync_layer_controls()
        self._refresh_map()

    def _resize_map(self) -> None:
        if not self.scene:
            return
        new_w = self.map_width.value()
        new_h = self.map_height.value()
        if new_w == self.scene.width_tiles and new_h == self.scene.height_tiles:
            return
        if any(any(v != EMPTY_TILE for v in layer.tiles) for layer in self.scene.layers):
            reply = QMessageBox.question(
                self,
                "Resize Map",
                "Resample all layers to the new map size?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.map_width.setValue(self.scene.width_tiles)
                self.map_height.setValue(self.scene.height_tiles)
                return
        self.scene.resize(new_w, new_h)
        self._mark_dirty()
        self._refresh_editor()

    def new_scene(
        self,
        path: Path,
        palette: str,
        tileset: str,
        width_tiles: int,
        height_tiles: int,
        *,
        layer_count: int = MIN_SCENE_LAYERS,
        collision_layer: int = 0,
    ) -> None:
        self.file_path = path.resolve()
        self.scene = Scene.create(
            palette,
            tileset,
            width_tiles,
            height_tiles,
            layer_count=layer_count,
            collision_layer=collision_layer,
        )
        self._dirty = True
        self._selected_tile = 0
        self._open_scene_data()

    def open_scene(self, path: Path) -> None:
        self.file_path = path.resolve()
        self.scene = load_scene(self.file_path)
        self._dirty = False
        self._selected_tile = 0
        self._open_scene_data()

    def _open_scene_data(self) -> None:
        try:
            self._load_tileset_for_scene()
            self._load_palette_for_scene()
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "Open Scene", str(exc))
            self.scene = None
            self.file_path = None
            return
        self._refresh_editor()
        self._update_status()

    def save(self) -> None:
        if not self.scene or not self.file_path:
            return
        save_scene(self.scene, self.file_path)
        self._dirty = False
        self._update_status()
        self.saved.emit(self.file_path)

    def has_unsaved_changes(self) -> bool:
        return self._dirty
