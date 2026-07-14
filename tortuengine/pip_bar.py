"""Pip bar prefabs (.tortupipbar) — reusable repeat-sprite counter definitions.

Bundles the look and layout of a GUI repeat sprite (full/empty sprite
textures, direction, spacing, scale) so the same "heart counter" style can
be placed as many times as needed across different `.tortuguilayer` files.
Each placement tracks its own position plus current/max count (`number`/
`max_number`), so the same style can represent "3 hearts" in one HUD and
"6 hearts" in another. `ranges` optionally swaps the filled-slot sprite
based on the placement's current `number` — a band system modeled on the
scene editor's background parallax bands (`SceneBgParallaxBand` /
`find_parallax_band` in `tortuengine/scene.py`): each range covers
`[min_number, max_number]`, first match wins, and falls back to the base
`full_sprite` if nothing matches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tortuengine.gui_layer import REPEAT_DIRECTIONS, REPEAT_HORIZONTAL

MAX_PIP_BAR_RANGES = 8


@dataclass
class PipBarRange:
    """Use `full_sprite` instead of the base sprite while `min_number <= number <= max_number`."""

    min_number: int
    max_number: int
    full_sprite: str = ""

    def copy(self) -> PipBarRange:
        return PipBarRange(self.min_number, self.max_number, self.full_sprite)


def find_pip_bar_range(number: int, ranges: list[PipBarRange]) -> PipBarRange | None:
    for r in ranges:
        if r.min_number <= number <= r.max_number:
            return r
    return None


@dataclass
class PipBar:
    """A reusable repeat-sprite counter prefab."""

    name: str
    full_sprite: str = ""  # .tortusprite path — drawn for filled slots
    empty_sprite: str = ""  # .tortusprite path — drawn for empty slots (blank if unset)
    direction: str = REPEAT_HORIZONTAL
    spacing: int = 0
    scale: float = 1.0
    ranges: list[PipBarRange] = field(default_factory=list)

    def copy(self) -> PipBar:
        return PipBar(
            self.name, self.full_sprite, self.empty_sprite,
            self.direction, self.spacing, self.scale,
            [r.copy() for r in self.ranges],
        )

    def full_sprite_for(self, number: int) -> str:
        """Filled-slot sprite to draw for the given current value.

        Picks the first matching range (list order — first match wins, like
        `find_parallax_band`); falls back to the base `full_sprite` if no
        range matches or the matching range has no sprite set.
        """
        match = find_pip_bar_range(number, self.ranges)
        if match is not None and match.full_sprite:
            return match.full_sprite
        return self.full_sprite


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


def _normalize_range(raw: dict) -> PipBarRange:
    min_number = int(raw.get("min_number", 0))
    max_number = int(raw.get("max_number", min_number))
    if max_number < min_number:
        min_number, max_number = max_number, min_number
    return PipBarRange(
        min_number, max_number, _normalize_asset_path(str(raw.get("full_sprite", "")))
    )


def _normalize_ranges(raw_ranges: list) -> list[PipBarRange]:
    if len(raw_ranges) > MAX_PIP_BAR_RANGES:
        raise ValueError(
            f"Pip bar has {len(raw_ranges)} texture ranges; maximum is {MAX_PIP_BAR_RANGES}"
        )
    return [_normalize_range(raw) for raw in raw_ranges if isinstance(raw, dict)]


def load_pip_bar(path: Path) -> PipBar:
    data = json.loads(path.read_text(encoding="utf-8"))
    direction = str(data.get("direction", REPEAT_HORIZONTAL))
    if direction not in REPEAT_DIRECTIONS:
        direction = REPEAT_HORIZONTAL
    return PipBar(
        name=str(data.get("name", path.stem)),
        full_sprite=_normalize_asset_path(str(data.get("full_sprite", ""))),
        empty_sprite=_normalize_asset_path(str(data.get("empty_sprite", ""))),
        direction=direction,
        spacing=int(data.get("spacing", 0)),
        scale=float(data.get("scale", 1.0)),
        ranges=_normalize_ranges(data.get("ranges", [])),
    )


def save_pip_bar(bar: PipBar, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": bar.name,
        "full_sprite": _normalize_asset_path(bar.full_sprite),
        "empty_sprite": _normalize_asset_path(bar.empty_sprite),
        "direction": bar.direction,
        "spacing": bar.spacing,
        "scale": bar.scale,
    }
    if bar.ranges:
        data["ranges"] = [
            {
                "min_number": r.min_number,
                "max_number": r.max_number,
                "full_sprite": _normalize_asset_path(r.full_sprite),
            }
            for r in bar.ranges
        ]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
