"""Background editor — paint bg layers on a wide canvas."""

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
    QInputDialog,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tortuengine.background import (
    DEFAULT_BACKGROUND_HEIGHT,
    DEFAULT_BACKGROUND_WIDTH,
    Background,
    MAX_BG_LAYERS,
    MIN_BG_LAYERS,
    load_background,
    save_background,
)
from tortuengine.constants import BACKGROUND_LAYERS, SCREEN_HEIGHT, SCREEN_WIDTH, TILE_BLOCK
from tortuengine.image import apply_color_key, load_image
from tortuengine.palette import (
    PAINTABLE_INDICES,
    TRANSPARENT_INDEX,
    load_palette,
    palette_path,
)
from tortustudio.sprite_editor import Tool


class BackgroundCanvas(QWidget):
    """Scrollable background canvas — composites bg layers, edits the active one."""

    PIXEL_GRID_COLOR = (48, 48, 64)
    SEGMENT_GRID_COLOR = (36, 36, 50)
    SCREEN_OVERLAY_COLOR = (255, 220, 80, 100)
    MAP_BG = (30, 30, 40)

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not pygame.get_init():
            pygame.init()

        self.background: Background | None = None
        self.palette: list[tuple[int, int, int]] = []
        self.active_bg_layer = 0
        self.current_index = 0
        self.tool = Tool.PENCIL
        self.show_pixel_grid = False
        self.show_segment_grid = True
        self.camera_x = 0
        self.zoom = 2
        self._drawing = False
        self._frame: QImage | None = None
        self.setMinimumSize(200, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_context(
        self,
        background: Background | None,
        palette: list[tuple[int, int, int]],
        active_bg_layer: int,
        current_index: int,
        *,
        camera_x: int,
    ) -> None:
        self.background = background
        self.palette = palette
        self.active_bg_layer = active_bg_layer
        self.current_index = current_index
        self.camera_x = camera_x
        self._refresh()

    def set_tool(self, tool: Tool) -> None:
        self.tool = tool

    def set_show_pixel_grid(self, visible: bool) -> None:
        self.show_pixel_grid = visible
        self.update()

    def set_show_segment_grid(self, visible: bool) -> None:
        self.show_segment_grid = visible
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(1, min(16, zoom))
        if self.background:
            self.setMinimumSize(
                self.background.width * self.zoom,
                self.background.height * self.zoom,
            )
        self.update()

    def _refresh(self) -> None:
        if not self.background:
            self._frame = None
            self.update()
            return

        composite = pygame.Surface((self.background.width, self.background.height))
        composite.fill(self.MAP_BG)
        for i, bg_layer in enumerate(self.background.bg_layers):
            if not bg_layer.visible:
                continue
            layer_surface = self.background.layer_surface(i, self.palette)
            composite.blit(layer_surface, (0, 0))
        map_w, map_h = self.background.width, self.background.height

        data = pygame.image.tobytes(composite, "RGBA")
        self._frame = QImage(data, map_w, map_h, map_w * 4, QImage.Format.Format_RGBA8888)
        self.setMinimumSize(map_w * self.zoom, map_h * self.zoom)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None or not self.background:
            painter.end()
            return

        sw = self._frame.width() * self.zoom
        sh = self._frame.height() * self.zoom
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)

        scaled = self._frame.scaled(
            sw,
            sh,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        painter.drawImage(ox, oy, scaled)

        if self.show_segment_grid and TILE_BLOCK > 0:
            pen = QPen(QColor(*self.SEGMENT_GRID_COLOR))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(TILE_BLOCK, self.background.width, TILE_BLOCK):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)

        if self.show_pixel_grid:
            pen = QPen(QColor(*self.PIXEL_GRID_COLOR))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            for px in range(1, self.background.width):
                lx = ox + px * self.zoom
                painter.drawLine(lx, oy, lx, oy + sh)
            for py in range(1, self.background.height):
                ly = oy + py * self.zoom
                painter.drawLine(ox, ly, ox + sw, ly)

        screen_w = min(SCREEN_WIDTH, self.background.width) * self.zoom
        screen_h = min(SCREEN_HEIGHT, self.background.height) * self.zoom
        cam_x = min(self.camera_x, max(0, self.background.width - SCREEN_WIDTH))
        pen = QPen(QColor(*self.SCREEN_OVERLAY_COLOR))
        pen.setWidth(2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(ox + cam_x * self.zoom, oy, screen_w, screen_h)

        painter.end()

    def _event_to_pixel(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None or not self.background:
            return None
        sw = self.background.width * self.zoom
        sh = self.background.height * self.zoom
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)
        px = (event.position().x() - ox) / self.zoom
        py = (event.position().y() - oy) / self.zoom
        if px < 0 or py < 0 or px >= self.background.width or py >= self.background.height:
            return None
        return int(px), int(py)

    def _apply_tool(self, x: int, y: int) -> None:
        if not self.background:
            return
        if self.tool == Tool.PENCIL:
            self.background.set_pixel(self.active_bg_layer, x, y, self.current_index)
        elif self.tool == Tool.ERASER:
            self.background.set_pixel(self.active_bg_layer, x, y, TRANSPARENT_INDEX)
        elif self.tool == Tool.EYEDROPPER:
            picked = self.background.get_pixel(self.active_bg_layer, x, y)
            if picked != TRANSPARENT_INDEX:
                self.current_index = picked
                self.changed.emit()
        self._refresh()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._event_to_pixel(event)
            if pos:
                self._drawing = True
                self._apply_tool(*pos)
                self.changed.emit()

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
            self.set_zoom(self.zoom + 1)
        elif delta < 0:
            self.set_zoom(self.zoom - 1)


class BackgroundEditorWidget(QWidget):
    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_background_requested = pyqtSignal()
    open_background_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.background: Background | None = None
        self._palette_colors: list[tuple[int, int, int]] = []
        self._dirty = False
        self._current_index = 0

        self.canvas = BackgroundCanvas()
        self.canvas.changed.connect(self._on_canvas_changed)

        self.btn_save = QPushButton("Save background")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_background)
        self.btn_new = QPushButton("New Background…")
        self.btn_new.clicked.connect(self.new_background_requested.emit)
        self.btn_open = QPushButton("Open Background…")
        self.btn_open.clicked.connect(self.open_background_requested.emit)

        self.status_label = QLabel("No background open")
        self.size_label = QLabel("—")

        self.bg_layer_combo = QComboBox()
        self.bg_layer_combo.currentIndexChanged.connect(self._on_bg_layer_changed)

        self.bg_layer_visible = QCheckBox("Bg layer visible")
        self.bg_layer_visible.setChecked(True)
        self.bg_layer_visible.toggled.connect(self._on_bg_layer_visible_toggled)

        self.btn_add_bg_layer = QPushButton("Add bg layer")
        self.btn_add_bg_layer.clicked.connect(self._add_bg_layer)
        self.btn_remove_bg_layer = QPushButton("Remove bg layer")
        self.btn_remove_bg_layer.clicked.connect(self._remove_bg_layer)

        self.bg_width = QSpinBox()
        self.bg_width.setRange(SCREEN_WIDTH, 4096)
        self.bg_width.setValue(DEFAULT_BACKGROUND_WIDTH)
        self.bg_width.setSuffix(" px")

        self.bg_height = QSpinBox()
        self.bg_height.setRange(SCREEN_HEIGHT, 2048)
        self.bg_height.setValue(DEFAULT_BACKGROUND_HEIGHT)
        self.bg_height.setSuffix(" px")

        self.btn_resize = QPushButton("Resize canvas")
        self.btn_resize.clicked.connect(self._resize_background)
        self.btn_reset_screen = QPushButton("Reset to screen")
        self.btn_reset_screen.setToolTip(f"Set height to {SCREEN_HEIGHT}px (screen height)")
        self.btn_reset_screen.clicked.connect(self._reset_to_screen_height)

        self.camera_slider = QSlider(Qt.Orientation.Horizontal)
        self.camera_slider.setRange(0, DEFAULT_BACKGROUND_WIDTH)
        self.camera_slider.valueChanged.connect(self._on_camera_changed)

        self.show_pixel_grid = QCheckBox("Pixel grid")
        self.show_pixel_grid.toggled.connect(self.canvas.set_show_pixel_grid)

        self.show_segment_grid = QCheckBox("Segment grid (8px)")
        self.show_segment_grid.setChecked(True)
        self.show_segment_grid.toggled.connect(self.canvas.set_show_segment_grid)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 16)
        self.zoom_spin.setValue(2)
        self.zoom_spin.valueChanged.connect(self.canvas.set_zoom)

        self.btn_pencil = QPushButton("Paint")
        self.btn_eraser = QPushButton("Erase")
        self.btn_dropper = QPushButton("Eyedropper")
        for btn in (self.btn_pencil, self.btn_eraser, self.btn_dropper):
            btn.setCheckable(True)
        self.btn_pencil.setChecked(True)
        self.btn_pencil.clicked.connect(lambda: self._set_tool(Tool.PENCIL))
        self.btn_eraser.clicked.connect(lambda: self._set_tool(Tool.ERASER))
        self.btn_dropper.clicked.connect(lambda: self._set_tool(Tool.EYEDROPPER))

        self.swatches_grid = QGridLayout()
        self.swatches_area = QWidget()
        self.swatches_area.setLayout(self.swatches_grid)

        self._build_layout()

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

        canvas_group = QGroupBox("Background")
        canvas_layout = QVBoxLayout(canvas_group)
        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setWidget(self.canvas)
        canvas_layout.addWidget(canvas_scroll)
        body.addWidget(canvas_group, stretch=1)

        side = QVBoxLayout()
        form = QFormLayout()
        form.addRow("Canvas size:", self.size_label)
        form.addRow("Active bg layer:", self.bg_layer_combo)
        form.addRow("", self.bg_layer_visible)
        bg_layer_btns = QHBoxLayout()
        bg_layer_btns.addWidget(self.btn_add_bg_layer)
        bg_layer_btns.addWidget(self.btn_remove_bg_layer)
        form.addRow(bg_layer_btns)
        form.addRow("Width:", self.bg_width)
        form.addRow("Height:", self.bg_height)
        resize_row = QHBoxLayout()
        resize_row.addWidget(self.btn_resize)
        resize_row.addWidget(self.btn_reset_screen)
        form.addRow(resize_row)
        form.addRow("Camera X:", self.camera_slider)
        form.addRow("Zoom:", self.zoom_spin)
        form.addRow(self.show_pixel_grid)
        form.addRow(self.show_segment_grid)
        side.addLayout(form)

        tools = QHBoxLayout()
        tools.addWidget(self.btn_pencil)
        tools.addWidget(self.btn_eraser)
        tools.addWidget(self.btn_dropper)
        side.addLayout(tools)

        side.addWidget(QLabel("Palette colors (0–62):"))
        side.addWidget(self.swatches_area)
        side.addStretch()
        body.addLayout(side)

    def _active_bg_layer_index(self) -> int:
        if not self.background or self.bg_layer_combo.count() == 0:
            return 0
        return self.bg_layer_combo.currentIndex()

    def _set_tool(self, tool: Tool) -> None:
        self.btn_pencil.setChecked(tool == Tool.PENCIL)
        self.btn_eraser.setChecked(tool == Tool.ERASER)
        self.btn_dropper.setChecked(tool == Tool.EYEDROPPER)
        self.canvas.set_tool(tool)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._update_status()

    def _update_status(self) -> None:
        if not self.background or not self.file_path:
            self.status_label.setText("No background open")
            return
        state = "edited" if self._dirty else "saved"
        self.status_label.setText(f"{self.file_path.name} ({state})")

    def _update_size_label(self) -> None:
        if not self.background:
            self.size_label.setText("—")
            return
        screens = self.background.width / SCREEN_WIDTH
        self.size_label.setText(
            f"{self.background.width}×{self.background.height} px  "
            f"({screens:.1f}× screen, {BACKGROUND_LAYERS} bg layers max)"
        )

    def _update_camera_slider(self) -> None:
        if not self.background:
            return
        max_cam = max(0, self.background.width - SCREEN_WIDTH)
        self.camera_slider.blockSignals(True)
        self.camera_slider.setRange(0, max_cam)
        self.camera_slider.setValue(min(self.camera_slider.value(), max_cam))
        self.camera_slider.blockSignals(False)

    def _load_palette_colors(self) -> None:
        if not self.background:
            return
        path = palette_path(self.project_root, self.background.palette)
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
        self._current_index = index
        self._refresh_canvas()
        self._set_tool(Tool.PENCIL)

    def _sync_bg_layer_controls(self) -> None:
        if not self.background:
            return
        self.bg_layer_combo.blockSignals(True)
        self.bg_layer_combo.clear()
        for i, bg_layer in enumerate(self.background.bg_layers):
            self.bg_layer_combo.addItem(f"{i}: {bg_layer.name}", i)
        active = min(
            self.canvas.active_bg_layer,
            max(0, self.background.bg_layer_count - 1),
        )
        self.bg_layer_combo.setCurrentIndex(active)
        bg_layer = self.background.bg_layers[active]
        self.bg_layer_visible.blockSignals(True)
        self.bg_layer_visible.setChecked(bg_layer.visible)
        self.bg_layer_visible.blockSignals(False)
        self.bg_layer_combo.blockSignals(False)
        self.btn_remove_bg_layer.setEnabled(
            self.background.bg_layer_count > MIN_BG_LAYERS
        )
        self.btn_add_bg_layer.setEnabled(
            self.background.bg_layer_count < MAX_BG_LAYERS
        )

    def _refresh_canvas(self) -> None:
        if not self.background:
            self.canvas.set_context(None, [], 0, 0, camera_x=0)
            return
        active = self._active_bg_layer_index()
        self.canvas.set_context(
            self.background,
            self._palette_colors,
            active,
            self._current_index,
            camera_x=self.camera_slider.value(),
        )

    def _refresh_editor(self) -> None:
        if not self.background:
            return
        self.bg_width.blockSignals(True)
        self.bg_height.blockSignals(True)
        self.bg_width.setValue(self.background.width)
        self.bg_height.setValue(self.background.height)
        self.bg_width.blockSignals(False)
        self.bg_height.blockSignals(False)
        self._update_size_label()
        self._update_camera_slider()
        self._sync_bg_layer_controls()
        self._refresh_canvas()

    def _on_canvas_changed(self) -> None:
        if (
            self.canvas.tool == Tool.EYEDROPPER
            and self.canvas.current_index != self._current_index
        ):
            self._current_index = self.canvas.current_index
        self._mark_dirty()
        self._refresh_canvas()

    def _on_bg_layer_changed(self, index: int) -> None:
        if not self.background or index < 0:
            return
        bg_layer = self.background.bg_layers[index]
        self.bg_layer_visible.blockSignals(True)
        self.bg_layer_visible.setChecked(bg_layer.visible)
        self.bg_layer_visible.blockSignals(False)
        self._refresh_canvas()

    def _on_bg_layer_visible_toggled(self, visible: bool) -> None:
        if not self.background:
            return
        index = self._active_bg_layer_index()
        if 0 <= index < self.background.bg_layer_count:
            self.background.bg_layers[index].visible = visible
            self._mark_dirty()
            self._refresh_canvas()

    def _on_camera_changed(self, value: int) -> None:
        self._refresh_canvas()

    def _add_bg_layer(self) -> None:
        if not self.background:
            return
        try:
            index = self.background.add_bg_layer()
        except ValueError as exc:
            QMessageBox.warning(self, "Add Bg Layer", str(exc))
            return
        self._mark_dirty()
        self._sync_bg_layer_controls()
        self.bg_layer_combo.setCurrentIndex(index)
        self._refresh_canvas()

    def _remove_bg_layer(self) -> None:
        if not self.background:
            return
        index = self._active_bg_layer_index()
        try:
            self.background.remove_bg_layer(index)
        except ValueError as exc:
            QMessageBox.warning(self, "Remove Bg Layer", str(exc))
            return
        self._mark_dirty()
        self._sync_bg_layer_controls()
        self._refresh_canvas()

    def _resize_background(self) -> None:
        if not self.background:
            return
        new_w = self.bg_width.value()
        new_h = self.bg_height.value()
        if new_w == self.background.width and new_h == self.background.height:
            return
        if any(
            any(p != TRANSPARENT_INDEX for p in bg_layer.pixels)
            for bg_layer in self.background.bg_layers
        ):
            reply = QMessageBox.question(
                self,
                "Resize Background",
                "Resample all bg layers to the new canvas size?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.bg_width.setValue(self.background.width)
                self.bg_height.setValue(self.background.height)
                return
        self.background.resize_pixels(new_w, new_h)
        self._mark_dirty()
        self._refresh_editor()

    def _reset_to_screen_height(self) -> None:
        self.bg_height.setValue(SCREEN_HEIGHT)
        self._resize_background()

    def new_background(
        self,
        path: Path,
        palette: str,
        image_path: Path,
        color_key_rgb: tuple[int, int, int] | None = None,
    ) -> None:
        self.file_path = path.resolve()
        try:
            palette_file = palette_path(self.project_root, palette)
            if not palette_file.is_file():
                raise FileNotFoundError(f"Palette not found: {palette_file}")
            colors = load_palette(palette_file)
            surface = load_image(image_path)
            if color_key_rgb is not None:
                surface = apply_color_key(surface, color_key_rgb)
            self.background = Background.create_from_image(palette, surface, colors)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "New Background", str(exc))
            self.background = None
            self.file_path = None
            return
        self._dirty = True
        self._current_index = 0
        self._open_background_data()

    def open_background(self, path: Path) -> None:
        self.file_path = path.resolve()
        try:
            self.background = load_background(self.file_path)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Open Background", str(exc))
            self.background = None
            self.file_path = None
            return
        self._dirty = False
        self._current_index = 0
        self._open_background_data()

    def _open_background_data(self) -> None:
        if not self.background:
            return
        try:
            self._load_palette_colors()
            self.background.ensure_all_bg_layer_pixels()
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "Open Background", str(exc))
            self.background = None
            self.file_path = None
            return
        self._refresh_editor()
        self._update_status()

    def save(self) -> None:
        if not self.background or not self.file_path:
            return
        save_background(self.background, self.file_path)
        self._dirty = False
        self._update_status()
        self.saved.emit(self.file_path)

    def _rename_background(self) -> None:
        if not self.background or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename Background", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename Background",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortubackground"
        if new_path.exists():
            QMessageBox.warning(self, "Rename Background", f"{new_path.name} already exists.")
            return
        for sidecar in sorted(old_path.parent.glob(f"{old_path.stem}.*")):
            if sidecar == old_path:
                continue
            sidecar.rename(sidecar.parent / sidecar.name.replace(old_path.stem, new_stem, 1))
        old_path.rename(new_path)
        self.file_path = new_path
        self._update_status()
        self.renamed.emit(old_path, new_path)

    def has_unsaved_changes(self) -> bool:
        return self._dirty
