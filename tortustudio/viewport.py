"""Pygame framebuffer embedded in a Qt widget."""

from __future__ import annotations

from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.engine import TortuEngine
from tortuengine.scene import Scene, load_scene
from tortuengine.scene_renderer import SceneRenderer


class ViewportWidget(QWidget):
    """264×198 engine preview scaled with nearest-neighbor filtering."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(SCREEN_WIDTH * 2, SCREEN_HEIGHT * 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background-color: #1a1a2e;")

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

        self._timer = QTimer(self)
        self._timer.setInterval(1000 // self._fps)
        self._timer.timeout.connect(self._on_tick)

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
        self.engine.unload_game()
        if module is not None:
            self.engine.load_game(module)
        self._refresh_frame()

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
        self._camera_x = camera_x
        self._camera_y = camera_y
        self._refresh_frame()

    def reload_scene_preview(self, project_root: Path) -> None:
        if not self._scene_path:
            return
        self._scene = load_scene(self._scene_path, project_root=project_root)
        if self._scene_renderer is None:
            self._scene_renderer = SceneRenderer(project_root)
        self._refresh_frame()

    def set_camera(self, camera_x: int, camera_y: int = 0) -> None:
        self._camera_x = camera_x
        self._camera_y = camera_y
        self._refresh_frame()

    def start_playback(self) -> None:
        self._playing = True
        self._timer.start()

    def stop_playback(self) -> None:
        self._playing = False
        self._timer.stop()
        self._refresh_frame()

    def _on_tick(self) -> None:
        if not self._playing:
            return
        if self._use_scene_preview:
            self._refresh_frame()
            return
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
        x = target.x() + (target.width() - scaled.width()) // 2
        y = target.y() + (target.height() - scaled.height()) // 2
        painter.drawImage(x, y, scaled)
        painter.end()
