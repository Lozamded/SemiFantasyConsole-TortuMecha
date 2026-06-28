"""Background assets (.tortubackground) — single pixel canvas; parallax configured per scene."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.palette import TRANSPARENT_INDEX, closest_index, load_palette, palette_path

DEFAULT_BACKGROUND_WIDTH = SCREEN_WIDTH * 2
DEFAULT_BACKGROUND_HEIGHT = SCREEN_HEIGHT


def _blank_pixels(width: int, height: int) -> list[int]:
    return [TRANSPARENT_INDEX] * (width * height)


def _pixels_from_surface(
    width: int,
    height: int,
    image: pygame.Surface,
    palette_colors: list[tuple[int, int, int]],
    *,
    alpha_threshold: int = 128,
) -> list[int]:
    if image.get_size() != (width, height):
        image = pygame.transform.scale(image, (width, height))
    out = _blank_pixels(width, height)
    for y in range(height):
        for x in range(width):
            r, g, b, a = image.get_at((x, y))
            if a < alpha_threshold:
                continue
            out[y * width + x] = closest_index(r, g, b, palette_colors)
    return out


@dataclass
class Background:
    """Wide pixel background; parallax is configured on the scene, not here."""

    palette: str
    width: int
    height: int
    pixels: list[int] = field(default_factory=list)

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @classmethod
    def create(
        cls,
        palette: str,
        width: int = DEFAULT_BACKGROUND_WIDTH,
        height: int = DEFAULT_BACKGROUND_HEIGHT,
    ) -> Background:
        if width < 1 or height < 1:
            raise ValueError("Background must be at least 1×1 pixels")
        return cls(palette, width, height, _blank_pixels(width, height))

    @classmethod
    def create_from_image(
        cls,
        palette: str,
        image: pygame.Surface,
        palette_colors: list[tuple[int, int, int]],
        *,
        alpha_threshold: int = 128,
    ) -> Background:
        width, height = image.get_size()
        if width < 1 or height < 1:
            raise ValueError("Image must be at least 1×1 pixels")
        pixels = _pixels_from_surface(
            width, height, image, palette_colors, alpha_threshold=alpha_threshold
        )
        return cls(palette, width, height, pixels)

    def fill_from_surface(
        self,
        image: pygame.Surface,
        palette_colors: list[tuple[int, int, int]],
        *,
        alpha_threshold: int = 128,
    ) -> None:
        if image.get_size() != (self.width, self.height):
            image = pygame.transform.scale(image, (self.width, self.height))
        self.pixels = _pixels_from_surface(
            self.width, self.height, image, palette_colors, alpha_threshold=alpha_threshold
        )

    def _validate_coords(self, x: int, y: int) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Pixel coordinate out of range: ({x}, {y})")

    def _cell_index(self, x: int, y: int) -> int:
        return y * self.width + x

    def get_pixel(self, x: int, y: int) -> int:
        self._validate_coords(x, y)
        return self.pixels[self._cell_index(x, y)]

    def set_pixel(self, x: int, y: int, index: int) -> None:
        self._validate_coords(x, y)
        self.pixels[self._cell_index(x, y)] = index

    def sample_pixel(
        self, x: int, y: int, palette: list[tuple[int, int, int]]
    ) -> tuple[int, int, int, int] | None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None
        index = self.pixels[self._cell_index(x, y)]
        if index == TRANSPARENT_INDEX:
            return None
        rgb = palette[index]
        return (*rgb, 255)

    def ensure_pixels(self) -> None:
        """Pad or resample pixels if the stored list length doesn't match width×height."""
        expected = self.pixel_count
        if len(self.pixels) == expected:
            return
        if not self.pixels:
            self.pixels = _blank_pixels(self.width, self.height)
            return
        old_w = self.width
        old_h = len(self.pixels) // old_w if old_w else 1
        out = _blank_pixels(self.width, self.height)
        for ny in range(self.height):
            for nx in range(self.width):
                sx = min(old_w - 1, int(nx * old_w / self.width)) if self.width else 0
                sy = min(old_h - 1, int(ny * old_h / self.height)) if self.height else 0
                idx = sy * old_w + sx
                if idx < len(self.pixels):
                    out[ny * self.width + nx] = self.pixels[idx]
        self.pixels = out

    def resize_pixels(self, width: int, height: int) -> None:
        if width < 1 or height < 1:
            raise ValueError("Background must be at least 1×1 pixels")
        if width == self.width and height == self.height:
            return
        old_w, old_h = self.width, self.height
        out = _blank_pixels(width, height)
        for ny in range(height):
            for nx in range(width):
                sx = int(nx * old_w / width) if width else 0
                sy = int(ny * old_h / height) if height else 0
                if sx < old_w and sy < old_h:
                    out[ny * width + nx] = self.pixels[sy * old_w + sx]
        self.width = width
        self.height = height
        self.pixels = out

    def to_surface(self, palette: list[tuple[int, int, int]]) -> pygame.Surface:
        """Render the background pixels to an RGBA surface."""
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for y in range(self.height):
            row = y * self.width
            for x in range(self.width):
                index = self.pixels[row + x]
                if index == TRANSPARENT_INDEX:
                    continue
                rgb = palette[index]
                surface.set_at((x, y), (*rgb, 255))
        return surface

    def draw_parallax(
        self,
        target: pygame.Surface,
        palette: list[tuple[int, int, int]],
        *,
        parallax_x: float = 0.0,
        parallax_y: float = 0.0,
        camera_x: float = 0.0,
        camera_y: float = 0.0,
        fixed: bool = False,
        repeat_x: bool = False,
        repeat_y: bool = False,
    ) -> None:
        """Draw this background onto *target* using scene parallax factors."""
        if fixed:
            offset_x = 0
            offset_y = 0
        else:
            offset_x = int(camera_x * parallax_x)
            offset_y = int(camera_y * parallax_y)
        tw, th = target.get_width(), target.get_height()
        for vy in range(th):
            sy = vy + offset_y
            if repeat_y:
                if self.height < 1:
                    continue
                sy %= self.height
            elif not (0 <= sy < self.height):
                continue
            for vx in range(tw):
                sx = vx + offset_x
                if repeat_x:
                    if self.width < 1:
                        continue
                    sx %= self.width
                elif not (0 <= sx < self.width):
                    continue
                color = self.sample_pixel(sx, sy, palette)
                if color is not None:
                    target.set_at((vx, vy), color)

    def draw_parallax_bands(
        self,
        target: pygame.Surface,
        palette: list[tuple[int, int, int]],
        bands: list,
        *,
        parallax_y: float = 0.0,
        camera_x: float = 0.0,
        camera_y: float = 0.0,
    ) -> None:
        """Draw using per-Y-band parallax (layer parallax_y still applies globally)."""
        from tortuengine.scene import find_parallax_band

        if not bands:
            return
        offset_y = int(camera_y * parallax_y)
        tw, th = target.get_width(), target.get_height()
        for vy in range(th):
            sy = vy + offset_y
            lookup_y = sy
            if self.height > 0:
                if lookup_y < 0 or lookup_y >= self.height:
                    lookup_y = max(0, min(self.height - 1, lookup_y))
            band = find_parallax_band(lookup_y, bands)
            if band is None:
                continue
            if band.repeat_y:
                if self.height < 1:
                    continue
                sy %= self.height
            elif not (0 <= sy < self.height):
                continue
            offset_x = 0 if band.fixed else int(camera_x * band.parallax_x)
            for vx in range(tw):
                sx = vx + offset_x
                if band.repeat_x:
                    if self.width < 1:
                        continue
                    sx %= self.width
                elif not (0 <= sx < self.width):
                    continue
                color = self.sample_pixel(sx, sy, palette)
                if color is not None:
                    target.set_at((vx, vy), color)

    def composite_surface(
        self,
        palette: list[tuple[int, int, int]],
        *,
        camera_x: float = 0.0,
        camera_y: float = 0.0,
        parallax_x: float = 0.0,
        parallax_y: float = 0.0,
        view_width: int = SCREEN_WIDTH,
        view_height: int = SCREEN_HEIGHT,
    ) -> pygame.Surface:
        """Render into a screen-sized view (used by background editor preview)."""
        surface = pygame.Surface((view_width, view_height), pygame.SRCALPHA)
        self.draw_parallax(
            surface,
            palette,
            parallax_x=parallax_x,
            parallax_y=parallax_y,
            camera_x=camera_x,
            camera_y=camera_y,
        )
        return surface


def load_background(path: Path) -> Background:
    data = json.loads(path.read_text(encoding="utf-8"))
    palette = str(data["palette"])
    width = int(data["width"])
    height = int(data["height"])
    if width < 1 or height < 1:
        raise ValueError(f"Background size must be at least 1×1 in {path.name}")

    expected = width * height

    if "pixels" in data:
        pixels = [int(v) for v in data["pixels"]]
    elif "bg_layers" in data:
        # Legacy multi-layer format: composite all visible layers into one
        pixels = [TRANSPARENT_INDEX] * expected
        for raw in data["bg_layers"]:
            if not raw.get("visible", True):
                continue
            layer_pixels = [int(v) for v in raw.get("pixels", [])]
            if len(layer_pixels) != expected:
                continue
            for i, p in enumerate(layer_pixels):
                if p != TRANSPARENT_INDEX and pixels[i] == TRANSPARENT_INDEX:
                    pixels[i] = p
    else:
        pixels = [TRANSPARENT_INDEX] * expected

    background = Background(palette, width, height, pixels)
    background.ensure_pixels()
    return background


def save_background(background: Background, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    background.ensure_pixels()
    data = {
        "palette": background.palette,
        "width": background.width,
        "height": background.height,
        "pixels": background.pixels,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_background_surface(
    project_root: Path,
    background_path: Path,
    *,
    camera_x: float = 0.0,
    camera_y: float = 0.0,
    parallax_x: float = 0.0,
    parallax_y: float = 0.0,
) -> pygame.Surface:
    background = load_background(background_path)
    palette = load_palette(palette_path(project_root, background.palette))
    return background.composite_surface(
        palette,
        camera_x=camera_x,
        camera_y=camera_y,
        parallax_x=parallax_x,
        parallax_y=parallax_y,
    )
