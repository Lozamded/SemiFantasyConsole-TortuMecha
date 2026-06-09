"""Pygame window wrapper around TortuEngine."""

from __future__ import annotations

import pygame

from tortuengine.constants import DEFAULT_FPS, SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.engine import TortuEngine


class WindowPlayer:
    def __init__(self, scale: int = 3, title: str = "TortuPlayer") -> None:
        if not pygame.get_init():
            pygame.init()

        self.engine = TortuEngine()
        self.scale = scale
        self.title = title
        self.window: pygame.Surface | None = None

    def _ensure_window(self) -> pygame.Surface:
        if self.window is None:
            w, h = SCREEN_WIDTH * self.scale, SCREEN_HEIGHT * self.scale
            self.window = pygame.display.set_mode((w, h))
            pygame.display.set_caption(self.title)
        return self.window

    def run(self) -> None:
        window = self._ensure_window()
        clock = pygame.time.Clock()
        self.engine.running = True

        while self.engine.running:
            dt = clock.tick(DEFAULT_FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.engine.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.engine.running = False

            self.engine.tick(dt)
            frame = self.engine.render_frame()
            scaled = pygame.transform.scale(frame, window.get_size())
            window.blit(scaled, (0, 0))
            pygame.display.flip()

        pygame.quit()
