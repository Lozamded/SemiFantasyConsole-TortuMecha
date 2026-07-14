"""Progress bar prefabs (.tortuprogressbar) — reusable tiled-rect fill-bar definitions.

Bundles the look of a GUI tiled rect (texture + fill direction, plus a
starting size) so the same "health bar" style can be placed as many times
as needed across different `.tortuguilayer` files without repeating the
same texture/direction on every placement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tortuengine.gui_layer import FILL_DIRECTIONS, FILL_LEFT_TO_RIGHT

DEFAULT_PROGRESS_BAR_WIDTH = 40
DEFAULT_PROGRESS_BAR_HEIGHT = 8


@dataclass
class ProgressBar:
    """A reusable tiled-rect fill-bar prefab."""

    name: str
    texture: str = ""
    fill_direction: str = FILL_LEFT_TO_RIGHT
    width: int = DEFAULT_PROGRESS_BAR_WIDTH
    height: int = DEFAULT_PROGRESS_BAR_HEIGHT

    def copy(self) -> ProgressBar:
        return ProgressBar(self.name, self.texture, self.fill_direction, self.width, self.height)


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


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
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
