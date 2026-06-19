"""Sprite fonts (.tortuspritefont) — hand-painted HUD fonts from 4×4 blocks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from tortuengine.constants import SPRITE_BLOCK
from tortuengine.palette import TRANSPARENT_INDEX, load_palette, palette_path
from tortuengine.text_font import TortuGlyph, unique_charset

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


def _blank_glyph(blocks_w: int, blocks_h: int, advance: int) -> TortuGlyph:
    width = blocks_w * SPRITE_BLOCK
    height = blocks_h * SPRITE_BLOCK
    return TortuGlyph(
        width,
        height,
        advance,
        [TRANSPARENT_INDEX] * (width * height),
    )


@dataclass
class TortuSpriteFont:
    """Pixel HUD font with fixed palette colors baked into each glyph."""

    name: str
    palette: str
    glyph_blocks_w: int = DEFAULT_GLYPH_BLOCKS_W
    glyph_blocks_h: int = DEFAULT_GLYPH_BLOCKS_H
    line_height: int = 0
    default_advance: int = 0
    charset: str = ""
    glyphs: dict[int, TortuGlyph] = field(default_factory=dict)

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
    ) -> TortuSpriteFont:
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
        resized: dict[int, TortuGlyph] = {}
        for code, glyph in self.glyphs.items():
            pixels = [TRANSPARENT_INDEX] * (new_w * new_h)
            for y in range(min(glyph.height, new_h)):
                for x in range(min(glyph.width, new_w)):
                    pixels[y * new_w + x] = glyph.pixels[y * glyph.width + x]
            resized[code] = TortuGlyph(
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

    def copy(self) -> TortuSpriteFont:
        return TortuSpriteFont(
            self.name,
            self.palette,
            self.glyph_blocks_w,
            self.glyph_blocks_h,
            self.line_height,
            self.default_advance,
            self.charset,
            {code: glyph.copy() for code, glyph in self.glyphs.items()},
        )


def load_sprite_font(path: Path) -> TortuSpriteFont:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = str(data.get("name", path.stem))
    palette = str(data.get("palette", "default"))
    blocks_w = int(data.get("glyph_blocks_w", data.get("blocks_w", DEFAULT_GLYPH_BLOCKS_W)))
    blocks_h = int(data.get("glyph_blocks_h", data.get("blocks_h", DEFAULT_GLYPH_BLOCKS_H)))

    glyphs_raw = data.get("glyphs", {})
    glyphs: dict[int, TortuGlyph] = {}
    for key, raw in glyphs_raw.items():
        code = int(key)
        pixels = [int(v) for v in raw["pixels"]]
        glyphs[code] = TortuGlyph(
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
        from tortuengine.text_font import charset_for_preset

        if preset in ("ascii", "latin1", "custom"):
            charset = charset_for_preset(preset, "")
        else:
            charset = hud_base_charset()

    pixel_w = blocks_w * SPRITE_BLOCK
    pixel_h = blocks_h * SPRITE_BLOCK
    font = TortuSpriteFont(
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


def save_sprite_font(font: TortuSpriteFont, path: Path) -> None:
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


def render_sprite_text_line(
    font: TortuSpriteFont,
    text: str,
    palette: list[tuple[int, int, int]],
) -> pygame.Surface:
    """Lay out one line using baked palette indices (fixed colors)."""
    if not text:
        return pygame.Surface((1, font.line_height), pygame.SRCALPHA)

    width = 0
    max_glyph_h = 0
    fallback_advance = font.default_advance or font.pixel_width
    for char in text:
        glyph = font.glyphs.get(ord(char))
        if glyph:
            width += glyph.advance
            max_glyph_h = max(max_glyph_h, glyph.height)
        else:
            width += fallback_advance

    height = max(font.line_height, max_glyph_h)
    surface = pygame.Surface((max(1, width), height), pygame.SRCALPHA)
    cursor_x = 0
    for char in text:
        glyph = font.glyphs.get(ord(char))
        if glyph is None:
            cursor_x += fallback_advance
            continue
        for y in range(glyph.height):
            for x in range(glyph.width):
                index = glyph.pixels[y * glyph.width + x]
                if index == TRANSPARENT_INDEX:
                    continue
                dst_x = cursor_x + x + glyph.bearing_x
                dst_y = y + glyph.bearing_y
                if 0 <= dst_x < surface.get_width() and 0 <= dst_y < surface.get_height():
                    rgb = palette[index]
                    surface.set_at((dst_x, dst_y), (*rgb, 255))
        cursor_x += glyph.advance
    return surface
