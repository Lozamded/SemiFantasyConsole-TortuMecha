"""Pygame framebuffer embedded in a Qt widget."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pygame
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPen,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.engine import TortuEngine
from tortuengine.scene import Scene, load_scene
from tortuengine.scene_renderer import SceneRenderer

class _KeyProxy:
    """Returned by the patched pygame.key.get_pressed() in debug-play mode.

    Supports both indexing (``proxy[pygame.K_UP]``) and ``bool`` conversion so
    game scripts work unchanged regardless of how large the key constant is.
    """

    def __init__(self) -> None:
        self._held: set[int] = set()

    def __getitem__(self, key: int) -> bool:
        return key in self._held

    def press(self, key: int) -> None:
        self._held.add(key)

    def release(self, key: int) -> None:
        self._held.discard(key)

    def clear(self) -> None:
        self._held.clear()


# Qt key → pygame key constant mapping (all keys used by game scripts)
_QT_TO_PYGAME: dict[int, int] = {
    Qt.Key.Key_Left: pygame.K_LEFT,
    Qt.Key.Key_Right: pygame.K_RIGHT,
    Qt.Key.Key_Up: pygame.K_UP,
    Qt.Key.Key_Down: pygame.K_DOWN,
    Qt.Key.Key_Space: pygame.K_SPACE,
    Qt.Key.Key_Z: pygame.K_z,
    Qt.Key.Key_X: pygame.K_x,
    Qt.Key.Key_C: pygame.K_c,
    Qt.Key.Key_W: pygame.K_w,
    Qt.Key.Key_A: pygame.K_a,
    Qt.Key.Key_S: pygame.K_s,
    Qt.Key.Key_D: pygame.K_d,
    Qt.Key.Key_Shift: pygame.K_LSHIFT,
    Qt.Key.Key_Return: pygame.K_RETURN,
    Qt.Key.Key_Escape: pygame.K_ESCAPE,
}

# Colors for collider overlay
_COLLIDER_ACTIVE_FILL   = QColor(80, 200, 80, 40)
_COLLIDER_ACTIVE_BORDER = QColor(80, 220, 80, 210)
_COLLIDER_INACTIVE_FILL   = QColor(200, 80, 60, 30)
_COLLIDER_INACTIVE_BORDER = QColor(220, 80, 60, 170)
_ORIGIN_COLOR = QColor(255, 230, 50, 230)


@dataclass
class DebugEntity:
    """Runtime position + static collider/origin info for one object instance."""
    px: float
    py: float
    cam_x: float = 0.0
    cam_y: float = 0.0
    origin_x: int = 0
    origin_y: int = 0
    # (sprite-pixel x, sprite-pixel y, w, h, active)
    colliders: list[tuple[int, int, int, int, bool]] = field(default_factory=list)
    name: str = ""


class ViewportWidget(QWidget):
    """264×198 engine preview scaled with nearest-neighbor filtering."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(SCREEN_WIDTH * 2, SCREEN_HEIGHT * 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #1a1a2e;")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.engine = TortuEngine()
        self._frame: QImage | None = None
        self._playing = False
        self._fps = 60
        self._scene: Scene | None = None
        self._scene_renderer: SceneRenderer | None = None
        self._scene_path: Path | None = None
        self._camera_x = 0
        self._camera_y = 0
        self._use_scene_preview = False
        self._pending_game_module = None

        # Debug-play state
        self._debug_mode: bool = False
        self._debug_probe: Callable[[], list[DebugEntity]] | None = None
        self._key_proxy = _KeyProxy()
        self._original_get_pressed = None

        self._timer = QTimer(self)
        self._timer.setInterval(1000 // self._fps)
        self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_fps(self, fps: int) -> None:
        self._fps = max(1, fps)
        self.engine.set_fps(self._fps)
        self._timer.setInterval(max(1, 1000 // self._fps))

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def scene_preview_active(self) -> bool:
        return self._use_scene_preview and self._scene is not None

    def set_game(self, module) -> None:
        self._use_scene_preview = False
        self._scene = None
        self._scene_renderer = None
        self._scene_path = None
        self._pending_game_module = module
        self.engine.unload_game()
        self._refresh_frame()

    def set_debug_mode(self, enabled: bool) -> None:
        """Enable or disable the collider/origin debug overlay."""
        self._debug_mode = enabled
        if enabled:
            self._patch_keyboard()
        else:
            self._unpatch_keyboard()
            self._key_proxy.clear()
        self.update()

    def set_debug_probe(self, fn: Callable[[], list[DebugEntity]] | None) -> None:
        """Provide a callable that returns DebugEntity objects each frame."""
        self._debug_probe = fn

    def set_scene_preview(
        self,
        project_root: Path,
        scene_path: Path,
        *,
        camera_x: int = 0,
        camera_y: int = 0,
    ) -> None:
        self._use_scene_preview = True
        self.engine.unload_game()
        self._scene_path = scene_path.resolve()
        self._scene = load_scene(self._scene_path, project_root=project_root)
        self._scene_renderer = SceneRenderer(project_root)
        self._scene_renderer.reset_animations()
        self._camera_x = camera_x
        self._camera_y = camera_y
        self._refresh_frame()

    def reload_scene_preview(self, project_root: Path) -> None:
        if not self._scene_path:
            return
        self._scene = load_scene(self._scene_path, project_root=project_root)
        if self._scene_renderer is None:
            self._scene_renderer = SceneRenderer(project_root)
        else:
            self._scene_renderer.reset_animations()
        self._refresh_frame()

    def invalidate_baked_assets(self) -> None:
        """Drop baked surfaces after asset edits while scene preview is active."""
        if self._scene_renderer is not None:
            self._scene_renderer.clear_baked_cache()
        if self._use_scene_preview:
            self._refresh_frame()

    def set_camera(self, camera_x: int, camera_y: int = 0) -> None:
        self._camera_x = camera_x
        self._camera_y = camera_y
        self._refresh_frame()

    def start_playback(self) -> None:
        if self._pending_game_module is not None:
            self.engine.load_game(self._pending_game_module)
        self._playing = True
        self._timer.start()

    def stop_playback(self) -> None:
        self._playing = False
        self._timer.stop()
        self.engine.unload_game()
        self._unpatch_keyboard()
        self._key_proxy.clear()
        self._refresh_frame()

    # ------------------------------------------------------------------
    # Keyboard bridging (Qt → pygame.key.get_pressed)
    # ------------------------------------------------------------------

    def _patch_keyboard(self) -> None:
        """Replace pygame.key.get_pressed with one driven by Qt key events."""
        if self._original_get_pressed is not None:
            return  # already patched
        self._original_get_pressed = pygame.key.get_pressed
        proxy = self._key_proxy

        def _fake_get_pressed():
            return proxy

        pygame.key.get_pressed = _fake_get_pressed

    def _unpatch_keyboard(self) -> None:
        if self._original_get_pressed is None:
            return
        pygame.key.get_pressed = self._original_get_pressed
        self._original_get_pressed = None

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._debug_mode:
            pg_key = _QT_TO_PYGAME.get(event.key())
            if pg_key is not None:
                self._key_proxy.press(pg_key)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if self._debug_mode:
            pg_key = _QT_TO_PYGAME.get(event.key())
            if pg_key is not None:
                self._key_proxy.release(pg_key)
        super().keyReleaseEvent(event)

    # ------------------------------------------------------------------
    # Tick / render
    # ------------------------------------------------------------------

    def _on_tick(self) -> None:
        if not self._playing:
            return
        if self._use_scene_preview:
            if self._scene and self._scene_renderer:
                self._scene_renderer.tick(self._scene, 1.0 / self._fps)
            self._refresh_frame()
            return
        pygame.event.pump()
        self.engine.tick(1.0 / self._fps)
        self._refresh_frame()

    def _refresh_frame(self) -> None:
        if self._use_scene_preview and self._scene and self._scene_renderer:
            surface = self._scene_renderer.render(
                self._scene,
                camera_x=self._camera_x,
                camera_y=self._camera_y,
            )
        else:
            surface = self.engine.render_frame()
        data = pygame.image.tobytes(surface, "RGB")
        self._frame = QImage(
            data,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            SCREEN_WIDTH * 3,
            QImage.Format.Format_RGB888,
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._frame is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        target = self.rect()
        scaled = self._frame.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        frame_x = target.x() + (target.width() - scaled.width()) // 2
        frame_y = target.y() + (target.height() - scaled.height()) // 2
        painter.drawImage(frame_x, frame_y, scaled)

        if self._debug_mode and self._debug_probe is not None:
            self._draw_debug_overlay(
                painter,
                frame_x, frame_y,
                scaled.width(), scaled.height(),
            )

        painter.end()

    # ------------------------------------------------------------------
    # Debug overlay drawing (Qt painter, on top of the game frame)
    # ------------------------------------------------------------------

    def _draw_debug_overlay(
        self, painter: QPainter,
        frame_x: int, frame_y: int,
        frame_w: int, frame_h: int,
    ) -> None:
        assert self._debug_probe is not None
        entities = self._debug_probe()
        if not entities:
            return

        scale_x = frame_w / SCREEN_WIDTH
        scale_y = frame_h / SCREEN_HEIGHT
        cross = max(3, int(4 * scale_x))

        for ent in entities:
            # World-space offset of entity from camera
            wx = ent.px - ent.cam_x
            wy = ent.py - ent.cam_y

            # Draw colliders (sprite-pixel space → world → screen)
            for cx, cy, cw, ch, active in ent.colliders:
                world_x = wx + cx - ent.origin_x
                world_y = wy + cy - ent.origin_y
                sx = frame_x + world_x * scale_x
                sy = frame_y + world_y * scale_y
                sw = cw * scale_x
                sh = ch * scale_y

                fill   = _COLLIDER_ACTIVE_FILL   if active else _COLLIDER_INACTIVE_FILL
                border = _COLLIDER_ACTIVE_BORDER if active else _COLLIDER_INACTIVE_BORDER

                painter.setPen(QPen(border, 1))
                painter.setBrush(QBrush(fill))
                painter.drawRect(int(sx), int(sy), max(1, int(sw)), max(1, int(sh)))

            # Draw origin cross
            ox = frame_x + wx * scale_x
            oy = frame_y + wy * scale_y
            painter.setPen(QPen(_ORIGIN_COLOR, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(int(ox - cross), int(oy), int(ox + cross), int(oy))
            painter.drawLine(int(ox), int(oy - cross), int(ox), int(oy + cross))

            # Object name label
            if ent.name:
                painter.setPen(QPen(_ORIGIN_COLOR, 1))
                painter.drawText(int(ox) + cross + 2, int(oy) - 2, ent.name)
