"""Progress bar editor — define reusable tiled-rect fill-bar prefabs (.tortuprogressbar)."""

from __future__ import annotations

from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tortuengine.bake import build_tiled_surface
from tortuengine.gui_layer import FILL_DIRECTIONS
from tortuengine.palette import load_palette, palette_path
from tortuengine.progress_bar import (
    DEFAULT_PROGRESS_BAR_HEIGHT,
    DEFAULT_PROGRESS_BAR_WIDTH,
    MAX_PROGRESS_BAR_RANGES,
    ProgressBar,
    ProgressBarRange,
    load_progress_bar,
    save_progress_bar,
)
from tortuengine.sprite import Sprite, load_sprite
from tortustudio.asset_drag import SpriteDropCombo
from tortustudio.scene_assets import list_sprite_paths


class ProgressBarPreviewCanvas(QWidget):
    """Static preview of the tiled texture at the bar's current width/height."""

    zoom_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not pygame.get_init():
            pygame.init()
        self._frame: QImage | None = None
        self._frame_w = 0
        self._frame_h = 0
        self.zoom = 4
        self.setMinimumSize(120, 60)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_zoom(self, zoom: int) -> None:
        new_zoom = max(1, min(16, zoom))
        if new_zoom == self.zoom:
            return
        self.zoom = new_zoom
        self.zoom_changed.emit(self.zoom)
        self._update_min_size()
        self.update()

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_zoom(self.zoom + 1)
        elif delta < 0:
            self.set_zoom(self.zoom - 1)
        event.accept()

    def _update_min_size(self) -> None:
        self.setMinimumSize(
            max(120, self._frame_w * self.zoom + 32),
            max(60, self._frame_h * self.zoom + 32),
        )

    def set_preview(self, surface: pygame.Surface | None) -> None:
        if surface is None:
            self._frame = None
            self._frame_w = 0
            self._frame_h = 0
            self.update()
            return
        w, h = surface.get_width(), surface.get_height()
        data = pygame.image.tobytes(surface, "RGBA")
        self._frame = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        self._frame_w, self._frame_h = w, h
        self._update_min_size()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is not None:
            sw, sh = self._frame_w * self.zoom, self._frame_h * self.zoom
            scaled = self._frame.scaled(
                sw, sh,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
        painter.end()


class ProgressBarEditorWidget(QWidget):
    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_progress_bar_requested = pyqtSignal()
    open_progress_bar_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.progress_bar: ProgressBar | None = None
        self._sprite: Sprite | None = None
        self._palette_colors: list[tuple[int, int, int]] = []
        self._dirty = False

        self.preview = ProgressBarPreviewCanvas()
        self.preview.zoom_changed.connect(self._on_preview_zoom_changed)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 16)
        self.zoom_spin.setValue(self.preview.zoom)
        self.zoom_spin.valueChanged.connect(self.preview.set_zoom)

        self.btn_new = QPushButton("New Progress Bar…")
        self.btn_new.clicked.connect(self.new_progress_bar_requested.emit)
        self.btn_open = QPushButton("Open Progress Bar…")
        self.btn_open.clicked.connect(self.open_progress_bar_requested.emit)
        self.btn_save = QPushButton("Save progress bar")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_progress_bar)

        self.status_label = QLabel("No progress bar open")

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_fields_changed)

        self.texture_combo = SpriteDropCombo()
        self.texture_combo.currentIndexChanged.connect(self._on_texture_changed)
        self.texture_combo.sprite_dropped.connect(self._on_sprite_dropped)

        self.fill_direction_combo = QComboBox()
        for value in FILL_DIRECTIONS:
            self.fill_direction_combo.addItem(value.replace("_", " ").title(), value)
        self.fill_direction_combo.currentIndexChanged.connect(self._on_fields_changed)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 2048)
        self.width_spin.setValue(DEFAULT_PROGRESS_BAR_WIDTH)
        self.width_spin.valueChanged.connect(self._on_size_changed)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 2048)
        self.height_spin.setValue(DEFAULT_PROGRESS_BAR_HEIGHT)
        self.height_spin.valueChanged.connect(self._on_size_changed)

        # -- texture ranges: swap the base texture over a [min, max] number band,
        # modeled on the scene editor's background parallax bands (band_combo +
        # shared detail panel) --
        self.range_combo = QComboBox()
        self.range_combo.currentIndexChanged.connect(self._on_range_changed)

        self.range_min_spin = QDoubleSpinBox()
        self.range_min_spin.setRange(0.0, 999999.0)
        self.range_min_spin.valueChanged.connect(self._on_range_fields_changed)

        self.range_max_spin = QDoubleSpinBox()
        self.range_max_spin.setRange(0.0, 999999.0)
        self.range_max_spin.valueChanged.connect(self._on_range_fields_changed)

        self.range_texture_combo = QComboBox()
        self.range_texture_combo.currentIndexChanged.connect(self._on_range_fields_changed)

        self.btn_add_range = QPushButton("Add range")
        self.btn_add_range.clicked.connect(self._add_range)
        self.btn_remove_range = QPushButton("Remove range")
        self.btn_remove_range.clicked.connect(self._remove_range)

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

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setWidget(self.preview)
        preview_layout.addWidget(preview_scroll)
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom:"))
        zoom_row.addWidget(self.zoom_spin)
        zoom_row.addStretch()
        preview_layout.addLayout(zoom_row)
        body.addWidget(preview_group, stretch=1)

        form = QFormLayout()
        form.addRow("Display name:", self.name_edit)
        form.addRow("Texture:", self.texture_combo)
        form.addRow("Fill direction:", self.fill_direction_combo)
        form.addRow("Default width:", self.width_spin)
        form.addRow("Default height:", self.height_spin)

        ranges_group = QGroupBox("Texture Ranges")
        ranges_layout = QVBoxLayout(ranges_group)
        ranges_layout.addWidget(QLabel(
            "Swap the texture above while number falls within a range\n"
            "(e.g. red for 0-20 HP). First matching range wins."
        ))
        range_btn_row = QHBoxLayout()
        range_btn_row.addWidget(self.range_combo, stretch=1)
        range_btn_row.addWidget(self.btn_add_range)
        range_btn_row.addWidget(self.btn_remove_range)
        ranges_layout.addLayout(range_btn_row)
        range_form = QFormLayout()
        range_form.addRow("Number from:", self.range_min_spin)
        range_form.addRow("Number to:", self.range_max_spin)
        range_form.addRow("Texture:", self.range_texture_combo)
        ranges_layout.addLayout(range_form)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addLayout(form)
        side_layout.addWidget(ranges_group)
        side_layout.addStretch()
        body.addWidget(side)

    # -- state helpers -----------------------------------------------------

    def _on_preview_zoom_changed(self, zoom: int) -> None:
        self.zoom_spin.blockSignals(True)
        self.zoom_spin.setValue(zoom)
        self.zoom_spin.blockSignals(False)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._update_status()

    def _update_status(self) -> None:
        if not self.progress_bar or not self.file_path:
            self.status_label.setText("No progress bar open")
            return
        state = "edited" if self._dirty else "saved"
        self.status_label.setText(f"{self.file_path.name} ({state})")

    def _populate_texture_combo(self, current: str) -> None:
        self.texture_combo.blockSignals(True)
        self.texture_combo.clear()
        for rel in list_sprite_paths(self.project_root):
            self.texture_combo.addItem(rel, rel)
        if current and self.texture_combo.findData(current) < 0:
            self.texture_combo.addItem(current, current)
        index = self.texture_combo.findData(current)
        self.texture_combo.setCurrentIndex(index if index >= 0 else 0)
        self.texture_combo.blockSignals(False)

    def _on_sprite_dropped(self, rel_path: str) -> None:
        if not self.progress_bar:
            return
        index = self.texture_combo.findData(rel_path)
        if index < 0:
            self.texture_combo.addItem(rel_path, rel_path)
            index = self.texture_combo.findData(rel_path)
        self.texture_combo.setCurrentIndex(index)

    def _populate_range_texture_combo(self, current: str) -> None:
        self.range_texture_combo.blockSignals(True)
        self.range_texture_combo.clear()
        for rel in list_sprite_paths(self.project_root):
            self.range_texture_combo.addItem(rel, rel)
        if current and self.range_texture_combo.findData(current) < 0:
            self.range_texture_combo.addItem(current, current)
        index = self.range_texture_combo.findData(current) if current else 0
        self.range_texture_combo.setCurrentIndex(index if index >= 0 else 0)
        self.range_texture_combo.blockSignals(False)

    def _active_range_index(self) -> int:
        if self.range_combo.count() == 0:
            return -1
        return self.range_combo.currentIndex()

    def _range_label(self, r: ProgressBarRange) -> str:
        texture_name = Path(r.texture).stem if r.texture else "(none)"
        return f"{r.min_number:g}–{r.max_number:g} → {texture_name}"

    def _sync_range_controls(self) -> None:
        self.range_combo.blockSignals(True)
        self.range_combo.clear()
        if not self.progress_bar:
            self.range_combo.blockSignals(False)
            self._set_range_controls_enabled(False)
            return
        for i, r in enumerate(self.progress_bar.ranges):
            self.range_combo.addItem(f"{i}: {self._range_label(r)}", i)
        if self.progress_bar.ranges:
            active = min(max(self._active_range_index(), 0), len(self.progress_bar.ranges) - 1)
            self.range_combo.setCurrentIndex(active)
            self._load_range_fields(self.progress_bar.ranges[active])
        self.range_combo.blockSignals(False)
        self._set_range_controls_enabled(bool(self.progress_bar.ranges))
        self.btn_add_range.setEnabled(len(self.progress_bar.ranges) < MAX_PROGRESS_BAR_RANGES)

    def _set_range_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.range_combo, self.range_min_spin, self.range_max_spin,
            self.range_texture_combo, self.btn_remove_range,
        ):
            widget.setEnabled(enabled)

    def _load_range_fields(self, r: ProgressBarRange) -> None:
        self.range_min_spin.blockSignals(True)
        self.range_max_spin.blockSignals(True)
        self.range_min_spin.setValue(r.min_number)
        self.range_max_spin.setValue(r.max_number)
        self.range_min_spin.blockSignals(False)
        self.range_max_spin.blockSignals(False)
        self._populate_range_texture_combo(r.texture)

    def _save_range_fields(self, r: ProgressBarRange) -> None:
        lo, hi = self.range_min_spin.value(), self.range_max_spin.value()
        r.min_number, r.max_number = min(lo, hi), max(lo, hi)
        texture = self.range_texture_combo.currentData()
        r.texture = str(texture) if texture else ""

    def _on_range_changed(self, index: int) -> None:
        if not self.progress_bar or index < 0 or index >= len(self.progress_bar.ranges):
            return
        self._load_range_fields(self.progress_bar.ranges[index])

    def _on_range_fields_changed(self) -> None:
        if not self.progress_bar:
            return
        index = self._active_range_index()
        if index < 0 or index >= len(self.progress_bar.ranges):
            return
        r = self.progress_bar.ranges[index]
        self._save_range_fields(r)
        self.range_combo.blockSignals(True)
        self.range_combo.setItemText(index, f"{index}: {self._range_label(r)}")
        self.range_combo.blockSignals(False)
        self._mark_dirty()

    def _add_range(self) -> None:
        if not self.progress_bar:
            return
        if len(self.progress_bar.ranges) >= MAX_PROGRESS_BAR_RANGES:
            QMessageBox.warning(
                self, "Add Range", f"Maximum {MAX_PROGRESS_BAR_RANGES} texture ranges."
            )
            return
        if self.progress_bar.ranges:
            lo = self.progress_bar.ranges[-1].max_number + 1
        else:
            lo = 0.0
        self.progress_bar.ranges.append(ProgressBarRange(lo, lo + 10, self.progress_bar.texture))
        self._mark_dirty()
        self._sync_range_controls()
        self.range_combo.setCurrentIndex(len(self.progress_bar.ranges) - 1)

    def _remove_range(self) -> None:
        if not self.progress_bar:
            return
        index = self._active_range_index()
        if index < 0 or index >= len(self.progress_bar.ranges):
            return
        self.progress_bar.ranges.pop(index)
        self._mark_dirty()
        self._sync_range_controls()

    def _load_texture_asset(self) -> None:
        texture = self.progress_bar.texture if self.progress_bar else ""
        if not texture:
            self._sprite = None
            self._palette_colors = []
            return
        path = (self.project_root / texture).resolve()
        if not path.is_file():
            self._sprite = None
            return
        try:
            self._sprite = load_sprite(path)
            palette_file = palette_path(self.project_root, self._sprite.palette)
            self._palette_colors = load_palette(palette_file)
        except (FileNotFoundError, ValueError, OSError):
            self._sprite = None

    def _refresh_preview(self) -> None:
        if not self.progress_bar or not self._sprite or not self._palette_colors:
            self.preview.set_preview(None)
            return
        base = self._sprite.to_surface(self._palette_colors, frame_index=0)
        width = max(1, self.width_spin.value())
        height = max(1, self.height_spin.value())
        tiled = build_tiled_surface(base, repeat_x=True, repeat_y=True, target_w=width, target_h=height)
        cropped = pygame.Surface((width, height), pygame.SRCALPHA)
        cropped.blit(tiled, (0, 0))
        self.preview.set_preview(cropped)

    def _refresh_editor(self) -> None:
        if not self.progress_bar:
            self.preview.set_preview(None)
            return
        self.name_edit.blockSignals(True)
        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)
        self.fill_direction_combo.blockSignals(True)
        self.name_edit.setText(self.progress_bar.name)
        self.width_spin.setValue(self.progress_bar.width)
        self.height_spin.setValue(self.progress_bar.height)
        index = self.fill_direction_combo.findData(self.progress_bar.fill_direction)
        self.fill_direction_combo.setCurrentIndex(index if index >= 0 else 0)
        self.name_edit.blockSignals(False)
        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)
        self.fill_direction_combo.blockSignals(False)
        self._populate_texture_combo(self.progress_bar.texture)
        self._load_texture_asset()
        self._refresh_preview()
        self._sync_range_controls()

    def _apply_fields_to_progress_bar(self) -> None:
        if not self.progress_bar:
            return
        self.progress_bar.name = self.name_edit.text().strip() or "progress_bar"
        texture = self.texture_combo.currentData()
        self.progress_bar.texture = str(texture) if texture else ""
        direction = self.fill_direction_combo.currentData()
        self.progress_bar.fill_direction = str(direction) if direction else FILL_DIRECTIONS[0]
        self.progress_bar.width = self.width_spin.value()
        self.progress_bar.height = self.height_spin.value()

    # -- field signal handlers -----------------------------------------------------

    def _on_fields_changed(self) -> None:
        self._apply_fields_to_progress_bar()
        self._mark_dirty()

    def _on_texture_changed(self, _index: int) -> None:
        self._apply_fields_to_progress_bar()
        self._load_texture_asset()
        self._refresh_preview()
        self._mark_dirty()

    def _on_size_changed(self) -> None:
        self._apply_fields_to_progress_bar()
        self._refresh_preview()
        self._mark_dirty()

    # -- public API -----------------------------------------------------

    def new_progress_bar(self, path: Path, texture: str, name: str) -> None:
        self.file_path = path.resolve()
        self.progress_bar = ProgressBar(name or "progress_bar", texture)
        self._dirty = True
        self._refresh_editor()
        self._update_status()

    def open_progress_bar(self, path: Path) -> None:
        self.file_path = path.resolve()
        try:
            self.progress_bar = load_progress_bar(self.file_path)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Open Progress Bar", str(exc))
            self.progress_bar = None
            self.file_path = None
            return
        self._dirty = False
        self._refresh_editor()
        self._update_status()

    def save(self) -> None:
        if not self.progress_bar or not self.file_path:
            return
        self._apply_fields_to_progress_bar()
        save_progress_bar(self.progress_bar, self.file_path)
        self._dirty = False
        self._update_status()
        self.saved.emit(self.file_path)

    def _rename_progress_bar(self) -> None:
        if not self.progress_bar or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename Progress Bar", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename Progress Bar",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortuprogressbar"
        if new_path.exists():
            QMessageBox.warning(self, "Rename Progress Bar", f"{new_path.name} already exists.")
            return
        old_path.rename(new_path)
        self.file_path = new_path
        self._update_status()
        self.renamed.emit(old_path, new_path)

    def has_unsaved_changes(self) -> bool:
        return self._dirty
