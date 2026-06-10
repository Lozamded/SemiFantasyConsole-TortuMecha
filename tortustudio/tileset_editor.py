"""Tileset editor: import sheet → edit one tile → save to stack."""

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
    QGridLayout,
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

from tortuengine.image import load_image
from tortuengine.palette import (
    PAINTABLE_INDICES,
    TRANSPARENT_INDEX,
    list_palette_names,
    load_palette,
    palette_path,
)
from tortuengine.tileset import (
    COLLISION_NONE,
    COLLISION_TYPES,
    ONE_WAY_NONE,
    ONE_WAY_TYPES,
    Tileset,
    import_sidecar_path,
    load_tileset,
    save_tileset,
    surface_tile_to_pixels,
)


class Tool(str, Enum):
    PENCIL = "pencil"
    ERASER = "eraser"
    EYEDROPPER = "eyedropper"


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


class TilesetStripCanvas(QWidget):
    """Horizontal tile stack preview — click to load a tile into the editor."""

    SELECTION_COLOR = (255, 220, 80)
    GRID_COLOR = (36, 36, 50)
    EMPTY_BG = (48, 48, 60)

    tile_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tileset: Tileset | None = None
        self.palette: list[tuple[int, int, int]] = []
        self.selected_index = 0
        self.cell_size = 32
        self._cols = 1
        self._rows = 0
        self.setMinimumHeight(self.cell_size + 8)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_tileset(self, tileset: Tileset | None, palette: list[tuple[int, int, int]]) -> None:
        self.tileset = tileset
        self.palette = palette
        if tileset:
            self._cols = tileset.strip_columns
            self._rows = max(1, tileset.strip_rows) if tileset.tiles else 1
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

            tile_img = pygame.Surface((size, size), pygame.SRCALPHA)
            for ly in range(size):
                for lx in range(size):
                    index = tile[ly * size + lx]
                    if index == TRANSPARENT_INDEX:
                        tile_img.set_at((lx, ly), (*self.EMPTY_BG, 255))
                    else:
                        rgb = self.palette[index]
                        tile_img.set_at((lx, ly), (*rgb, 255))

            data = pygame.image.tobytes(tile_img, "RGBA")
            qimg = QImage(data, size, size, size * 4, QImage.Format.Format_RGBA8888)
            scaled = qimg.scaled(
                self.cell_size,
                self.cell_size,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            painter.drawImage(cell_x, cell_y, scaled)

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

        self.import_canvas = ImportImageCanvas()
        self.import_canvas.tile_clicked.connect(self._on_import_tile_clicked)

        self.edit_canvas = SingleTileCanvas()
        self.edit_canvas.changed.connect(self._on_buffer_changed)

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
        self.show_edit_pixel_grid.toggled.connect(self.edit_canvas.set_show_pixel_grid)

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

        self.btn_save = QPushButton("Save tileset")
        self.btn_save.clicked.connect(self.save)
        self.btn_new = QPushButton("New Tileset…")
        self.btn_new.clicked.connect(self.new_tileset_requested.emit)
        self.btn_open = QPushButton("Open Tileset…")
        self.btn_open.clicked.connect(self.open_tileset_requested.emit)
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
        self.btn_save_to_stack.setToolTip("Add the edited tile to the stack, or replace the selected slot")
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

    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        file_row = QHBoxLayout()
        file_row.addWidget(self.btn_new)
        file_row.addWidget(self.btn_open)
        file_row.addWidget(self.btn_save)
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
        import_layout.addWidget(self.btn_save_all)
        canvases.addWidget(import_group, stretch=1)

        edit_group = QGroupBox("Edit tile")
        edit_layout = QVBoxLayout(edit_group)
        edit_scroll = QScrollArea()
        edit_scroll.setWidgetResizable(True)
        edit_scroll.setWidget(self.edit_canvas)
        edit_layout.addWidget(edit_scroll)
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

        tools = QHBoxLayout()
        tools.addWidget(self.btn_pencil)
        tools.addWidget(self.btn_eraser)
        tools.addWidget(self.btn_dropper)
        side.addLayout(tools)

        side.addWidget(QLabel("Palette colors (0–62):"))
        side.addWidget(self.swatches_area)
        side.addStretch()
        canvases.addLayout(side)

        strip_group = QGroupBox("Tile stack")
        strip_layout = QVBoxLayout(strip_group)
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

    def _sync_tile_size_to_import(self) -> None:
        self.import_canvas.set_tile_size(self.tile_size.value())

    def _on_buffer_changed(self) -> None:
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

    def _on_one_way_changed(self, value: str) -> None:
        if not self.tileset or not value:
            return
        if self._stack_index < self.tileset.tile_count:
            self.tileset.set_one_way(self._stack_index, value)
            self._mark_dirty()
        else:
            self._pending_one_way = value

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
            "Discard unsaved changes in the editor?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Discard

    def _load_buffer_from_stack(self, index: int) -> None:
        if not self.tileset:
            return
        if index < self.tileset.tile_count:
            pixels = self.tileset.get_tile(index)
        else:
            pixels = self.tileset.blank_tile()
        self.edit_canvas.set_tile(pixels, self.tileset.tile_size, self._palette_colors)
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
            self.strip_canvas.set_tileset(self.tileset, self._palette_colors)
            self.strip_canvas.set_selected_index(self._stack_index)
            self._update_stack_label()
            self._update_stack_index_limits()

    def _refresh_editor(self) -> None:
        if self.tileset:
            self._load_buffer_from_stack(self._stack_index)
            self._refresh_strip()

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
        self._buffer_dirty = True
        self._update_editor_status()

    def _save_to_stack(self) -> None:
        if not self.tileset:
            return
        pixels = self.edit_canvas.get_pixels()
        index = self.tileset.save_tile(
            self._stack_index,
            pixels,
            collision=self.collision_combobox.currentText(),
            one_way=self.one_way_combobox.currentText(),
        )
        self._pending_collision = COLLISION_NONE
        self._pending_one_way = ONE_WAY_NONE
        self._dirty = True
        self._buffer_dirty = False
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

    def _clear_editor(self) -> None:
        if not self.tileset:
            return
        self.edit_canvas.clear_tile(self.tileset.tile_size)
        self._buffer_dirty = True
        self._update_editor_status()

    def open_tileset(self, path: Path) -> None:
        self.file_path = path.resolve()
        self.tileset = load_tileset(self.file_path)
        self._dirty = False
        self._buffer_dirty = False
        self._pending_collision = COLLISION_NONE
        self._pending_one_way = ONE_WAY_NONE

        self.tile_size.blockSignals(True)
        self.tile_size.setValue(self.tileset.tile_size)
        self.tile_size.blockSignals(False)

        self._reload_palette_names()
        self.palette_combo.setCurrentText(self.tileset.palette)
        self._load_palette_colors()
        self._sync_tile_size_to_import()
        self._try_load_import_sidecar()
        self._set_stack_index(0)

    def new_tileset(self, path: Path, palette: str, tile_size: int = 8) -> None:
        self.file_path = path.resolve()
        self.tileset = Tileset.create(palette, tile_size=tile_size)
        self._dirty = True
        self._buffer_dirty = False
        self._pending_collision = COLLISION_NONE
        self._pending_one_way = ONE_WAY_NONE
        self._import_image = None
        self.import_canvas.set_image(None)

        self.tile_size.blockSignals(True)
        self.tile_size.setValue(tile_size)
        self.tile_size.blockSignals(False)

        self._reload_palette_names()
        self.palette_combo.setCurrentText(palette)
        self._load_palette_colors()
        self._sync_tile_size_to_import()
        self._set_stack_index(0)

    def save(self) -> None:
        if not self.tileset or not self.file_path:
            return
        save_tileset(self.tileset, self.file_path)
        self._dirty = False
        self.saved.emit(self.file_path)

    def _try_load_import_sidecar(self) -> None:
        if not self.file_path:
            return
        sidecar = import_sidecar_path(self.file_path)
        if sidecar.is_file():
            self._set_import_image(load_image(sidecar), save_sidecar=False)

    def _set_import_image(self, surface: pygame.Surface, save_sidecar: bool = True) -> None:
        self._import_image = surface
        self.import_canvas.set_image(surface)
        if save_sidecar and self.file_path:
            pygame.image.save(surface, str(import_sidecar_path(self.file_path)))

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
        self._set_import_image(load_image(path))

    def has_unsaved_changes(self) -> bool:
        return self._dirty or self._buffer_dirty
