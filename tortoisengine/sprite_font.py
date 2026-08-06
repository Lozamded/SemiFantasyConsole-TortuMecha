"""Sprite fonts (.tortuspritefont) — hand-painted HUD fonts from 4×4 blocks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from tortoisengine.constants import SPRITE_BLOCK
from tortoisengine.palette import TRANSPARENT_INDEX, closest_index, load_palette, palette_path
from tortoisengine.text_font import TortoiseGlyph, unique_charset

DEFAULT_GLYPH_BLOCKS_W = 2
DEFAULT_GLYPH_BLOCKS_H = 2
MIN_GLYPH_BLOCKS = 1
MAX_GLYPH_BLOCKS = 8


def hud_base_charset() -> str:
    """Default HUD letters, digits, space, and common punctuation."""
    return (
        " ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789"
        ".:+-/%"
    )


def is_base_character(char: str) -> bool:
    return len(char) == 1 and char in hud_base_charset()


def ordered_unique_charset(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for char in text:
        if char not in seen:
            seen.add(char)
            out.append(char)
    return "".join(out)


def _blank_glyph(blocks_w: int, blocks_h: int, advance: int) -> TortoiseGlyph:
    width = blocks_w * SPRITE_BLOCK
    height = blocks_h * SPRITE_BLOCK
    return TortoiseGlyph(
        width,
        height,
        advance,
        [TRANSPARENT_INDEX] * (width * height),
    )


@dataclass
class TortoiseSpriteFont:
    """Pixel HUD font with fixed palette colors baked into each glyph."""

    name: str
    palette: str
    glyph_blocks_w: int = DEFAULT_GLYPH_BLOCKS_W
    glyph_blocks_h: int = DEFAULT_GLYPH_BLOCKS_H
    line_height: int = 0
    default_advance: int = 0
    charset: str = ""
    glyphs: dict[int, TortoiseGlyph] = field(default_factory=dict)

    @property
    def pixel_width(self) -> int:
        return self.glyph_blocks_w * SPRITE_BLOCK

    @property
    def pixel_height(self) -> int:
        return self.glyph_blocks_h * SPRITE_BLOCK

    @classmethod
    def create(
        cls,
        name: str,
        palette: str,
        *,
        glyph_blocks_w: int = DEFAULT_GLYPH_BLOCKS_W,
        glyph_blocks_h: int = DEFAULT_GLYPH_BLOCKS_H,
        charset: str | None = None,
        default_advance: int | None = None,
        line_height: int | None = None,
    ) -> TortoiseSpriteFont:
        if glyph_blocks_w < MIN_GLYPH_BLOCKS or glyph_blocks_h < MIN_GLYPH_BLOCKS:
            raise ValueError("Glyph size must be at least 1×1 blocks")
        chars = ordered_unique_charset(charset if charset is not None else hud_base_charset())
        advance = default_advance if default_advance is not None else glyph_blocks_w * SPRITE_BLOCK
        height = line_height if line_height is not None else glyph_blocks_h * SPRITE_BLOCK
        font = cls(
            name=name or "sprite_font",
            palette=palette,
            glyph_blocks_w=glyph_blocks_w,
            glyph_blocks_h=glyph_blocks_h,
            line_height=height,
            default_advance=advance,
            charset=chars,
        )
        font.ensure_glyphs()
        return font

    def resolved_charset(self) -> str:
        if not self.charset:
            return hud_base_charset()
        base = hud_base_charset()
        extras = "".join(char for char in self.charset if char not in base)
        return ordered_unique_charset(base + extras)

    def add_character(self, char: str) -> bool:
        if len(char) != 1:
            return False
        chars = self.resolved_charset()
        if char in chars:
            return False
        self.charset = chars + char
        self.ensure_glyphs()
        return True

    def remove_character(self, char: str) -> bool:
        if len(char) != 1 or is_base_character(char):
            return False
        chars = self.resolved_charset()
        if char not in chars:
            return False
        self.charset = "".join(c for c in chars if c != char)
        self.glyphs.pop(ord(char), None)
        return True

    def ensure_glyphs(self) -> None:
        """Create blank glyphs for every character in the charset."""
        chars = self.resolved_charset()
        self.charset = chars
        advance = self.default_advance or self.pixel_width
        for char in chars:
            code = ord(char)
            if code not in self.glyphs:
                self.glyphs[code] = _blank_glyph(self.glyph_blocks_w, self.glyph_blocks_h, advance)

    def sync_metrics(self) -> None:
        """Keep spacing metrics at least as large as glyph cells."""
        self.line_height = max(self.line_height, self.pixel_height)
        self.default_advance = max(self.default_advance, 1)

    def resize_glyph_blocks(self, blocks_w: int, blocks_h: int) -> None:
        if blocks_w < MIN_GLYPH_BLOCKS or blocks_h < MIN_GLYPH_BLOCKS:
            raise ValueError("Glyph size must be at least 1×1 blocks")
        old_w, old_h = self.pixel_width, self.pixel_height
        new_w, new_h = blocks_w * SPRITE_BLOCK, blocks_h * SPRITE_BLOCK
        resized: dict[int, TortoiseGlyph] = {}
        for code, glyph in self.glyphs.items():
            pixels = [TRANSPARENT_INDEX] * (new_w * new_h)
            for y in range(min(glyph.height, new_h)):
                for x in range(min(glyph.width, new_w)):
                    pixels[y * new_w + x] = glyph.pixels[y * glyph.width + x]
            resized[code] = TortoiseGlyph(
                new_w,
                new_h,
                max(glyph.advance, new_w),
                pixels,
                glyph.bearing_x,
                glyph.bearing_y,
            )
        self.glyph_blocks_w = blocks_w
        self.glyph_blocks_h = blocks_h
        self.glyphs = resized
        self.sync_metrics()

    def copy(self) -> TortoiseSpriteFont:
        return TortoiseSpriteFont(
            self.name,
            self.palette,
            self.glyph_blocks_w,
            self.glyph_blocks_h,
            self.line_height,
            self.default_advance,
            self.charset,
            {code: glyph.copy() for code, glyph in self.glyphs.items()},
        )


def load_sprite_font(path: Path) -> TortoiseSpriteFont:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = str(data.get("name", path.stem))
    palette = str(data.get("palette", "default"))
    blocks_w = int(data.get("glyph_blocks_w", data.get("blocks_w", DEFAULT_GLYPH_BLOCKS_W)))
    blocks_h = int(data.get("glyph_blocks_h", data.get("blocks_h", DEFAULT_GLYPH_BLOCKS_H)))

    glyphs_raw = data.get("glyphs", {})
    glyphs: dict[int, TortoiseGlyph] = {}
    for key, raw in glyphs_raw.items():
        code = int(key)
        pixels = [int(v) for v in raw["pixels"]]
        glyphs[code] = TortoiseGlyph(
            int(raw.get("w", raw.get("width", 0))),
            int(raw.get("h", raw.get("height", 0))),
            int(raw.get("advance", data.get("default_advance", blocks_w * SPRITE_BLOCK))),
            pixels,
            int(raw.get("bearing_x", 0)),
            int(raw.get("bearing_y", 0)),
        )

    preset = str(data.get("charset_preset", "")).lower()
    charset = str(data.get("charset", ""))
    if not charset:
        from tortoisengine.text_font import charset_for_preset

        if preset in ("ascii", "latin1", "custom"):
            charset = charset_for_preset(preset, "")
        else:
            charset = hud_base_charset()

    pixel_w = blocks_w * SPRITE_BLOCK
    pixel_h = blocks_h * SPRITE_BLOCK
    font = TortoiseSpriteFont(
        name=name,
        palette=palette,
        glyph_blocks_w=blocks_w,
        glyph_blocks_h=blocks_h,
        line_height=int(data.get("line_height", pixel_h)),
        default_advance=int(data.get("default_advance", pixel_w)),
        charset=ordered_unique_charset(charset),
        glyphs=glyphs,
    )
    font.ensure_glyphs()
    font.sync_metrics()
    return font


def save_sprite_font(font: TortoiseSpriteFont, path: Path) -> None:
    font.ensure_glyphs()
    font.sync_metrics()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": font.name,
        "palette": font.palette,
        "glyph_blocks_w": font.glyph_blocks_w,
        "glyph_blocks_h": font.glyph_blocks_h,
        "line_height": font.line_height,
        "default_advance": font.default_advance,
        "charset": font.resolved_charset(),
        "glyphs": {
            str(code): {
                "w": glyph.width,
                "h": glyph.height,
                "advance": glyph.advance,
                "bearing_x": glyph.bearing_x,
                "bearing_y": glyph.bearing_y,
                "pixels": glyph.pixels,
            }
            for code, glyph in sorted(font.glyphs.items())
        },
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def surface_glyph_to_pixels(
    surface: pygame.Surface,
    cell_x: int,
    cell_y: int,
    width: int,
    height: int,
    palette: list[tuple[int, int, int]],
    *,
    src_width: int | None = None,
    src_height: int | None = None,
    alpha_threshold: int = 128,
) -> list[int]:
    """Palette-convert one glyph cell from an import image."""
    sw = src_width if src_width is not None else width
    sh = src_height if src_height is not None else height
    src_x0 = cell_x * sw
    src_y0 = cell_y * sh
    pixels = [TRANSPARENT_INDEX] * (width * height)
    for ly in range(height):
        for lx in range(width):
            sx = src_x0 + int(lx * sw / width) if width else src_x0
            sy = src_y0 + int(ly * sh / height) if height else src_y0
            if sx < 0 or sy < 0 or sx >= surface.get_width() or sy >= surface.get_height():
                continue
            r, g, b, a = surface.get_at((sx, sy))
            if a < alpha_threshold:
                continue
            pixels[ly * width + lx] = closest_index(r, g, b, palette)
    return pixels


def _sprite_char_advance(font: TortoiseSpriteFont, char: str) -> int:
    glyph = font.glyphs.get(ord(char))
    if glyph:
        return glyph.advance
    return font.default_advance or font.pixel_width


def measure_sprite_text_width(font: TortoiseSpriteFont, text: str) -> int:
    return sum(_sprite_char_advance(font, char) for char in text)


def _blit_sprite_glyphs(
    surface: pygame.Surface,
    font: TortoiseSpriteFont,
    text: str,
    palette: list[tuple[int, int, int]],
    cursor_x: int,
    y: int,
) -> int:
    """Draw `text` onto `surface` starting at (cursor_x, y); returns the ending cursor_x."""
    fallback_advance = font.default_advance or font.pixel_width
    for char in text:
        glyph = font.glyphs.get(ord(char))
        if glyph is None:
            cursor_x += fallback_advance
            continue
        for gy in range(glyph.height):
            for gx in range(glyph.width):
                index = glyph.pixels[gy * glyph.width + gx]
                if index == TRANSPARENT_INDEX:
                    continue
                dst_x = cursor_x + gx + glyph.bearing_x
                dst_y = y + gy + glyph.bearing_y
                if 0 <= dst_x < surface.get_width() and 0 <= dst_y < surface.get_height():
                    rgb = palette[index]
                    surface.set_at((dst_x, dst_y), (*rgb, 255))
        cursor_x += glyph.advance
    return cursor_x


def render_sprite_text_line(
    font: TortoiseSpriteFont,
    text: str,
    palette: list[tuple[int, int, int]],
) -> pygame.Surface:
    """Lay out one line using baked palette indices (fixed colors)."""
    if not text:
        return pygame.Surface((1, font.line_height), pygame.SRCALPHA)

    width = measure_sprite_text_width(font, text)
    max_glyph_h = max(
        (font.glyphs[ord(char)].height for char in text if ord(char) in font.glyphs), default=0
    )
    height = max(font.line_height, max_glyph_h)
    surface = pygame.Surface((max(1, width), height), pygame.SRCALPHA)
    _blit_sprite_glyphs(surface, font, text, palette, 0, 0)
    return surface


def render_sprite_text_block(
    font: TortoiseSpriteFont,
    lines: list[str],
    palette: list[tuple[int, int, int]],
    *,
    justify: str = "left",
    box_width: int | None = None,
) -> pygame.Surface:
    """Lay out pre-wrapped `lines` stacked at the font's line height.

    `justify` positions each line horizontally within `box_width` (falls back
    to the widest line's own width): "left", "center", "right", or "justify"
    (stretches inter-word gaps to fill the box — the last line is left-aligned,
    matching conventional paragraph justification).
    """
    if not lines:
        return pygame.Surface((1, font.line_height), pygame.SRCALPHA)

    line_widths = [measure_sprite_text_width(font, line) for line in lines]
    width = box_width if box_width and box_width > 0 else max((*line_widths, 1))
    height = font.line_height * len(lines)
    surface = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)

    last_index = len(lines) - 1
    for i, line in enumerate(lines):
        y = i * font.line_height
        words = line.split(" ") if line else [""]
        if justify == "justify" and i != last_index and len(words) > 1:
            word_widths = [measure_sprite_text_width(font, word) for word in words]
            gaps = len(words) - 1
            extra_total = max(0, width - sum(word_widths))
            cursor_x = 0
            for wi, word in enumerate(words):
                cursor_x = _blit_sprite_glyphs(surface, font, word, palette, cursor_x, y)
                if wi < gaps:
                    gap = extra_total // gaps + (1 if wi < extra_total % gaps else 0)
                    cursor_x += gap
            continue

        line_width = line_widths[i]
        if justify == "center":
            start_x = max(0, (width - line_width) // 2)
        elif justify == "right":
            start_x = max(0, width - line_width)
        else:
            start_x = 0
        _blit_sprite_glyphs(surface, font, line, palette, start_x, y)
    return surface
