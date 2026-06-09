"""Sprite assets (.tortusprite) — block-based pixel grids with palette indices."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pygame

from tortuengine.constants import SPRITE_BLOCK
from tortuengine.palette import TRANSPARENT_INDEX, closest_index, load_palette, palette_path


@dataclass
class Sprite:
    blocks_w: int
    blocks_h: int
    palette: str
    pixels: list[int]

    @property
    def pixel_width(self) -> int:
        return self.blocks_w * SPRITE_BLOCK

    @property
    def pixel_height(self) -> int:
        return self.blocks_h * SPRITE_BLOCK

    @classmethod
    def create(cls, blocks_w: int, blocks_h: int, palette: str) -> Sprite:
        if blocks_w < 1 or blocks_h < 1:
            raise ValueError("Sprite must be at least 1×1 blocks")
        count = blocks_w * blocks_h * SPRITE_BLOCK * SPRITE_BLOCK
        return cls(blocks_w, blocks_h, palette, [TRANSPARENT_INDEX] * count)

    def resize(self, blocks_w: int, blocks_h: int) -> None:
        old = self
        new_pixels = [TRANSPARENT_INDEX] * (blocks_w * blocks_h * SPRITE_BLOCK * SPRITE_BLOCK)
        for y in range(min(old.pixel_height, blocks_h * SPRITE_BLOCK)):
            for x in range(min(old.pixel_width, blocks_w * SPRITE_BLOCK)):
                new_pixels[y * blocks_w * SPRITE_BLOCK + x] = old.get_pixel(x, y)
        self.blocks_w = blocks_w
        self.blocks_h = blocks_h
        self.pixels = new_pixels

    def get_pixel(self, x: int, y: int) -> int:
        if 0 <= x < self.pixel_width and 0 <= y < self.pixel_height:
            return self.pixels[y * self.pixel_width + x]
        return TRANSPARENT_INDEX

    def set_pixel(self, x: int, y: int, index: int) -> None:
        if 0 <= x < self.pixel_width and 0 <= y < self.pixel_height:
            self.pixels[y * self.pixel_width + x] = index

    def to_surface(self, palette: list[tuple[int, int, int]]) -> pygame.Surface:
        surface = pygame.Surface((self.pixel_width, self.pixel_height), pygame.SRCALPHA)
        for y in range(self.pixel_height):
            for x in range(self.pixel_width):
                index = self.get_pixel(x, y)
                if index == TRANSPARENT_INDEX:
                    continue
                surface.set_at((x, y), (*palette[index], 255))
        return surface

    def fill_from_surface(
        self,
        image: pygame.Surface,
        palette: list[tuple[int, int, int]],
        alpha_threshold: int = 128,
    ) -> None:
        scaled = pygame.transform.scale(image, (self.pixel_width, self.pixel_height))
        for y in range(self.pixel_height):
            for x in range(self.pixel_width):
                r, g, b, a = scaled.get_at((x, y))
                if a < alpha_threshold:
                    self.set_pixel(x, y, TRANSPARENT_INDEX)
                else:
                    self.set_pixel(x, y, closest_index(r, g, b, palette))


def load_sprite(path: Path) -> Sprite:
    data = json.loads(path.read_text(encoding="utf-8"))
    sprite = Sprite(
        blocks_w=int(data["blocks_w"]),
        blocks_h=int(data["blocks_h"]),
        palette=str(data["palette"]),
        pixels=[int(v) for v in data["pixels"]],
    )
    expected = sprite.pixel_width * sprite.pixel_height
    if len(sprite.pixels) != expected:
        raise ValueError(f"Sprite pixel count mismatch in {path.name}")
    return sprite


def save_sprite(sprite: Sprite, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "blocks_w": sprite.blocks_w,
        "blocks_h": sprite.blocks_h,
        "palette": sprite.palette,
        "pixels": sprite.pixels,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_sprite_surface(project_root: Path, sprite_path: Path) -> pygame.Surface:
    sprite = load_sprite(sprite_path)
    palette = load_palette(palette_path(project_root, sprite.palette))
    return sprite.to_surface(palette)
