"""Load images for TortuStudio / engine without requiring a visible pygame window."""

from __future__ import annotations

from pathlib import Path

import numpy as np
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


def apply_color_key(surface: pygame.Surface, color_rgb: tuple[int, int, int]) -> pygame.Surface:
    """Return copy of surface with all pixels matching color_rgb set to alpha=0."""
    ensure_pygame()
    out = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    out.blit(surface, (0, 0))
    arr = pygame.surfarray.pixels3d(out)
    alpha = pygame.surfarray.pixels_alpha(out)
    r, g, b = color_rgb
    mask = (arr[:, :, 0] == r) & (arr[:, :, 1] == g) & (arr[:, :, 2] == b)
    alpha[mask] = 0
    del arr, alpha
    return out
