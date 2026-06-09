"""Pygame framebuffer embedded in a Qt widget."""

from __future__ import annotations

import pygame
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.engine import TortuEngine


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

        self._timer = QTimer(self)
        self._timer.setInterval(1000 // 60)
        self._timer.timeout.connect(self._on_tick)

    @property
    def playing(self) -> bool:
        return self._playing

    def set_game(self, module) -> None:
        self.engine.unload_game()
        if module is not None:
            self.engine.load_game(module)
        self._refresh_frame()

    def start_playback(self) -> None:
        self._playing = True
        self._timer.start()

    def stop_playback(self) -> None:
        self._playing = False
        self._timer.stop()
        self._refresh_frame()

    def _on_tick(self) -> None:
        if self._playing:
            self.engine.tick()
            self._refresh_frame()

    def _refresh_frame(self) -> None:
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
