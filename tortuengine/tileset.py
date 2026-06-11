"""Tileset assets (.tortutileset) — stack of square palette-indexed tiles."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from tortuengine.constants import TILE_BLOCK
from tortuengine.palette import TRANSPARENT_INDEX, closest_index, load_palette, palette_path

COLLISION_NONE = "none"
COLLISION_SOLID = "solid"
COLLISION_POLYGON = "polygon"
COLLISION_TYPES = (COLLISION_NONE, COLLISION_SOLID, COLLISION_POLYGON)

ONE_WAY_NONE = "none"
ONE_WAY_UP = "up"
ONE_WAY_DOWN = "down"
ONE_WAY_LEFT = "left"
ONE_WAY_RIGHT = "right"
ONE_WAY_TYPES = (ONE_WAY_NONE, ONE_WAY_UP, ONE_WAY_DOWN, ONE_WAY_LEFT, ONE_WAY_RIGHT)


def _blank_tile(tile_size: int) -> list[int]:
    return [TRANSPARENT_INDEX] * (tile_size * tile_size)


def _blank_collision_mask(tile_size: int) -> list[int]:
    return [0] * (tile_size * tile_size)


def _full_collision_mask(tile_size: int) -> list[int]:
    return [1] * (tile_size * tile_size)


def _resample_mask(mask: list[int], old_size: int, new_size: int) -> list[int]:
    if old_size == new_size:
        return mask.copy()
    out = _blank_collision_mask(new_size)
    for ly in range(new_size):
        for lx in range(new_size):
            sx = int(lx * old_size / new_size)
            sy = int(ly * old_size / new_size)
            out[ly * new_size + lx] = 1 if mask[sy * old_size + sx] else 0
    return out


def surface_tile_to_pixels(
    surface: pygame.Surface,
    tx: int,
    ty: int,
    dst_tile_size: int,
    palette: list[tuple[int, int, int]],
    src_tile_size: int | None = None,
    alpha_threshold: int = 128,
) -> list[int]:
    """Palette-convert one square region from a surface into tile pixels."""
    src_size = src_tile_size or dst_tile_size
    src_x0 = tx * src_size
    src_y0 = ty * src_size
    pixels = _blank_tile(dst_tile_size)
    for ly in range(dst_tile_size):
        for lx in range(dst_tile_size):
            sx = src_x0 + int(lx * src_size / dst_tile_size)
            sy = src_y0 + int(ly * src_size / dst_tile_size)
            if sx < 0 or sy < 0 or sx >= surface.get_width() or sy >= surface.get_height():
                continue
            r, g, b, a = surface.get_at((sx, sy))
            if a < alpha_threshold:
                continue
            pixels[ly * dst_tile_size + lx] = closest_index(r, g, b, palette)
    return pixels


def _resample_tile(pixels: list[int], old_size: int, new_size: int) -> list[int]:
    if old_size == new_size:
        return pixels.copy()
    out = _blank_tile(new_size)
    for ly in range(new_size):
        for lx in range(new_size):
            sx = int(lx * old_size / new_size)
            sy = int(ly * old_size / new_size)
            out[ly * new_size + lx] = pixels[sy * old_size + sx]
    return out


def _normalize_collision(value: str) -> str:
    value = value.lower()
    if value not in COLLISION_TYPES:
        raise ValueError(f"Invalid collision type: {value}")
    return value


def _normalize_one_way(value: str) -> str:
    value = value.lower()
    if value not in ONE_WAY_TYPES:
        raise ValueError(f"Invalid one-way type: {value}")
    return value


@dataclass
class Tileset:
    palette: str
    tile_size: int = TILE_BLOCK
    tiles: list[list[int]] = field(default_factory=list)
    collisions: list[str] = field(default_factory=list)
    one_ways: list[str] = field(default_factory=list)
    collision_shapes: list[list[int]] = field(default_factory=list)

    @property
    def tile_count(self) -> int:
        return len(self.tiles)

    @property
    def strip_columns(self) -> int:
        if not self.tiles:
            return 1
        return max(1, min(16, math.ceil(math.sqrt(self.tile_count))))

    @property
    def strip_rows(self) -> int:
        if not self.tiles:
            return 0
        cols = self.strip_columns
        return math.ceil(self.tile_count / cols)

    @classmethod
    def create(cls, palette: str, tile_size: int = TILE_BLOCK) -> Tileset:
        if tile_size < 1:
            raise ValueError("Tile size must be at least 1 px")
        return cls(palette=palette, tile_size=tile_size, tiles=[])

    def blank_tile(self) -> list[int]:
        return _blank_tile(self.tile_size)

    def _ensure_meta_length(self) -> None:
        while len(self.collisions) < len(self.tiles):
            self.collisions.append(COLLISION_NONE)
        while len(self.one_ways) < len(self.tiles):
            self.one_ways.append(ONE_WAY_NONE)
        while len(self.collision_shapes) < len(self.tiles):
            self.collision_shapes.append(_blank_collision_mask(self.tile_size))
        del self.collisions[len(self.tiles) :]
        del self.one_ways[len(self.tiles) :]
        del self.collision_shapes[len(self.tiles) :]

    def collision_mask_for_type(self, collision: str, mask: list[int] | None = None) -> list[int]:
        if collision == COLLISION_SOLID:
            return _full_collision_mask(self.tile_size)
        if collision == COLLISION_NONE:
            return _blank_collision_mask(self.tile_size)
        if mask is not None:
            return mask.copy()
        return _blank_collision_mask(self.tile_size)

    def get_collision_shape(self, index: int) -> list[int]:
        self._ensure_meta_length()
        if 0 <= index < len(self.collision_shapes):
            collision = self.get_collision(index)
            return self.collision_mask_for_type(collision, self.collision_shapes[index])
        return _blank_collision_mask(self.tile_size)

    def set_collision_shape(self, index: int, mask: list[int]) -> None:
        if index < 0 or index >= len(self.tiles):
            raise IndexError(f"Tile index out of range: {index}")
        expected = self.tile_size * self.tile_size
        if len(mask) != expected:
            raise ValueError(f"Collision mask must have {expected} cells")
        self._ensure_meta_length()
        self.collision_shapes[index] = [1 if v else 0 for v in mask]

    def get_collision(self, index: int) -> str:
        self._ensure_meta_length()
        if 0 <= index < len(self.collisions):
            return self.collisions[index]
        return COLLISION_NONE

    def set_collision(self, index: int, collision: str) -> None:
        if index < 0 or index >= len(self.tiles):
            raise IndexError(f"Tile index out of range: {index}")
        self._ensure_meta_length()
        self.collisions[index] = _normalize_collision(collision)

    def get_one_way(self, index: int) -> str:
        self._ensure_meta_length()
        if 0 <= index < len(self.one_ways):
            return self.one_ways[index]
        return ONE_WAY_NONE

    def set_one_way(self, index: int, one_way: str) -> None:
        if index < 0 or index >= len(self.tiles):
            raise IndexError(f"Tile index out of range: {index}")
        self._ensure_meta_length()
        self.one_ways[index] = _normalize_one_way(one_way)

    def get_tile(self, index: int) -> list[int]:
        if 0 <= index < len(self.tiles):
            return self.tiles[index]
        return self.blank_tile()

    def replace_tile(self, index: int, pixels: list[int]) -> None:
        expected = self.tile_size * self.tile_size
        if len(pixels) != expected:
            raise ValueError(f"Tile must have {expected} pixels")
        if index < 0 or index >= len(self.tiles):
            raise IndexError(f"Tile index out of range: {index}")
        self.tiles[index] = pixels.copy()

    def append_tile(self, pixels: list[int]) -> int:
        expected = self.tile_size * self.tile_size
        if len(pixels) != expected:
            raise ValueError(f"Tile must have {expected} pixels")
        self.tiles.append(pixels.copy())
        self.collisions.append(COLLISION_NONE)
        self.one_ways.append(ONE_WAY_NONE)
        self.collision_shapes.append(_blank_collision_mask(self.tile_size))
        return len(self.tiles) - 1

    def append_tile_with_meta(
        self,
        pixels: list[int],
        collision: str = COLLISION_NONE,
        one_way: str = ONE_WAY_NONE,
        collision_shape: list[int] | None = None,
    ) -> int:
        index = self.append_tile(pixels)
        self.collisions[index] = _normalize_collision(collision)
        self.one_ways[index] = _normalize_one_way(one_way)
        mask = collision_shape or self.collision_mask_for_type(collision)
        self.set_collision_shape(index, mask)
        return index

    def save_tile(
        self,
        index: int,
        pixels: list[int],
        collision: str | None = None,
        one_way: str | None = None,
        collision_shape: list[int] | None = None,
    ) -> int:
        collision_type = collision or (
            self.get_collision(index) if index < len(self.tiles) else COLLISION_NONE
        )
        if index < len(self.tiles):
            self.replace_tile(index, pixels)
            if collision is not None:
                self.set_collision(index, collision)
            if one_way is not None:
                self.set_one_way(index, one_way)
            if collision_shape is not None:
                self.set_collision_shape(
                    index,
                    self.collision_mask_for_type(collision_type, collision_shape),
                )
            elif collision is not None and collision_type != COLLISION_POLYGON:
                self.set_collision_shape(
                    index, self.collision_mask_for_type(collision_type)
                )
            return index
        if index == len(self.tiles):
            return self.append_tile_with_meta(
                pixels,
                collision or COLLISION_NONE,
                one_way or ONE_WAY_NONE,
                collision_shape=collision_shape,
            )
        raise IndexError(f"Cannot save tile at index {index}")

    def has_pixels(self) -> bool:
        return any(p != TRANSPARENT_INDEX for tile in self.tiles for p in tile)

    def set_tile_size(self, tile_size: int) -> None:
        if tile_size < 1:
            raise ValueError("Tile size must be at least 1 px")
        if tile_size == self.tile_size:
            return
        old_size = self.tile_size
        self._ensure_meta_length()
        self.tiles = [_resample_tile(tile, old_size, tile_size) for tile in self.tiles]
        self.collision_shapes = [
            _resample_mask(mask, old_size, tile_size) for mask in self.collision_shapes
        ]
        self.tile_size = tile_size

    def to_surface(
        self,
        palette: list[tuple[int, int, int]],
        *,
        empty_color: tuple[int, int, int] | None = None,
    ) -> pygame.Surface:
        cols = self.strip_columns
        rows = max(1, self.strip_rows) if self.tiles else 1
        w, h = cols * self.tile_size, rows * self.tile_size
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        for i, tile in enumerate(self.tiles):
            tx = i % cols
            ty = i // cols
            base_x = tx * self.tile_size
            base_y = ty * self.tile_size
            for ly in range(self.tile_size):
                for lx in range(self.tile_size):
                    index = tile[ly * self.tile_size + lx]
                    if index == TRANSPARENT_INDEX:
                        if empty_color is not None:
                            surface.set_at((base_x + lx, base_y + ly), (*empty_color, 255))
                        continue
                    surface.set_at((base_x + lx, base_y + ly), (*palette[index], 255))
        return surface


def _sheet_to_tiles(
    pixels: list[int],
    tiles_w: int,
    tiles_h: int,
    tile_size: int,
) -> list[list[int]]:
    tiles: list[list[int]] = []
    sheet_w = tiles_w * tile_size
    for ty in range(tiles_h):
        for tx in range(tiles_w):
            tile = _blank_tile(tile_size)
            base_x = tx * tile_size
            base_y = ty * tile_size
            for ly in range(tile_size):
                row_start = (base_y + ly) * sheet_w + base_x
                tile[ly * tile_size : (ly + 1) * tile_size] = pixels[
                    row_start : row_start + tile_size
                ]
            tiles.append(tile)
    return tiles


def load_tileset(path: Path) -> Tileset:
    data = json.loads(path.read_text(encoding="utf-8"))
    palette = str(data["palette"])
    tile_size = int(data.get("tile_size", TILE_BLOCK))

    if "tiles" in data:
        tiles = [[int(v) for v in tile] for tile in data["tiles"]]
        expected = tile_size * tile_size
        for i, tile in enumerate(tiles):
            if len(tile) != expected:
                raise ValueError(f"Tile {i} pixel count mismatch in {path.name}")
        collisions = [_normalize_collision(v) for v in data.get("collisions", [])]
        one_ways = [_normalize_one_way(v) for v in data.get("one_ways", [])]
        shapes_raw = data.get("collision_shapes", [])
        collision_shapes: list[list[int]] = []
        expected = tile_size * tile_size
        for i, shape in enumerate(shapes_raw):
            cells = [1 if int(v) else 0 for v in shape]
            if len(cells) != expected:
                raise ValueError(f"Collision shape {i} size mismatch in {path.name}")
            collision_shapes.append(cells)
        tileset = Tileset(
            palette=palette,
            tile_size=tile_size,
            tiles=tiles,
            collisions=collisions,
            one_ways=one_ways,
            collision_shapes=collision_shapes,
        )
        tileset._ensure_meta_length()
        return tileset

    tiles_w = int(data["tiles_w"])
    tiles_h = int(data["tiles_h"])
    pixels = [int(v) for v in data["pixels"]]
    expected = tiles_w * tiles_h * tile_size * tile_size
    if len(pixels) != expected:
        raise ValueError(f"Pixel count mismatch in {path.name}")
    tiles = _sheet_to_tiles(pixels, tiles_w, tiles_h, tile_size)
    tileset = Tileset(palette=palette, tile_size=tile_size, tiles=tiles)
    tileset._ensure_meta_length()
    return tileset


def save_tileset(tileset: Tileset, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tileset._ensure_meta_length()
    data = {
        "tile_size": tileset.tile_size,
        "palette": tileset.palette,
        "tiles": tileset.tiles,
        "collisions": tileset.collisions,
        "one_ways": tileset.one_ways,
        "collision_shapes": tileset.collision_shapes,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_tileset_surface(project_root: Path, tileset_path: Path) -> pygame.Surface:
    tileset = load_tileset(tileset_path)
    palette = load_palette(palette_path(project_root, tileset.palette))
    return tileset.to_surface(palette)


STACK_PREVIEW_EMPTY_BG = (48, 48, 60)


def stack_sidecar_path(tileset_path: Path) -> Path:
    return tileset_path.with_name(f"{tileset_path.stem}.stack.png")


def existing_stack_preview_path(tileset_path: Path) -> Path | None:
    for candidate in (
        stack_sidecar_path(tileset_path),
        tileset_path.with_name(f"{tileset_path.stem}.import.png"),
        tileset_path.with_suffix(".ref.png"),
    ):
        if candidate.is_file():
            return candidate
    return None


def import_sidecar_path(tileset_path: Path) -> Path:
    """Legacy alias — new saves use :func:`stack_sidecar_path`."""
    return stack_sidecar_path(tileset_path)
