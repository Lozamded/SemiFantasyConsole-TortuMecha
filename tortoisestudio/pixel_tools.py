"""Shared pixel-editing helpers used by the sprite/tileset/background/glyph canvases."""

from __future__ import annotations

from typing import Callable


def flood_fill_indices(
    get_pixel: Callable[[int, int], int],
    set_pixel: Callable[[int, int, int], None],
    width: int,
    height: int,
    x: int,
    y: int,
    new_index: int,
) -> None:
    """4-connected flood fill starting at *(x, y)*, replacing the contiguous run
    of matching palette indices with *new_index*."""
    target = get_pixel(x, y)
    if target == new_index:
        return

    stack = [(x, y)]
    visited = {(x, y)}
    while stack:
        cx, cy = stack.pop()
        set_pixel(cx, cy, new_index)
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if (
                0 <= nx < width
                and 0 <= ny < height
                and (nx, ny) not in visited
                and get_pixel(nx, ny) == target
            ):
                visited.add((nx, ny))
                stack.append((nx, ny))
