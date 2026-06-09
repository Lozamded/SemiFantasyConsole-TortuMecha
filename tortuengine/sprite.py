"""Sprite assets (.tortusprite) — block-based pixel grids with palette indices."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from tortuengine.constants import SPRITE_BLOCK
from tortuengine.palette import TRANSPARENT_INDEX, closest_index, load_palette, palette_path


def _blank_frame(blocks_w: int, blocks_h: int) -> list[int]:
    count = blocks_w * blocks_h * SPRITE_BLOCK * SPRITE_BLOCK
    return [TRANSPARENT_INDEX] * count


@dataclass
class Sprite:
    blocks_w: int
    blocks_h: int
    palette: str
    frames: list[list[int]]
    fps: int = 8
    current_frame: int = field(default=0, compare=False)

    @property
    def pixel_width(self) -> int:
        return self.blocks_w * SPRITE_BLOCK

    @property
    def pixel_height(self) -> int:
        return self.blocks_h * SPRITE_BLOCK

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def pixels(self) -> list[int]:
        return self.frames[self.current_frame]

    @pixels.setter
    def pixels(self, value: list[int]) -> None:
        self.frames[self.current_frame] = value

    @classmethod
    def create(cls, blocks_w: int, blocks_h: int, palette: str) -> Sprite:
        if blocks_w < 1 or blocks_h < 1:
            raise ValueError("Sprite must be at least 1×1 blocks")
        return cls(blocks_w, blocks_h, palette, [_blank_frame(blocks_w, blocks_h)])

    def select_frame(self, index: int) -> None:
        if index < 0 or index >= len(self.frames):
            raise IndexError(f"Frame index out of range: {index}")
        self.current_frame = index

    def add_frame(self, copy_current: bool = False) -> int:
        if copy_current:
            self.frames.append(self.pixels.copy())
        else:
            self.frames.append(_blank_frame(self.blocks_w, self.blocks_h))
        self.current_frame = len(self.frames) - 1
        return self.current_frame

    def duplicate_frame(self, index: int | None = None) -> int:
        source = self.frames[index if index is not None else self.current_frame]
        self.frames.append(source.copy())
        self.current_frame = len(self.frames) - 1
        return self.current_frame

    def delete_frame(self, index: int | None = None) -> None:
        if len(self.frames) <= 1:
            raise ValueError("Sprite must have at least one frame")
        idx = index if index is not None else self.current_frame
        self.frames.pop(idx)
        if self.current_frame >= len(self.frames):
            self.current_frame = len(self.frames) - 1

    def frame_has_pixels(self, index: int | None = None) -> bool:
        idx = index if index is not None else self.current_frame
        return any(p != TRANSPARENT_INDEX for p in self.frames[idx])

    def any_frame_has_pixels(self) -> bool:
        return any(self.frame_has_pixels(i) for i in range(len(self.frames)))

    def _resize_frame(
        self,
        pixels: list[int],
        old_w: int,
        old_h: int,
        new_w: int,
        new_h: int,
    ) -> list[int]:
        new_pixels = _blank_frame(new_w // SPRITE_BLOCK, new_h // SPRITE_BLOCK)
        for y in range(min(old_h, new_h)):
            for x in range(min(old_w, new_w)):
                new_pixels[y * new_w + x] = pixels[y * old_w + x]
        return new_pixels

    def resize(self, blocks_w: int, blocks_h: int) -> None:
        old_w, old_h = self.pixel_width, self.pixel_height
        new_w, new_h = blocks_w * SPRITE_BLOCK, blocks_h * SPRITE_BLOCK
        self.frames = [
            self._resize_frame(frame, old_w, old_h, new_w, new_h) for frame in self.frames
        ]
        self.blocks_w = blocks_w
        self.blocks_h = blocks_h

    def get_pixel(self, x: int, y: int) -> int:
        if 0 <= x < self.pixel_width and 0 <= y < self.pixel_height:
            return self.pixels[y * self.pixel_width + x]
        return TRANSPARENT_INDEX

    def set_pixel(self, x: int, y: int, index: int) -> None:
        if 0 <= x < self.pixel_width and 0 <= y < self.pixel_height:
            self.pixels[y * self.pixel_width + x] = index

    def to_surface(
        self,
        palette: list[tuple[int, int, int]],
        frame_index: int | None = None,
    ) -> pygame.Surface:
        idx = frame_index if frame_index is not None else self.current_frame
        surface = pygame.Surface((self.pixel_width, self.pixel_height), pygame.SRCALPHA)
        pixels = self.frames[idx]
        for y in range(self.pixel_height):
            for x in range(self.pixel_width):
                index = pixels[y * self.pixel_width + x]
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


def _validate_frames(sprite: Sprite, path: Path) -> None:
    expected = sprite.pixel_width * sprite.pixel_height
    for i, frame in enumerate(sprite.frames):
        if len(frame) != expected:
            raise ValueError(f"Frame {i} pixel count mismatch in {path.name}")


def load_sprite(path: Path) -> Sprite:
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks_w = int(data["blocks_w"])
    blocks_h = int(data["blocks_h"])
    palette = str(data["palette"])
    fps = int(data.get("fps", 8))

    if "frames" in data:
        frames = [[int(v) for v in frame] for frame in data["frames"]]
    elif "pixels" in data:
        frames = [[int(v) for v in data["pixels"]]]
    else:
        raise ValueError(f"Sprite file has no frames or pixels: {path.name}")

    if not frames:
        frames = [_blank_frame(blocks_w, blocks_h)]

    sprite = Sprite(blocks_w, blocks_h, palette, frames, fps=fps)
    _validate_frames(sprite, path)
    return sprite


def save_sprite(sprite: Sprite, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "blocks_w": sprite.blocks_w,
        "blocks_h": sprite.blocks_h,
        "palette": sprite.palette,
        "fps": sprite.fps,
        "frames": sprite.frames,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_sprite_surface(
    project_root: Path,
    sprite_path: Path,
    frame_index: int = 0,
) -> pygame.Surface:
    sprite = load_sprite(sprite_path)
    palette = load_palette(palette_path(project_root, sprite.palette))
    return sprite.to_surface(palette, frame_index=frame_index)


def reference_sidecar_path(sprite_path: Path, frame_index: int) -> Path:
    """Path to a frame's reference image; checks legacy `.ref.png` for frame 0."""
    candidates = []
    if frame_index == 0:
        candidates.append(sprite_path.with_suffix(".ref.png"))
    candidates.append(sprite_path.with_name(f"{sprite_path.stem}.ref{frame_index}.png"))
    for path in candidates:
        if path.is_file():
            return path
    return candidates[-1]
