"""Palette files in palettes/*.pal — index 85 is always transparent."""

from __future__ import annotations

import re
from pathlib import Path

from tortuengine.constants import MAX_COLORS

TRANSPARENT_INDEX = 85
PAINTABLE_INDICES = range(TRANSPARENT_INDEX)


def _parse_hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#").strip()
    if len(value) != 6:
        raise ValueError(f"Expected 6-digit hex color, got: {value!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def load_palette(path: Path) -> list[tuple[int, int, int]]:
    """Load a .pal file into 86 RGB tuples; index 85 is forced transparent."""
    colors: list[tuple[int, int, int] | None] = [None] * MAX_COLORS
    line_re = re.compile(r"^\s*(\d+)\s+(#?[0-9a-fA-F]{6}|transparent)\s*(?:#.*)?$")

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = line_re.match(line)
        if not match:
            raise ValueError(f"Invalid palette line in {path.name}: {raw!r}")

        index = int(match.group(1))
        token = match.group(2).lower()
        if index < 0 or index >= MAX_COLORS:
            raise ValueError(f"Palette index out of range (0-{MAX_COLORS - 1}): {index}")

        if token == "transparent":
            colors[index] = (0, 0, 0)
        else:
            colors[index] = _parse_hex(token)

    missing = [i for i, c in enumerate(colors) if c is None]
    if missing:
        raise ValueError(f"Palette {path.name} missing indices: {missing[:8]}{'…' if len(missing) > 8 else ''}")

    return [(r, g, b) for r, g, b in colors]  # type: ignore[misc]


def save_palette(path: Path, colors: list[tuple[int, int, int]]) -> None:
    if len(colors) != MAX_COLORS:
        raise ValueError(f"Palette must have {MAX_COLORS} entries")

    lines = [f"# Tortu palette — index {TRANSPARENT_INDEX} is always transparent"]
    for i in range(MAX_COLORS):
        if i == TRANSPARENT_INDEX:
            lines.append(f"{i} transparent")
        else:
            r, g, b = colors[i]
            lines.append(f"{i} {r:02x}{g:02x}{b:02x}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def list_palette_names(project_root: Path) -> list[str]:
    folder = project_root / "palettes"
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.pal"))


def palette_path(project_root: Path, name: str) -> Path:
    return project_root / "palettes" / f"{name}.pal"


def color_distance(r: int, g: int, b: int, rgb: tuple[int, int, int]) -> int:
    return (r - rgb[0]) ** 2 + (g - rgb[1]) ** 2 + (b - rgb[2]) ** 2


def closest_index(r: int, g: int, b: int, palette: list[tuple[int, int, int]]) -> int:
    best_index = 0
    best_distance = float("inf")
    for i in PAINTABLE_INDICES:
        dist = color_distance(r, g, b, palette[i])
        if dist < best_distance:
            best_distance = dist
            best_index = i
    return best_index


def default_palette_colors() -> list[tuple[int, int, int]]:
    """Starter 85-color set for new projects."""
    raw = [
        "1a1c2e", "ffffff", "f8f9fa", "ced4da", "868e96", "495057", "212529", "000000",
        "ff6b6b", "f06595", "cc5de8", "845ef7", "5c7cfa", "339af0", "22b8cf", "20c997",
        "51cf66", "94d82d", "fcc419", "ff922b", "ff6b00", "e03131", "c2255c", "9c36b5",
        "6741d9", "364fc7", "1864ab", "0b7285", "087f5b", "2b8a3e", "5c940d", "e67700",
        "d9480f", "fab005", "ffe066", "ff8787", "ffa8a8", "ffc9c9", "eebefa", "da77f2",
        "b197fc", "91a7ff", "74c0fc", "66d9e8", "63e6be", "8ce99a", "c0eb75", "ffd43b",
        "ffa94d", "ffc078", "ffd8a8", "ffe8cc", "3d5a80", "98c1d9", "e0fbfc", "293241",
        "ee6c4d", "f4a261", "e9c46a", "2a9d8f", "264653", "6d597a", "b56576", "343a40",
        "e9ecef", "adb5bd", "f1f3f5", "a61e4d", "862e9c", "5f3dc4", "1971c2", "0c8599",
        "099268", "2f9e44", "66a80f", "f08c00", "e8590c", "9b2226", "580c1f", "7048e8",
        "4263eb", "1098ad", "0ca678", "37b24d", "f76707",
    ]
    colors: list[tuple[int, int, int]] = []
    for hex_color in raw:
        colors.append(_parse_hex(hex_color))
    while len(colors) < TRANSPARENT_INDEX:
        colors.append((0, 0, 0))
    colors = colors[:TRANSPARENT_INDEX]
    colors.append((0, 0, 0))  # last slot — transparent in engine
    return colors
