"""Object editor — define prefabs (sprite, script, hitbox) for scene placement."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPolygonF
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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tortuengine.project import load_project
from tortuengine.object import (
    MAX_OBJECT_ANIMATIONS,
    ObjectAnimation,
    TortuObject,
    load_object,
    save_object,
)
from tortuengine.palette import load_palette, palette_path
from tortuengine.sprite import Sprite, load_sprite
from tortustudio.asset_drag import SpriteDropCombo
from tortustudio.scene_assets import list_sprite_paths


class ObjectPreviewCanvas(QWidget):
    """Sprite preview with origin and optional hitbox overlay."""

    HITBOX_COLOR = (255, 220, 80, 180)
    ORIGIN_COLOR = (255, 100, 100, 220)

    origin_clicked = pyqtSignal(int, int)
    hitbox_moved = pyqtSignal(int, int)
    hitbox_resized = pyqtSignal(int, int, int, int)  # x, y, w, h

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not pygame.get_init():
            pygame.init()
        self._frame: QImage | None = None
        self._sprite_w = 0
        self._sprite_h = 0
        self._hitbox: tuple[int, int, int, int] | None = None
        self._origin = (0, 0)
        self._show_hitbox = True
        self._show_origin = True
        self._dragging_origin = False
        self._hitbox_selected = False
        self._dragging_hitbox = False
        self._dragging_resize: str | None = None
        self._drag_start_screen: tuple[float, float] | None = None
        self._drag_start_hitbox_pos: tuple[int, int] | None = None
        self._drag_start_hitbox: tuple[int, int, int, int] | None = None
        self.zoom = 4
        self.setMinimumSize(120, 120)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Drag the origin marker to move it")

    def set_show_hitbox(self, visible: bool) -> None:
        self._show_hitbox = visible
        self.update()

    def set_show_origin(self, visible: bool) -> None:
        self._show_origin = visible
        self.update()

    def set_zoom(self, zoom: int) -> None:
        self.zoom = max(1, min(16, zoom))
        self.update()

    def set_preview(
        self,
        surface: pygame.Surface | None,
        *,
        hitbox: tuple[int, int, int, int] | None = None,
        origin: tuple[int, int] = (0, 0),
    ) -> None:
        if surface is None:
            self._frame = None
            self._sprite_w = 0
            self._sprite_h = 0
            self._hitbox = None
            self._origin = (0, 0)
            self.update()
            return
        w, h = surface.get_width(), surface.get_height()
        data = pygame.image.tobytes(surface, "RGBA")
        self._frame = QImage(data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        self._sprite_w = w
        self._sprite_h = h
        self._hitbox = hitbox
        self._origin = origin
        self.setMinimumSize(w * self.zoom + 32, h * self.zoom + 32)
        self.update()

    def _sprite_offset(self) -> tuple[int, int, int, int]:
        sw = self._sprite_w * self.zoom
        sh = self._sprite_h * self.zoom
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)
        return ox, oy, sw, sh

    def _event_to_sprite_pixel(self, event: QMouseEvent) -> tuple[int, int] | None:
        if self._frame is None:
            return None
        ox, oy, sw, sh = self._sprite_offset()
        px = (event.position().x() - ox) / self.zoom
        py = (event.position().y() - oy) / self.zoom
        if px < 0 or py < 0 or px >= self._sprite_w or py >= self._sprite_h:
            return None
        return int(px), int(py)

    def _is_near_origin(self, event: QMouseEvent, threshold: int = 8) -> bool:
        if not self._show_origin or self._frame is None:
            return False
        ox, oy, _sw, _sh = self._sprite_offset()
        origin_x, origin_y = self._origin
        cx = ox + origin_x * self.zoom
        cy = oy + origin_y * self.zoom
        dx = event.position().x() - cx
        dy = event.position().y() - cy
        return dx * dx + dy * dy <= threshold * threshold

    def _is_near_hitbox_border(self, mx: float, my: float, threshold: int = 8) -> bool:
        if not self._show_hitbox or self._hitbox is None or self._frame is None:
            return False
        ox, oy, _sw, _sh = self._sprite_offset()
        hx, hy, hw, hh = self._hitbox
        sx0 = ox + hx * self.zoom
        sy0 = oy + hy * self.zoom
        sx1 = sx0 + hw * self.zoom
        sy1 = sy0 + hh * self.zoom
        in_outer = sx0 - threshold <= mx <= sx1 + threshold and sy0 - threshold <= my <= sy1 + threshold
        in_inner = sx0 + threshold < mx < sx1 - threshold and sy0 + threshold < my < sy1 - threshold
        return in_outer and not in_inner

    def _hitbox_center_screen(self) -> tuple[int, int] | None:
        if self._hitbox is None:
            return None
        ox, oy, _sw, _sh = self._sprite_offset()
        hx, hy, hw, hh = self._hitbox
        return int(ox + (hx + hw / 2) * self.zoom), int(oy + (hy + hh / 2) * self.zoom)

    def _get_arrow_positions(self) -> dict[str, tuple[float, float]]:
        """Center screen positions of the 4 resize arrows on each side."""
        if self._hitbox is None or self._frame is None:
            return {}
        ox, oy, _sw, _sh = self._sprite_offset()
        hx, hy, hw, hh = self._hitbox
        sx0 = ox + hx * self.zoom
        sy0 = oy + hy * self.zoom
        sx1 = sx0 + hw * self.zoom
        sy1 = sy0 + hh * self.zoom
        mx = (sx0 + sx1) / 2
        my = (sy0 + sy1) / 2
        return {
            'top': (mx, sy0),
            'bottom': (mx, sy1),
            'left': (sx0, my),
            'right': (sx1, my),
        }

    def _get_arrow_hit(self, mx: float, my: float, radius: int = 12) -> str | None:
        """Return which resize arrow is at (mx, my), or None."""
        if not self._hitbox_selected:
            return None
        for edge, (ax, ay) in self._get_arrow_positions().items():
            if (mx - ax) ** 2 + (my - ay) ** 2 <= radius * radius:
                return edge
        return None

    def _draw_move_icon(self, painter: QPainter, cx: int, cy: int) -> None:
        arm, tip = 10, 5
        for color, width in [(QColor(0, 0, 0, 200), 3), (QColor(255, 255, 255, 230), 2)]:
            pen = QPen(color)
            pen.setWidth(width)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLine(cx - arm, cy, cx + arm, cy)
            painter.drawLine(cx, cy - arm, cx, cy + arm)
            for ax, ay, bx, by, ex, ey in [
                (cx, cy - arm - tip, cx - tip, cy - arm, cx + tip, cy - arm),
                (cx, cy + arm + tip, cx - tip, cy + arm, cx + tip, cy + arm),
                (cx - arm - tip, cy, cx - arm, cy - tip, cx - arm, cy + tip),
                (cx + arm + tip, cy, cx + arm, cy - tip, cx + arm, cy + tip),
            ]:
                painter.drawLine(ax, ay, bx, by)
                painter.drawLine(ax, ay, ex, ey)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawEllipse(cx - 3, cy - 3, 6, 6)

    def _draw_resize_arrow(self, painter: QPainter, cx: float, cy: float, direction: str) -> None:
        s, h = 9, 5
        if direction == 'top':
            pts = [QPointF(cx, cy - s), QPointF(cx - h, cy + 2), QPointF(cx + h, cy + 2)]
        elif direction == 'bottom':
            pts = [QPointF(cx, cy + s), QPointF(cx - h, cy - 2), QPointF(cx + h, cy - 2)]
        elif direction == 'left':
            pts = [QPointF(cx - s, cy), QPointF(cx + 2, cy - h), QPointF(cx + 2, cy + h)]
        else:
            pts = [QPointF(cx + s, cy), QPointF(cx - 2, cy - h), QPointF(cx - 2, cy + h)]
        poly = QPolygonF(pts)
        pen = QPen(QColor(0, 0, 0, 200))
        pen.setWidth(2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.drawPolygon(poly)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        mx, my = event.position().x(), event.position().y()

        if self._hitbox_selected and self._hitbox is not None:
            arrow = self._get_arrow_hit(mx, my)
            if arrow is not None:
                self._dragging_resize = arrow
                self._drag_start_screen = (mx, my)
                self._drag_start_hitbox = tuple(self._hitbox)  # type: ignore[assignment]
                return
            center = self._hitbox_center_screen()
            if center is not None:
                cdx, cdy = mx - center[0], my - center[1]
                if cdx * cdx + cdy * cdy <= 14 * 14:
                    self._dragging_hitbox = True
                    self._drag_start_screen = (mx, my)
                    self._drag_start_hitbox_pos = (self._hitbox[0], self._hitbox[1])
                    return

        if self._is_near_hitbox_border(mx, my):
            if not self._hitbox_selected:
                self._hitbox_selected = True
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                self.update()
            return

        if self._hitbox_selected:
            self._hitbox_selected = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()

        if self._is_near_origin(event):
            self._dragging_origin = True

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging_origin and event.buttons() & Qt.MouseButton.LeftButton:
            pixel = self._event_to_sprite_pixel(event)
            if pixel is not None:
                self._origin = pixel
                self.origin_clicked.emit(pixel[0], pixel[1])
                self.update()
            return

        if self._dragging_resize is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self._drag_start_screen and self._drag_start_hitbox and self._hitbox:
                dx_px = int((event.position().x() - self._drag_start_screen[0]) / self.zoom)
                dy_px = int((event.position().y() - self._drag_start_screen[1]) / self.zoom)
                ox, oy, ow, oh = self._drag_start_hitbox
                if self._dragging_resize == 'top':
                    dy = max(-oy, min(oh - 1, dy_px))
                    self._hitbox = (ox, oy + dy, ow, oh - dy)
                    self.hitbox_resized.emit(ox, oy + dy, ow, oh - dy)
                elif self._dragging_resize == 'bottom':
                    dy = max(1 - oh, min(self._sprite_h - oy - oh, dy_px))
                    self._hitbox = (ox, oy, ow, oh + dy)
                    self.hitbox_resized.emit(ox, oy, ow, oh + dy)
                elif self._dragging_resize == 'left':
                    dx = max(-ox, min(ow - 1, dx_px))
                    self._hitbox = (ox + dx, oy, ow - dx, oh)
                    self.hitbox_resized.emit(ox + dx, oy, ow - dx, oh)
                elif self._dragging_resize == 'right':
                    dx = max(1 - ow, min(self._sprite_w - ox - ow, dx_px))
                    self._hitbox = (ox, oy, ow + dx, oh)
                    self.hitbox_resized.emit(ox, oy, ow + dx, oh)
                self.update()
            return

        if self._dragging_hitbox and event.buttons() & Qt.MouseButton.LeftButton:
            if self._drag_start_screen and self._drag_start_hitbox_pos and self._hitbox:
                dx = int((event.position().x() - self._drag_start_screen[0]) / self.zoom)
                dy = int((event.position().y() - self._drag_start_screen[1]) / self.zoom)
                new_x = self._drag_start_hitbox_pos[0] + dx
                new_y = self._drag_start_hitbox_pos[1] + dy
                hw, hh = self._hitbox[2], self._hitbox[3]
                new_x = max(0, min(self._sprite_w - hw, new_x))
                new_y = max(0, min(self._sprite_h - hh, new_y))
                self._hitbox = (new_x, new_y, hw, hh)
                self.hitbox_moved.emit(new_x, new_y)
                self.update()
            return

        mx, my = event.position().x(), event.position().y()
        if self._hitbox_selected:
            arrow = self._get_arrow_hit(mx, my)
            if arrow in ('top', 'bottom'):
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            elif arrow in ('left', 'right'):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif self._is_near_hitbox_border(mx, my):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            if self._is_near_hitbox_border(mx, my):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_origin = False
            self._dragging_hitbox = False
            self._dragging_resize = None
            self._drag_start_screen = None
            self._drag_start_hitbox_pos = None
            self._drag_start_hitbox = None

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        if self._frame is None:
            painter.end()
            return

        sw = self._sprite_w * self.zoom
        sh = self._sprite_h * self.zoom
        ox, oy, sw, sh = self._sprite_offset()

        scaled = self._frame.scaled(
            sw,
            sh,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        painter.drawImage(ox, oy, scaled)

        if self._show_origin:
            origin_x, origin_y = self._origin
            cx = ox + origin_x * self.zoom
            cy = oy + origin_y * self.zoom
            pen = QPen(QColor(*self.ORIGIN_COLOR))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLine(int(cx - 6), int(cy), int(cx + 6), int(cy))
            painter.drawLine(int(cx), int(cy - 6), int(cx), int(cy + 6))
            painter.drawEllipse(int(cx - 3), int(cy - 3), 6, 6)

        if self._show_hitbox and self._hitbox is not None:
            hx, hy, hw, hh = self._hitbox
            pen = QPen(QColor(*self.HITBOX_COLOR))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(
                ox + hx * self.zoom,
                oy + hy * self.zoom,
                hw * self.zoom,
                hh * self.zoom,
            )
            if self._hitbox_selected or self._dragging_hitbox or self._dragging_resize:
                center = self._hitbox_center_screen()
                if center is not None:
                    self._draw_move_icon(painter, *center)
                for edge, (ax, ay) in self._get_arrow_positions().items():
                    self._draw_resize_arrow(painter, ax, ay, edge)

        painter.end()


class ObjectEditorWidget(QWidget):
    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_object_requested = pyqtSignal()
    open_object_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.tortu_object: TortuObject | None = None
        self._sprite: Sprite | None = None
        self._palette_colors: list[tuple[int, int, int]] = []
        self._dirty = False
        self._preview_frame = 0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(125)
        self._anim_timer.timeout.connect(self._advance_preview_frame)

        self.preview = ObjectPreviewCanvas()
        self.preview.origin_clicked.connect(self._on_preview_origin_clicked)
        self.preview.hitbox_moved.connect(self._on_preview_hitbox_moved)
        self.preview.hitbox_resized.connect(self._on_preview_hitbox_resized)

        self.btn_save = QPushButton("Save object")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_object)
        self.btn_new = QPushButton("New Object…")
        self.btn_new.clicked.connect(self.new_object_requested.emit)
        self.btn_open = QPushButton("Open Object…")
        self.btn_open.clicked.connect(self.open_object_requested.emit)

        self.status_label = QLabel("No object open")

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_fields_changed)

        self.animation_combo = QComboBox()
        self.animation_combo.currentIndexChanged.connect(self._on_animation_changed)

        self.anim_name_edit = QLineEdit()
        self.anim_name_edit.textChanged.connect(self._on_animation_fields_changed)

        self.anim_sprite_combo = SpriteDropCombo()
        self.anim_sprite_combo.currentIndexChanged.connect(self._on_animation_sprite_changed)
        self.anim_sprite_combo.sprite_dropped.connect(self._on_sprite_dropped)

        self.default_animation_combo = QComboBox()
        self.default_animation_combo.currentIndexChanged.connect(self._on_default_animation_changed)

        self.btn_add_animation = QPushButton("Add animation")
        self.btn_add_animation.clicked.connect(self._add_animation)
        self.btn_remove_animation = QPushButton("Remove animation")
        self.btn_remove_animation.clicked.connect(self._remove_animation)

        self.script_edit = QLineEdit()
        self.script_edit.setPlaceholderText("scripts/my_object.py")
        self.script_edit.textChanged.connect(self._on_fields_changed)
        self.script_edit.textChanged.connect(self._refresh_script_row)

        self.btn_browse_script = QPushButton("Browse…")
        self.btn_browse_script.clicked.connect(self._browse_script)
        self.btn_open_script = QPushButton("Open script")
        self.btn_open_script.clicked.connect(self._open_script_in_editor)

        self.btn_create_script = QPushButton("Create Script")
        self.btn_create_script.clicked.connect(self._create_script)

        self._script_container = QWidget()
        _script_vbox = QVBoxLayout(self._script_container)
        _script_vbox.setContentsMargins(0, 0, 0, 0)
        _script_vbox.setSpacing(2)
        _script_vbox.addWidget(self.btn_create_script)
        self._script_edit_row = QWidget()
        _script_edit_inner = QHBoxLayout(self._script_edit_row)
        _script_edit_inner.setContentsMargins(0, 0, 0, 0)
        _script_edit_inner.addWidget(self.script_edit, stretch=1)
        _script_edit_inner.addWidget(self.btn_browse_script)
        _script_edit_inner.addWidget(self.btn_open_script)
        _script_vbox.addWidget(self._script_edit_row)

        self.solid = QCheckBox("Solid (collides with tiles)")
        self.solid.toggled.connect(self._on_fields_changed)

        self.origin_x = QSpinBox()
        self.origin_y = QSpinBox()
        for spin in (self.origin_x, self.origin_y):
            spin.setRange(0, 512)
            spin.setToolTip("Placement anchor in sprite pixels (scene x/y aligns here)")
            spin.valueChanged.connect(self._on_origin_changed)

        self.show_origin = QCheckBox("Show origin on preview")
        self.show_origin.setChecked(True)
        self.show_origin.toggled.connect(self.preview.set_show_origin)

        self.hitbox_x = QSpinBox()
        self.hitbox_y = QSpinBox()
        self.hitbox_w = QSpinBox()
        self.hitbox_h = QSpinBox()
        for spin in (self.hitbox_x, self.hitbox_y, self.hitbox_w, self.hitbox_h):
            spin.setRange(0, 512)
            spin.valueChanged.connect(self._on_hitbox_changed)

        self.hitbox_full_sprite = QCheckBox("Full sprite hitbox")
        self.hitbox_full_sprite.setChecked(True)
        self.hitbox_full_sprite.toggled.connect(self._on_hitbox_full_toggled)

        self.show_hitbox = QCheckBox("Show hitbox on preview")
        self.show_hitbox.setChecked(True)
        self.show_hitbox.toggled.connect(self.preview.set_show_hitbox)

        self.preview_frame = QSpinBox()
        self.preview_frame.setRange(0, 0)
        self.preview_frame.valueChanged.connect(self._on_preview_frame_changed)

        self.preview_animate = QCheckBox("Animate preview")
        self.preview_animate.toggled.connect(self._on_preview_animate_toggled)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(1, 16)
        self.zoom_spin.setValue(4)
        self.zoom_spin.valueChanged.connect(self.preview.set_zoom)

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
        body.addWidget(preview_group, stretch=1)

        form = QFormLayout()
        form.addRow("Display name:", self.name_edit)
        form.addRow("Script:", self._script_container)
        form.addRow(QLabel("<b>Animations</b>"))
        form.addRow("Active animation:", self.animation_combo)
        form.addRow("Animation name:", self.anim_name_edit)
        form.addRow("Sprite:", self.anim_sprite_combo)
        form.addRow("Default animation:", self.default_animation_combo)
        anim_btns = QHBoxLayout()
        anim_btns.addWidget(self.btn_add_animation)
        anim_btns.addWidget(self.btn_remove_animation)
        form.addRow(anim_btns)
        form.addRow("", self.solid)
        form.addRow(QLabel("<b>Origin</b> (placement anchor)"))
        form.addRow("X:", self.origin_x)
        form.addRow("Y:", self.origin_y)
        form.addRow("", self.show_origin)
        form.addRow(QLabel("<b>Hitbox</b> (sprite pixels)"))
        form.addRow("", self.hitbox_full_sprite)
        form.addRow("X:", self.hitbox_x)
        form.addRow("Y:", self.hitbox_y)
        form.addRow("Width:", self.hitbox_w)
        form.addRow("Height:", self.hitbox_h)
        form.addRow("", self.show_hitbox)
        form.addRow("Preview frame:", self.preview_frame)
        form.addRow("", self.preview_animate)
        form.addRow("Zoom:", self.zoom_spin)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addLayout(form)
        side_layout.addStretch()
        body.addWidget(side)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._update_status()

    def _update_status(self) -> None:
        if not self.tortu_object or not self.file_path:
            self.status_label.setText("No object open")
            return
        state = "edited" if self._dirty else "saved"
        self.status_label.setText(f"{self.file_path.name} ({state})")

    def _active_animation_index(self) -> int:
        if self.animation_combo.count() == 0:
            return -1
        return self.animation_combo.currentIndex()

    def _set_combo_sprite(self, combo: QComboBox, rel_path: str) -> None:
        if not rel_path:
            return
        index = combo.findData(rel_path)
        if index < 0:
            combo.addItem(rel_path, rel_path)
            index = combo.findData(rel_path)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _populate_sprite_combo(self, combo: QComboBox, current: str) -> None:
        combo.blockSignals(True)
        combo.clear()
        for rel in list_sprite_paths(self.project_root):
            combo.addItem(rel, rel)
        if current and combo.findData(current) < 0:
            combo.addItem(current, current)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _on_sprite_dropped(self, rel_path: str) -> None:
        if not self.tortu_object:
            return
        self._set_combo_sprite(self.anim_sprite_combo, rel_path)
        self._on_animation_sprite_changed(self.anim_sprite_combo.currentIndex())

    def _sync_animation_controls(self) -> None:
        if not self.tortu_object:
            self.animation_combo.blockSignals(True)
            self.default_animation_combo.blockSignals(True)
            self.animation_combo.clear()
            self.default_animation_combo.clear()
            self.animation_combo.blockSignals(False)
            self.default_animation_combo.blockSignals(False)
            self.btn_add_animation.setEnabled(False)
            self.btn_remove_animation.setEnabled(False)
            return

        active = self._active_animation_index()
        self.animation_combo.blockSignals(True)
        self.default_animation_combo.blockSignals(True)
        self.animation_combo.clear()
        self.default_animation_combo.clear()
        for i, anim in enumerate(self.tortu_object.animations):
            self.animation_combo.addItem(f"{i}: {anim.name}", i)
            self.default_animation_combo.addItem(anim.name, anim.name)
        if self.tortu_object.animations:
            pick = min(max(active, 0), len(self.tortu_object.animations) - 1)
            self.animation_combo.setCurrentIndex(pick)
            self._load_animation_fields(self.tortu_object.animations[pick])
            default_index = self.default_animation_combo.findData(
                self.tortu_object.default_animation
            )
            self.default_animation_combo.setCurrentIndex(
                default_index if default_index >= 0 else 0
            )
        self.animation_combo.blockSignals(False)
        self.default_animation_combo.blockSignals(False)
        self.btn_add_animation.setEnabled(
            len(self.tortu_object.animations) < MAX_OBJECT_ANIMATIONS
        )
        self.btn_remove_animation.setEnabled(len(self.tortu_object.animations) > 1)

    def _load_animation_fields(self, anim: ObjectAnimation) -> None:
        self.anim_name_edit.blockSignals(True)
        self._populate_sprite_combo(self.anim_sprite_combo, anim.sprite)
        self.anim_name_edit.setText(anim.name)
        self.anim_name_edit.blockSignals(False)

    def _save_animation_fields(self, anim: ObjectAnimation) -> None:
        name = self.anim_name_edit.text().strip().replace(" ", "_")
        if name:
            anim.name = name
        rel = self.anim_sprite_combo.currentData()
        if rel:
            anim.sprite = str(rel)

    def _preview_sprite_path(self) -> str:
        if not self.tortu_object or not self.tortu_object.animations:
            return ""
        index = self._active_animation_index()
        if 0 <= index < len(self.tortu_object.animations):
            return self.tortu_object.animations[index].sprite
        return self.tortu_object.default_sprite

    def _load_sprite_asset(self) -> bool:
        sprite_path = self._preview_sprite_path()
        if not sprite_path:
            self._sprite = None
            self._palette_colors = []
            return False
        path = (self.project_root / sprite_path).resolve()
        if not path.is_file():
            QMessageBox.warning(self, "Object Editor", f"Sprite not found: {path}")
            self._sprite = None
            return False
        try:
            self._sprite = load_sprite(path)
            palette_file = palette_path(self.project_root, self._sprite.palette)
            self._palette_colors = load_palette(palette_file)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Object Editor", str(exc))
            self._sprite = None
            return False
        return True

    def _sync_sprite_combo(self) -> None:
        """Legacy hook — animation controls own sprite pickers now."""
        self._sync_animation_controls()

    def _resolved_hitbox(self) -> tuple[int, int, int, int] | None:
        if not self._sprite:
            return None
        obj = self.tortu_object
        if obj is None:
            return None
        return obj.hitbox.resolved(self._sprite.pixel_width, self._sprite.pixel_height)

    def _refresh_preview(self) -> None:
        if not self._sprite or not self._palette_colors:
            self.preview.set_preview(None)
            return
        frame_index = min(self._preview_frame, self._sprite.frame_count - 1)
        surface = self._sprite.to_surface(self._palette_colors, frame_index=frame_index)
        origin = (0, 0)
        if self.tortu_object:
            origin = (self.tortu_object.origin.x, self.tortu_object.origin.y)
        self.preview.set_preview(
            surface,
            hitbox=self._resolved_hitbox(),
            origin=origin,
        )

    def _refresh_origin_controls(self) -> None:
        if not self.tortu_object or not self._sprite:
            return
        max_w = max(0, self._sprite.pixel_width - 1)
        max_h = max(0, self._sprite.pixel_height - 1)
        origin = self.tortu_object.origin
        self.origin_x.blockSignals(True)
        self.origin_y.blockSignals(True)
        self.origin_x.setMaximum(max_w)
        self.origin_y.setMaximum(max_h)
        self.origin_x.setValue(min(origin.x, max_w))
        self.origin_y.setValue(min(origin.y, max_h))
        self.origin_x.blockSignals(False)
        self.origin_y.blockSignals(False)

    def _refresh_hitbox_controls(self) -> None:
        if not self.tortu_object or not self._sprite:
            return
        self._refresh_origin_controls()
        full = (
            self.tortu_object.hitbox.w == 0
            and self.tortu_object.hitbox.h == 0
            and self.tortu_object.hitbox.x == 0
            and self.tortu_object.hitbox.y == 0
        )
        self.hitbox_full_sprite.blockSignals(True)
        self.hitbox_full_sprite.setChecked(full)
        self.hitbox_full_sprite.blockSignals(False)

        enabled = not full
        for spin in (self.hitbox_x, self.hitbox_y, self.hitbox_w, self.hitbox_h):
            spin.setEnabled(enabled)

        max_w = self._sprite.pixel_width
        max_h = self._sprite.pixel_height
        hb = self.tortu_object.hitbox
        rx, ry, rw, rh = hb.resolved(max_w, max_h)

        self.hitbox_x.blockSignals(True)
        self.hitbox_y.blockSignals(True)
        self.hitbox_w.blockSignals(True)
        self.hitbox_h.blockSignals(True)
        self.hitbox_x.setMaximum(max(0, max_w - 1))
        self.hitbox_y.setMaximum(max(0, max_h - 1))
        self.hitbox_w.setMaximum(max_w)
        self.hitbox_h.setMaximum(max_h)
        self.hitbox_x.setValue(hb.x if not full else 0)
        self.hitbox_y.setValue(hb.y if not full else 0)
        self.hitbox_w.setValue(rw if not full else max_w)
        self.hitbox_h.setValue(rh if not full else max_h)
        self.hitbox_x.blockSignals(False)
        self.hitbox_y.blockSignals(False)
        self.hitbox_w.blockSignals(False)
        self.hitbox_h.blockSignals(False)

        self.preview_frame.blockSignals(True)
        self.preview_frame.setMaximum(max(0, self._sprite.frame_count - 1))
        self.preview_frame.setValue(min(self._preview_frame, self._sprite.frame_count - 1))
        self.preview_frame.blockSignals(False)

    def _refresh_editor(self) -> None:
        if not self.tortu_object:
            self.preview.set_preview(None)
            return
        self.name_edit.blockSignals(True)
        self.script_edit.blockSignals(True)
        self.solid.blockSignals(True)
        self.name_edit.setText(self.tortu_object.name)
        self.script_edit.setText(self.tortu_object.script)
        self.solid.setChecked(self.tortu_object.solid)
        self.name_edit.blockSignals(False)
        self.script_edit.blockSignals(False)
        self.solid.blockSignals(False)
        self._refresh_script_row()
        self._sync_animation_controls()
        if self._load_sprite_asset():
            self._refresh_hitbox_controls()
            self._refresh_preview()

    def _apply_fields_to_object(self) -> None:
        if not self.tortu_object:
            return
        self.tortu_object.name = self.name_edit.text().strip() or "object"
        index = self._active_animation_index()
        if 0 <= index < len(self.tortu_object.animations):
            self._save_animation_fields(self.tortu_object.animations[index])
        self.tortu_object.script = self.script_edit.text().strip()
        self.tortu_object.solid = self.solid.isChecked()

    def _on_fields_changed(self) -> None:
        self._apply_fields_to_object()
        self._mark_dirty()

    def _on_animation_changed(self, index: int) -> None:
        if not self.tortu_object or index < 0:
            return
        if index >= len(self.tortu_object.animations):
            return
        self._load_animation_fields(self.tortu_object.animations[index])
        self._preview_frame = 0
        if self._load_sprite_asset():
            self._refresh_hitbox_controls()
            self._refresh_preview()

    def _on_animation_fields_changed(self) -> None:
        if not self.tortu_object:
            return
        index = self._active_animation_index()
        if index < 0 or index >= len(self.tortu_object.animations):
            return
        anim = self.tortu_object.animations[index]
        old_name = anim.name
        self._save_animation_fields(anim)
        if anim.name != old_name:
            if self.tortu_object.default_animation == old_name:
                self.tortu_object.default_animation = anim.name
            self._sync_animation_controls()
        else:
            label = f"{index}: {anim.name}"
            self.animation_combo.blockSignals(True)
            self.animation_combo.setItemText(index, label)
            self.animation_combo.blockSignals(False)
        self._mark_dirty()

    def _on_animation_sprite_changed(self, _index: int) -> None:
        if not self.tortu_object:
            return
        anim_index = self._active_animation_index()
        if anim_index < 0 or anim_index >= len(self.tortu_object.animations):
            return
        rel = self.anim_sprite_combo.currentData()
        if not rel:
            return
        self.tortu_object.animations[anim_index].sprite = str(rel)
        self._preview_frame = 0
        self._mark_dirty()
        if self._load_sprite_asset():
            self._refresh_hitbox_controls()
            self._refresh_preview()

    def _on_default_animation_changed(self, _index: int) -> None:
        if not self.tortu_object:
            return
        name = self.default_animation_combo.currentData()
        if name:
            self.tortu_object.default_animation = str(name)
            self._mark_dirty()

    def _add_animation(self) -> None:
        if not self.tortu_object:
            return
        if len(self.tortu_object.animations) >= MAX_OBJECT_ANIMATIONS:
            QMessageBox.warning(
                self, "Add Animation", f"Maximum {MAX_OBJECT_ANIMATIONS} animations."
            )
            return
        sprites = list_sprite_paths(self.project_root)
        if not sprites:
            QMessageBox.warning(self, "Add Animation", "Create a sprite asset first.")
            return
        base = "anim"
        n = 1
        names = {a.name for a in self.tortu_object.animations}
        while f"{base}{n}" in names:
            n += 1
        new_name = f"{base}{n}"
        self.tortu_object.animations.append(ObjectAnimation(new_name, sprites[0]))
        self._mark_dirty()
        self._sync_animation_controls()
        self.animation_combo.setCurrentIndex(len(self.tortu_object.animations) - 1)
        if self._load_sprite_asset():
            self._refresh_hitbox_controls()
            self._refresh_preview()

    def _remove_animation(self) -> None:
        if not self.tortu_object:
            return
        index = self._active_animation_index()
        if index < 0:
            return
        if len(self.tortu_object.animations) <= 1:
            QMessageBox.warning(self, "Remove Animation", "Keep at least one animation.")
            return
        removed = self.tortu_object.animations.pop(index)
        if self.tortu_object.default_animation == removed.name:
            self.tortu_object.default_animation = self.tortu_object.animations[0].name
        self._mark_dirty()
        self._sync_animation_controls()
        if self._load_sprite_asset():
            self._refresh_hitbox_controls()
            self._refresh_preview()

    def _on_origin_changed(self) -> None:
        if not self.tortu_object:
            return
        self.tortu_object.origin.x = self.origin_x.value()
        self.tortu_object.origin.y = self.origin_y.value()
        self._refresh_preview()
        self._mark_dirty()

    def _on_preview_origin_clicked(self, x: int, y: int) -> None:
        if not self.tortu_object:
            return
        self.tortu_object.origin.x = x
        self.tortu_object.origin.y = y
        self.origin_x.blockSignals(True)
        self.origin_y.blockSignals(True)
        self.origin_x.setValue(x)
        self.origin_y.setValue(y)
        self.origin_x.blockSignals(False)
        self.origin_y.blockSignals(False)
        self._refresh_preview()
        self._mark_dirty()

    def _on_preview_hitbox_moved(self, x: int, y: int) -> None:
        if not self.tortu_object or not self._sprite:
            return
        if self.hitbox_full_sprite.isChecked():
            self.hitbox_full_sprite.blockSignals(True)
            self.hitbox_full_sprite.setChecked(False)
            self.hitbox_full_sprite.blockSignals(False)
            self.tortu_object.hitbox.w = self._sprite.pixel_width
            self.tortu_object.hitbox.h = self._sprite.pixel_height
        self.tortu_object.hitbox.x = x
        self.tortu_object.hitbox.y = y
        self._refresh_hitbox_controls()
        self._mark_dirty()

    def _on_preview_hitbox_resized(self, x: int, y: int, w: int, h: int) -> None:
        if not self.tortu_object or not self._sprite:
            return
        if self.hitbox_full_sprite.isChecked():
            self.hitbox_full_sprite.blockSignals(True)
            self.hitbox_full_sprite.setChecked(False)
            self.hitbox_full_sprite.blockSignals(False)
        self.tortu_object.hitbox.x = x
        self.tortu_object.hitbox.y = y
        self.tortu_object.hitbox.w = max(1, w)
        self.tortu_object.hitbox.h = max(1, h)
        self._refresh_hitbox_controls()
        self._mark_dirty()

    def _on_hitbox_full_toggled(self, full: bool) -> None:
        if not self.tortu_object or not self._sprite:
            return
        if full:
            self.tortu_object.hitbox = self.tortu_object.hitbox.__class__()
        else:
            self.tortu_object.hitbox.w = self._sprite.pixel_width
            self.tortu_object.hitbox.h = self._sprite.pixel_height
        self._refresh_hitbox_controls()
        self._refresh_preview()
        self._mark_dirty()

    def _on_hitbox_changed(self) -> None:
        if not self.tortu_object or not self._sprite or self.hitbox_full_sprite.isChecked():
            return
        self.tortu_object.hitbox.x = self.hitbox_x.value()
        self.tortu_object.hitbox.y = self.hitbox_y.value()
        self.tortu_object.hitbox.w = max(1, self.hitbox_w.value())
        self.tortu_object.hitbox.h = max(1, self.hitbox_h.value())
        self._refresh_preview()
        self._mark_dirty()

    def _on_preview_frame_changed(self, value: int) -> None:
        self._preview_frame = value
        self._refresh_preview()

    def _on_preview_animate_toggled(self, enabled: bool) -> None:
        if enabled and self._sprite and self._sprite.frame_count > 1:
            interval = max(16, int(1000 / max(1, self._sprite.fps)))
            self._anim_timer.setInterval(interval)
            self._anim_timer.start()
        else:
            self._anim_timer.stop()

    def _advance_preview_frame(self) -> None:
        if not self._sprite or self._sprite.frame_count <= 1:
            return
        self._preview_frame = (self._preview_frame + 1) % self._sprite.frame_count
        self.preview_frame.blockSignals(True)
        self.preview_frame.setValue(self._preview_frame)
        self.preview_frame.blockSignals(False)
        self._refresh_preview()

    def _refresh_script_row(self) -> None:
        has_script = bool(self.script_edit.text().strip())
        self.btn_create_script.setVisible(not has_script)
        self._script_edit_row.setVisible(has_script)

    def _create_script(self) -> None:
        if not self.tortu_object or not self.file_path:
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
            name = self.tortu_object.name
            template = (
                f'"""Script for {name}."""\n\n\n'
                "def init(engine):\n    pass\n\n\n"
                "def update(dt):\n    pass\n\n\n"
                "def draw(engine):\n    pass\n"
            )
            script_path.write_text(template, encoding="utf-8")
        rel = script_path.resolve().relative_to(self.project_root.resolve()).as_posix()
        self.script_edit.setText(rel)
        self._on_fields_changed()
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

    def new_object(self, path: Path, sprite: str, name: str, animation_name: str = "idle") -> None:
        self.file_path = path.resolve()
        try:
            self.tortu_object = TortuObject.create(name, sprite, animation_name)
        except ValueError as exc:
            QMessageBox.warning(self, "New Object", str(exc))
            self.tortu_object = None
            self.file_path = None
            return
        self._dirty = True
        self._preview_frame = 0
        self._refresh_editor()
        self._update_status()

    def open_object(self, path: Path) -> None:
        self.file_path = path.resolve()
        try:
            self.tortu_object = load_object(self.file_path)
        except (FileNotFoundError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Open Object", str(exc))
            self.tortu_object = None
            self.file_path = None
            return
        self._dirty = False
        self._preview_frame = 0
        self._refresh_editor()
        self._update_status()

    def save(self) -> None:
        if not self.tortu_object or not self.file_path:
            return
        self._apply_fields_to_object()
        if not self.tortu_object.animations:
            QMessageBox.warning(self, "Save Object", "Add at least one animation before saving.")
            return
        save_object(self.tortu_object, self.file_path)
        self._dirty = False
        self._update_status()
        self.saved.emit(self.file_path)

    def _rename_object(self) -> None:
        if not self.tortu_object or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename Object", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename Object",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortuobject"
        if new_path.exists():
            QMessageBox.warning(self, "Rename Object", f"{new_path.name} already exists.")
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
