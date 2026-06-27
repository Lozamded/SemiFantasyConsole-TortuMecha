"""Sprite font editor — paint HUD glyphs on a 4×4 block grid."""

from __future__ import annotations

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
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH, SPRITE_BLOCK
from tortuengine.image import load_image
from tortustudio.color_key_widget import ColorKeyWidget
from tortuengine.palette import (
    PAINTABLE_INDICES,
    TRANSPARENT_INDEX,
    list_palette_names,
    load_palette,
    palette_path,
)
from tortuengine.sprite_font import (
    MAX_GLYPH_BLOCKS,
    MIN_GLYPH_BLOCKS,
    TortuGlyph,
    TortuSpriteFont,
    is_base_character,
    load_sprite_font,
    render_sprite_text_line,
    save_sprite_font,
    surface_glyph_to_pixels,
)
from tortustudio.new_sprite_font_dialog import NewSpriteFontDialog


class Tool(str, Enum):
    PENCIL = "pencil"
    ERASER = "eraser"
    EYEDROPPER = "eyedropper"


class ImportGlyphCanvas(QWidget):
    """Source sheet — click a glyph cell to select the import region."""

    PIXEL_GRID_COLOR = (72, 72, 92)
    CELL_GRID_COLOR = (36, 36, 50)
    CELL_GRID_WIDTH = 2
    SELECTION_COLOR = (255, 220, 80)

    cell_clicked = pyqtSignal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.zoom = 8
        self.cell_w = 8
        self.cell_h = 8
        self.show_pixel_grid = False
        self.show_cell_grid = True
        self.selected_cell_x = 0
        self.selected_cell_y = 0
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

    def set_cell_size(self, width: int, height: int) -> None:
        self.cell_w = max(1, width)
        self.cell_h = max(1, height)
        self.update()

    def set_selected_cell(self, cx: int, cy: int) -> None:
        self.selected_cell_x = cx
        self.selected_cell_y = cy
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

        cells_w = self._image_w // self.cell_w if self.cell_w else 0
        cells_h = self._image_h // self.cell_h if self.cell_h else 0
        if self.selected_cell_x < cells_w and self.selected_cell_y < cells_h:
            tx = self.selected_cell_x * self.cell_w * self.zoom
            ty = self.selected_cell_y * self.cell_h * self.zoom
            sw = self.cell_w * self.zoom
            sh = self.cell_h * self.zoom
            pen = QPen(QColor(*self.SELECTION_COLOR))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(ox + tx, oy + ty, sw, sh)

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
        if self.show_cell_grid and self.cell_w and self.cell_h:
            pen = QPen(QColor(*self.CELL_GRID_COLOR))
            pen.setWidth(self.CELL_GRID_WIDTH)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(self.cell_w, pw, self.cell_w):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for py in range(self.cell_h, ph, self.cell_h):
                ly = oy + py * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = self._event_to_pixel(event)
        if not pos:
            return
        cx = pos[0] // self.cell_w
        cy = pos[1] // self.cell_h
        if cx >= self._image_w // self.cell_w or cy >= self._image_h // self.cell_h:
            return
        self.set_selected_cell(cx, cy)
        self.cell_clicked.emit(cx, cy)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_zoom(self.zoom + 2)
        elif delta < 0:
            self.set_zoom(self.zoom - 2)


class GlyphCanvas(QWidget):
    """Zoomed single-glyph paint surface."""

    PIXEL_GRID_COLOR = (72, 72, 92)
    BLOCK_GRID_COLOR = (36, 36, 50)
    BLOCK_GRID_WIDTH = 2

    changed = pyqtSignal()
    tool_cycled = pyqtSignal(object)

    _TOOL_CYCLE = [Tool.PENCIL, Tool.ERASER, Tool.EYEDROPPER]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not pygame.get_init():
            pygame.init()

        self.glyph: TortuGlyph | None = None
        self.palette: list[tuple[int, int, int]] = []
        self.tool = Tool.PENCIL
        self.current_index = 1
        self.zoom = 16
        self.show_pixel_grid = False
        self.show_block_grid = True
        self._drawing = False
        self._frame: QImage | None = None
        self._hover_pixel: tuple[int, int] | None = None

        self.setMinimumSize(200, 200)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_glyph(self, glyph: TortuGlyph | None, palette: list[tuple[int, int, int]]) -> None:
        self.glyph = glyph
        self.palette = palette
        self._refresh()
        self._update_minimum_size()

    def set_show_pixel_grid(self, visible: bool) -> None:
        self.show_pixel_grid = visible
        self.update()

    def set_show_block_grid(self, visible: bool) -> None:
        self.show_block_grid = visible
        self.update()

    def set_tool(self, tool: Tool) -> None:
        self.tool = tool
        self.update()

    def set_color_index(self, index: int) -> None:
        if index in PAINTABLE_INDICES:
            self.current_index = index

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(4, min(32, zoom))
        self._update_minimum_size()
        self._refresh()

    def _glyph_size(self) -> tuple[int, int]:
        if not self.glyph:
            return 0, 0
        return self.glyph.width, self.glyph.height

    def _update_minimum_size(self) -> None:
        w, h = self._glyph_size()
        if w and h:
            self.setMinimumSize(w * self.zoom, h * self.zoom + 20)

    def _get_pixel(self, x: int, y: int) -> int:
        if not self.glyph:
            return TRANSPARENT_INDEX
        w, h = self.glyph.width, self.glyph.height
        if 0 <= x < w and 0 <= y < h:
            return self.glyph.pixels[y * w + x]
        return TRANSPARENT_INDEX

    def _set_pixel(self, x: int, y: int, index: int) -> None:
        if not self.glyph:
            return
        w, h = self.glyph.width, self.glyph.height
        if 0 <= x < w and 0 <= y < h:
            self.glyph.pixels[y * w + x] = index

    def _refresh(self) -> None:
        if not self.glyph:
            self._frame = None
            self.update()
            return

        w, h = self.glyph.width, self.glyph.height
        composite = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            for x in range(w):
                index = self._get_pixel(x, y)
                if index == TRANSPARENT_INDEX:
                    continue
                rgb = self.palette[index]
                composite.set_at((x, y), (*rgb, 255))

        data = pygame.image.tobytes(composite, "RGBA")
        self._frame = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None:
            painter.end()
            return

        scaled = self._frame.scaled(
            self._frame.width() * self.zoom,
            self._frame.height() * self.zoom,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawImage(x, y, scaled)

        w, h = self._glyph_size()
        if w and h and (self.show_pixel_grid or self.show_block_grid):
            sw = w * self.zoom
            sh = h * self.zoom
            if self.show_pixel_grid:
                pen = QPen(QColor(*self.PIXEL_GRID_COLOR))
                pen.setWidth(1)
                pen.setCosmetic(True)
                painter.setPen(pen)
                for px in range(1, w):
                    lx = x + px * self.zoom
                    painter.drawLine(lx, y, lx, y + sh)
                for py in range(1, h):
                    ly = y + py * self.zoom
                    painter.drawLine(x, ly, x + sw, ly)

            if self.show_block_grid:
                pen = QPen(QColor(*self.BLOCK_GRID_COLOR))
                pen.setWidth(self.BLOCK_GRID_WIDTH)
                pen.setCosmetic(True)
                painter.setPen(pen)
                for px in range(SPRITE_BLOCK, w, SPRITE_BLOCK):
                    lx = x + px * self.zoom
                    painter.drawLine(lx, y, lx, y + sh)
                for py in range(SPRITE_BLOCK, h, SPRITE_BLOCK):
                    ly = y + py * self.zoom
                    painter.drawLine(x, ly, x + sw, ly)
        self._draw_cursor_indicator(painter, x, y)
        painter.end()

    def _draw_cursor_indicator(self, painter: QPainter, ox: int, oy: int) -> None:
        if self._frame is None:
            return
        if self.tool == Tool.PENCIL:
            r, g, b = self.palette[self.current_index] if self.palette else (255, 255, 255)
            fill = QColor(r, g, b, 80)
            outline = QColor(255, 255, 255, 220)
        elif self.tool == Tool.ERASER:
            fill = QColor(220, 60, 60, 60)
            outline = QColor(220, 60, 60, 220)
        else:
            fill = QColor(80, 200, 255, 60)
            outline = QColor(80, 200, 255, 220)

        if self._hover_pixel:
            hx, hy = self._hover_pixel
            pen = QPen(outline)
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawRect(ox + hx * self.zoom, oy + hy * self.zoom, self.zoom - 1, self.zoom - 1)

        label = self.tool.value.title()
        painter.save()
        font = painter.font()
        font.setPixelSize(10)
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(label)
        text_h = fm.height()
        img_bottom = oy + self._frame.height() * self.zoom
        lx = ox + 4
        ly = img_bottom + 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.drawRect(lx - 2, ly - 1, text_w + 4, text_h + 2)
        painter.setPen(outline)
        painter.drawText(lx, ly + fm.ascent(), label)
        painter.restore()

    def _event_to_pixel(self, event: QMouseEvent) -> tuple[int, int] | None:
        if not self.glyph or self._frame is None:
            return None

        sw = self._frame.width() * self.zoom
        sh = self._frame.height() * self.zoom
        ox = (self.width() - sw) // 2
        oy = (self.height() - sh) // 2
        px = int((event.position().x() - ox) // self.zoom)
        py = int((event.position().y() - oy) // self.zoom)
        w, h = self.glyph.width, self.glyph.height
        if 0 <= px < w and 0 <= py < h:
            return px, py
        return None

    def _apply_tool(self, x: int, y: int) -> None:
        if not self.glyph:
            return
        if self.tool == Tool.PENCIL:
            self._set_pixel(x, y, self.current_index)
        elif self.tool == Tool.ERASER:
            self._set_pixel(x, y, TRANSPARENT_INDEX)
        elif self.tool == Tool.EYEDROPPER:
            index = self._get_pixel(x, y)
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
        pos = self._event_to_pixel(event)
        self._hover_pixel = pos
        self.update()
        if self._drawing and event.buttons() & Qt.MouseButton.LeftButton and pos:
            self._apply_tool(*pos)
            self.changed.emit()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_pixel = None
        self.update()

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


class SpriteFontEditorWidget(QWidget):
    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_font_requested = pyqtSignal()
    open_font_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.sprite_font: TortuSpriteFont | None = None
        self._palette_colors: list[tuple[int, int, int]] = []
        self._dirty = False
        self._syncing_fields = False
        self._current_char = "A"
        self._swatch_buttons: list[QPushButton] = []
        self._import_image: pygame.Surface | None = None

        from tortustudio.font_editor import TextFontPreviewCanvas

        self.btn_new = QPushButton("New Sprite Font…")
        self.btn_new.clicked.connect(self.new_font_requested.emit)
        self.btn_open = QPushButton("Open…")
        self.btn_open.clicked.connect(self.open_font_requested.emit)
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_font)
        self.status_label = QLabel("No sprite font open")
        self.glyph_count_label = QLabel("Glyphs: —")

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_fields_changed)

        self.blocks_w_spin = QSpinBox()
        self.blocks_w_spin.setRange(MIN_GLYPH_BLOCKS, MAX_GLYPH_BLOCKS)
        self.blocks_w_spin.valueChanged.connect(self._on_glyph_blocks_changed)

        self.blocks_h_spin = QSpinBox()
        self.blocks_h_spin.setRange(MIN_GLYPH_BLOCKS, MAX_GLYPH_BLOCKS)
        self.blocks_h_spin.valueChanged.connect(self._on_glyph_blocks_changed)

        self.pixel_size_label = QLabel()

        self.line_height_spin = QSpinBox()
        self.line_height_spin.setRange(4, MAX_GLYPH_BLOCKS * SPRITE_BLOCK * 2)
        self.line_height_spin.valueChanged.connect(self._on_fields_changed)

        self.advance_spin = QSpinBox()
        self.advance_spin.setRange(1, MAX_GLYPH_BLOCKS * SPRITE_BLOCK * 4)
        self.advance_spin.valueChanged.connect(self._on_advance_changed)

        self.add_char_edit = QLineEdit()
        self.add_char_edit.setPlaceholderText("ñ")
        self.add_char_edit.setMaxLength(1)
        self.add_char_edit.setClearButtonEnabled(True)
        self.btn_add_char = QPushButton("Add character")
        self.btn_add_char.setToolTip("Add one extra character to paint (ñ, 字, …)")
        self.btn_add_char.clicked.connect(self._add_character)
        self.btn_remove_char = QPushButton("Remove character")
        self.btn_remove_char.setToolTip("Remove the selected extra character (base set cannot be removed)")
        self.btn_remove_char.clicked.connect(self._remove_character)

        self.palette_combo = QComboBox()
        self.palette_combo.currentTextChanged.connect(self._on_palette_changed)

        self.preview_text = QPlainTextEdit()
        self.preview_text.setPlainText("SCORE: 1200\nHP: 99")
        self.preview_text.setMaximumHeight(72)
        self.preview_text.textChanged.connect(self._refresh_preview)

        self.preview_scale_spin = QSpinBox()
        self.preview_scale_spin.setRange(1, 4)
        self.preview_scale_spin.setValue(2)
        self.preview_scale_spin.valueChanged.connect(self._on_preview_scale_changed)

        self.show_screen_frame = QCheckBox("Show screen frame")
        self.show_screen_frame.setChecked(True)
        self.show_screen_frame.toggled.connect(self._on_show_screen_frame_toggled)

        self.char_filter_edit = QLineEdit()
        self.char_filter_edit.setPlaceholderText("Search…")
        self.char_filter_edit.setClearButtonEnabled(True)
        self.char_filter_edit.textChanged.connect(self._apply_char_filter)

        self.char_list = QListWidget()
        self.char_list.setMinimumHeight(140)
        self.char_list.currentTextChanged.connect(self._on_char_selected)

        self.import_canvas = ImportGlyphCanvas()
        self.import_canvas.cell_clicked.connect(self._on_import_cell_clicked)
        self.color_key = ColorKeyWidget()
        self.btn_load_import = QPushButton("Load Import Image…")
        self.btn_load_import.clicked.connect(self._load_import_image)
        self.btn_load_to_glyph = QPushButton("Load to Glyph")
        self.btn_load_to_glyph.setToolTip(
            "Palette-convert the selected import cell into the current glyph"
        )
        self.btn_load_to_glyph.clicked.connect(self._load_import_to_glyph)
        self.btn_import_all = QPushButton("Import All Glyphs")
        self.btn_import_all.setToolTip(
            "Convert every cell left-to-right, top-to-bottom into the character list"
        )
        self.btn_import_all.clicked.connect(self._import_all_glyphs)
        self.show_import_pixel_grid = QCheckBox("Import: 1×1 grid")
        self.show_import_pixel_grid.toggled.connect(self._toggle_import_pixel_grid)
        self.show_import_cell_grid = QCheckBox("Import: glyph grid")
        self.show_import_cell_grid.setChecked(True)
        self.show_import_cell_grid.toggled.connect(self._toggle_import_cell_grid)

        self.canvas = GlyphCanvas()
        self.canvas.changed.connect(self._mark_dirty)
        self.canvas.tool_cycled.connect(self._set_tool)

        self.show_1x1_grid = QCheckBox("Show 1×1 Grid")
        self.show_1x1_grid.toggled.connect(self.canvas.set_show_pixel_grid)
        self.show_4x4_grid = QCheckBox("Show 4×4 Grid")
        self.show_4x4_grid.setChecked(True)
        self.show_4x4_grid.toggled.connect(self.canvas.set_show_block_grid)

        self.btn_pencil = QPushButton("Pencil")
        self.btn_eraser = QPushButton("Eraser")
        self.btn_dropper = QPushButton("Eyedropper")
        for btn in (self.btn_pencil, self.btn_eraser, self.btn_dropper):
            btn.setCheckable(True)
        self.btn_pencil.setChecked(True)
        self.btn_pencil.clicked.connect(lambda: self._set_tool(Tool.PENCIL))
        self.btn_eraser.clicked.connect(lambda: self._set_tool(Tool.ERASER))
        self.btn_dropper.clicked.connect(lambda: self._set_tool(Tool.EYEDROPPER))

        self.preview_canvas = TextFontPreviewCanvas()
        self._build_layout()
        self.preview_canvas.set_scale(self.preview_scale_spin.value())
        self._refresh_preview()

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

        preview_page = QWidget()
        preview_layout = QVBoxLayout(preview_page)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(self.preview_canvas, stretch=1)
        preview_hint = QLabel("Colors are baked into glyphs (fixed palette).")
        preview_hint.setStyleSheet("color: #aaa; font-size: 11px;")
        preview_layout.addWidget(preview_hint)

        import_page = QWidget()
        import_layout = QVBoxLayout(import_page)
        import_layout.setContentsMargins(0, 0, 0, 0)
        import_scroll = QScrollArea()
        import_scroll.setWidgetResizable(True)
        import_scroll.setWidget(self.import_canvas)
        import_layout.addWidget(import_scroll, stretch=1)
        import_layout.addWidget(self.btn_load_import)
        import_layout.addWidget(self.color_key)
        import_layout.addWidget(self.btn_load_to_glyph)
        import_layout.addWidget(self.btn_import_all)
        import_grid_row = QHBoxLayout()
        import_grid_row.addWidget(self.show_import_pixel_grid)
        import_grid_row.addWidget(self.show_import_cell_grid)
        import_layout.addLayout(import_grid_row)

        self.left_tabs = QTabWidget()
        self.left_tabs.addTab(preview_page, "Preview")
        self.left_tabs.addTab(import_page, "Import image")
        body.addWidget(self.left_tabs, stretch=1)

        paint_group = QVBoxLayout()
        paint_group.addWidget(QLabel("Glyph editor"))
        paint_group.addWidget(self.canvas, stretch=1)
        tool_row = QHBoxLayout()
        tool_row.addWidget(self.btn_pencil)
        tool_row.addWidget(self.btn_eraser)
        tool_row.addWidget(self.btn_dropper)
        tool_row.addWidget(self.show_1x1_grid)
        tool_row.addWidget(self.show_4x4_grid)
        paint_group.addLayout(tool_row)

        self.swatch_area = QScrollArea()
        self.swatch_area.setWidgetResizable(True)
        self.swatch_area.setMaximumHeight(88)
        self.swatch_widget = QWidget()
        self.swatch_grid = QGridLayout(self.swatch_widget)
        self.swatch_grid.setContentsMargins(0, 0, 0, 0)
        self.swatch_area.setWidget(self.swatch_widget)
        paint_group.addWidget(self.swatch_area)
        body.addLayout(paint_group, stretch=1)

        side_widget = QWidget()
        form = QFormLayout(side_widget)
        form.addRow("Name:", self.name_edit)
        form.addRow("Glyph blocks W:", self.blocks_w_spin)
        form.addRow("Glyph blocks H:", self.blocks_h_spin)
        form.addRow("Glyph size:", self.pixel_size_label)
        form.addRow("Line height:", self.line_height_spin)
        form.addRow("Default advance:", self.advance_spin)
        add_char_row = QHBoxLayout()
        add_char_row.addWidget(self.add_char_edit, stretch=1)
        add_char_row.addWidget(self.btn_add_char)
        form.addRow("Add character:", add_char_row)
        form.addRow(self.btn_remove_char)
        form.addRow("Palette:", self.palette_combo)
        form.addRow("Preview text:", self.preview_text)
        form.addRow("Preview zoom:", self.preview_scale_spin)
        form.addRow(self.show_screen_frame)
        form.addRow("Find character:", self.char_filter_edit)
        form.addRow("Characters:", self.char_list)
        form.addRow(self.glyph_count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(side_widget)
        scroll.setMinimumWidth(240)
        body.addWidget(scroll)

    def set_project_root(self, project_root: Path) -> None:
        self.project_root = project_root
        self._refresh_palette_combo()
        default_palette = palette_path(project_root, "default")
        if default_palette.is_file():
            self._palette_colors = load_palette(default_palette)
            self._build_swatches()

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def new_font(self) -> None:
        dialog = NewSpriteFontDialog(self.project_root, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            sprite_font = TortuSpriteFont.create(
                dialog.font_name,
                dialog.palette_name,
                glyph_blocks_w=dialog.glyph_blocks_w,
                glyph_blocks_h=dialog.glyph_blocks_h,
            )
            self._palette_colors = load_palette(
                palette_path(self.project_root, dialog.palette_name)
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "New Sprite Font", str(exc))
            return

        dest = self.project_root / "assets" / "fonts" / f"{dialog.font_name}.tortuspritefont"
        self.file_path = dest
        self.sprite_font = sprite_font
        self._dirty = True
        self._current_char = sprite_font.resolved_charset()[0] if sprite_font.charset else "A"
        self._build_swatches()
        self._sync_fields()
        self.status_label.setText(f"New: {dest.name}")

    def open_font(self, path: Path) -> None:
        try:
            sprite_font = load_sprite_font(path)
            self._palette_colors = load_palette(
                palette_path(self.project_root, sprite_font.palette)
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Open Sprite Font", str(exc))
            return
        self.file_path = path.resolve()
        self.sprite_font = sprite_font
        self._dirty = False
        chars = sprite_font.resolved_charset()
        self._current_char = chars[0] if chars else "A"
        self._build_swatches()
        self._sync_fields()
        self.status_label.setText(path.name)

    def save(self) -> None:
        if not self.sprite_font or not self.file_path:
            QMessageBox.information(self, "Save Sprite Font", "Nothing to save.")
            return
        self._apply_fields()
        self._apply_current_glyph_advance()
        try:
            save_sprite_font(self.sprite_font, self.file_path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Save Sprite Font", str(exc))
            return
        self._dirty = False
        self.status_label.setText(f"Saved {self.file_path.name}")
        self.saved.emit(self.file_path)

    def _rename_font(self) -> None:
        if not self.sprite_font or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename Sprite Font", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename Sprite Font",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortuspritefont"
        if new_path.exists():
            QMessageBox.warning(self, "Rename Sprite Font", f"{new_path.name} already exists.")
            return
        for sidecar in sorted(old_path.parent.glob(f"{old_path.stem}.*")):
            if sidecar == old_path:
                continue
            sidecar.rename(sidecar.parent / sidecar.name.replace(old_path.stem, new_stem, 1))
        old_path.rename(new_path)
        self.file_path = new_path
        self.status_label.setText(new_path.name)
        self.renamed.emit(old_path, new_path)

    def _apply_fields(self) -> None:
        if not self.sprite_font:
            return
        self.sprite_font.name = self.name_edit.text().strip() or self.sprite_font.name
        self.sprite_font.line_height = self.line_height_spin.value()
        self.sprite_font.default_advance = self.advance_spin.value()
        self.sprite_font.palette = self.palette_combo.currentText()
        self.sprite_font.ensure_glyphs()
        self.sprite_font.sync_metrics()

    def _apply_current_glyph_advance(self) -> None:
        if not self.sprite_font:
            return
        glyph = self.sprite_font.glyphs.get(ord(self._current_char))
        if glyph:
            glyph.advance = self.advance_spin.value()

    def _sync_fields(self) -> None:
        if not self.sprite_font:
            return
        self._syncing_fields = True
        self._refresh_palette_combo()

        self.name_edit.blockSignals(True)
        self.blocks_w_spin.blockSignals(True)
        self.blocks_h_spin.blockSignals(True)
        self.line_height_spin.blockSignals(True)
        self.advance_spin.blockSignals(True)
        self.palette_combo.blockSignals(True)
        self.char_list.blockSignals(True)

        self.name_edit.setText(self.sprite_font.name)
        self.blocks_w_spin.setValue(self.sprite_font.glyph_blocks_w)
        self.blocks_h_spin.setValue(self.sprite_font.glyph_blocks_h)
        self._update_pixel_size_label()
        self.line_height_spin.setValue(self.sprite_font.line_height)
        self.advance_spin.setValue(self.sprite_font.default_advance)
        palette_index = self.palette_combo.findText(self.sprite_font.palette)
        if palette_index >= 0:
            self.palette_combo.setCurrentIndex(palette_index)

        self._rebuild_char_list()
        self._update_remove_char_button()
        self.glyph_count_label.setText(f"Glyphs: {len(self.sprite_font.glyphs)}")

        self.name_edit.blockSignals(False)
        self.blocks_w_spin.blockSignals(False)
        self.blocks_h_spin.blockSignals(False)
        self.line_height_spin.blockSignals(False)
        self.advance_spin.blockSignals(False)
        self.palette_combo.blockSignals(False)
        self.char_list.blockSignals(False)

        self._load_current_glyph_into_canvas()

        self._syncing_fields = False
        self._sync_import_cell_size()
        self._refresh_preview()

    def _sync_import_cell_size(self) -> None:
        if not self.sprite_font:
            return
        self.import_canvas.set_cell_size(
            self.sprite_font.pixel_width,
            self.sprite_font.pixel_height,
        )

    def _toggle_import_pixel_grid(self, visible: bool) -> None:
        self.import_canvas.show_pixel_grid = visible
        self.import_canvas.update()

    def _toggle_import_cell_grid(self, visible: bool) -> None:
        self.import_canvas.show_cell_grid = visible
        self.import_canvas.update()

    def _on_import_cell_clicked(self, _cx: int, _cy: int) -> None:
        pass

    def _set_import_image(self, surface: pygame.Surface | None) -> None:
        self._import_image = surface
        self.import_canvas.set_image(surface)
        if surface is not None:
            self.left_tabs.setCurrentIndex(1)

    def _load_import_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Import Image",
            "",
            "Images (*.png *.bmp *.gif *.jpg *.jpeg);;All files (*)",
        )
        if not path:
            return
        try:
            self._set_import_image(self.color_key.apply_to(load_image(Path(path))))
        except OSError as exc:
            QMessageBox.warning(self, "Load Import Image", str(exc))

    def _load_import_to_glyph(self) -> None:
        if not self.sprite_font or self._import_image is None:
            QMessageBox.information(
                self,
                "Load to Glyph",
                "Open a sprite font and load an import image first.",
            )
            return
        if not self._palette_colors:
            return
        glyph = self.sprite_font.glyphs.get(ord(self._current_char))
        if glyph is None:
            return
        pixels = surface_glyph_to_pixels(
            self._import_image,
            self.import_canvas.selected_cell_x,
            self.import_canvas.selected_cell_y,
            glyph.width,
            glyph.height,
            self._palette_colors,
        )
        glyph.pixels = pixels
        self._load_current_glyph_into_canvas()
        self._mark_dirty()
        self._refresh_preview()

    def _import_all_glyphs(self) -> None:
        if not self.sprite_font or self._import_image is None:
            QMessageBox.information(
                self,
                "Import All Glyphs",
                "Open a sprite font and load an import image first.",
            )
            return
        if not self._palette_colors:
            return

        gw = self.sprite_font.pixel_width
        gh = self.sprite_font.pixel_height
        if gw < 1 or gh < 1:
            return
        cells_w = self._import_image.get_width() // gw
        cells_h = self._import_image.get_height() // gh
        if cells_w == 0 or cells_h == 0:
            QMessageBox.warning(
                self,
                "Import All Glyphs",
                "Import image is smaller than one glyph cell.",
            )
            return

        chars = self.sprite_font.resolved_charset()
        total_cells = cells_w * cells_h
        count = min(len(chars), total_cells)
        reply = QMessageBox.question(
            self,
            "Import All Glyphs",
            f"Convert {count} cells into the character list "
            f"({cells_w}×{cells_h} grid, left-to-right)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.sprite_font.ensure_glyphs()
        for index, char in enumerate(chars):
            if index >= total_cells:
                break
            cx = index % cells_w
            cy = index // cells_w
            glyph = self.sprite_font.glyphs.get(ord(char))
            if glyph is None:
                continue
            glyph.pixels = surface_glyph_to_pixels(
                self._import_image,
                cx,
                cy,
                gw,
                gh,
                self._palette_colors,
            )

        self._load_current_glyph_into_canvas()
        self._mark_dirty()
        self._refresh_preview()

    def _update_pixel_size_label(self) -> None:
        if not self.sprite_font:
            self.pixel_size_label.setText("—")
            return
        w = self.sprite_font.pixel_width
        h = self.sprite_font.pixel_height
        self.pixel_size_label.setText(
            f"{w} × {h} px ({self.sprite_font.glyph_blocks_w}×{self.sprite_font.glyph_blocks_h} blocks)"
        )

    def _char_list_label(self, char: str) -> str:
        if char == " ":
            return "space"
        if is_base_character(char):
            return char
        code = ord(char)
        return f"{char}  (U+{code:04X})"

    def _rebuild_char_list(self) -> None:
        self.char_list.clear()
        if not self.sprite_font:
            return
        for char in self.sprite_font.resolved_charset():
            item = QListWidgetItem(self._char_list_label(char))
            item.setData(Qt.ItemDataRole.UserRole, char)
            if is_base_character(char):
                item.setToolTip("Base character")
            else:
                item.setToolTip("Extra character — can be removed")
            self.char_list.addItem(item)
            if char == self._current_char:
                self.char_list.setCurrentItem(item)
        self._apply_char_filter()

    def _char_matches_filter(self, char: str, label: str, query: str) -> bool:
        query = query.strip().lower()
        if not query:
            return True
        if query == "space" and char == " ":
            return True
        if len(query) == 1 and char.lower() == query:
            return True
        if query in label.lower() or query in char.lower():
            return True
        code_hex = f"{ord(char):04x}"
        normalized = query.removeprefix("u+").removeprefix("0x")
        return normalized in code_hex

    def _apply_char_filter(self) -> None:
        query = self.char_filter_edit.text()
        for row in range(self.char_list.count()):
            item = self.char_list.item(row)
            if item is None:
                continue
            char = item.data(Qt.ItemDataRole.UserRole)
            hidden = not self._char_matches_filter(char, item.text(), query)
            item.setHidden(hidden)
        if query.strip():
            current = self.char_list.currentItem()
            if current is None or current.isHidden():
                for row in range(self.char_list.count()):
                    item = self.char_list.item(row)
                    if item is not None and not item.isHidden():
                        self.char_list.setCurrentItem(item)
                        break

    def _update_remove_char_button(self) -> None:
        can_remove = bool(
            self.sprite_font
            and self._current_char
            and not is_base_character(self._current_char)
        )
        self.btn_remove_char.setEnabled(can_remove)

    def _add_character(self) -> None:
        if not self.sprite_font:
            return
        char = self.add_char_edit.text()
        if len(char) != 1:
            QMessageBox.information(
                self,
                "Add Character",
                "Enter exactly one character (for example ñ or 字).",
            )
            return
        if self.sprite_font.add_character(char):
            self._apply_current_glyph_advance()
            self._current_char = char
            self.add_char_edit.clear()
            self.char_filter_edit.clear()
            self._rebuild_char_list()
            self._load_current_glyph_into_canvas()
            self._update_remove_char_button()
            self._mark_dirty()
            self._refresh_preview()
            return
        QMessageBox.information(self, "Add Character", f"'{char}' is already in this font.")

    def _remove_character(self) -> None:
        if not self.sprite_font or not self._current_char:
            return
        char = self._current_char
        if is_base_character(char):
            QMessageBox.information(
                self,
                "Remove Character",
                "Base Latin characters cannot be removed.",
            )
            return
        if not self.sprite_font.remove_character(char):
            return
        chars = self.sprite_font.resolved_charset()
        self._current_char = chars[0] if chars else "A"
        self._rebuild_char_list()
        self._load_current_glyph_into_canvas()
        self._update_remove_char_button()
        self.glyph_count_label.setText(f"Glyphs: {len(self.sprite_font.glyphs)}")
        self._mark_dirty()
        self._refresh_preview()

    def _load_current_glyph_into_canvas(self) -> None:
        if not self.sprite_font or not self._palette_colors:
            self.canvas.set_glyph(None, [])
            return
        self.sprite_font.ensure_glyphs()
        glyph = self.sprite_font.glyphs.get(ord(self._current_char))
        self.canvas.set_glyph(glyph, self._palette_colors)
        if glyph:
            self.advance_spin.blockSignals(True)
            self.advance_spin.setValue(glyph.advance)
            self.advance_spin.blockSignals(False)

    def _build_swatches(self) -> None:
        while self.swatch_grid.count():
            item = self.swatch_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._swatch_buttons.clear()
        if not self._palette_colors:
            return
        cols = 16
        for n, index in enumerate(PAINTABLE_INDICES):
            r, g, b = self._palette_colors[index]
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            selected = index == self.canvas.current_index
            border = "2px solid #00dcff" if selected else "1px solid #444"
            btn.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: {border};")
            btn.setToolTip(f"Paint color — index {index}")
            btn.clicked.connect(lambda _checked, i=index: self._pick_color(i))
            self.swatch_grid.addWidget(btn, n // cols, n % cols)
            self._swatch_buttons.append(btn)

    def _pick_color(self, index: int) -> None:
        self.canvas.set_color_index(index)
        self._build_swatches()

    def _set_tool(self, tool: Tool) -> None:
        self.canvas.set_tool(tool)
        self.btn_pencil.setChecked(tool == Tool.PENCIL)
        self.btn_eraser.setChecked(tool == Tool.ERASER)
        self.btn_dropper.setChecked(tool == Tool.EYEDROPPER)

    def _on_char_selected(self, _label: str) -> None:
        if self._syncing_fields or not self.sprite_font:
            return
        item = self.char_list.currentItem()
        if not item:
            return
        char = item.data(Qt.ItemDataRole.UserRole)
        if not char or char == self._current_char:
            return
        self._apply_current_glyph_advance()
        self._current_char = char
        self._load_current_glyph_into_canvas()
        self._update_remove_char_button()

    def _on_glyph_blocks_changed(self, _value: int) -> None:
        if not self.sprite_font or self._syncing_fields:
            return
        try:
            self.sprite_font.resize_glyph_blocks(
                self.blocks_w_spin.value(),
                self.blocks_h_spin.value(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Glyph Size", str(exc))
            return
        self._update_pixel_size_label()
        self.line_height_spin.setValue(self.sprite_font.line_height)
        self._sync_import_cell_size()
        self._load_current_glyph_into_canvas()
        self._mark_dirty()
        self._refresh_preview()

    def _on_advance_changed(self, value: int) -> None:
        if not self.sprite_font or self._syncing_fields:
            return
        glyph = self.sprite_font.glyphs.get(ord(self._current_char))
        if glyph:
            glyph.advance = value
        self.sprite_font.default_advance = value
        self._mark_dirty()
        self._refresh_preview()

    def _on_fields_changed(self) -> None:
        if not self.sprite_font or self._syncing_fields:
            return
        self._apply_fields()
        self._mark_dirty()
        self._refresh_preview()

    def _refresh_palette_combo(self) -> None:
        current = self.palette_combo.currentText() if self.palette_combo.count() else "default"
        names = list_palette_names(self.project_root)
        if not names:
            names = ["default"]
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(names)
        if self.sprite_font:
            current = self.sprite_font.palette
        idx = self.palette_combo.findText(current)
        if idx >= 0:
            self.palette_combo.setCurrentIndex(idx)
        self.palette_combo.blockSignals(False)

    def _on_palette_changed(self, _name: str) -> None:
        if not self.sprite_font or self._syncing_fields:
            return
        path = palette_path(self.project_root, self.palette_combo.currentText())
        if path.is_file():
            self._palette_colors = load_palette(path)
        self.sprite_font.palette = self.palette_combo.currentText()
        self._build_swatches()
        self._load_current_glyph_into_canvas()
        self._refresh_preview()
        self._mark_dirty()

    def _refresh_preview(self) -> None:
        from tortustudio.font_editor import TextFontPreviewCanvas

        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        screen.fill(
            (
                TextFontPreviewCanvas.SCREEN_BG[0],
                TextFontPreviewCanvas.SCREEN_BG[1],
                TextFontPreviewCanvas.SCREEN_BG[2],
                255,
            )
        )
        if self.sprite_font and self._palette_colors:
            lines = self.preview_text.toPlainText().splitlines() or ["Aa"]
            y = TextFontPreviewCanvas.TEXT_MARGIN
            for line in lines:
                if y + self.sprite_font.line_height > SCREEN_HEIGHT:
                    break
                if line:
                    try:
                        line_surface = render_sprite_text_line(
                            self.sprite_font,
                            line,
                            self._palette_colors,
                        )
                        screen.blit(line_surface, (TextFontPreviewCanvas.TEXT_MARGIN, y))
                    except (KeyError, IndexError):
                        pass
                y += self.sprite_font.line_height
        self.preview_canvas.set_screen_preview(screen)

    def _on_preview_scale_changed(self, value: int) -> None:
        self.preview_canvas.set_scale(value)

    def _on_show_screen_frame_toggled(self, checked: bool) -> None:
        self.preview_canvas.set_show_screen_frame(checked)

    def _mark_dirty(self) -> None:
        self._dirty = True
        if self.file_path:
            self.status_label.setText(f"{self.file_path.name} *")
