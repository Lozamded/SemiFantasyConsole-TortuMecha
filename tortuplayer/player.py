"""Pygame window wrapper around TortuEngine."""

from __future__ import annotations

import pygame

from tortuengine.constants import DEFAULT_FPS
from tortuengine.engine import TortuEngine
from tortuplayer.display import Display


class WindowPlayer:
    def __init__(
        self,
        scale: int = 3,
        title: str = "TortuPlayer",
        fps: int = DEFAULT_FPS,
        fullscreen: bool = False,
    ) -> None:
        if not pygame.get_init():
            pygame.init()

        self.engine = TortuEngine()
        self.engine.set_fps(fps)
        self.scale = scale
        self.title = title
        self.fps = fps
        self.fullscreen = fullscreen
        self.display: Display | None = None

    def _ensure_window(self) -> pygame.Surface:
        if self.display is None:
            self.display = Display(self.scale, self.fullscreen, self.title)
            self.engine.framebuffer = self.engine.framebuffer.convert(self.display.window)
        return self.display.window

    def run(self) -> None:
        self._ensure_window()
        clock = pygame.time.Clock()
        self.engine.running = True

        while self.engine.running:
            dt = clock.tick(self.fps) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.engine.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.engine.running = False

            self.engine.tick(dt)
            frame = self.engine.render_frame()
            self.display.present(frame)

        pygame.quit()
