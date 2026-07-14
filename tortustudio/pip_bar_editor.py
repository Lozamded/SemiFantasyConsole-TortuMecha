"""Pip bar editor — define reusable repeat-sprite counter prefabs (.tortupipbar)."""

from __future__ import annotations

from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPainter
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

from tortuengine.gui_layer import REPEAT_DIRECTIONS
from tortuengine.palette import load_palette, palette_path
from tortuengine.pip_bar import MAX_PIP_BAR_RANGES, PipBar, PipBarRange, load_pip_bar, save_pip_bar
from tortuengine.sprite import Sprite, load_sprite
from tortustudio.asset_drag import SpriteDropCombo
from tortustudio.scene_assets import list_sprite_paths


class PipBarPreviewCanvas(QWidget):
    """Static preview of the full/empty icon slots at the bar's current settings."""

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


class PipBarEditorWidget(QWidget):
    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_pip_bar_requested = pyqtSignal()
    open_pip_bar_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.pip_bar: PipBar | None = None
        self._dirty = False

        self.preview = PipBarPreviewCanvas()
        self.preview.zoom_changed.connect(self._on_preview_zoom_changed)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 16)
        self.zoom_spin.setValue(self.preview.zoom)
        self.zoom_spin.valueChanged.connect(self.preview.set_zoom)

        self.btn_new = QPushButton("New Pip Bar…")
        self.btn_new.clicked.connect(self.new_pip_bar_requested.emit)
        self.btn_open = QPushButton("Open Pip Bar…")
        self.btn_open.clicked.connect(self.open_pip_bar_requested.emit)
        self.btn_save = QPushButton("Save pip bar")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_pip_bar)

        self.status_label = QLabel("No pip bar open")

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_fields_changed)

        self.full_sprite_combo = SpriteDropCombo()
        self.full_sprite_combo.setToolTip("Sprite drawn for filled slots")
        self.full_sprite_combo.currentIndexChanged.connect(self._on_fields_changed)
        self.full_sprite_combo.sprite_dropped.connect(self._on_full_sprite_dropped)

        self.empty_sprite_combo = SpriteDropCombo()
        self.empty_sprite_combo.setToolTip(
            "Sprite drawn for empty slots — leave unset to skip them entirely"
        )
        self.empty_sprite_combo.currentIndexChanged.connect(self._on_fields_changed)
        self.empty_sprite_combo.sprite_dropped.connect(self._on_empty_sprite_dropped)

        self.direction_combo = QComboBox()
        for value in REPEAT_DIRECTIONS:
            self.direction_combo.addItem(value.title(), value)
        self.direction_combo.currentIndexChanged.connect(self._on_fields_changed)

        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(-99, 99)
        self.spacing_spin.valueChanged.connect(self._on_fields_changed)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.1, 10.0)
        self.scale_spin.setSingleStep(0.1)
        self.scale_spin.setValue(1.0)
        self.scale_spin.valueChanged.connect(self._on_fields_changed)

        # -- texture ranges: swap the filled-slot sprite over a [min, max] number
        # band, modeled on the scene editor's background parallax bands (band_combo
        # + shared detail panel) --
        self.range_combo = QComboBox()
        self.range_combo.currentIndexChanged.connect(self._on_range_changed)

        self.range_min_spin = QSpinBox()
        self.range_min_spin.setRange(0, 999999)
        self.range_min_spin.valueChanged.connect(self._on_range_fields_changed)

        self.range_max_spin = QSpinBox()
        self.range_max_spin.setRange(0, 999999)
        self.range_max_spin.valueChanged.connect(self._on_range_fields_changed)

        self.range_sprite_combo = QComboBox()
        self.range_sprite_combo.currentIndexChanged.connect(self._on_range_fields_changed)

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
        form.addRow("Full sprite:", self.full_sprite_combo)
        form.addRow("Empty sprite:", self.empty_sprite_combo)
        form.addRow("Direction:", self.direction_combo)
        form.addRow("Spacing:", self.spacing_spin)
        form.addRow("Scale:", self.scale_spin)

        ranges_group = QGroupBox("Texture Ranges")
        ranges_layout = QVBoxLayout(ranges_group)
        ranges_layout.addWidget(QLabel(
            "Swap the full sprite above while number falls within a range\n"
            "(e.g. a cracked heart for 0-1 lives). First matching range wins."
        ))
        range_btn_row = QHBoxLayout()
        range_btn_row.addWidget(self.range_combo, stretch=1)
        range_btn_row.addWidget(self.btn_add_range)
        range_btn_row.addWidget(self.btn_remove_range)
        ranges_layout.addLayout(range_btn_row)
        range_form = QFormLayout()
        range_form.addRow("Number from:", self.range_min_spin)
        range_form.addRow("Number to:", self.range_max_spin)
        range_form.addRow("Full sprite:", self.range_sprite_combo)
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
        if not self.pip_bar or not self.file_path:
            self.status_label.setText("No pip bar open")
            return
        state = "edited" if self._dirty else "saved"
        self.status_label.setText(f"{self.file_path.name} ({state})")

    def _populate_sprite_combo(self, combo: QComboBox, current: str, *, placeholder: str = "") -> None:
        combo.blockSignals(True)
        combo.clear()
        if placeholder:
            combo.addItem(placeholder, "")
        for rel in list_sprite_paths(self.project_root):
            combo.addItem(rel, rel)
        if current and combo.findData(current) < 0:
            combo.addItem(current, current)
        index = combo.findData(current) if current else 0
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _on_full_sprite_dropped(self, rel_path: str) -> None:
        index = self.full_sprite_combo.findData(rel_path)
        if index < 0:
            self.full_sprite_combo.addItem(rel_path, rel_path)
            index = self.full_sprite_combo.findData(rel_path)
        self.full_sprite_combo.setCurrentIndex(index)

    def _on_empty_sprite_dropped(self, rel_path: str) -> None:
        index = self.empty_sprite_combo.findData(rel_path)
        if index < 0:
            self.empty_sprite_combo.addItem(rel_path, rel_path)
            index = self.empty_sprite_combo.findData(rel_path)
        self.empty_sprite_combo.setCurrentIndex(index)

    def _active_range_index(self) -> int:
        if self.range_combo.count() == 0:
            return -1
        return self.range_combo.currentIndex()

    def _range_label(self, r: PipBarRange) -> str:
        sprite_name = Path(r.full_sprite).stem if r.full_sprite else "(none)"
        return f"{r.min_number}–{r.max_number} → {sprite_name}"

    def _sync_range_controls(self) -> None:
        self.range_combo.blockSignals(True)
        self.range_combo.clear()
        if not self.pip_bar:
            self.range_combo.blockSignals(False)
            self._set_range_controls_enabled(False)
            return
        for i, r in enumerate(self.pip_bar.ranges):
            self.range_combo.addItem(f"{i}: {self._range_label(r)}", i)
        if self.pip_bar.ranges:
            active = min(max(self._active_range_index(), 0), len(self.pip_bar.ranges) - 1)
            self.range_combo.setCurrentIndex(active)
            self._load_range_fields(self.pip_bar.ranges[active])
        self.range_combo.blockSignals(False)
        self._set_range_controls_enabled(bool(self.pip_bar.ranges))
        self.btn_add_range.setEnabled(len(self.pip_bar.ranges) < MAX_PIP_BAR_RANGES)

    def _set_range_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.range_combo, self.range_min_spin, self.range_max_spin,
            self.range_sprite_combo, self.btn_remove_range,
        ):
            widget.setEnabled(enabled)

    def _load_range_fields(self, r: PipBarRange) -> None:
        self.range_min_spin.blockSignals(True)
        self.range_max_spin.blockSignals(True)
        self.range_min_spin.setValue(r.min_number)
        self.range_max_spin.setValue(r.max_number)
        self.range_min_spin.blockSignals(False)
        self.range_max_spin.blockSignals(False)
        self._populate_sprite_combo(self.range_sprite_combo, r.full_sprite)

    def _save_range_fields(self, r: PipBarRange) -> None:
        lo, hi = self.range_min_spin.value(), self.range_max_spin.value()
        r.min_number, r.max_number = min(lo, hi), max(lo, hi)
        sprite = self.range_sprite_combo.currentData()
        r.full_sprite = str(sprite) if sprite else ""

    def _on_range_changed(self, index: int) -> None:
        if not self.pip_bar or index < 0 or index >= len(self.pip_bar.ranges):
            return
        self._load_range_fields(self.pip_bar.ranges[index])

    def _on_range_fields_changed(self) -> None:
        if not self.pip_bar:
            return
        index = self._active_range_index()
        if index < 0 or index >= len(self.pip_bar.ranges):
            return
        r = self.pip_bar.ranges[index]
        self._save_range_fields(r)
        self.range_combo.blockSignals(True)
        self.range_combo.setItemText(index, f"{index}: {self._range_label(r)}")
        self.range_combo.blockSignals(False)
        self._mark_dirty()

    def _add_range(self) -> None:
        if not self.pip_bar:
            return
        if len(self.pip_bar.ranges) >= MAX_PIP_BAR_RANGES:
            QMessageBox.warning(self, "Add Range", f"Maximum {MAX_PIP_BAR_RANGES} texture ranges.")
            return
        lo = self.pip_bar.ranges[-1].max_number + 1 if self.pip_bar.ranges else 0
        self.pip_bar.ranges.append(PipBarRange(lo, lo + 3, self.pip_bar.full_sprite))
        self._mark_dirty()
        self._sync_range_controls()
        self.range_combo.setCurrentIndex(len(self.pip_bar.ranges) - 1)

    def _remove_range(self) -> None:
        if not self.pip_bar:
            return
        index = self._active_range_index()
        if index < 0 or index >= len(self.pip_bar.ranges):
            return
        self.pip_bar.ranges.pop(index)
        self._mark_dirty()
        self._sync_range_controls()

    def _sprite_frame(self, sprite_path: str) -> pygame.Surface | None:
        if not sprite_path:
            return None
        path = (self.project_root / sprite_path).resolve()
        if not path.is_file():
            return None
        try:
            sprite: Sprite = load_sprite(path)
            palette_file = palette_path(self.project_root, sprite.palette)
            colors = load_palette(palette_file)
            return sprite.to_surface(colors, frame_index=0)
        except (FileNotFoundError, ValueError, OSError):
            return None

    def _refresh_preview(self) -> None:
        if not self.pip_bar:
            self.preview.set_preview(None)
            return
        full_frame = self._sprite_frame(self.pip_bar.full_sprite)
        if full_frame is None:
            self.preview.set_preview(None)
            return
        empty_frame = self._sprite_frame(self.pip_bar.empty_sprite)
        scale = max(0.1, self.pip_bar.scale)
        icon_w = max(1, round(full_frame.get_width() * scale))
        icon_h = max(1, round(full_frame.get_height() * scale))
        step = icon_w + self.pip_bar.spacing if self.pip_bar.direction != "vertical" else icon_h + self.pip_bar.spacing
        slots = 3  # illustrative only — actual slot count is set per-placement
        if self.pip_bar.direction == "vertical":
            surface = pygame.Surface((icon_w, step * slots), pygame.SRCALPHA)
        else:
            surface = pygame.Surface((step * slots, icon_h), pygame.SRCALPHA)
        for i in range(slots):
            frame = full_frame if i == 0 else (empty_frame or full_frame)
            scaled = frame if scale == 1.0 else pygame.transform.scale(frame, (icon_w, icon_h))
            if self.pip_bar.direction == "vertical":
                surface.blit(scaled, (0, i * step))
            else:
                surface.blit(scaled, (i * step, 0))
        self.preview.set_preview(surface)

    def _refresh_editor(self) -> None:
        if not self.pip_bar:
            self.preview.set_preview(None)
            return
        self.name_edit.blockSignals(True)
        self.direction_combo.blockSignals(True)
        self.spacing_spin.blockSignals(True)
        self.scale_spin.blockSignals(True)
        self.name_edit.setText(self.pip_bar.name)
        direction_index = self.direction_combo.findData(self.pip_bar.direction)
        self.direction_combo.setCurrentIndex(direction_index if direction_index >= 0 else 0)
        self.spacing_spin.setValue(self.pip_bar.spacing)
        self.scale_spin.setValue(self.pip_bar.scale)
        self.name_edit.blockSignals(False)
        self.direction_combo.blockSignals(False)
        self.spacing_spin.blockSignals(False)
        self.scale_spin.blockSignals(False)
        self._populate_sprite_combo(self.full_sprite_combo, self.pip_bar.full_sprite)
        self._populate_sprite_combo(
            self.empty_sprite_combo, self.pip_bar.empty_sprite, placeholder="(none)"
        )
        self._refresh_preview()
        self._sync_range_controls()

    def _apply_fields_to_pip_bar(self) -> None:
        if not self.pip_bar:
            return
        self.pip_bar.name = self.name_edit.text().strip() or "pip_bar"
        full_sprite = self.full_sprite_combo.currentData()
        self.pip_bar.full_sprite = str(full_sprite) if full_sprite else ""
        empty_sprite = self.empty_sprite_combo.currentData()
        self.pip_bar.empty_sprite = str(empty_sprite) if empty_sprite else ""
        direction = self.direction_combo.currentData()
        self.pip_bar.direction = str(direction) if direction else REPEAT_DIRECTIONS[0]
        self.pip_bar.spacing = self.spacing_spin.value()
        self.pip_bar.scale = self.scale_spin.value()

    # -- field signal handlers -----------------------------------------------------

    def _on_fields_changed(self) -> None:
        self._apply_fields_to_pip_bar()
        self._refresh_preview()
        self._mark_dirty()

    # -- public API -----------------------------------------------------

    def new_pip_bar(self, path: Path, full_sprite: str, name: str) -> None:
        self.file_path = path.resolve()
        self.pip_bar = PipBar(name or "pip_bar", full_sprite)
        self._dirty = True
        self._refresh_editor()
        self._update_status()

    def open_pip_bar(self, path: Path) -> None:
        self.file_path = path.resolve()
        try:
            self.pip_bar = load_pip_bar(self.file_path)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Open Pip Bar", str(exc))
            self.pip_bar = None
            self.file_path = None
            return
        self._dirty = False
        self._refresh_editor()
        self._update_status()

    def save(self) -> None:
        if not self.pip_bar or not self.file_path:
            return
        self._apply_fields_to_pip_bar()
        save_pip_bar(self.pip_bar, self.file_path)
        self._dirty = False
        self._update_status()
        self.saved.emit(self.file_path)

    def _rename_pip_bar(self) -> None:
        if not self.pip_bar or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename Pip Bar", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename Pip Bar",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortupipbar"
        if new_path.exists():
            QMessageBox.warning(self, "Rename Pip Bar", f"{new_path.name} already exists.")
            return
        old_path.rename(new_path)
        self.file_path = new_path
        self._update_status()
        self.renamed.emit(old_path, new_path)

    def has_unsaved_changes(self) -> bool:
        return self._dirty
