"""Pygame-based sprite editor embedded in Qt."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tortuengine.image import load_image
from tortustudio.color_key_widget import ColorKeyWidget
from tortuengine.constants import SPRITE_BLOCK
from tortuengine.palette import (
    PAINTABLE_INDICES,
    TRANSPARENT_INDEX,
    list_palette_names,
    load_palette,
    palette_path,
)
from tortuengine.sprite import (
    Sprite,
    load_sprite,
    reference_sidecar_path,
    save_all_sprite_frame_pngs,
    save_sprite,
    save_sprite_frame_png,
)


class Tool(str, Enum):
    PENCIL = "pencil"
    ERASER = "eraser"
    EYEDROPPER = "eyedropper"


class SpriteCanvas(QWidget):
    """Zoomed sprite canvas with grid, reference overlay, and painting."""

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

        self.sprite: Sprite | None = None
        self.palette: list[tuple[int, int, int]] = []
        self.tool = Tool.PENCIL
        self.current_index = 0
        self.zoom = 16
        self.reference: pygame.Surface | None = None
        self.reference_opacity = 128
        self.show_pixel_grid = False
        self.show_block_grid = True
        self._drawing = False
        self._frame: QImage | None = None
        self._hover_pixel: tuple[int, int] | None = None

        self.setMinimumSize(200, 200)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_sprite(self, sprite: Sprite, palette: list[tuple[int, int, int]]) -> None:
        self.sprite = sprite
        self.palette = palette
        self._refresh()
        self._update_minimum_size()

    def set_reference(self, surface: pygame.Surface | None) -> None:
        self.reference = surface
        self._refresh()

    def set_reference_opacity(self, value: int) -> None:
        self.reference_opacity = max(0, min(255, value))
        self._refresh()

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

    def _update_minimum_size(self) -> None:
        if not self.sprite:
            return
        w, h = self.sprite.pixel_width, self.sprite.pixel_height
        self.setMinimumSize(w * self.zoom, h * self.zoom + 20)

    def _refresh(self) -> None:
        if not self.sprite:
            self._frame = None
            self.update()
            return

        w, h = self.sprite.pixel_width, self.sprite.pixel_height
        composite = pygame.Surface((w, h), pygame.SRCALPHA)

        ref_surface: pygame.Surface | None = None
        if self.reference is not None:
            ref_surface = pygame.transform.scale(self.reference, (w, h))
            ref_surface.set_alpha(self.reference_opacity)

        for y in range(h):
            for x in range(w):
                if ref_surface is not None:
                    composite.set_at((x, y), ref_surface.get_at((x, y)))
                index = self.sprite.get_pixel(x, y)
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
        if self.sprite and (self.show_pixel_grid or self.show_block_grid):
            self._draw_grid_overlay(painter, x, y)
        self._draw_cursor_indicator(painter, x, y)
        painter.end()

    def _draw_grid_overlay(self, painter: QPainter, ox: int, oy: int) -> None:
        if not self.sprite:
            return

        pw = self.sprite.pixel_width
        ph = self.sprite.pixel_height
        sw = pw * self.zoom
        sh = ph * self.zoom

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

        if self.show_block_grid:
            pen = QPen(QColor(*self.BLOCK_GRID_COLOR))
            pen.setWidth(self.BLOCK_GRID_WIDTH)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(SPRITE_BLOCK, pw, SPRITE_BLOCK):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for py in range(SPRITE_BLOCK, ph, SPRITE_BLOCK):
                ly = oy + py * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)

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
        if not self.sprite or self._frame is None:
            return None

        sw = self._frame.width() * self.zoom
        sh = self._frame.height() * self.zoom
        ox = (self.width() - sw) // 2
        oy = (self.height() - sh) // 2
        px = int((event.position().x() - ox) // self.zoom)
        py = int((event.position().y() - oy) // self.zoom)
        if 0 <= px < self.sprite.pixel_width and 0 <= py < self.sprite.pixel_height:
            return px, py
        return None

    def _apply_tool(self, x: int, y: int) -> None:
        if not self.sprite:
            return
        if self.tool == Tool.PENCIL:
            self.sprite.set_pixel(x, y, self.current_index)
        elif self.tool == Tool.ERASER:
            self.sprite.set_pixel(x, y, TRANSPARENT_INDEX)
        elif self.tool == Tool.EYEDROPPER:
            index = self.sprite.get_pixel(x, y)
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


class SpriteEditorWidget(QWidget):
    """Sprite editor panel: canvas, tools, palette swatches, reference import."""

    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_sprite_requested = pyqtSignal()
    open_sprite_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.sprite: Sprite | None = None
        self._palette_colors: list[tuple[int, int, int]] = []
        self._dirty = False
        self._playing = False

        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._on_playback_tick)

        self.canvas = SpriteCanvas()
        self.canvas.changed.connect(self._mark_dirty)
        self.canvas.tool_cycled.connect(self._set_tool)

        self.blocks_w = QSpinBox()
        self.blocks_w.setRange(1, 32)
        self.blocks_h = QSpinBox()
        self.blocks_h.setRange(1, 32)
        self.pixel_size_label = QLabel()

        self.show_1x1_grid = QCheckBox("Show 1×1 Grid")
        self.show_1x1_grid.setChecked(False)
        self.show_1x1_grid.setToolTip("Light gaps between every pixel")
        self.show_1x1_grid.toggled.connect(self.canvas.set_show_pixel_grid)

        self.show_4x4_grid = QCheckBox("Show 4×4 Grid")
        self.show_4x4_grid.setChecked(True)
        self.show_4x4_grid.setToolTip("Dark gaps between 4×4 blocks")
        self.show_4x4_grid.toggled.connect(self.canvas.set_show_block_grid)
        self.palette_combo = QComboBox()
        self.palette_combo.currentTextChanged.connect(self._on_palette_changed)

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

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_sprite)
        self.btn_new = QPushButton("New Sprite…")
        self.btn_new.clicked.connect(self.new_sprite_requested.emit)
        self.btn_open = QPushButton("Open Sprite…")
        self.btn_open.clicked.connect(self.open_sprite_requested.emit)
        self.btn_load_ref = QPushButton("Load Reference…")
        self.btn_load_ref.clicked.connect(self._load_reference)
        self.color_key = ColorKeyWidget()
        self.btn_convert = QPushButton("Convert to Current Palette")
        self.btn_convert.clicked.connect(self._convert_reference)
        self.btn_convert.setEnabled(False)

        self.frame_spin = QSpinBox()
        self.frame_spin.setMinimum(1)
        self.frame_spin.valueChanged.connect(self._on_frame_spin_changed)
        self.frame_label = QLabel("1 / 1")
        self.btn_frame_prev = QPushButton("◀")
        self.btn_frame_prev.setFixedWidth(32)
        self.btn_frame_prev.clicked.connect(self._prev_frame)
        self.btn_frame_next = QPushButton("▶")
        self.btn_frame_next.setFixedWidth(32)
        self.btn_frame_next.clicked.connect(self._next_frame)
        self.btn_frame_add = QPushButton("+ Frame")
        self.btn_frame_add.clicked.connect(self._add_frame)
        self.btn_frame_dup = QPushButton("Duplicate")
        self.btn_frame_dup.clicked.connect(self._duplicate_frame)
        self.btn_frame_del = QPushButton("Delete")
        self.btn_frame_del.clicked.connect(self._delete_frame)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(8)
        self.fps_spin.valueChanged.connect(self._on_fps_changed)

        self.btn_playback = QPushButton("Play")
        self.btn_playback.setCheckable(True)
        self.btn_playback.clicked.connect(self._toggle_playback)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.25, 4.0)
        self.speed_spin.setSingleStep(0.25)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSuffix("×")
        self.speed_spin.setToolTip("Playback speed multiplier")
        self.speed_spin.valueChanged.connect(self._update_playback_interval)

        self.ref_opacity = QSlider(Qt.Orientation.Horizontal)
        self.ref_opacity.setRange(0, 255)
        self.ref_opacity.setValue(128)
        self.ref_opacity.valueChanged.connect(self.canvas.set_reference_opacity)

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
        file_row.addWidget(self.btn_rename)
        file_row.addStretch()
        outer.addLayout(file_row)

        frame_row = QHBoxLayout()
        frame_row.addWidget(QLabel("Frame:"))
        frame_row.addWidget(self.btn_frame_prev)
        frame_row.addWidget(self.frame_spin)
        frame_row.addWidget(self.frame_label)
        frame_row.addWidget(self.btn_frame_next)
        frame_row.addWidget(self.btn_frame_add)
        frame_row.addWidget(self.btn_frame_dup)
        frame_row.addWidget(self.btn_frame_del)
        frame_row.addWidget(QLabel("  "))
        frame_row.addWidget(self.btn_playback)
        frame_row.addWidget(QLabel("Speed:"))
        frame_row.addWidget(self.speed_spin)
        frame_row.addStretch()
        frame_row.addWidget(QLabel("FPS:"))
        frame_row.addWidget(self.fps_spin)
        outer.addLayout(frame_row)

        root = QHBoxLayout()
        outer.addLayout(root, stretch=1)

        canvas_col = QVBoxLayout()
        canvas_col.addWidget(self.canvas, stretch=1)
        tools = QHBoxLayout()
        tools.addWidget(self.btn_pencil)
        tools.addWidget(self.btn_eraser)
        tools.addWidget(self.btn_dropper)
        tools.addStretch()
        canvas_col.addLayout(tools)
        root.addLayout(canvas_col, stretch=1)

        side = QVBoxLayout()
        title = QLabel("<b>Sprite Editor</b>")
        side.addWidget(title)

        form = QFormLayout()
        form.addRow("Blocks wide:", self.blocks_w)
        form.addRow("Blocks tall:", self.blocks_h)
        form.addRow("Pixel size:", self.pixel_size_label)
        form.addRow("Palette:", self.palette_combo)
        form.addRow("Show pixel Grid:", self.show_1x1_grid)
        form.addRow("Show block Grid:", self.show_4x4_grid)
        side.addLayout(form)

        self.blocks_w.valueChanged.connect(self._apply_resize)
        self.blocks_h.valueChanged.connect(self._apply_resize)

        side.addWidget(self.btn_load_ref)
        side.addWidget(self.color_key)
        side.addWidget(self.btn_convert)
        side.addWidget(QLabel("Reference opacity:"))
        side.addWidget(self.ref_opacity)

        side.addWidget(QLabel("Palette colors (0–62):"))
        side.addWidget(self.swatches_area)
        side.addStretch()
        root.addLayout(side)

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
        self.canvas.set_tool(tool)

    def _update_size_label(self) -> None:
        if not self.sprite:
            return
        self.pixel_size_label.setText(
            f"{self.sprite.pixel_width} × {self.sprite.pixel_height} px"
        )

    def _apply_resize(self) -> None:
        if not self.sprite:
            return
        new_w, new_h = self.blocks_w.value(), self.blocks_h.value()
        if new_w == self.sprite.blocks_w and new_h == self.sprite.blocks_h:
            return
        if any(self.sprite.frame_has_pixels(i) for i in range(self.sprite.frame_count)):
            reply = QMessageBox.question(
                self,
                "Resize Sprite",
                "Resize canvas? Pixels outside the new area will be cropped on all frames.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.blocks_w.blockSignals(True)
                self.blocks_h.blockSignals(True)
                self.blocks_w.setValue(self.sprite.blocks_w)
                self.blocks_h.setValue(self.sprite.blocks_h)
                self.blocks_w.blockSignals(False)
                self.blocks_h.blockSignals(False)
                return
        self.sprite.resize(new_w, new_h)
        self._dirty = True
        self._refresh_canvas()

    def _on_palette_changed(self, name: str) -> None:
        if not self.sprite or not name:
            return
        if self.sprite.palette != name and self.sprite.any_frame_has_pixels():
            reply = QMessageBox.question(
                self,
                "Change Palette",
                "Change palette? Pixel indices stay the same but colors will change.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.palette_combo.blockSignals(True)
                self.palette_combo.setCurrentText(self.sprite.palette)
                self.palette_combo.blockSignals(False)
                return
        self.sprite.palette = name
        self._load_palette_colors()
        self._dirty = True
        self._refresh_canvas()

    def _load_palette_colors(self) -> None:
        if not self.sprite:
            return
        path = palette_path(self.project_root, self.sprite.palette)
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
        self.canvas.set_color_index(index)
        self._set_tool(Tool.PENCIL)

    def _sync_frame_controls(self) -> None:
        if not self.sprite:
            self.frame_spin.setMaximum(1)
            self.frame_spin.setValue(1)
            self.frame_label.setText("1 / 1")
            self.btn_playback.setEnabled(False)
            return

        count = self.sprite.frame_count
        current = self.sprite.current_frame + 1
        self.frame_spin.blockSignals(True)
        self.frame_spin.setMaximum(count)
        self.frame_spin.setValue(current)
        self.frame_spin.blockSignals(False)
        self.frame_label.setText(f"{current} / {count}")
        self.btn_frame_del.setEnabled(count > 1)
        self.btn_playback.setEnabled(count > 1)

    def _playback_interval_ms(self) -> int:
        fps = self.fps_spin.value() if self.sprite else 8
        speed = self.speed_spin.value()
        interval = int(1000 / max(fps * speed, 1))
        return max(interval, 16)

    def _update_playback_interval(self) -> None:
        if self._playing:
            self._playback_timer.setInterval(self._playback_interval_ms())

    def _toggle_playback(self) -> None:
        if self.btn_playback.isChecked():
            self._start_playback()
        else:
            self._stop_playback()

    def _start_playback(self) -> None:
        if not self.sprite or self.sprite.frame_count <= 1:
            self.btn_playback.setChecked(False)
            return
        self._save_reference_sidecar()
        self.canvas.set_reference(None)
        self._playing = True
        self.btn_playback.setText("Stop")
        self._playback_timer.start(self._playback_interval_ms())

    def _stop_playback(self) -> None:
        if not self._playing and not self.btn_playback.isChecked():
            return
        self._playing = False
        self._playback_timer.stop()
        self.btn_playback.blockSignals(True)
        self.btn_playback.setChecked(False)
        self.btn_playback.setText("Play")
        self.btn_playback.blockSignals(False)
        self._try_load_reference_sidecar()

    def _on_playback_tick(self) -> None:
        if not self.sprite or self.sprite.frame_count <= 1:
            self._stop_playback()
            return
        next_idx = (self.sprite.current_frame + 1) % self.sprite.frame_count
        self.sprite.select_frame(next_idx)
        self._sync_frame_controls()
        self._refresh_canvas()

    def _select_frame(self, index: int) -> None:
        if not self.sprite:
            return
        self._stop_playback()
        self._save_reference_sidecar()
        self.sprite.select_frame(index)
        self._sync_frame_controls()
        self._try_load_reference_sidecar()
        self._refresh_canvas()

    def _on_frame_spin_changed(self, value: int) -> None:
        if not self.sprite:
            return
        index = value - 1
        if index != self.sprite.current_frame:
            self._select_frame(index)

    def _prev_frame(self) -> None:
        if not self.sprite or self.sprite.current_frame <= 0:
            return
        self._select_frame(self.sprite.current_frame - 1)

    def _next_frame(self) -> None:
        if not self.sprite or self.sprite.current_frame >= self.sprite.frame_count - 1:
            return
        self._select_frame(self.sprite.current_frame + 1)

    def _add_frame(self) -> None:
        if not self.sprite:
            return
        self._save_reference_sidecar()
        self.sprite.add_frame(copy_current=False)
        self.canvas.set_reference(None)
        self.btn_convert.setEnabled(False)
        self._dirty = True
        self._sync_frame_controls()
        self._refresh_canvas()

    def _duplicate_frame(self) -> None:
        if not self.sprite:
            return
        self._save_reference_sidecar()
        self.sprite.duplicate_frame()
        self.canvas.set_reference(None)
        self.btn_convert.setEnabled(False)
        self._dirty = True
        self._sync_frame_controls()
        self._refresh_canvas()

    def _delete_frame(self) -> None:
        if not self.sprite or self.sprite.frame_count <= 1:
            return
        if self.sprite.frame_has_pixels():
            reply = QMessageBox.question(
                self,
                "Delete Frame",
                f"Delete frame {self.sprite.current_frame + 1}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._save_reference_sidecar()
        self.sprite.delete_frame()
        self._dirty = True
        self._sync_frame_controls()
        self._try_load_reference_sidecar()
        self._refresh_canvas()

    def _on_fps_changed(self, value: int) -> None:
        if self.sprite:
            self.sprite.fps = value
            self._dirty = True
        self._update_playback_interval()

    def _refresh_canvas(self) -> None:
        if self.sprite:
            self.canvas.set_sprite(self.sprite, self._palette_colors)
            self._update_size_label()

    def open_sprite(self, path: Path) -> None:
        self._stop_playback()
        self.file_path = path.resolve()
        self.sprite = load_sprite(self.file_path)
        self._dirty = False

        self.blocks_w.blockSignals(True)
        self.blocks_h.blockSignals(True)
        self.blocks_w.setValue(self.sprite.blocks_w)
        self.blocks_h.setValue(self.sprite.blocks_h)
        self.blocks_w.blockSignals(False)
        self.blocks_h.blockSignals(False)

        self._reload_palette_names()
        self.palette_combo.setCurrentText(self.sprite.palette)
        self.fps_spin.blockSignals(True)
        self.fps_spin.setValue(self.sprite.fps)
        self.fps_spin.blockSignals(False)
        self._load_palette_colors()
        self._sync_frame_controls()
        self._try_load_reference_sidecar()
        self._refresh_canvas()

    def new_sprite(self, path: Path, blocks_w: int, blocks_h: int, palette: str) -> None:
        self._stop_playback()
        self.file_path = path.resolve()
        self.sprite = Sprite.create(blocks_w, blocks_h, palette)
        self._dirty = True
        self.canvas.set_reference(None)
        self.btn_convert.setEnabled(False)

        self.blocks_w.blockSignals(True)
        self.blocks_h.blockSignals(True)
        self.blocks_w.setValue(blocks_w)
        self.blocks_h.setValue(blocks_h)
        self.blocks_w.blockSignals(False)
        self.blocks_h.blockSignals(False)

        self._reload_palette_names()
        self.palette_combo.setCurrentText(palette)
        self.fps_spin.blockSignals(True)
        self.fps_spin.setValue(8)
        self.fps_spin.blockSignals(False)
        self._load_palette_colors()
        self._sync_frame_controls()
        self._refresh_canvas()

    def save(self) -> None:
        if not self.sprite or not self.file_path:
            return
        save_sprite(self.sprite, self.file_path)
        self._save_all_render_sidecars()
        self._dirty = False
        self.saved.emit(self.file_path)

    def _rename_sprite(self) -> None:
        if not self.sprite or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename Sprite", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename Sprite",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortusprite"
        if new_path.exists():
            QMessageBox.warning(self, "Rename Sprite", f"{new_path.name} already exists.")
            return
        # rename sidecars before the main file (they still carry the old stem)
        for sidecar in sorted(old_path.parent.glob(f"{old_path.stem}.*")):
            if sidecar == old_path:
                continue
            sidecar.rename(sidecar.parent / sidecar.name.replace(old_path.stem, new_stem, 1))
        old_path.rename(new_path)
        self.file_path = new_path
        self.renamed.emit(old_path, new_path)

    def _save_render_sidecar(self, frame_index: int | None = None) -> None:
        if not self.sprite or not self.file_path or not self._palette_colors:
            return
        idx = frame_index if frame_index is not None else self.sprite.current_frame
        save_sprite_frame_png(self.sprite, self._palette_colors, self.file_path, idx)

    def _save_all_render_sidecars(self) -> None:
        if not self.sprite or not self.file_path or not self._palette_colors:
            return
        save_all_sprite_frame_pngs(self.sprite, self._palette_colors, self.file_path)

    def _reference_sidecar(self, frame_index: int | None = None) -> Path | None:
        if not self.file_path:
            return None
        idx = frame_index if frame_index is not None else (self.sprite.current_frame if self.sprite else 0)
        return reference_sidecar_path(self.file_path, idx)

    def _save_reference_sidecar(self) -> None:
        if not self.file_path or self.canvas.reference is None or not self.sprite:
            return
        sidecar = self.file_path.with_name(
            f"{self.file_path.stem}.ref{self.sprite.current_frame}.png"
        )
        pygame.image.save(self.canvas.reference, str(sidecar))

    def _try_load_reference_sidecar(self) -> None:
        if not self.file_path or not self.sprite:
            return
        sidecar_path = reference_sidecar_path(self.file_path, self.sprite.current_frame)
        if sidecar_path.is_file():
            surface = load_image(sidecar_path)
            self.canvas.set_reference(surface)
            self.btn_convert.setEnabled(True)
        else:
            self.canvas.set_reference(None)
            self.btn_convert.setEnabled(False)

    def _load_reference(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Reference Image",
            str(self.project_root),
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if not path:
            return
        surface = self.color_key.apply_to(load_image(path))
        self.canvas.set_reference(surface)
        self.btn_convert.setEnabled(True)

        if self.file_path and self.sprite:
            sidecar = self.file_path.with_name(
                f"{self.file_path.stem}.ref{self.sprite.current_frame}.png"
            )
            pygame.image.save(surface, str(sidecar))
            if self.sprite.current_frame == 0:
                pygame.image.save(surface, str(self.file_path.with_suffix(".ref.png")))

    def _convert_reference(self) -> None:
        if not self.sprite or self.canvas.reference is None:
            return
        if self.sprite.frame_has_pixels():
            reply = QMessageBox.question(
                self,
                "Convert to Palette",
                "Replace all sprite pixels with converted reference colors?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.sprite.fill_from_surface(self.canvas.reference, self._palette_colors)
        self._dirty = True
        self._save_render_sidecar()
        self._refresh_canvas()

    def has_unsaved_changes(self) -> bool:
        return self._dirty
