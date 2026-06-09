"""Load images for TortuStudio / engine without requiring a visible pygame window."""

from __future__ import annotations

from pathlib import Path

import pygame


def ensure_pygame() -> None:
    if not pygame.get_init():
        pygame.init()


def load_image(path: str | Path) -> pygame.Surface:
    """Load an image with alpha; safe when no pygame display is open (Qt embed)."""
    ensure_pygame()
    surface = pygame.image.load(str(path))
    if surface.get_flags() & pygame.SRCALPHA:
        return surface.copy()
    rgba = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    rgba.blit(surface, (0, 0))
    return rgba
