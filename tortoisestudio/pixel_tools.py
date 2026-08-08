"""Shared pixel-editing helpers used by the sprite/tileset/background/glyph canvases."""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class UndoStack(Generic[T]):
    """Snapshot-based undo/redo, one entry per stroke/edit. *T* is whatever a
    subclass wants to snapshot — a flat pixel-index list for the pixel canvases,
    or a small tagged tuple for the scene editor's heterogeneous edits."""

    def __init__(self, limit: int = 50) -> None:
        self._undo: list[T] = []
        self._redo: list[T] = []
        self._limit = limit

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def push(self, snapshot: T) -> None:
        self._undo.append(snapshot)
        if len(self._undo) > self._limit:
            del self._undo[0]
        self._redo.clear()

    def peek_undo(self) -> T | None:
        return self._undo[-1] if self._undo else None

    def peek_redo(self) -> T | None:
        return self._redo[-1] if self._redo else None

    def undo(self, current: T) -> T | None:
        if not self._undo:
            return None
        self._redo.append(current)
        return self._undo.pop()

    def redo(self, current: T) -> T | None:
        if not self._redo:
            return None
        self._undo.append(current)
        return self._redo.pop()


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
