"""Text fonts (.tortufont) — TTF-backed glyph atlases with palette indices."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from tortuengine.palette import TRANSPARENT_INDEX, closest_index, load_palette, palette_path

CHARSET_ASCII = "ascii"
CHARSET_LATIN1 = "latin1"
CHARSET_CUSTOM = "custom"
CHARSET_PRESETS = (CHARSET_ASCII, CHARSET_LATIN1, CHARSET_CUSTOM)

DEFAULT_FONT_SIZE = 8
DEFAULT_LINE_HEIGHT = 10
MIN_FONT_SIZE = 4
MAX_FONT_SIZE = 32


def ascii_charset() -> str:
    return "".join(chr(code) for code in range(32, 127))


def latin1_charset() -> str:
    """Printable Latin-1 (Spanish, French, German, etc.)."""
    return "".join(chr(code) for code in range(32, 256))


def charset_for_preset(preset: str, custom: str = "") -> str:
    preset = preset.strip().lower()
    if preset == CHARSET_ASCII:
        return ascii_charset()
    if preset == CHARSET_LATIN1:
        return latin1_charset()
    return custom


def unique_charset(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for char in text:
        if char not in seen:
            seen.add(char)
            out.append(char)
    return "".join(out)


@dataclass
class TortuGlyph:
    width: int
    height: int
    advance: int
    pixels: list[int]
    bearing_x: int = 0
    bearing_y: int = 0

    def copy(self) -> TortuGlyph:
        return TortuGlyph(
            self.width,
            self.height,
            self.advance,
            self.pixels.copy(),
            self.bearing_x,
            self.bearing_y,
        )


@dataclass
class TortuFont:
    """Baked dialogue / message font (palette indices; scene tints at draw time)."""

    name: str
    source: str
    size: int = DEFAULT_FONT_SIZE
    line_height: int = DEFAULT_LINE_HEIGHT
    palette: str = "default"
    charset_preset: str = CHARSET_LATIN1
    charset: str = ""
    glyphs: dict[int, TortuGlyph] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        source: str,
        *,
        size: int = DEFAULT_FONT_SIZE,
        palette: str = "default",
        charset_preset: str = CHARSET_LATIN1,
        charset: str = "",
    ) -> TortuFont:
        preset = charset_preset if charset_preset in CHARSET_PRESETS else CHARSET_LATIN1
        chars = charset if preset == CHARSET_CUSTOM else charset_for_preset(preset)
        return cls(
            name=name or "font",
            source=source,
            size=size,
            line_height=max(size, DEFAULT_LINE_HEIGHT),
            palette=palette,
            charset_preset=preset,
            charset=unique_charset(chars),
        )

    def resolved_charset(self) -> str:
        if self.charset_preset == CHARSET_CUSTOM:
            return unique_charset(self.charset)
        return charset_for_preset(self.charset_preset, self.charset)

    def copy(self) -> TortuFont:
        return TortuFont(
            self.name,
            self.source,
            self.size,
            self.line_height,
            self.palette,
            self.charset_preset,
            self.charset,
            {code: glyph.copy() for code, glyph in self.glyphs.items()},
        )


def _glyph_from_surface(
    surface: pygame.Surface,
    palette: list[tuple[int, int, int]],
    *,
    advance: int,
) -> TortuGlyph:
    width, height = surface.get_size()
    pixels: list[int] = []
    for y in range(height):
        for x in range(width):
            r, g, b, a = surface.get_at((x, y))
            if a < 128:
                pixels.append(TRANSPARENT_INDEX)
            else:
                pixels.append(closest_index(r, g, b, palette))
    return TortuGlyph(width, height, advance, pixels)


def bake_glyph(
    font: pygame.font.Font,
    char: str,
    palette: list[tuple[int, int, int]],
) -> TortuGlyph | None:
    if not char or len(char) != 1:
        return None
    try:
        # Antialiased render gets a real alpha channel; non-AA fills the bbox with opaque black.
        surface = font.render(char, True, (255, 255, 255))
    except Exception:
        return None
    if surface.get_width() == 0 or surface.get_height() == 0:
        return None
    advance = max(1, font.size(char)[0])
    return _glyph_from_surface(surface, palette, advance=advance)


def sync_line_height(tortu_font: TortuFont, *, min_linesize: int | None = None) -> None:
    """Raise line_height so baked glyphs are not clipped when drawing."""
    floor = tortu_font.size
    if min_linesize is not None:
        floor = max(floor, min_linesize)
    if tortu_font.glyphs:
        floor = max(floor, max(glyph.height for glyph in tortu_font.glyphs.values()))
    tortu_font.line_height = max(tortu_font.line_height, floor)


def rebuild_font_glyphs(
    tortu_font: TortuFont,
    project_root: Path,
    *,
    preview_palette: list[tuple[int, int, int]] | None = None,
) -> None:
    """Rasterize all charset glyphs from the source TTF into palette indices."""
    ttf_path = (project_root / tortu_font.source).resolve()
    if not ttf_path.is_file():
        raise FileNotFoundError(f"Font source not found: {tortu_font.source}")

    if not pygame.get_init():
        pygame.init()

    palette_colors = preview_palette
    if palette_colors is None:
        palette_colors = load_palette(palette_path(project_root, tortu_font.palette))

    pygame_font = pygame.font.Font(str(ttf_path), tortu_font.size)

    charset = tortu_font.resolved_charset()
    tortu_font.charset = unique_charset(charset)
    baked: dict[int, TortuGlyph] = {}
    for char in tortu_font.charset:
        glyph = bake_glyph(pygame_font, char, palette_colors)
        if glyph is not None:
            baked[ord(char)] = glyph
    tortu_font.glyphs = baked
    sync_line_height(tortu_font, min_linesize=pygame_font.get_linesize())


def install_ttf_source(project_root: Path, ttf_path: Path, font_name: str) -> str:
    """Copy a TTF into the project and return the project-relative path."""
    root = project_root.resolve()
    fonts_dir = root / "assets" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    stem = font_name.strip().replace(" ", "_") or ttf_path.stem
    dest = fonts_dir / f"{stem}.ttf"
    source = ttf_path.resolve()
    if source != dest.resolve():
        shutil.copy2(source, dest)
    return dest.relative_to(root).as_posix()


def load_tortu_font(path: Path) -> TortuFont:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = str(data.get("name", path.stem))
    source = str(data.get("source", "")).replace("\\", "/")
    if not source:
        raise ValueError(f"Font file missing source TTF: {path.name}")

    glyphs_raw = data.get("glyphs", {})
    glyphs: dict[int, TortuGlyph] = {}
    for key, raw in glyphs_raw.items():
        code = int(key)
        pixels = [int(v) for v in raw["pixels"]]
        glyphs[code] = TortuGlyph(
            int(raw.get("w", raw.get("width", 0))),
            int(raw.get("h", raw.get("height", 0))),
            int(raw.get("advance", 1)),
            pixels,
            int(raw.get("bearing_x", 0)),
            int(raw.get("bearing_y", 0)),
        )

    preset = str(data.get("charset_preset", CHARSET_LATIN1)).lower()
    if preset not in CHARSET_PRESETS:
        preset = CHARSET_LATIN1

    tortu_font = TortuFont(
        name=name,
        source=source,
        size=int(data.get("size", DEFAULT_FONT_SIZE)),
        line_height=int(data.get("line_height", DEFAULT_LINE_HEIGHT)),
        palette=str(data.get("palette", "default")),
        charset_preset=preset,
        charset=str(data.get("charset", "")),
        glyphs=glyphs,
    )
    sync_line_height(tortu_font)
    return tortu_font


def save_tortu_font(tortu_font: TortuFont, path: Path) -> None:
    sync_line_height(tortu_font)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": tortu_font.name,
        "source": tortu_font.source.replace("\\", "/"),
        "size": tortu_font.size,
        "line_height": tortu_font.line_height,
        "palette": tortu_font.palette,
        "charset_preset": tortu_font.charset_preset,
        "charset": tortu_font.resolved_charset(),
        "glyphs": {
            str(code): {
                "w": glyph.width,
                "h": glyph.height,
                "advance": glyph.advance,
                "bearing_x": glyph.bearing_x,
                "bearing_y": glyph.bearing_y,
                "pixels": glyph.pixels,
            }
            for code, glyph in sorted(tortu_font.glyphs.items())
        },
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def render_text_line(
    tortu_font: TortuFont,
    text: str,
    palette: list[tuple[int, int, int]],
    *,
    fore_index: int | None = None,
) -> pygame.Surface:
    """Lay out one line of UTF-8 text using baked glyphs."""
    if not text:
        return pygame.Surface((1, tortu_font.line_height), pygame.SRCALPHA)

    width = 0
    max_glyph_h = 0
    for char in text:
        glyph = tortu_font.glyphs.get(ord(char))
        if glyph:
            width += glyph.advance
            max_glyph_h = max(max_glyph_h, glyph.height)
        else:
            width += tortu_font.size // 2

    height = max(tortu_font.line_height, max_glyph_h)
    surface = pygame.Surface((max(1, width), height), pygame.SRCALPHA)
    cursor_x = 0
    for char in text:
        glyph = tortu_font.glyphs.get(ord(char))
        if glyph is None:
            cursor_x += max(1, tortu_font.size // 2)
            continue
        for y in range(glyph.height):
            for x in range(glyph.width):
                index = glyph.pixels[y * glyph.width + x]
                if index == TRANSPARENT_INDEX:
                    continue
                if fore_index is not None:
                    index = fore_index
                dst_x = cursor_x + x
                dst_y = y
                if 0 <= dst_x < surface.get_width() and 0 <= dst_y < surface.get_height():
                    rgb = palette[index]
                    surface.set_at((dst_x, dst_y), (*rgb, 255))
        cursor_x += glyph.advance
    return surface
