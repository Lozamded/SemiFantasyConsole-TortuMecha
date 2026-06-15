"""Scene editor — paint tile layers on a map using a linked tileset."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tortuengine.background import Background, load_background
from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_BLOCK
from tortuengine.palette import TRANSPARENT_INDEX, load_palette, palette_path
from tortuengine.object import TortuObject, load_object
from tortuengine.scene import (
    DEFAULT_SCENE_HEIGHT,
    DEFAULT_SCENE_WIDTH,
    EMPTY_TILE,
    MAX_PARALLAX_BANDS,
    MAX_SCENE_BG_LAYERS,
    MAX_SCENE_OBJECTS,
    MAX_SCENE_TILE_LAYERS,
    MIN_SCENE_TILE_LAYERS,
    Scene,
    SceneBgParallaxBand,
    SceneObject,
    default_parallax_band,
    load_scene,
    save_scene,
    tile_size_for_tile_layer,
)
from tortuengine.sprite import Sprite, load_sprite
from tortuengine.tileset import Tileset, load_tileset
from tortustudio.object_strip import ObjectStripCanvas
from tortustudio.scene_assets import list_background_paths, list_object_paths, list_tileset_paths
from tortustudio.tileset_editor import TilesetStripCanvas


class Tool(str, Enum):
    PAINT = "paint"
    ERASE = "erase"
    EYEDROPPER = "eyedropper"


class SceneMapCanvas(QWidget):
    """Scrollable tile map — composites visible tile layers, edits the active one."""

    TILE_GRID_COLOR = (48, 48, 64)
    MAP_BG = (30, 30, 40)
    BAND_GUIDE_COLORS = (
        (80, 180, 255),
        (255, 170, 80),
        (140, 220, 120),
        (220, 140, 255),
        (255, 220, 90),
        (120, 200, 200),
        (255, 120, 160),
        (180, 180, 255),
    )

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scene: Scene | None = None
        self.project_root: Path | None = None
        self.tilesets: dict[str, Tileset] = {}
        self.backgrounds: dict[str, Background] = {}
        self.bg_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self.tortu_objects: dict[str, TortuObject] = {}
        self.object_sprites: dict[str, Sprite] = {}
        self.object_sprite_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self.active_tileset: Tileset | None = None
        self.palette: list[tuple[int, int, int]] = []
        self.active_tile_layer = 0
        self.camera_x = 0
        self.show_backgrounds = True
        self.show_band_guides = False
        self.parallax_bands: list[SceneBgParallaxBand] = []
        self.active_band_index = -1
        self.selected_tile = 0
        self.selected_object_prefab = ""
        self.edit_objects = False
        self.show_objects = True
        self.tool = Tool.PAINT
        self.show_grid = True
        self.zoom = 2
        self._drawing = False
        self._frame: QImage | None = None
        self.resize(200, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_context(
        self,
        scene: Scene | None,
        project_root: Path | None,
        tilesets: dict[str, Tileset],
        backgrounds: dict[str, Background],
        bg_palettes: dict[str, list[tuple[int, int, int]]],
        active_tileset: Tileset | None,
        palette: list[tuple[int, int, int]],
        active_tile_layer: int,
        selected_tile: int,
        *,
        camera_x: int = 0,
        show_backgrounds: bool = True,
        show_band_guides: bool = False,
        parallax_bands: list[SceneBgParallaxBand] | None = None,
        active_band_index: int = -1,
        edit_objects: bool = False,
        selected_object_prefab: str = "",
        show_objects: bool = True,
    ) -> None:
        self.scene = scene
        self.project_root = project_root
        self.tilesets = tilesets
        self.backgrounds = backgrounds
        self.bg_palettes = bg_palettes
        self.active_tileset = active_tileset
        self.palette = palette
        self.active_tile_layer = active_tile_layer
        self.selected_tile = selected_tile
        self.camera_x = camera_x
        self.show_backgrounds = show_backgrounds
        self.show_band_guides = show_band_guides
        self.parallax_bands = list(parallax_bands or [])
        self.active_band_index = active_band_index
        self.edit_objects = edit_objects
        self.selected_object_prefab = selected_object_prefab
        self.show_objects = show_objects
        self._refresh()

    def set_tool(self, tool: Tool) -> None:
        self.tool = tool

    def set_show_band_guides(self, visible: bool) -> None:
        self.show_band_guides = visible
        self.update()

    def _band_overlap_regions(
        self, bands: list[SceneBgParallaxBand]
    ) -> list[tuple[int, int]]:
        regions: list[tuple[int, int]] = []
        for i, left in enumerate(bands):
            for right in bands[i + 1 :]:
                y0 = max(left.y0, right.y0)
                y1 = min(left.y1, right.y1)
                if y0 <= y1:
                    regions.append((y0, y1))
        return regions

    def _paint_band_guides(
        self,
        painter: QPainter,
        ox: int,
        oy: int,
        sw: int,
        sh: int,
    ) -> None:
        if not self.show_band_guides or not self.parallax_bands or not self.scene:
            return

        map_h = self.scene.height
        z = self.zoom

        for y0, y1 in self._band_overlap_regions(self.parallax_bands):
            top = max(0, y0)
            bottom = min(map_h, y1 + 1)
            if top >= bottom:
                continue
            painter.fillRect(
                ox,
                oy + top * z,
                sw,
                (bottom - top) * z,
                QColor(255, 70, 70, 70),
            )

        font = QFont()
        font.setPixelSize(max(10, min(16, 8 + z)))
        painter.setFont(font)

        for i, band in enumerate(self.parallax_bands):
            active = i == self.active_band_index
            rgb = self.BAND_GUIDE_COLORS[i % len(self.BAND_GUIDE_COLORS)]
            alpha = 255 if active else 190
            pen = QPen(QColor(*rgb, alpha))
            pen.setWidth(3 if active else 2)
            pen.setCosmetic(True)
            pen.setStyle(
                Qt.PenStyle.SolidLine if active else Qt.PenStyle.DashLine
            )
            painter.setPen(pen)
            for boundary in (band.y0, band.y1 + 1):
                if 0 <= boundary <= map_h:
                    ly = oy + boundary * z
                    painter.drawLine(ox, ly, ox + sw, ly)

            mid_y = (band.y0 + band.y1) / 2.0
            if mid_y < 0 or mid_y > map_h:
                continue
            label_y = oy + int(mid_y * z) - 8
            label = f"Band {i}"
            detail = f"Y {band.y0}–{band.y1}"
            metrics = painter.fontMetrics()
            text_w = max(metrics.horizontalAdvance(label), metrics.horizontalAdvance(detail))
            text_h = metrics.height() * 2 + 4
            label_x = ox + 6
            label_y = max(oy + 2, min(oy + sh - text_h - 2, label_y))
            painter.fillRect(label_x - 2, label_y - 2, text_w + 8, text_h + 4, QColor(20, 20, 28, 190))
            painter.setPen(QColor(*rgb, 255))
            painter.drawText(label_x + 2, label_y + metrics.ascent(), label)
            painter.setPen(QColor(220, 220, 220, 230))
            painter.drawText(
                label_x + 2,
                label_y + metrics.ascent() + metrics.height() + 2,
                detail,
            )

        painter.setPen(Qt.PenStyle.NoPen)

    def set_show_grid(self, visible: bool) -> None:
        self.show_grid = visible
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(1, min(16, zoom))
        self._apply_canvas_pixel_size()
        self.update()

    def _apply_canvas_pixel_size(self) -> None:
        if self.scene:
            self.resize(self.scene.width * self.zoom, self.scene.height * self.zoom)
        else:
            self.resize(200, 200)

    def _tile_surface(self, tileset: Tileset, tile_index: int) -> pygame.Surface | None:
        if tile_index < 0 or tile_index >= tileset.tile_count:
            return None
        size = tileset.tile_size
        tile = tileset.get_tile(tile_index)
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        for ly in range(size):
            for lx in range(size):
                index = tile[ly * size + lx]
                if index == TRANSPARENT_INDEX:
                    continue
                rgb = self.palette[index]
                surface.set_at((lx, ly), (*rgb, 255))
        return surface

    def _tile_layer_tileset(self, tileset_path: str) -> Tileset | None:
        if not tileset_path:
            return None
        if tileset_path in self.tilesets:
            return self.tilesets[tileset_path]
        if self.project_root is None:
            return None
        path = (self.project_root / tileset_path).resolve()
        if not path.is_file():
            return None
        loaded = load_tileset(path)
        self.tilesets[tileset_path] = loaded
        return loaded

    def _get_background(self, rel_path: str) -> Background | None:
        if not rel_path:
            return None
        if rel_path in self.backgrounds:
            return self.backgrounds[rel_path]
        if self.project_root is None:
            return None
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_background(path)
        self.backgrounds[rel_path] = loaded
        return loaded

    def _background_palette(self, background: Background) -> list[tuple[int, int, int]] | None:
        if background.palette in self.bg_palettes:
            return self.bg_palettes[background.palette]
        if self.project_root is None:
            return None
        path = palette_path(self.project_root, background.palette)
        if not path.is_file():
            return None
        colors = load_palette(path)
        self.bg_palettes[background.palette] = colors
        return colors

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

    def _object_instance_surface(self, inst: SceneObject) -> pygame.Surface | None:
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

    def _draw_scene_objects(self, composite: pygame.Surface) -> None:
        if not self.scene or not self.show_objects:
            return
        for inst in self.scene.objects:
            surface = self._object_instance_surface(inst)
            if surface is None:
                continue
            tortu_object = self._get_tortu_object(inst.prefab)
            if tortu_object is None:
                continue
            draw_x = inst.x - tortu_object.origin.x
            draw_y = inst.y - tortu_object.origin.y
            composite.blit(surface, (draw_x, draw_y))

    def _refresh(self) -> None:
        if not self.scene:
            self._frame = None
            self.update()
            return

        map_w = self.scene.width
        map_h = self.scene.height
        composite = pygame.Surface((map_w, map_h))
        composite.fill(self.MAP_BG)

        if self.show_backgrounds:
            for scene_bg in self.scene.scene_bg_layers:
                if not scene_bg.visible or not scene_bg.background:
                    continue
                bg = self._get_background(scene_bg.background)
                if bg is None:
                    continue
                bg_palette = self._background_palette(bg)
                if bg_palette is None:
                    continue
                if scene_bg.band_parallax and scene_bg.parallax_bands:
                    bg.draw_parallax_bands(
                        composite,
                        bg_palette,
                        scene_bg.parallax_bands,
                        parallax_y=scene_bg.parallax_y,
                        camera_x=float(self.camera_x),
                        camera_y=0.0,
                    )
                else:
                    bg.draw_parallax(
                        composite,
                        bg_palette,
                        parallax_x=scene_bg.parallax_x,
                        parallax_y=scene_bg.parallax_y,
                        camera_x=float(self.camera_x),
                        fixed=scene_bg.fixed,
                        repeat_x=scene_bg.repeat_x,
                        repeat_y=scene_bg.repeat_y,
                    )

        for tile_layer in self.scene.tile_layers:
            if not tile_layer.visible or not tile_layer.tileset:
                continue
            tileset = self._tile_layer_tileset(tile_layer.tileset)
            if tileset is None:
                continue
            tile_size = tileset.tile_size
            cols = self.scene.grid_columns(tile_size)
            rows = self.scene.grid_rows(tile_size)
            for ty in range(rows):
                for tx in range(cols):
                    px = tx * tile_size
                    py = ty * tile_size
                    if px >= map_w or py >= map_h:
                        continue
                    tile_index = tile_layer.tiles[ty * cols + tx]
                    if tile_index == EMPTY_TILE:
                        continue
                    tile_surface = self._tile_surface(tileset, tile_index)
                    if tile_surface is None:
                        continue
                    composite.blit(tile_surface, (px, py))

        self._draw_scene_objects(composite)

        data = pygame.image.tobytes(composite, "RGBA")
        self._frame = QImage(data, map_w, map_h, map_w * 4, QImage.Format.Format_RGBA8888)
        self._apply_canvas_pixel_size()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None or not self.scene:
            painter.end()
            return

        tile_size = self.active_tileset.tile_size if self.active_tileset else TILE_BLOCK
        sw = self.scene.width * self.zoom
        sh = self.scene.height * self.zoom
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)

        scaled = self._frame.scaled(
            sw,
            sh,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        painter.drawImage(ox, oy, scaled)

        if self.show_grid and tile_size > 0:
            pen = QPen(QColor(*self.TILE_GRID_COLOR))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(tile_size, self.scene.width, tile_size):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for py in range(tile_size, self.scene.height, tile_size):
                ly = oy + py * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)

        if self.scene.collision_tile_layer == self.active_tile_layer:
            pen = QPen(QColor(255, 220, 80, 180))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(ox, oy, sw, sh)

        self._paint_band_guides(painter, ox, oy, sw, sh)

        if self.edit_objects and self.scene and self.show_objects:
            pen = QPen(QColor(255, 120, 120, 200))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for inst in self.scene.objects:
                lx = ox + inst.x * self.zoom
                ly = oy + inst.y * self.zoom
                painter.drawLine(int(lx - 4), int(ly), int(lx + 4), int(ly))
                painter.drawLine(int(lx), int(ly - 4), int(lx), int(ly + 4))

        painter.end()

    def _event_to_map_pixel(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None or not self.scene:
            return None
        sw = self.scene.width * self.zoom
        sh = self.scene.height * self.zoom
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)
        px = (event.position().x() - ox) / self.zoom
        py = (event.position().y() - oy) / self.zoom
        if px < 0 or py < 0 or px >= self.scene.width or py >= self.scene.height:
            return None
        return int(px), int(py)

    def _event_to_tile(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None or not self.scene or not self.active_tileset:
            return None
        tile_size = self.active_tileset.tile_size
        sw = self.scene.width * self.zoom
        sh = self.scene.height * self.zoom
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)
        px = (event.position().x() - ox) / self.zoom
        py = (event.position().y() - oy) / self.zoom
        if px < 0 or py < 0 or px >= self.scene.width or py >= self.scene.height:
            return None
        tx = int(px // tile_size)
        ty = int(py // tile_size)
        cols = self.scene.grid_columns(tile_size)
        rows = self.scene.grid_rows(tile_size)
        if 0 <= tx < cols and 0 <= ty < rows:
            return tx, ty
        return None

    def _apply_tool(self, x: int, y: int) -> None:
        if not self.scene or not self.active_tileset:
            return
        tile_size = self.active_tileset.tile_size
        if self.tool == Tool.PAINT:
            self.scene.set_tile(
                self.active_tile_layer, x, y, self.selected_tile, tile_size
            )
        elif self.tool == Tool.ERASE:
            self.scene.set_tile(self.active_tile_layer, x, y, EMPTY_TILE, tile_size)
        elif self.tool == Tool.EYEDROPPER:
            picked = self.scene.get_tile(self.active_tile_layer, x, y, tile_size)
            if picked != EMPTY_TILE:
                self.selected_tile = picked
                self.changed.emit()
        self._refresh()

    def _apply_object_tool(self, px: int, py: int) -> None:
        if not self.scene:
            return
        if self.tool == Tool.ERASE:
            index = self.scene.find_object_near(px, py)
            if index is not None:
                self.scene.remove_object(index)
        elif self.tool == Tool.PAINT and self.selected_object_prefab:
            try:
                self.scene.add_object(self.selected_object_prefab, px, py)
            except ValueError:
                pass
        self._refresh()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self.edit_objects:
                pos = self._event_to_map_pixel(event)
                if pos:
                    self._drawing = True
                    self._apply_object_tool(*pos)
                    self.changed.emit()
                return
            pos = self._event_to_tile(event)
            if pos:
                self._drawing = True
                self._apply_tool(*pos)
                self.changed.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drawing and event.buttons() & Qt.MouseButton.LeftButton:
            if self.edit_objects:
                if self.tool == Tool.ERASE:
                    pos = self._event_to_map_pixel(event)
                    if pos:
                        self._apply_object_tool(*pos)
                        self.changed.emit()
                return
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
        self._active_tileset: Tileset | None = None
        self._tilesets_cache: dict[str, Tileset] = {}
        self._backgrounds_cache: dict[str, Background] = {}
        self._bg_palettes_cache: dict[str, list[tuple[int, int, int]]] = {}
        self._palette_colors: list[tuple[int, int, int]] = []
        self._dirty = False
        self._selected_tile = 0

        self.map_canvas = SceneMapCanvas()
        self.map_canvas.changed.connect(self._on_map_changed)

        self.strip_canvas = TilesetStripCanvas()
        self.strip_canvas.tile_clicked.connect(self._on_strip_tile_clicked)

        self.object_strip = ObjectStripCanvas()
        self.object_strip.object_clicked.connect(self._on_object_strip_clicked)

        self.btn_save = QPushButton("Save scene")
        self.btn_save.clicked.connect(self.save)
        self.btn_new = QPushButton("New Scene…")
        self.btn_new.clicked.connect(self.new_scene_requested.emit)
        self.btn_open = QPushButton("Open Scene…")
        self.btn_open.clicked.connect(self.open_scene_requested.emit)

        self.status_label = QLabel("No scene open")
        self.map_size_label = QLabel("—")

        self.tile_layer_combo = QComboBox()
        self.tile_layer_combo.currentIndexChanged.connect(self._on_tile_layer_changed)

        self.tile_layer_tileset_combo = QComboBox()
        self.tile_layer_tileset_combo.setToolTip("Tileset used by the active tile layer")
        self.tile_layer_tileset_combo.currentIndexChanged.connect(
            self._on_tile_layer_tileset_changed
        )

        self.tile_layer_visible = QCheckBox("Tile layer visible")
        self.tile_layer_visible.setChecked(True)
        self.tile_layer_visible.toggled.connect(self._on_tile_layer_visible_toggled)

        self.collision_tile_layer_combo = QComboBox()
        self.collision_tile_layer_combo.currentIndexChanged.connect(
            self._on_collision_tile_layer_changed
        )

        self.btn_add_tile_layer = QPushButton("Add tile layer")
        self.btn_add_tile_layer.clicked.connect(self._add_tile_layer)
        self.btn_remove_tile_layer = QPushButton("Remove tile layer")
        self.btn_remove_tile_layer.clicked.connect(self._remove_tile_layer)

        self.scene_bg_layer_combo = QComboBox()
        self.scene_bg_layer_combo.currentIndexChanged.connect(self._on_scene_bg_layer_changed)

        self.scene_bg_background_combo = QComboBox()
        self.scene_bg_background_combo.setToolTip("Background asset for the active scene bg layer")
        self.scene_bg_background_combo.currentIndexChanged.connect(
            self._on_scene_bg_background_changed
        )

        self.scene_bg_visible = QCheckBox("Bg layer visible")
        self.scene_bg_visible.setChecked(True)
        self.scene_bg_visible.toggled.connect(self._on_scene_bg_visible_toggled)

        self.scene_bg_parallax_x = QDoubleSpinBox()
        self.scene_bg_parallax_x.setRange(0.0, 1.0)
        self.scene_bg_parallax_x.setSingleStep(0.05)
        self.scene_bg_parallax_x.setValue(0.5)
        self.scene_bg_parallax_x.setToolTip("Scroll factor when camera moves (disabled when Fixed)")
        self.scene_bg_parallax_x.valueChanged.connect(self._on_scene_bg_parallax_changed)

        self.scene_bg_parallax_y = QDoubleSpinBox()
        self.scene_bg_parallax_y.setRange(0.0, 1.0)
        self.scene_bg_parallax_y.setSingleStep(0.05)
        self.scene_bg_parallax_y.valueChanged.connect(self._on_scene_bg_parallax_changed)

        self.scene_bg_fixed = QCheckBox("Fixed")
        self.scene_bg_fixed.setToolTip("Background stays on screen and ignores camera scroll")
        self.scene_bg_fixed.toggled.connect(self._on_scene_bg_fixed_toggled)

        self.scene_bg_repeat_x = QCheckBox("Repeat X")
        self.scene_bg_repeat_x.setToolTip("Tile the background horizontally")
        self.scene_bg_repeat_x.toggled.connect(self._on_scene_bg_repeat_x_toggled)

        self.scene_bg_repeat_y = QCheckBox("Repeat Y")
        self.scene_bg_repeat_y.setToolTip("Tile the background vertically")
        self.scene_bg_repeat_y.toggled.connect(self._on_scene_bg_repeat_y_toggled)

        self.scene_bg_band_parallax = QCheckBox("Band parallax (Y strips)")
        self.scene_bg_band_parallax.setToolTip(
            "Split the background into horizontal Y bands, each with its own parallax X / fixed / repeat"
        )
        self.scene_bg_band_parallax.toggled.connect(self._on_scene_bg_band_parallax_toggled)

        self.show_band_guides = QCheckBox("Show band guides on map")
        self.show_band_guides.setToolTip(
            "Draw Y band lines, names, and overlap highlights on the map canvas"
        )
        self.show_band_guides.toggled.connect(self._on_show_band_guides_toggled)

        self.band_combo = QComboBox()
        self.band_combo.currentIndexChanged.connect(self._on_band_changed)

        self.band_y0 = QSpinBox()
        self.band_y0.setRange(0, 2048)
        self.band_y0.valueChanged.connect(self._on_band_fields_changed)

        self.band_y1 = QSpinBox()
        self.band_y1.setRange(0, 2048)
        self.band_y1.valueChanged.connect(self._on_band_fields_changed)

        self.band_parallax_x = QDoubleSpinBox()
        self.band_parallax_x.setRange(0.0, 1.0)
        self.band_parallax_x.setSingleStep(0.05)
        self.band_parallax_x.valueChanged.connect(self._on_band_fields_changed)

        self.band_fixed = QCheckBox("Band fixed")
        self.band_fixed.toggled.connect(self._on_band_fields_changed)

        self.band_repeat_x = QCheckBox("Band repeat X")
        self.band_repeat_x.toggled.connect(self._on_band_fields_changed)

        self.band_repeat_y = QCheckBox("Band repeat Y")
        self.band_repeat_y.toggled.connect(self._on_band_fields_changed)

        self.btn_add_band = QPushButton("Add band")
        self.btn_add_band.clicked.connect(self._add_parallax_band)
        self.btn_remove_band = QPushButton("Remove band")
        self.btn_remove_band.clicked.connect(self._remove_parallax_band)

        self.btn_add_scene_bg_layer = QPushButton("Add bg layer")
        self.btn_add_scene_bg_layer.clicked.connect(self._add_scene_bg_layer)
        self.btn_remove_scene_bg_layer = QPushButton("Remove bg layer")
        self.btn_remove_scene_bg_layer.clicked.connect(self._remove_scene_bg_layer)

        self.show_backgrounds = QCheckBox("Show backgrounds")
        self.show_backgrounds.setChecked(True)
        self.show_backgrounds.toggled.connect(self._on_show_backgrounds_toggled)

        self.show_objects = QCheckBox("Show objects")
        self.show_objects.setChecked(True)
        self.show_objects.toggled.connect(self._on_show_objects_toggled)

        self.camera_slider = QSlider(Qt.Orientation.Horizontal)
        self.camera_slider.setRange(0, DEFAULT_SCENE_WIDTH)
        self.camera_slider.valueChanged.connect(self._on_camera_changed)

        self.map_width = QSpinBox()
        self.map_width.setRange(8, 2048)
        self.map_width.setValue(DEFAULT_SCENE_WIDTH)
        self.map_width.setSuffix(" px")

        self.map_height = QSpinBox()
        self.map_height.setRange(8, 2048)
        self.map_height.setValue(DEFAULT_SCENE_HEIGHT)
        self.map_height.setSuffix(" px")

        self.btn_resize_map = QPushButton("Resize map")
        self.btn_resize_map.clicked.connect(self._resize_map)
        self.btn_reset_screen = QPushButton("Reset to screen")
        self.btn_reset_screen.setToolTip(
            f"Set map size to {SCREEN_WIDTH}×{SCREEN_HEIGHT} (camera / screen)"
        )
        self.btn_reset_screen.clicked.connect(self._reset_map_to_screen)

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
        map_scroll.setWidgetResizable(False)
        map_scroll.setWidget(self.map_canvas)
        map_layout.addWidget(map_scroll)
        body.addWidget(map_group, stretch=1)

        side_widget = QWidget()
        side = QVBoxLayout(side_widget)
        side.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.addRow("Map size:", self.map_size_label)
        form.addRow("Active tile layer:", self.tile_layer_combo)
        form.addRow("Tileset:", self.tile_layer_tileset_combo)
        form.addRow("", self.tile_layer_visible)
        form.addRow("Collision tile layer:", self.collision_tile_layer_combo)
        tile_layer_btns = QHBoxLayout()
        tile_layer_btns.addWidget(self.btn_add_tile_layer)
        tile_layer_btns.addWidget(self.btn_remove_tile_layer)
        form.addRow(tile_layer_btns)
        form.addRow(QLabel("<b>Background layers</b>"))
        form.addRow("Active bg layer:", self.scene_bg_layer_combo)
        form.addRow("Background:", self.scene_bg_background_combo)
        form.addRow("", self.scene_bg_visible)
        form.addRow("Parallax X:", self.scene_bg_parallax_x)
        form.addRow("Parallax Y:", self.scene_bg_parallax_y)
        form.addRow("", self.scene_bg_fixed)
        form.addRow("", self.scene_bg_repeat_x)
        form.addRow("", self.scene_bg_repeat_y)
        form.addRow("", self.scene_bg_band_parallax)
        form.addRow("", self.show_band_guides)
        form.addRow("Parallax band:", self.band_combo)
        form.addRow("Band Y from:", self.band_y0)
        form.addRow("Band Y to:", self.band_y1)
        form.addRow("Band parallax X:", self.band_parallax_x)
        form.addRow("", self.band_fixed)
        form.addRow("", self.band_repeat_x)
        form.addRow("", self.band_repeat_y)
        band_btns = QHBoxLayout()
        band_btns.addWidget(self.btn_add_band)
        band_btns.addWidget(self.btn_remove_band)
        form.addRow(band_btns)
        scene_bg_btns = QHBoxLayout()
        scene_bg_btns.addWidget(self.btn_add_scene_bg_layer)
        scene_bg_btns.addWidget(self.btn_remove_scene_bg_layer)
        form.addRow(scene_bg_btns)
        form.addRow("Camera X:", self.camera_slider)
        form.addRow(self.show_backgrounds)
        form.addRow(self.show_objects)
        form.addRow("Width:", self.map_width)
        form.addRow("Height:", self.map_height)
        resize_row = QHBoxLayout()
        resize_row.addWidget(self.btn_resize_map)
        resize_row.addWidget(self.btn_reset_screen)
        form.addRow(resize_row)
        form.addRow("Zoom:", self.zoom_spin)
        form.addRow(self.show_grid)
        side.addLayout(form)

        tools = QHBoxLayout()
        tools.addWidget(self.btn_paint)
        tools.addWidget(self.btn_erase)
        tools.addWidget(self.btn_dropper)
        side.addLayout(tools)

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
        self.bottom_tabs.currentChanged.connect(self._on_bottom_tab_changed)

        outer.addWidget(self.bottom_tabs)

    def _active_tile_layer_index(self) -> int:
        if not self.scene or self.tile_layer_combo.count() == 0:
            return 0
        return self.tile_layer_combo.currentIndex()

    def _active_scene_bg_layer_index(self) -> int:
        if not self.scene or self.scene_bg_layer_combo.count() == 0:
            return -1
        return self.scene_bg_layer_combo.currentIndex()

    def _active_tile_layer_tile_size(self) -> int:
        if not self.scene:
            return TILE_BLOCK
        tile_layer = self.scene.tile_layers[self._active_tile_layer_index()]
        return tile_size_for_tile_layer(tile_layer, self.project_root)

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

    def _get_background(self, rel_path: str) -> Background | None:
        if not rel_path:
            return None
        if rel_path in self._backgrounds_cache:
            return self._backgrounds_cache[rel_path]
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_background(path)
        self._backgrounds_cache[rel_path] = loaded
        return loaded

    def _load_active_tile_layer_tileset(self) -> None:
        if not self.scene:
            self._active_tileset = None
            return
        tile_layer = self.scene.tile_layers[self._active_tile_layer_index()]
        self._active_tileset = self._get_tileset(tile_layer.tileset)

    def _set_tool(self, tool: Tool) -> None:
        self.btn_paint.setChecked(tool == Tool.PAINT)
        self.btn_erase.setChecked(tool == Tool.ERASE)
        self.btn_dropper.setChecked(tool == Tool.EYEDROPPER)
        self.map_canvas.set_tool(tool)

    def _on_map_changed(self) -> None:
        if (
            self.map_canvas.tool == Tool.EYEDROPPER
            and self.map_canvas.selected_tile != self._selected_tile
        ):
            self._selected_tile = self.map_canvas.selected_tile
            self.strip_canvas.set_selected_index(self._selected_tile)
        self._mark_dirty()
        self._refresh_map()

    def _on_strip_tile_clicked(self, index: int) -> None:
        self._selected_tile = index
        self._set_tool(Tool.PAINT)
        self.bottom_tabs.setCurrentIndex(0)
        self._refresh_map()

    def _on_object_strip_clicked(self, _index: int) -> None:
        self._set_tool(Tool.PAINT)
        self._refresh_map()

    def _on_bottom_tab_changed(self, _index: int) -> None:
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

    def _update_map_size_label(self) -> None:
        if not self.scene:
            self.map_size_label.setText("—")
            return
        ts = self._active_tile_layer_tile_size()
        cols = self.scene.grid_columns(ts)
        rows = self.scene.grid_rows(ts)
        self.map_size_label.setText(
            f"{self.scene.width}×{self.scene.height} px  ({cols}×{rows} @ {ts}px tiles)"
        )

    def _sync_tile_layer_tileset_combo(self) -> None:
        self.tile_layer_tileset_combo.blockSignals(True)
        self.tile_layer_tileset_combo.clear()
        self.tile_layer_tileset_combo.addItem("(none)", "")
        for rel in list_tileset_paths(self.project_root):
            self.tile_layer_tileset_combo.addItem(rel, rel)
        if not self.scene:
            self.tile_layer_tileset_combo.blockSignals(False)
            return
        tile_layer = self.scene.tile_layers[self._active_tile_layer_index()]
        index = self.tile_layer_tileset_combo.findData(tile_layer.tileset)
        self.tile_layer_tileset_combo.setCurrentIndex(index if index >= 0 else 0)
        self.tile_layer_tileset_combo.blockSignals(False)

    def _background_height_for_scene_bg(self, scene_bg) -> int:
        if not scene_bg.background:
            return SCREEN_HEIGHT
        bg = self._get_background(scene_bg.background)
        return bg.height if bg else SCREEN_HEIGHT

    def _update_scene_bg_parallax_enabled(self, scene_bg) -> None:
        layer_mode = not scene_bg.band_parallax
        layer_x_enabled = layer_mode and not scene_bg.fixed
        self.scene_bg_parallax_x.setEnabled(layer_x_enabled)
        self.scene_bg_parallax_y.setEnabled(True)
        self.scene_bg_fixed.setEnabled(layer_mode)
        self.scene_bg_repeat_x.setEnabled(layer_mode)
        self.scene_bg_repeat_y.setEnabled(layer_mode)
        band_on = scene_bg.band_parallax and bool(scene_bg.background)
        self._set_band_controls_enabled(band_on)

    def _set_band_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.band_combo,
            self.band_y0,
            self.band_y1,
            self.band_parallax_x,
            self.band_fixed,
            self.band_repeat_x,
            self.band_repeat_y,
            self.btn_add_band,
            self.btn_remove_band,
            self.show_band_guides,
        ):
            widget.setEnabled(enabled)

    def _active_band_index(self) -> int:
        if self.band_combo.count() == 0:
            return -1
        return self.band_combo.currentIndex()

    def _sync_band_controls(self) -> None:
        index = self._active_scene_bg_layer_index()
        self.scene_bg_band_parallax.blockSignals(True)
        self.band_combo.blockSignals(True)
        self.band_combo.clear()
        if not self.scene or index < 0:
            self.scene_bg_band_parallax.setChecked(False)
            self.scene_bg_band_parallax.blockSignals(False)
            self.band_combo.blockSignals(False)
            self._set_band_controls_enabled(False)
            return
        scene_bg = self.scene.scene_bg_layers[index]
        self.scene_bg_band_parallax.setChecked(scene_bg.band_parallax)
        self.scene_bg_band_parallax.blockSignals(False)
        bg_height = self._background_height_for_scene_bg(scene_bg)
        self.band_y0.setMaximum(max(0, bg_height - 1))
        self.band_y1.setMaximum(max(0, bg_height - 1))
        for i, band in enumerate(scene_bg.parallax_bands):
            self.band_combo.addItem(f"{i}: Y {band.y0}–{band.y1}", i)
        if scene_bg.parallax_bands:
            active = min(self._active_band_index(), len(scene_bg.parallax_bands) - 1)
            if active < 0:
                active = 0
            self.band_combo.setCurrentIndex(active)
            self._load_band_fields(scene_bg.parallax_bands[active])
        self.band_combo.blockSignals(False)
        self.btn_remove_band.setEnabled(len(scene_bg.parallax_bands) > 1)
        self.btn_add_band.setEnabled(len(scene_bg.parallax_bands) < MAX_PARALLAX_BANDS)
        self._update_scene_bg_parallax_enabled(scene_bg)

    def _load_band_fields(self, band: SceneBgParallaxBand) -> None:
        self.band_y0.blockSignals(True)
        self.band_y1.blockSignals(True)
        self.band_parallax_x.blockSignals(True)
        self.band_fixed.blockSignals(True)
        self.band_repeat_x.blockSignals(True)
        self.band_repeat_y.blockSignals(True)
        self.band_y0.setValue(band.y0)
        self.band_y1.setValue(band.y1)
        self.band_parallax_x.setValue(band.parallax_x)
        self.band_fixed.setChecked(band.fixed)
        self.band_repeat_x.setChecked(band.repeat_x)
        self.band_repeat_y.setChecked(band.repeat_y)
        self.band_y0.blockSignals(False)
        self.band_y1.blockSignals(False)
        self.band_parallax_x.blockSignals(False)
        self.band_fixed.blockSignals(False)
        self.band_repeat_x.blockSignals(False)
        self.band_repeat_y.blockSignals(False)

    def _save_band_fields(self, band: SceneBgParallaxBand) -> None:
        y0 = self.band_y0.value()
        y1 = self.band_y1.value()
        band.y0 = min(y0, y1)
        band.y1 = max(y0, y1)
        band.parallax_x = self.band_parallax_x.value()
        band.fixed = self.band_fixed.isChecked()
        band.repeat_x = self.band_repeat_x.isChecked()
        band.repeat_y = self.band_repeat_y.isChecked()

    def _sync_scene_bg_background_combo(self) -> None:
        self.scene_bg_background_combo.blockSignals(True)
        self.scene_bg_background_combo.clear()
        self.scene_bg_background_combo.addItem("(none)", "")
        for rel in list_background_paths(self.project_root):
            self.scene_bg_background_combo.addItem(rel, rel)
        index = self._active_scene_bg_layer_index()
        if not self.scene or index < 0:
            self.scene_bg_background_combo.blockSignals(False)
            return
        scene_bg = self.scene.scene_bg_layers[index]
        bg_index = self.scene_bg_background_combo.findData(scene_bg.background)
        self.scene_bg_background_combo.setCurrentIndex(bg_index if bg_index >= 0 else 0)
        self.scene_bg_background_combo.blockSignals(False)

    def _sync_scene_bg_layer_controls(self) -> None:
        if not self.scene:
            return
        self.scene_bg_layer_combo.blockSignals(True)
        self.scene_bg_layer_combo.clear()
        for i, scene_bg in enumerate(self.scene.scene_bg_layers):
            self.scene_bg_layer_combo.addItem(f"{i}: {scene_bg.name}", i)
        if self.scene.scene_bg_layer_count == 0:
            self.scene_bg_visible.setEnabled(False)
            self.scene_bg_background_combo.setEnabled(False)
            self.scene_bg_parallax_x.setEnabled(False)
            self.scene_bg_parallax_y.setEnabled(False)
            self.scene_bg_fixed.setEnabled(False)
            self.scene_bg_repeat_x.setEnabled(False)
            self.scene_bg_repeat_y.setEnabled(False)
            self.scene_bg_band_parallax.setEnabled(False)
            self._set_band_controls_enabled(False)
            self.scene_bg_layer_combo.blockSignals(False)
            self.btn_add_scene_bg_layer.setEnabled(True)
            self.btn_remove_scene_bg_layer.setEnabled(False)
            return
        self.scene_bg_visible.setEnabled(True)
        self.scene_bg_background_combo.setEnabled(True)
        self.scene_bg_parallax_x.setEnabled(True)
        self.scene_bg_parallax_y.setEnabled(True)
        self.scene_bg_fixed.setEnabled(True)
        self.scene_bg_repeat_x.setEnabled(True)
        self.scene_bg_repeat_y.setEnabled(True)
        self.scene_bg_band_parallax.setEnabled(True)
        active = self.scene_bg_layer_combo.currentIndex()
        if active < 0:
            active = 0
        if self.scene_bg_layer_combo.count() > 0:
            self.scene_bg_layer_combo.setCurrentIndex(
                min(active, self.scene.scene_bg_layer_count - 1)
            )
            scene_bg = self.scene.scene_bg_layers[self.scene_bg_layer_combo.currentIndex()]
            self.scene_bg_visible.blockSignals(True)
            self.scene_bg_visible.setChecked(scene_bg.visible)
            self.scene_bg_visible.blockSignals(False)
            self.scene_bg_parallax_x.blockSignals(True)
            self.scene_bg_parallax_y.blockSignals(True)
            self.scene_bg_parallax_x.setValue(scene_bg.parallax_x)
            self.scene_bg_parallax_y.setValue(scene_bg.parallax_y)
            self.scene_bg_parallax_x.blockSignals(False)
            self.scene_bg_parallax_y.blockSignals(False)
            self.scene_bg_fixed.blockSignals(True)
            self.scene_bg_repeat_x.blockSignals(True)
            self.scene_bg_repeat_y.blockSignals(True)
            self.scene_bg_fixed.setChecked(scene_bg.fixed)
            self.scene_bg_repeat_x.setChecked(scene_bg.repeat_x)
            self.scene_bg_repeat_y.setChecked(scene_bg.repeat_y)
            self.scene_bg_fixed.blockSignals(False)
            self.scene_bg_repeat_x.blockSignals(False)
            self.scene_bg_repeat_y.blockSignals(False)
            self.scene_bg_band_parallax.blockSignals(True)
            self.scene_bg_band_parallax.setChecked(scene_bg.band_parallax)
            self.scene_bg_band_parallax.blockSignals(False)
            self._update_scene_bg_parallax_enabled(scene_bg)
            self._sync_band_controls()
        self.scene_bg_layer_combo.blockSignals(False)
        self.btn_add_scene_bg_layer.setEnabled(
            self.scene.scene_bg_layer_count < MAX_SCENE_BG_LAYERS
        )
        self.btn_remove_scene_bg_layer.setEnabled(self.scene.scene_bg_layer_count > 0)

    def _update_camera_slider(self) -> None:
        if not self.scene:
            return
        max_cam = max(0, self.scene.width - SCREEN_WIDTH)
        self.camera_slider.blockSignals(True)
        self.camera_slider.setRange(0, max_cam)
        self.camera_slider.setValue(min(self.camera_slider.value(), max_cam))
        self.camera_slider.blockSignals(False)

    def _load_palette_for_scene(self) -> None:
        if not self.scene:
            return
        path = palette_path(self.project_root, self.scene.palette)
        if not path.is_file():
            raise FileNotFoundError(f"Palette not found: {path}")
        self._palette_colors = load_palette(path)

    def _sync_tile_layer_controls(self) -> None:
        if not self.scene:
            return
        self.tile_layer_combo.blockSignals(True)
        self.collision_tile_layer_combo.blockSignals(True)
        self.tile_layer_combo.clear()
        self.collision_tile_layer_combo.clear()
        for i, tile_layer in enumerate(self.scene.tile_layers):
            label = f"{i}: {tile_layer.name}"
            self.tile_layer_combo.addItem(label, i)
            self.collision_tile_layer_combo.addItem(label, i)
        active = min(
            self.map_canvas.active_tile_layer,
            max(0, self.scene.tile_layer_count - 1),
        )
        self.tile_layer_combo.setCurrentIndex(active)
        self.collision_tile_layer_combo.setCurrentIndex(self.scene.collision_tile_layer)
        self.tile_layer_visible.setChecked(self.scene.tile_layers[active].visible)
        self.tile_layer_combo.blockSignals(False)
        self.collision_tile_layer_combo.blockSignals(False)
        self.btn_remove_tile_layer.setEnabled(
            self.scene.tile_layer_count > MIN_SCENE_TILE_LAYERS
        )
        self.btn_add_tile_layer.setEnabled(
            self.scene.tile_layer_count < MAX_SCENE_TILE_LAYERS
        )

    def _refresh_map(self) -> None:
        if not self.scene:
            self.map_canvas.set_context(
                None, None, {}, {}, {}, None, [], 0, 0, camera_x=0, show_backgrounds=True
            )
            return
        scene_bg_index = self._active_scene_bg_layer_index()
        show_band_guides = False
        parallax_bands: list[SceneBgParallaxBand] = []
        active_band_index = -1
        if scene_bg_index >= 0:
            scene_bg = self.scene.scene_bg_layers[scene_bg_index]
            if (
                scene_bg.band_parallax
                and scene_bg.background
                and self.show_band_guides.isChecked()
            ):
                show_band_guides = True
                parallax_bands = scene_bg.parallax_bands
                active_band_index = self._active_band_index()
        active = self._active_tile_layer_index()
        self.map_canvas.set_context(
            self.scene,
            self.project_root,
            self._tilesets_cache,
            self._backgrounds_cache,
            self._bg_palettes_cache,
            self._active_tileset,
            self._palette_colors,
            active,
            self._selected_tile,
            camera_x=self.camera_slider.value(),
            show_backgrounds=self.show_backgrounds.isChecked(),
            show_band_guides=show_band_guides,
            parallax_bands=parallax_bands,
            active_band_index=active_band_index,
            edit_objects=self.bottom_tabs.currentIndex() == 1,
            selected_object_prefab=self.object_strip.selected_prefab(),
            show_objects=self.show_objects.isChecked(),
        )

    def _refresh_object_strip(self) -> None:
        paths = list_object_paths(self.project_root)
        self.object_strip.set_project(self.project_root, paths)

    def _refresh_strip(self) -> None:
        if self._active_tileset:
            self.strip_canvas.set_tileset(self._active_tileset, self._palette_colors)
            self.strip_canvas.set_selected_index(self._selected_tile)
        else:
            self.strip_canvas.set_tileset(None, [])

    def _refresh_editor(self) -> None:
        if not self.scene:
            return
        self.map_width.blockSignals(True)
        self.map_height.blockSignals(True)
        self.map_width.setValue(self.scene.width)
        self.map_height.setValue(self.scene.height)
        self.map_width.blockSignals(False)
        self.map_height.blockSignals(False)
        self._update_map_size_label()
        self._sync_tile_layer_controls()
        self._sync_tile_layer_tileset_combo()
        self._sync_scene_bg_layer_controls()
        self._sync_scene_bg_background_combo()
        self._sync_band_controls()
        self._update_camera_slider()
        self._load_active_tile_layer_tileset()
        self._refresh_map()
        self._refresh_strip()
        self._refresh_object_strip()

    def _on_scene_bg_layer_changed(self, index: int) -> None:
        if not self.scene or index < 0:
            return
        scene_bg = self.scene.scene_bg_layers[index]
        self.scene_bg_visible.blockSignals(True)
        self.scene_bg_visible.setChecked(scene_bg.visible)
        self.scene_bg_visible.blockSignals(False)
        self.scene_bg_parallax_x.blockSignals(True)
        self.scene_bg_parallax_y.blockSignals(True)
        self.scene_bg_parallax_x.setValue(scene_bg.parallax_x)
        self.scene_bg_parallax_y.setValue(scene_bg.parallax_y)
        self.scene_bg_parallax_x.blockSignals(False)
        self.scene_bg_parallax_y.blockSignals(False)
        self.scene_bg_fixed.blockSignals(True)
        self.scene_bg_repeat_x.blockSignals(True)
        self.scene_bg_repeat_y.blockSignals(True)
        self.scene_bg_fixed.setChecked(scene_bg.fixed)
        self.scene_bg_repeat_x.setChecked(scene_bg.repeat_x)
        self.scene_bg_repeat_y.setChecked(scene_bg.repeat_y)
        self.scene_bg_fixed.blockSignals(False)
        self.scene_bg_repeat_x.blockSignals(False)
        self.scene_bg_repeat_y.blockSignals(False)
        self.scene_bg_band_parallax.blockSignals(True)
        self.scene_bg_band_parallax.setChecked(scene_bg.band_parallax)
        self.scene_bg_band_parallax.blockSignals(False)
        self._update_scene_bg_parallax_enabled(scene_bg)
        self._sync_scene_bg_background_combo()
        self._sync_band_controls()
        self._refresh_map()

    def _on_scene_bg_background_changed(self, index: int) -> None:
        if not self.scene or index < 0:
            return
        bg_index = self._active_scene_bg_layer_index()
        if bg_index < 0:
            return
        rel = self.scene_bg_background_combo.itemData(index)
        rel_path = str(rel) if rel else ""
        scene_bg = self.scene.scene_bg_layers[bg_index]
        if scene_bg.background == rel_path:
            return
        scene_bg.background = rel_path
        if rel_path:
            self._get_background(rel_path)
            scene_bg.ensure_parallax_bands(self._background_height_for_scene_bg(scene_bg))
        self._mark_dirty()
        self._sync_band_controls()
        self._refresh_map()

    def _on_scene_bg_band_parallax_toggled(self, enabled: bool) -> None:
        if not self.scene:
            return
        index = self._active_scene_bg_layer_index()
        if index < 0:
            return
        scene_bg = self.scene.scene_bg_layers[index]
        scene_bg.band_parallax = enabled
        if enabled:
            if not scene_bg.background:
                QMessageBox.information(
                    self,
                    "Band Parallax",
                    "Assign a background asset before enabling band parallax.",
                )
                self.scene_bg_band_parallax.blockSignals(True)
                self.scene_bg_band_parallax.setChecked(False)
                self.scene_bg_band_parallax.blockSignals(False)
                scene_bg.band_parallax = False
                return
            scene_bg.ensure_parallax_bands(self._background_height_for_scene_bg(scene_bg))
        self._mark_dirty()
        self._update_scene_bg_parallax_enabled(scene_bg)
        self._sync_band_controls()
        self._refresh_map()

    def _on_band_changed(self, index: int) -> None:
        if not self.scene or index < 0:
            return
        scene_bg_index = self._active_scene_bg_layer_index()
        if scene_bg_index < 0:
            return
        scene_bg = self.scene.scene_bg_layers[scene_bg_index]
        if index >= len(scene_bg.parallax_bands):
            return
        self._load_band_fields(scene_bg.parallax_bands[index])
        self._refresh_map()

    def _on_band_fields_changed(self) -> None:
        if not self.scene:
            return
        scene_bg_index = self._active_scene_bg_layer_index()
        band_index = self._active_band_index()
        if scene_bg_index < 0 or band_index < 0:
            return
        scene_bg = self.scene.scene_bg_layers[scene_bg_index]
        if band_index >= len(scene_bg.parallax_bands):
            return
        self._save_band_fields(scene_bg.parallax_bands[band_index])
        label = f"{band_index}: Y {scene_bg.parallax_bands[band_index].y0}–{scene_bg.parallax_bands[band_index].y1}"
        self.band_combo.blockSignals(True)
        self.band_combo.setItemText(band_index, label)
        self.band_combo.blockSignals(False)
        self._mark_dirty()
        self._refresh_map()

    def _add_parallax_band(self) -> None:
        if not self.scene:
            return
        scene_bg_index = self._active_scene_bg_layer_index()
        if scene_bg_index < 0:
            return
        scene_bg = self.scene.scene_bg_layers[scene_bg_index]
        if len(scene_bg.parallax_bands) >= MAX_PARALLAX_BANDS:
            QMessageBox.warning(self, "Add Band", f"Maximum {MAX_PARALLAX_BANDS} parallax bands.")
            return
        bg_height = self._background_height_for_scene_bg(scene_bg)
        y1 = max(0, bg_height - 1)
        if scene_bg.parallax_bands:
            last = scene_bg.parallax_bands[-1]
            y0 = min(y1, last.y1 + 1)
        else:
            y0 = 0
        if y0 > y1:
            y0 = y1
        scene_bg.parallax_bands.append(SceneBgParallaxBand(y0, y1, parallax_x=scene_bg.parallax_x))
        self._mark_dirty()
        self._sync_band_controls()
        self.band_combo.setCurrentIndex(len(scene_bg.parallax_bands) - 1)
        self._refresh_map()

    def _remove_parallax_band(self) -> None:
        if not self.scene:
            return
        scene_bg_index = self._active_scene_bg_layer_index()
        band_index = self._active_band_index()
        if scene_bg_index < 0 or band_index < 0:
            return
        scene_bg = self.scene.scene_bg_layers[scene_bg_index]
        if len(scene_bg.parallax_bands) <= 1:
            QMessageBox.warning(self, "Remove Band", "Keep at least one parallax band.")
            return
        scene_bg.parallax_bands.pop(band_index)
        self._mark_dirty()
        self._sync_band_controls()
        self._refresh_map()

    def _on_scene_bg_visible_toggled(self, visible: bool) -> None:
        if not self.scene:
            return
        index = self._active_scene_bg_layer_index()
        if 0 <= index < self.scene.scene_bg_layer_count:
            self.scene.scene_bg_layers[index].visible = visible
            self._mark_dirty()
            self._refresh_map()

    def _on_scene_bg_parallax_changed(self) -> None:
        if not self.scene:
            return
        index = self._active_scene_bg_layer_index()
        if index < 0:
            return
        scene_bg = self.scene.scene_bg_layers[index]
        scene_bg.parallax_x = self.scene_bg_parallax_x.value()
        scene_bg.parallax_y = self.scene_bg_parallax_y.value()
        self._mark_dirty()
        self._refresh_map()

    def _on_scene_bg_fixed_toggled(self, fixed: bool) -> None:
        if not self.scene:
            return
        index = self._active_scene_bg_layer_index()
        if index < 0:
            return
        scene_bg = self.scene.scene_bg_layers[index]
        scene_bg.fixed = fixed
        self._update_scene_bg_parallax_enabled(scene_bg)
        self._mark_dirty()
        self._refresh_map()

    def _on_scene_bg_repeat_x_toggled(self, repeat_x: bool) -> None:
        if not self.scene:
            return
        index = self._active_scene_bg_layer_index()
        if index < 0:
            return
        self.scene.scene_bg_layers[index].repeat_x = repeat_x
        self._mark_dirty()
        self._refresh_map()

    def _on_scene_bg_repeat_y_toggled(self, repeat_y: bool) -> None:
        if not self.scene:
            return
        index = self._active_scene_bg_layer_index()
        if index < 0:
            return
        self.scene.scene_bg_layers[index].repeat_y = repeat_y
        self._mark_dirty()
        self._refresh_map()

    def _on_camera_changed(self, _value: int) -> None:
        self._refresh_map()

    def _on_show_backgrounds_toggled(self, _visible: bool) -> None:
        self._refresh_map()

    def _on_show_objects_toggled(self, _visible: bool) -> None:
        self._refresh_map()

    def _on_show_band_guides_toggled(self, _visible: bool) -> None:
        self._refresh_map()

    def _add_scene_bg_layer(self) -> None:
        if not self.scene:
            return
        try:
            index = self.scene.add_scene_bg_layer()
        except ValueError as exc:
            QMessageBox.warning(self, "Add Bg Layer", str(exc))
            return
        self._mark_dirty()
        self._sync_scene_bg_layer_controls()
        self.scene_bg_layer_combo.setCurrentIndex(index)
        self._sync_scene_bg_background_combo()
        self._refresh_map()

    def _remove_scene_bg_layer(self) -> None:
        if not self.scene:
            return
        index = self._active_scene_bg_layer_index()
        if index < 0:
            return
        try:
            self.scene.remove_scene_bg_layer(index)
        except ValueError as exc:
            QMessageBox.warning(self, "Remove Bg Layer", str(exc))
            return
        self._mark_dirty()
        self._sync_scene_bg_layer_controls()
        self._sync_scene_bg_background_combo()
        self._refresh_map()

    def _on_tile_layer_changed(self, index: int) -> None:
        if not self.scene or index < 0:
            return
        self.tile_layer_visible.blockSignals(True)
        self.tile_layer_visible.setChecked(self.scene.tile_layers[index].visible)
        self.tile_layer_visible.blockSignals(False)
        self._sync_tile_layer_tileset_combo()
        self._load_active_tile_layer_tileset()
        self._update_map_size_label()
        self._refresh_map()
        self._refresh_strip()

    def _on_tile_layer_tileset_changed(self, index: int) -> None:
        if not self.scene or index < 0:
            return
        rel = self.tile_layer_tileset_combo.itemData(index)
        rel_path = str(rel) if rel else ""
        tile_layer_index = self._active_tile_layer_index()
        tile_layer = self.scene.tile_layers[tile_layer_index]
        if tile_layer.tileset == rel_path:
            return
        tile_layer.tileset = rel_path
        self.scene.ensure_tile_layer_grid(
            tile_layer_index, tile_size_for_tile_layer(tile_layer, self.project_root)
        )
        self._load_active_tile_layer_tileset()
        self._mark_dirty()
        self._update_map_size_label()
        self._refresh_map()
        self._refresh_strip()

    def _on_tile_layer_visible_toggled(self, visible: bool) -> None:
        if not self.scene:
            return
        index = self.tile_layer_combo.currentIndex()
        if 0 <= index < self.scene.tile_layer_count:
            self.scene.tile_layers[index].visible = visible
            self._mark_dirty()
            self._refresh_map()

    def _on_collision_tile_layer_changed(self, index: int) -> None:
        if not self.scene or index < 0:
            return
        self.scene.set_collision_tile_layer(index)
        self._mark_dirty()
        self._refresh_map()

    def _add_tile_layer(self) -> None:
        if not self.scene:
            return
        try:
            index = self.scene.add_tile_layer(TILE_BLOCK)
        except ValueError as exc:
            QMessageBox.warning(self, "Add Tile Layer", str(exc))
            return
        self._mark_dirty()
        self._sync_tile_layer_controls()
        self.tile_layer_combo.setCurrentIndex(index)
        self._refresh_map()

    def _remove_tile_layer(self) -> None:
        if not self.scene:
            return
        index = self.tile_layer_combo.currentIndex()
        try:
            self.scene.remove_tile_layer(index)
        except ValueError as exc:
            QMessageBox.warning(self, "Remove Tile Layer", str(exc))
            return
        self._mark_dirty()
        self._sync_tile_layer_controls()
        self._refresh_map()

    def _resize_map(self) -> None:
        if not self.scene:
            return
        new_w = self.map_width.value()
        new_h = self.map_height.value()
        if new_w == self.scene.width and new_h == self.scene.height:
            return
        if any(
            any(v != EMPTY_TILE for v in tile_layer.tiles)
            for tile_layer in self.scene.tile_layers
        ):
            reply = QMessageBox.question(
                self,
                "Resize Map",
                "Resample all tile layers to the new map size?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.map_width.setValue(self.scene.width)
                self.map_height.setValue(self.scene.height)
                return
        self.scene.resize_pixels(new_w, new_h, self.project_root)
        self._mark_dirty()
        self._refresh_editor()

    def _reset_map_to_screen(self) -> None:
        self.map_width.setValue(SCREEN_WIDTH)
        self.map_height.setValue(SCREEN_HEIGHT)
        self._resize_map()

    def new_scene(self, path: Path, palette: str) -> None:
        self.file_path = path.resolve()
        self._tilesets_cache.clear()
        self._backgrounds_cache.clear()
        self._bg_palettes_cache.clear()
        self._active_tileset = None
        try:
            self.scene = Scene.create(palette)
        except ValueError as exc:
            QMessageBox.warning(self, "New Scene", str(exc))
            self.scene = None
            self.file_path = None
            return
        self._dirty = True
        self._selected_tile = 0
        self._open_scene_data()

    def open_scene(self, path: Path) -> None:
        self.file_path = path.resolve()
        self._tilesets_cache.clear()
        self._backgrounds_cache.clear()
        self._bg_palettes_cache.clear()
        self._active_tileset = None
        try:
            self.scene = load_scene(self.file_path, project_root=self.project_root)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Open Scene", str(exc))
            self.scene = None
            self.file_path = None
            return
        self._dirty = False
        self._selected_tile = 0
        self._open_scene_data()

    def _open_scene_data(self) -> None:
        if not self.scene:
            return
        try:
            self._load_palette_for_scene()
            self.scene.ensure_all_tile_layer_grids(self.project_root)
            for tile_layer in self.scene.tile_layers:
                if tile_layer.tileset:
                    self._get_tileset(tile_layer.tileset)
            for scene_bg in self.scene.scene_bg_layers:
                if scene_bg.background:
                    self._get_background(scene_bg.background)
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
        save_scene(self.scene, self.file_path, project_root=self.project_root)
        self._dirty = False
        self._update_status()
        self.saved.emit(self.file_path)

    def has_unsaved_changes(self) -> bool:
        return self._dirty
