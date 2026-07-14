"""Pip bar prefabs (.tortupipbar) — reusable repeat-sprite counter definitions.

Bundles the look and layout of a GUI repeat sprite (full/empty sprite
textures, direction, spacing, scale) so the same "heart counter" style can
be placed as many times as needed across different `.tortuguilayer` files.
Each placement tracks its own position plus current/max count (`number`/
`max_number`), so the same style can represent "3 hearts" in one HUD and
"6 hearts" in another.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tortuengine.gui_layer import REPEAT_DIRECTIONS, REPEAT_HORIZONTAL


@dataclass
class PipBar:
    """A reusable repeat-sprite counter prefab."""

    name: str
    full_sprite: str = ""  # .tortusprite path — drawn for filled slots
    empty_sprite: str = ""  # .tortusprite path — drawn for empty slots (blank if unset)
    direction: str = REPEAT_HORIZONTAL
    spacing: int = 0
    scale: float = 1.0

    def copy(self) -> PipBar:
        return PipBar(
            self.name, self.full_sprite, self.empty_sprite,
            self.direction, self.spacing, self.scale,
        )


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


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
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
