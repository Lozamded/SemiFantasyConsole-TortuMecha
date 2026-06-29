"""Core framebuffer engine — no OS window; callers display the surface."""

from __future__ import annotations

import pygame

from tortuengine.constants import DEFAULT_FPS, SCREEN_HEIGHT, SCREEN_WIDTH


class TortuEngine:
    """264×198 fantasy console framebuffer with a simple drawing API."""

    def __init__(self) -> None:
        if not pygame.get_init():
            pygame.init()

        self.framebuffer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), 0, 32)
        self.clock = pygame.time.Clock()
        self.fps = DEFAULT_FPS
        self._game_module = None
        self.running = False

    def set_fps(self, fps: int) -> None:
        self.fps = max(1, fps)

    @property
    def game(self):
        return self._game_module

    def load_game(self, module) -> None:
        self._game_module = module
        if hasattr(module, "init"):
            module.init(self)

    def unload_game(self) -> None:
        self._game_module = None
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.stop()

    def clear(self, color: tuple[int, int, int]) -> None:
        self.framebuffer.fill(color)

    def pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT:
            self.framebuffer.set_at((x, y), color)

    def rect(
        self,
        color: tuple[int, int, int],
        rect: pygame.Rect | tuple[int, int, int, int],
        width: int = 0,
    ) -> None:
        pygame.draw.rect(self.framebuffer, color, rect, width)

    def text(
        self,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int] = (255, 255, 255),
        font_size: int = 8,
    ) -> None:
        font = pygame.font.Font(None, font_size)
        surface = font.render(text, True, color)
        self.framebuffer.blit(surface, (x, y))

    def blit(self, surface: pygame.Surface, pos: tuple[int, int]) -> None:
        self.framebuffer.blit(surface, pos)

    def tick(self, dt: float | None = None) -> float:
        if dt is None:
            dt = self.clock.tick(self.fps) / 1000.0

        game = self._game_module
        if game and hasattr(game, "update"):
            game.update(dt)

        return dt

    def render_frame(self) -> pygame.Surface:
        game = self._game_module
        if game and hasattr(game, "draw"):
            game.draw(self)
        return self.framebuffer
