"""Bake palette-index assets to pygame surfaces and blit parallax efficiently."""

from __future__ import annotations

import numpy as np
import pygame

from tortuengine.background import Background
from tortuengine.palette import TRANSPARENT_INDEX
from tortuengine.scene import SceneBgParallaxBand, find_parallax_band
from tortuengine.sprite import Sprite
from tortuengine.tileset import Tileset


def bake_sprite_frame(
    sprite: Sprite,
    palette: list[tuple[int, int, int]],
    frame_index: int,
) -> pygame.Surface:
    return sprite.to_surface(palette, frame_index=frame_index)


def bake_tile(
    tileset: Tileset,
    palette: list[tuple[int, int, int]],
    tile_index: int,
) -> pygame.Surface:
    return tileset.tile_surface(palette, tile_index)


def _composite_layers_to_arrays(
    bg_layers,
    palette: list[tuple[int, int, int]],
    w: int,
    h: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (rgb, alpha) arrays in surfarray (w, h) convention."""
    pal_rgb = np.array(palette, dtype=np.uint8)  # (64, 3)
    rgb = np.zeros((w, h, 3), dtype=np.uint8)
    alpha = np.zeros((w, h), dtype=np.uint8)
    filled = np.zeros((w, h), dtype=bool)

    for layer in bg_layers:
        if not layer.visible:
            continue
        # pixels is row-major (y*w + x); reshape to (h, w) then transpose to (w, h)
        pixels = np.array(layer.pixels, dtype=np.uint8).reshape(h, w).T
        can_set = ~filled & (pixels != TRANSPARENT_INDEX)
        rgb[can_set] = pal_rgb[pixels[can_set]]
        alpha[can_set] = 255
        filled |= can_set
        if filled.all():
            break

    return rgb, alpha


def _write_arrays_to_surface(
    surface: pygame.Surface,
    rgb: np.ndarray,
    alpha: np.ndarray,
) -> None:
    pix = pygame.surfarray.pixels3d(surface)
    alp = pygame.surfarray.pixels_alpha(surface)
    pix[:] = rgb
    alp[:] = alpha
    del pix, alp


def bake_background(
    background: Background,
    palette: list[tuple[int, int, int]],
) -> pygame.Surface:
    """Composite visible bg layers into one RGBA surface."""
    w, h = background.width, background.height
    surface = pygame.Surface((w, h), pygame.SRCALPHA)
    rgb, alpha = _composite_layers_to_arrays(background.bg_layers, palette, w, h)
    _write_arrays_to_surface(surface, rgb, alpha)
    return surface


def bake_background_band(
    background: Background,
    palette: list[tuple[int, int, int]],
    y0: int,
    y1: int,
) -> pygame.Surface:
    """Bake a horizontal strip [y0, y1] inclusive for band parallax."""
    top = max(0, min(y0, background.height - 1))
    bottom = max(0, min(y1, background.height - 1))
    if bottom < top:
        top, bottom = bottom, top
    band_h = bottom - top + 1
    w = background.width

    surface = pygame.Surface((w, band_h), pygame.SRCALPHA)

    pal_rgb = np.array(palette, dtype=np.uint8)
    rgb = np.zeros((w, band_h, 3), dtype=np.uint8)
    alpha = np.zeros((w, band_h), dtype=np.uint8)
    filled = np.zeros((w, band_h), dtype=bool)

    for layer in background.bg_layers:
        if not layer.visible:
            continue
        # Slice only the band rows before transposing to avoid full-image allocation
        full = np.array(layer.pixels, dtype=np.uint8).reshape(background.height, w)
        pixels = full[top : bottom + 1, :].T  # (w, band_h)
        can_set = ~filled & (pixels != TRANSPARENT_INDEX)
        rgb[can_set] = pal_rgb[pixels[can_set]]
        alpha[can_set] = 255
        filled |= can_set
        if filled.all():
            break

    _write_arrays_to_surface(surface, rgb, alpha)
    return surface


def _blit_clipped(
    target: pygame.Surface,
    source: pygame.Surface,
    src_rect: pygame.Rect,
    dest_pos: tuple[int, int],
) -> None:
    bw, bh = source.get_width(), source.get_height()
    x0, y0, w, h = src_rect.x, src_rect.y, src_rect.width, src_rect.height
    dest_x, dest_y = dest_pos
    if x0 < 0:
        dest_x -= x0
        w += x0
        x0 = 0
    if y0 < 0:
        dest_y -= y0
        h += y0
        y0 = 0
    if x0 + w > bw:
        w = bw - x0
    if y0 + h > bh:
        h = bh - y0
    if w <= 0 or h <= 0:
        return
    target.blit(source, (dest_x, dest_y), pygame.Rect(x0, y0, w, h))


def _blit_row_tiled_x(
    target: pygame.Surface,
    row_source: pygame.Surface,
    *,
    dest_y: int,
    offset_x: int,
    dest_width: int,
) -> None:
    row_width = row_source.get_width()
    if row_width < 1:
        return
    start_x = -(offset_x % row_width)
    x = start_x
    while x < dest_width:
        clip_w = min(row_width, dest_width - x)
        if clip_w > 0:
            target.blit(row_source, (x, dest_y), pygame.Rect(0, 0, clip_w, 1))
        x += row_width


def _blit_row_clipped_x(
    target: pygame.Surface,
    row_source: pygame.Surface,
    *,
    dest_y: int,
    offset_x: int,
    dest_width: int,
) -> None:
    row_width = row_source.get_width()
    if offset_x >= row_width or offset_x + dest_width <= 0:
        return
    src_x = max(0, offset_x)
    dest_x = max(0, -offset_x)
    width = min(dest_width - dest_x, row_width - src_x)
    if width > 0:
        target.blit(row_source, (dest_x, dest_y), pygame.Rect(src_x, 0, width, 1))


def blit_parallax(
    target: pygame.Surface,
    baked: pygame.Surface,
    *,
    parallax_x: float = 0.0,
    parallax_y: float = 0.0,
    camera_x: float = 0.0,
    camera_y: float = 0.0,
    fixed: bool = False,
    repeat_x: bool = False,
    repeat_y: bool = False,
) -> None:
    """Draw a baked background onto *target* using scene parallax factors."""
    tw, th = target.get_width(), target.get_height()
    bw, bh = baked.get_width(), baked.get_height()
    if bw < 1 or bh < 1:
        return

    offset_x = 0 if fixed else int(camera_x * parallax_x)
    offset_y = 0 if fixed else int(camera_y * parallax_y)

    if not repeat_x and not repeat_y:
        _blit_clipped(target, baked, pygame.Rect(offset_x, offset_y, tw, th), (0, 0))
        return

    for vy in range(th):
        sy = vy + offset_y
        if repeat_y:
            sy %= bh
        elif sy < 0 or sy >= bh:
            continue
        row = baked.subsurface((0, sy, bw, 1))
        if repeat_x:
            _blit_row_tiled_x(target, row, dest_y=vy, offset_x=offset_x, dest_width=tw)
        else:
            _blit_row_clipped_x(target, row, dest_y=vy, offset_x=offset_x, dest_width=tw)


def blit_parallax_bands(
    target: pygame.Surface,
    bands: list[SceneBgParallaxBand],
    band_surfaces: dict[tuple[int, int], pygame.Surface],
    *,
    bg_height: int,
    parallax_y: float = 0.0,
    camera_x: float = 0.0,
    camera_y: float = 0.0,
) -> None:
    """Draw band-parallax backgrounds from pre-baked horizontal strips."""
    if not bands or bg_height < 1:
        return

    offset_y = int(camera_y * parallax_y)
    tw, th = target.get_width(), target.get_height()

    for vy in range(th):
        sy = vy + offset_y
        lookup_y = sy
        if lookup_y < 0 or lookup_y >= bg_height:
            lookup_y = max(0, min(bg_height - 1, lookup_y))

        band = find_parallax_band(lookup_y, bands)
        if band is None:
            continue

        strip = band_surfaces.get((band.y0, band.y1))
        if strip is None:
            continue

        strip_h = band.y1 - band.y0 + 1
        if strip_h < 1:
            continue

        if band.repeat_y:
            sy_draw = sy % bg_height
        elif sy < 0 or sy >= bg_height:
            continue
        else:
            sy_draw = sy

        if not (band.y0 <= sy_draw <= band.y1):
            continue

        local_y = sy_draw - band.y0
        row = strip.subsurface((0, local_y, strip.get_width(), 1))
        offset_x = 0 if band.fixed else int(camera_x * band.parallax_x)
        if band.repeat_x:
            _blit_row_tiled_x(target, row, dest_y=vy, offset_x=offset_x, dest_width=tw)
        else:
            _blit_row_clipped_x(target, row, dest_y=vy, offset_x=offset_x, dest_width=tw)
