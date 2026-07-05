"""GUI layer assets (.tortuguilayer) — sized on-screen UI canvas: one tile layer, objects, text labels."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_BLOCK

DEFAULT_GUI_LAYER_WIDTH = SCREEN_WIDTH
DEFAULT_GUI_LAYER_HEIGHT = SCREEN_HEIGHT

EMPTY_TILE = -1
MAX_GUI_OBJECTS = 64
MAX_GUI_TEXT_LABELS = 32


def grid_columns(width_px: int, tile_size: int) -> int:
    if tile_size < 1:
        raise ValueError("Tile size must be at least 1 px")
    return (width_px + tile_size - 1) // tile_size


def grid_rows(height_px: int, tile_size: int) -> int:
    if tile_size < 1:
        raise ValueError("Tile size must be at least 1 px")
    return (height_px + tile_size - 1) // tile_size


def _blank_tile_grid(cols: int, rows: int) -> list[int]:
    return [EMPTY_TILE] * (cols * rows)


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


@dataclass
class GuiObject:
    """Placed object instance inside a GUI layer (prefab path + position)."""

    prefab: str
    x: int
    y: int
    animation: str = ""

    def copy(self) -> GuiObject:
        return GuiObject(self.prefab, self.x, self.y, self.animation)


@dataclass
class GuiTextLabel:
    """Text label placed inside a GUI layer."""

    text: str
    x: int
    y: int
    font: str = ""

    def copy(self) -> GuiTextLabel:
        return GuiTextLabel(self.text, self.x, self.y, self.font)


@dataclass
class GuiLayer:
    """Reusable GUI layer canvas: one tile layer + placed objects + text labels."""

    width: int
    height: int
    palette: str = "default"
    tileset: str = ""
    tiles: list[int] = field(default_factory=list)
    tile_layer_visible: bool = True
    objects: list[GuiObject] = field(default_factory=list)
    text_labels: list[GuiTextLabel] = field(default_factory=list)
    script: str = ""

    @classmethod
    def create(
        cls, width: int = DEFAULT_GUI_LAYER_WIDTH, height: int = DEFAULT_GUI_LAYER_HEIGHT
    ) -> GuiLayer:
        if width < 1 or height < 1:
            raise ValueError("GUI layer must be at least 1×1 pixels")
        return cls(width, height)

    def grid_columns(self, tile_size: int) -> int:
        return grid_columns(self.width, tile_size)

    def grid_rows(self, tile_size: int) -> int:
        return grid_rows(self.height, tile_size)

    def resize(self, width: int, height: int, tile_size: int = TILE_BLOCK) -> None:
        if width < 1 or height < 1:
            raise ValueError("GUI layer must be at least 1×1 pixels")
        if width == self.width and height == self.height:
            return
        old_cols = self.grid_columns(tile_size)
        old_rows = self.grid_rows(tile_size)
        self.width = width
        self.height = height
        new_cols = self.grid_columns(tile_size)
        new_rows = self.grid_rows(tile_size)
        out = _blank_tile_grid(new_cols, new_rows)
        for ny in range(new_rows):
            for nx in range(new_cols):
                sx = int(nx * old_cols / new_cols) if new_cols else 0
                sy = int(ny * old_rows / new_rows) if new_rows else 0
                if sx < old_cols and sy < old_rows:
                    idx = sy * old_cols + sx
                    if idx < len(self.tiles):
                        out[ny * new_cols + nx] = self.tiles[idx]
        self.tiles = out

    def ensure_tile_grid(self, tile_size: int) -> None:
        """Resize the tile grid to match pixel bounds at *tile_size*, discarding tiles on mismatch."""
        cols = self.grid_columns(tile_size)
        rows = self.grid_rows(tile_size)
        expected = cols * rows
        if len(self.tiles) == expected:
            return
        self.tiles = _blank_tile_grid(cols, rows)

    def _validate_coords(self, x: int, y: int, tile_size: int) -> None:
        cols = self.grid_columns(tile_size)
        rows = self.grid_rows(tile_size)
        if not (0 <= x < cols and 0 <= y < rows):
            raise IndexError(f"Tile coordinate out of range: ({x}, {y})")

    def get_tile(self, x: int, y: int, tile_size: int) -> int:
        self._validate_coords(x, y, tile_size)
        cols = self.grid_columns(tile_size)
        return self.tiles[y * cols + x]

    def set_tile(self, x: int, y: int, tile_index: int, tile_size: int) -> None:
        if tile_index < EMPTY_TILE:
            raise ValueError(f"Invalid tile index: {tile_index}")
        self._validate_coords(x, y, tile_size)
        cols = self.grid_columns(tile_size)
        self.tiles[y * cols + x] = tile_index

    def add_object(self, prefab: str, x: int, y: int, *, animation: str = "") -> int:
        if len(self.objects) >= MAX_GUI_OBJECTS:
            raise ValueError(f"GUI layer cannot have more than {MAX_GUI_OBJECTS} objects")
        self.objects.append(GuiObject(prefab, x, y, animation))
        return len(self.objects) - 1

    def remove_object(self, index: int) -> None:
        if not (0 <= index < len(self.objects)):
            raise IndexError(f"Object index out of range: {index}")
        self.objects.pop(index)

    def find_object_near(self, x: int, y: int, radius: int = 12) -> int | None:
        radius_sq = radius * radius
        best_index: int | None = None
        best_dist = radius_sq + 1
        for index, inst in enumerate(self.objects):
            dx = inst.x - x
            dy = inst.y - y
            dist = dx * dx + dy * dy
            if dist <= radius_sq and dist < best_dist:
                best_dist = dist
                best_index = index
        return best_index

    def add_text_label(self, text: str, x: int, y: int, *, font: str = "") -> int:
        if len(self.text_labels) >= MAX_GUI_TEXT_LABELS:
            raise ValueError(
                f"GUI layer cannot have more than {MAX_GUI_TEXT_LABELS} text labels"
            )
        self.text_labels.append(GuiTextLabel(text, x, y, font))
        return len(self.text_labels) - 1

    def remove_text_label(self, index: int) -> None:
        if not (0 <= index < len(self.text_labels)):
            raise IndexError(f"Text label index out of range: {index}")
        self.text_labels.pop(index)

    def find_text_label_near(self, x: int, y: int, radius: int = 12) -> int | None:
        radius_sq = radius * radius
        best_index: int | None = None
        best_dist = radius_sq + 1
        for index, label in enumerate(self.text_labels):
            dx = label.x - x
            dy = label.y - y
            dist = dx * dx + dy * dy
            if dist <= radius_sq and dist < best_dist:
                best_dist = dist
                best_index = index
        return best_index


def tile_size_for_gui_layer(gui_layer: GuiLayer, project_root: Path | None) -> int:
    if gui_layer.tileset and project_root is not None:
        path = (project_root / gui_layer.tileset).resolve()
        if path.is_file():
            from tortuengine.tileset import load_tileset

            return load_tileset(path).tile_size
    return TILE_BLOCK


def load_gui_layer(path: Path, *, project_root: Path | None = None) -> GuiLayer:
    data = json.loads(path.read_text(encoding="utf-8"))
    width = int(data["width"])
    height = int(data["height"])
    if width < 1 or height < 1:
        raise ValueError(f"GUI layer size must be at least 1×1 in {path.name}")

    palette = str(data.get("palette", "default"))
    tileset = _normalize_asset_path(str(data.get("tileset", "")))
    tile_layer_visible = bool(data.get("tile_layer_visible", True))
    tiles = [int(v) for v in data.get("tiles", [])]

    objects = [
        GuiObject(
            _normalize_asset_path(str(raw.get("object", raw.get("prefab", "")))),
            int(raw.get("x", 0)),
            int(raw.get("y", 0)),
            str(raw.get("animation", "")),
        )
        for raw in data.get("objects", [])
        if raw.get("object", raw.get("prefab", ""))
    ]
    text_labels = [
        GuiTextLabel(
            str(raw.get("text", "")),
            int(raw.get("x", 0)),
            int(raw.get("y", 0)),
            _normalize_asset_path(str(raw.get("font", ""))),
        )
        for raw in data.get("text_labels", [])
    ]
    script = _normalize_asset_path(str(data.get("script", "")))

    gui_layer = GuiLayer(
        width, height, palette, tileset, tiles, tile_layer_visible, objects, text_labels, script
    )
    gui_layer.ensure_tile_grid(tile_size_for_gui_layer(gui_layer, project_root))
    return gui_layer


def save_gui_layer(gui_layer: GuiLayer, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "width": gui_layer.width,
        "height": gui_layer.height,
        "palette": gui_layer.palette,
        **({"tileset": _normalize_asset_path(gui_layer.tileset)} if gui_layer.tileset else {}),
        **({"tiles": gui_layer.tiles} if gui_layer.tileset else {}),
        "tile_layer_visible": gui_layer.tile_layer_visible,
        "objects": [
            {
                "object": _normalize_asset_path(obj.prefab),
                "x": obj.x,
                "y": obj.y,
                **({"animation": obj.animation} if obj.animation else {}),
            }
            for obj in gui_layer.objects
        ],
        "text_labels": [
            {
                "text": label.text,
                "x": label.x,
                "y": label.y,
                **({"font": _normalize_asset_path(label.font)} if label.font else {}),
            }
            for label in gui_layer.text_labels
        ],
        **({"script": _normalize_asset_path(gui_layer.script)} if gui_layer.script else {}),
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
