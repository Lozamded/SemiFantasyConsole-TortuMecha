"""Background assets (.tortubackground) — multi bg-layer pixel strips (parallax set per scene)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from tortuengine.constants import BACKGROUND_LAYERS, SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.palette import TRANSPARENT_INDEX, closest_index, load_palette, palette_path

MIN_BG_LAYERS = 1
MAX_BG_LAYERS = BACKGROUND_LAYERS

DEFAULT_BACKGROUND_WIDTH = SCREEN_WIDTH * 2
DEFAULT_BACKGROUND_HEIGHT = SCREEN_HEIGHT

DEFAULT_BG_LAYER_NAMES = tuple(f"bg_layer_{i}" for i in range(MAX_BG_LAYERS))


def _blank_bg_layer_pixels(width: int, height: int) -> list[int]:
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
    out = _blank_bg_layer_pixels(width, height)
    for y in range(height):
        for x in range(width):
            r, g, b, a = image.get_at((x, y))
            if a < alpha_threshold:
                continue
            out[y * width + x] = closest_index(r, g, b, palette_colors)
    return out


@dataclass
class BackgroundLayer:
    """One paint layer inside a background asset."""

    name: str
    pixels: list[int]
    visible: bool = True

    def copy(self) -> BackgroundLayer:
        return BackgroundLayer(self.name, self.pixels.copy(), self.visible)


@dataclass
class Background:
    """Wide pixel background; parallax is configured on the scene, not here."""

    palette: str
    width: int
    height: int
    bg_layers: list[BackgroundLayer] = field(default_factory=list)

    @property
    def bg_layer_count(self) -> int:
        return len(self.bg_layers)

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
        bg_layers = [
            BackgroundLayer(
                DEFAULT_BG_LAYER_NAMES[0],
                _blank_bg_layer_pixels(width, height),
            )
        ]
        return cls(palette, width, height, bg_layers)

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
        bg_layers = [BackgroundLayer(DEFAULT_BG_LAYER_NAMES[0], pixels)]
        return cls(palette, width, height, bg_layers)

    def fill_bg_layer_from_surface(
        self,
        bg_layer_index: int,
        image: pygame.Surface,
        palette_colors: list[tuple[int, int, int]],
        *,
        alpha_threshold: int = 128,
    ) -> None:
        self._validate_bg_layer(bg_layer_index)
        if image.get_size() != (self.width, self.height):
            image = pygame.transform.scale(image, (self.width, self.height))
        self.bg_layers[bg_layer_index].pixels = _pixels_from_surface(
            self.width,
            self.height,
            image,
            palette_colors,
            alpha_threshold=alpha_threshold,
        )

    def _validate_bg_layer(self, bg_layer_index: int) -> None:
        if not (0 <= bg_layer_index < len(self.bg_layers)):
            raise IndexError(f"Bg layer index out of range: {bg_layer_index}")

    def _validate_bg_layer_count(self) -> None:
        count = len(self.bg_layers)
        if not (MIN_BG_LAYERS <= count <= MAX_BG_LAYERS):
            raise ValueError(f"Background must have {MIN_BG_LAYERS}–{MAX_BG_LAYERS} bg layers")

    def _validate_coords(self, x: int, y: int) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"Pixel coordinate out of range: ({x}, {y})")

    def _cell_index(self, x: int, y: int) -> int:
        return y * self.width + x

    def get_pixel(self, bg_layer_index: int, x: int, y: int) -> int:
        self._validate_bg_layer(bg_layer_index)
        self._validate_coords(x, y)
        return self.bg_layers[bg_layer_index].pixels[self._cell_index(x, y)]

    def set_pixel(self, bg_layer_index: int, x: int, y: int, index: int) -> None:
        self._validate_bg_layer(bg_layer_index)
        self._validate_coords(x, y)
        self.bg_layers[bg_layer_index].pixels[self._cell_index(x, y)] = index

    def sample_pixel(
        self, x: int, y: int, palette: list[tuple[int, int, int]]
    ) -> tuple[int, int, int, int] | None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return None
        for bg_layer in self.bg_layers:
            if not bg_layer.visible:
                continue
            index = bg_layer.pixels[self._cell_index(x, y)]
            if index == TRANSPARENT_INDEX:
                continue
            rgb = palette[index]
            return (*rgb, 255)
        return None

    def ensure_bg_layer_pixels(self, bg_layer_index: int) -> None:
        self._validate_bg_layer(bg_layer_index)
        bg_layer = self.bg_layers[bg_layer_index]
        expected = self.pixel_count
        if len(bg_layer.pixels) == expected:
            return

        old_w = max(1, self.width)
        old_h = max(1, len(bg_layer.pixels) // old_w)
        out = _blank_bg_layer_pixels(self.width, self.height)
        for ny in range(self.height):
            for nx in range(self.width):
                sx = min(old_w - 1, int(nx * old_w / self.width)) if self.width else 0
                sy = min(old_h - 1, int(ny * old_h / self.height)) if self.height else 0
                out[ny * self.width + nx] = bg_layer.pixels[sy * old_w + sx]
        self.bg_layers[bg_layer_index] = BackgroundLayer(bg_layer.name, out, bg_layer.visible)

    def ensure_all_bg_layer_pixels(self) -> None:
        for index in range(len(self.bg_layers)):
            self.ensure_bg_layer_pixels(index)

    def add_bg_layer(self, *, copy_from: int | None = None) -> int:
        if len(self.bg_layers) >= MAX_BG_LAYERS:
            raise ValueError(f"Background cannot have more than {MAX_BG_LAYERS} bg layers")
        index = len(self.bg_layers)
        if copy_from is not None:
            self._validate_bg_layer(copy_from)
            source = self.bg_layers[copy_from]
            pixels = source.pixels.copy()
            visible = source.visible
            name = f"{source.name}_copy"
        else:
            pixels = _blank_bg_layer_pixels(self.width, self.height)
            visible = True
            name = DEFAULT_BG_LAYER_NAMES[index]
        self.bg_layers.append(BackgroundLayer(name, pixels, visible))
        self.ensure_bg_layer_pixels(index)
        return index

    def remove_bg_layer(self, bg_layer_index: int) -> None:
        if len(self.bg_layers) <= MIN_BG_LAYERS:
            raise ValueError(f"Background must keep at least {MIN_BG_LAYERS} bg layer")
        self._validate_bg_layer(bg_layer_index)
        self.bg_layers.pop(bg_layer_index)

    def resize_pixels(self, width: int, height: int) -> None:
        if width < 1 or height < 1:
            raise ValueError("Background must be at least 1×1 pixels")
        if width == self.width and height == self.height:
            return

        old_w, old_h = self.width, self.height
        new_bg_layers: list[BackgroundLayer] = []
        for bg_layer in self.bg_layers:
            out = _blank_bg_layer_pixels(width, height)
            for ny in range(height):
                for nx in range(width):
                    sx = int(nx * old_w / width) if width else 0
                    sy = int(ny * old_h / height) if height else 0
                    if sx < old_w and sy < old_h:
                        out[ny * width + nx] = bg_layer.pixels[sy * old_w + sx]
            new_bg_layers.append(BackgroundLayer(bg_layer.name, out, bg_layer.visible))

        self.width = width
        self.height = height
        self.bg_layers = new_bg_layers

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

    def layer_surface(
        self,
        bg_layer_index: int,
        palette: list[tuple[int, int, int]],
    ) -> pygame.Surface:
        self._validate_bg_layer(bg_layer_index)
        bg_layer = self.bg_layers[bg_layer_index]
        surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for y in range(self.height):
            row = y * self.width
            for x in range(self.width):
                index = bg_layer.pixels[row + x]
                if index == TRANSPARENT_INDEX:
                    continue
                rgb = palette[index]
                surface.set_at((x, y), (*rgb, 255))
        return surface


def _normalize_bg_layer(
    raw: dict,
    bg_layer_index: int,
    width: int,
    height: int,
    path: Path,
) -> BackgroundLayer:
    expected = width * height
    name = str(raw.get("name", DEFAULT_BG_LAYER_NAMES[bg_layer_index]))
    visible = bool(raw.get("visible", True))
    pixels = [int(v) for v in raw["pixels"]]
    if len(pixels) != expected:
        raise ValueError(
            f"Bg layer {bg_layer_index} pixel count mismatch in {path.name}: "
            f"expected {expected}, got {len(pixels)}"
        )
    return BackgroundLayer(name, pixels, visible)


def _normalize_bg_layers(
    raw_bg_layers: list[dict],
    width: int,
    height: int,
    path: Path,
) -> list[BackgroundLayer]:
    if not raw_bg_layers:
        return [
            BackgroundLayer(
                DEFAULT_BG_LAYER_NAMES[0],
                _blank_bg_layer_pixels(width, height),
            )
        ]
    if len(raw_bg_layers) > MAX_BG_LAYERS:
        raise ValueError(
            f"Background has {len(raw_bg_layers)} bg layers in {path.name}; "
            f"maximum is {MAX_BG_LAYERS}"
        )
    return [_normalize_bg_layer(raw, i, width, height, path) for i, raw in enumerate(raw_bg_layers)]


def load_background(path: Path) -> Background:
    data = json.loads(path.read_text(encoding="utf-8"))
    palette = str(data["palette"])
    width = int(data["width"])
    height = int(data["height"])
    if width < 1 or height < 1:
        raise ValueError(f"Background size must be at least 1×1 in {path.name}")

    bg_layers = _normalize_bg_layers(data.get("bg_layers", []), width, height, path)
    background = Background(palette, width, height, bg_layers)
    background.ensure_all_bg_layer_pixels()
    return background


def save_background(background: Background, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    background._validate_bg_layer_count()
    background.ensure_all_bg_layer_pixels()
    data = {
        "palette": background.palette,
        "width": background.width,
        "height": background.height,
        "bg_layers": [
            {
                "name": bg_layer.name,
                "visible": bg_layer.visible,
                "pixels": bg_layer.pixels,
            }
            for bg_layer in background.bg_layers
        ],
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
