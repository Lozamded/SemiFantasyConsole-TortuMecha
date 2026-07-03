"""Shared OS-window setup for TortuPlayer runners (windowed and fullscreen)."""

from __future__ import annotations

import pygame

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH


class Display:
    """Opens the OS window and scales 264x198 frames onto it each tick.

    In fullscreen mode the scale factor is auto-picked as the largest integer
    multiple of the console resolution that fits the real display, keeping
    pixels crisp and letterboxing the rest — a fixed --scale would otherwise
    either not fill the screen or stretch unevenly across SBC output modes.
    """

    def __init__(self, scale: int, fullscreen: bool, title: str) -> None:
        if fullscreen:
            window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
            display_w, display_h = window.get_size()
            scale = max(1, min(display_w // SCREEN_WIDTH, display_h // SCREEN_HEIGHT))
        else:
            window = pygame.display.set_mode((SCREEN_WIDTH * scale, SCREEN_HEIGHT * scale))
        pygame.display.set_caption(title)

        scaled_size = (SCREEN_WIDTH * scale, SCREEN_HEIGHT * scale)
        window_w, window_h = window.get_size()
        self.offset = ((window_w - scaled_size[0]) // 2, (window_h - scaled_size[1]) // 2)
        if self.offset != (0, 0):
            window.fill((0, 0, 0))

        self.window = window
        # Pre-converted to the display's native pixel format so the per-frame
        # blit doesn't pay a format-conversion cost on weak ARM SoCs.
        self.scaled_frame = pygame.Surface(scaled_size).convert(window)

    def present(self, frame: pygame.Surface) -> None:
        pygame.transform.scale(frame, self.scaled_frame.get_size(), self.scaled_frame)
        self.window.blit(self.scaled_frame, self.offset)
        pygame.display.flip()
