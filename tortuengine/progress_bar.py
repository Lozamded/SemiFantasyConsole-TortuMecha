"""Progress bar prefabs (.tortuprogressbar) — reusable tiled-rect fill-bar definitions.

Bundles the look of a GUI tiled rect (texture + fill direction, plus a
starting size) so the same "health bar" style can be placed as many times
as needed across different `.tortuguilayer` files without repeating the
same texture/direction on every placement. `ranges` optionally swaps the
texture based on the placement's current `number` — a band system modeled
on the scene editor's background parallax bands (`SceneBgParallaxBand` /
`find_parallax_band` in `tortuengine/scene.py`): each range covers
`[min_number, max_number]`, first match wins, and falls back to the base
`texture` if nothing matches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tortuengine.gui_layer import FILL_DIRECTIONS, FILL_LEFT_TO_RIGHT

DEFAULT_PROGRESS_BAR_WIDTH = 40
DEFAULT_PROGRESS_BAR_HEIGHT = 8
MAX_PROGRESS_BAR_RANGES = 8


@dataclass
class ProgressBarRange:
    """Use `texture` instead of the base texture while `min_number <= number <= max_number`."""

    min_number: float
    max_number: float
    texture: str = ""

    def copy(self) -> ProgressBarRange:
        return ProgressBarRange(self.min_number, self.max_number, self.texture)


def find_progress_bar_range(
    number: float, ranges: list[ProgressBarRange]
) -> ProgressBarRange | None:
    for r in ranges:
        if r.min_number <= number <= r.max_number:
            return r
    return None


@dataclass
class ProgressBar:
    """A reusable tiled-rect fill-bar prefab."""

    name: str
    texture: str = ""
    fill_direction: str = FILL_LEFT_TO_RIGHT
    width: int = DEFAULT_PROGRESS_BAR_WIDTH
    height: int = DEFAULT_PROGRESS_BAR_HEIGHT
    ranges: list[ProgressBarRange] = field(default_factory=list)

    def copy(self) -> ProgressBar:
        return ProgressBar(
            self.name, self.texture, self.fill_direction, self.width, self.height,
            [r.copy() for r in self.ranges],
        )

    def texture_for(self, number: float) -> str:
        """Texture to draw for the given current value.

        Picks the first matching range (list order — first match wins, like
        `find_parallax_band`); falls back to the base `texture` if no range
        matches or the matching range has no texture set.
        """
        match = find_progress_bar_range(number, self.ranges)
        if match is not None and match.texture:
            return match.texture
        return self.texture


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


def _normalize_range(raw: dict) -> ProgressBarRange:
    min_number = float(raw.get("min_number", 0.0))
    max_number = float(raw.get("max_number", min_number))
    if max_number < min_number:
        min_number, max_number = max_number, min_number
    return ProgressBarRange(
        min_number, max_number, _normalize_asset_path(str(raw.get("texture", "")))
    )


def _normalize_ranges(raw_ranges: list) -> list[ProgressBarRange]:
    if len(raw_ranges) > MAX_PROGRESS_BAR_RANGES:
        raise ValueError(
            f"Progress bar has {len(raw_ranges)} texture ranges; "
            f"maximum is {MAX_PROGRESS_BAR_RANGES}"
        )
    return [_normalize_range(raw) for raw in raw_ranges if isinstance(raw, dict)]


def load_progress_bar(path: Path) -> ProgressBar:
    data = json.loads(path.read_text(encoding="utf-8"))
    fill_direction = str(data.get("fill_direction", FILL_LEFT_TO_RIGHT))
    if fill_direction not in FILL_DIRECTIONS:
        fill_direction = FILL_LEFT_TO_RIGHT
    return ProgressBar(
        name=str(data.get("name", path.stem)),
        texture=_normalize_asset_path(str(data.get("texture", ""))),
        fill_direction=fill_direction,
        width=int(data.get("width", DEFAULT_PROGRESS_BAR_WIDTH)),
        height=int(data.get("height", DEFAULT_PROGRESS_BAR_HEIGHT)),
        ranges=_normalize_ranges(data.get("ranges", [])),
    )


def save_progress_bar(bar: ProgressBar, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "name": bar.name,
        "texture": _normalize_asset_path(bar.texture),
        "fill_direction": bar.fill_direction,
        "width": bar.width,
        "height": bar.height,
    }
    if bar.ranges:
        data["ranges"] = [
            {
                "min_number": r.min_number,
                "max_number": r.max_number,
                "texture": _normalize_asset_path(r.texture),
            }
            for r in bar.ranges
        ]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
