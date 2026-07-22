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
MAX_GUI_TILED_RECTS = 16
MAX_GUI_REPEAT_SPRITES = 16

FILL_LEFT_TO_RIGHT = "left_to_right"
FILL_RIGHT_TO_LEFT = "right_to_left"
FILL_TOP_TO_BOTTOM = "top_to_bottom"
FILL_BOTTOM_TO_TOP = "bottom_to_top"
FILL_DIRECTIONS = (FILL_LEFT_TO_RIGHT, FILL_RIGHT_TO_LEFT, FILL_TOP_TO_BOTTOM, FILL_BOTTOM_TO_TOP)

REPEAT_HORIZONTAL = "horizontal"
REPEAT_VERTICAL = "vertical"
REPEAT_DIRECTIONS = (REPEAT_HORIZONTAL, REPEAT_VERTICAL)


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


def _unique_element_id(existing_ids: set[str], base: str) -> str:
    base = base or "element"
    n = 1
    candidate = f"{base}{n}"
    while candidate in existing_ids:
        n += 1
        candidate = f"{base}{n}"
    return candidate


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


@dataclass
class GuiObject:
    """Placed object instance inside a GUI layer (prefab path + position)."""

    prefab: str
    x: int
    y: int
    animation: str = ""
    scale: float = 1.0
    visible: bool = True
    # Off at scene start: not drawn.
    enabled: bool = True
    # Optional name so instance scripts can find and reposition this placed
    # object at runtime via instance_api — e.g. a menu selection cursor.
    id: str = ""

    def copy(self) -> GuiObject:
        return GuiObject(
            self.prefab, self.x, self.y, self.animation, self.scale, self.visible, self.enabled,
            self.id,
        )


@dataclass
class GuiTextLabel:
    """Text label placed inside a GUI layer.

    `id` is optional (blank by default, unlike GuiTiledRect/GuiRepeatSprite)
    — most labels are static UI text, but naming one lets instance scripts
    find and update its text at runtime via instance_api, e.g. a lives
    counter.
    """

    text: str
    x: int
    y: int
    id: str = ""
    font: str = ""
    # Palette index to render the ink with, overriding the font's own baked
    # color. -1 means "use the font's baked color". Only meaningful for
    # .tortufont labels — .tortuspritefont glyphs are pre-colored bitmaps.
    color_index: int = -1
    # Uniform size multiplier applied to the already-baked glyph bitmap (same
    # technique as GuiLayerObject.scale) — never re-rasterizes the source TTF,
    # so this stays cheap regardless of value.
    scale: float = 1.0
    # How (x, y) anchors the rendered text: "left" (x is the left edge, the
    # historical default), "center" (x is the horizontal center), or "right"
    # (x is the right edge). y always anchors the top edge.
    align: str = "left"
    visible: bool = True
    # Off at scene start: not drawn.
    enabled: bool = True

    def copy(self) -> GuiTextLabel:
        return GuiTextLabel(
            self.text, self.x, self.y, self.id, self.font, self.color_index,
            self.scale, self.align, self.visible, self.enabled,
        )

    def draw_x(self, width: int) -> int:
        """Left-edge x to blit a `width`-px-wide rendered surface at, honoring align."""
        if self.align == "center":
            return self.x - width // 2
        if self.align == "right":
            return self.x - width
        return self.x


@dataclass
class GuiTiledRect:
    """Rect filled with a repeating sprite texture, cropped to `number / max_number`.

    Distinct from a stretched single image: the texture tiles to cover the
    rect instead of scaling, so pixel-art patterns stay crisp at any bar
    size. `prefab` points to a reusable `.tortuprogressbar` (texture + fill
    direction); this placement only tracks its own position, size and fill
    state — e.g. `number`/`max_number` as current/max HP for a health bar.
    `id` lets instance scripts find and update it at runtime via
    instance_api.
    """

    id: str
    prefab: str
    x: int
    y: int
    width: int
    height: int
    number: float = 1.0
    max_number: float = 1.0
    visible: bool = True
    enabled: bool = True

    def copy(self) -> GuiTiledRect:
        return GuiTiledRect(
            self.id, self.prefab, self.x, self.y, self.width, self.height,
            self.number, self.max_number, self.visible, self.enabled,
        )

    @property
    def fill_fraction(self) -> float:
        if self.max_number <= 0:
            return 0.0
        return max(0.0, min(1.0, self.number / self.max_number))


@dataclass
class GuiRepeatSprite:
    """A prefab drawn `number` times (out of `max_number` slots) — e.g. life pips or hearts.

    `prefab` points to a reusable `.tortupipbar` (full/empty sprites,
    direction, spacing, scale); this placement tracks its own position plus
    current/max count — e.g. `number`/`max_number` as current/max lives.
    Slots from `number` up to `max_number` draw the prefab's `empty_sprite`
    if set, otherwise are simply skipped. `id` lets instance scripts find
    and update it at runtime via instance_api.
    """

    id: str
    prefab: str
    x: int
    y: int
    number: int = 0
    max_number: int = 0
    visible: bool = True
    enabled: bool = True

    def copy(self) -> GuiRepeatSprite:
        return GuiRepeatSprite(
            self.id, self.prefab, self.x, self.y, self.number, self.max_number,
            self.visible, self.enabled,
        )


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
    tiled_rects: list[GuiTiledRect] = field(default_factory=list)
    repeat_sprites: list[GuiRepeatSprite] = field(default_factory=list)
    script: str = ""
    # Runtime-only pan offset (e.g. sliding between two panels laid out
    # side by side on one wide canvas) — driven by instance scripts via
    # instance_api, never read from or written to the .tortuguilayer file.
    scroll_x: int = 0
    scroll_y: int = 0

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

    def add_object(
        self, prefab: str, x: int, y: int, *, animation: str = "", scale: float = 1.0
    ) -> int:
        if len(self.objects) >= MAX_GUI_OBJECTS:
            raise ValueError(f"GUI layer cannot have more than {MAX_GUI_OBJECTS} objects")
        self.objects.append(GuiObject(prefab, x, y, animation, scale))
        return len(self.objects) - 1

    def unique_object_id(self, base: str = "object") -> str:
        return _unique_element_id({o.id for o in self.objects if o.id}, base)

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

    def unique_text_label_id(self, base: str = "label") -> str:
        return _unique_element_id({t.id for t in self.text_labels if t.id}, base)

    def add_text_label(
        self, text: str, x: int, y: int, *, font: str = "", label_id: str = ""
    ) -> int:
        if len(self.text_labels) >= MAX_GUI_TEXT_LABELS:
            raise ValueError(
                f"GUI layer cannot have more than {MAX_GUI_TEXT_LABELS} text labels"
            )
        self.text_labels.append(GuiTextLabel(text, x, y, label_id, font))
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

    def unique_tiled_rect_id(self, base: str = "bar") -> str:
        return _unique_element_id({r.id for r in self.tiled_rects if r.id}, base)

    def add_tiled_rect(
        self,
        prefab: str,
        x: int,
        y: int,
        width: int,
        height: int,
        *,
        rect_id: str = "",
        number: float = 1.0,
        max_number: float = 1.0,
    ) -> int:
        if len(self.tiled_rects) >= MAX_GUI_TILED_RECTS:
            raise ValueError(f"GUI layer cannot have more than {MAX_GUI_TILED_RECTS} tiled rects")
        rect_id = rect_id or self.unique_tiled_rect_id()
        self.tiled_rects.append(
            GuiTiledRect(rect_id, prefab, x, y, width, height, number, max_number)
        )
        return len(self.tiled_rects) - 1

    def remove_tiled_rect(self, index: int) -> None:
        if not (0 <= index < len(self.tiled_rects)):
            raise IndexError(f"Tiled rect index out of range: {index}")
        self.tiled_rects.pop(index)

    def unique_repeat_sprite_id(self, base: str = "pips") -> str:
        return _unique_element_id({s.id for s in self.repeat_sprites if s.id}, base)

    def add_repeat_sprite(
        self,
        prefab: str,
        x: int,
        y: int,
        *,
        sprite_id: str = "",
        number: int = 0,
        max_number: int = 0,
    ) -> int:
        if len(self.repeat_sprites) >= MAX_GUI_REPEAT_SPRITES:
            raise ValueError(
                f"GUI layer cannot have more than {MAX_GUI_REPEAT_SPRITES} repeat sprites"
            )
        sprite_id = sprite_id or self.unique_repeat_sprite_id()
        self.repeat_sprites.append(
            GuiRepeatSprite(sprite_id, prefab, x, y, number, max_number)
        )
        return len(self.repeat_sprites) - 1

    def remove_repeat_sprite(self, index: int) -> None:
        if not (0 <= index < len(self.repeat_sprites)):
            raise IndexError(f"Repeat sprite index out of range: {index}")
        self.repeat_sprites.pop(index)

    def find_tiled_rect_near(self, x: int, y: int, radius: int = 12) -> int | None:
        radius_sq = radius * radius
        best_index: int | None = None
        best_dist = radius_sq + 1
        for index, rect in enumerate(self.tiled_rects):
            dx = rect.x - x
            dy = rect.y - y
            dist = dx * dx + dy * dy
            if dist <= radius_sq and dist < best_dist:
                best_dist = dist
                best_index = index
        return best_index

    def find_repeat_sprite_near(self, x: int, y: int, radius: int = 12) -> int | None:
        radius_sq = radius * radius
        best_index: int | None = None
        best_dist = radius_sq + 1
        for index, rep in enumerate(self.repeat_sprites):
            dx = rep.x - x
            dy = rep.y - y
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
            float(raw.get("scale", 1.0)),
            bool(raw.get("visible", True)),
            bool(raw.get("enabled", True)),
            str(raw.get("id", "")).strip(),
        )
        for raw in data.get("objects", [])
        if raw.get("object", raw.get("prefab", ""))
    ]
    text_labels = [
        GuiTextLabel(
            str(raw.get("text", "")),
            int(raw.get("x", 0)),
            int(raw.get("y", 0)),
            str(raw.get("id", "")).strip(),
            _normalize_asset_path(str(raw.get("font", ""))),
            int(raw.get("color_index", -1)),
            float(raw.get("scale", 1.0)),
            str(raw.get("align", "left")),
            bool(raw.get("visible", True)),
            bool(raw.get("enabled", True)),
        )
        for raw in data.get("text_labels", [])
    ]
    tiled_rects = [
        GuiTiledRect(
            str(raw.get("id", "")).strip(),
            _normalize_asset_path(str(raw.get("prefab", raw.get("texture", "")))),
            int(raw.get("x", 0)),
            int(raw.get("y", 0)),
            int(raw.get("width", 0)),
            int(raw.get("height", 0)),
            float(raw.get("number", raw.get("value", 1.0))),
            float(raw.get("max_number", 1.0)),
            bool(raw.get("visible", True)),
            bool(raw.get("enabled", True)),
        )
        for raw in data.get("tiled_rects", [])
        if raw.get("prefab", raw.get("texture", ""))
    ]
    repeat_sprites = [
        GuiRepeatSprite(
            str(raw.get("id", "")).strip(),
            _normalize_asset_path(str(raw.get("prefab", raw.get("object", "")))),
            int(raw.get("x", 0)),
            int(raw.get("y", 0)),
            int(raw.get("number", raw.get("count", 0))),
            int(raw.get("max_number", 0)),
            bool(raw.get("visible", True)),
            bool(raw.get("enabled", True)),
        )
        for raw in data.get("repeat_sprites", [])
        if raw.get("prefab", raw.get("object", ""))
    ]
    script = _normalize_asset_path(str(data.get("script", "")))

    gui_layer = GuiLayer(
        width, height, palette, tileset, tiles, tile_layer_visible, objects, text_labels,
        tiled_rects, repeat_sprites, script,
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
                **({"scale": obj.scale} if obj.scale != 1.0 else {}),
                **({"visible": False} if not obj.visible else {}),
                **({"enabled": False} if not obj.enabled else {}),
                **({"id": obj.id} if obj.id else {}),
            }
            for obj in gui_layer.objects
        ],
        "text_labels": [
            {
                "text": label.text,
                "x": label.x,
                "y": label.y,
                **({"id": label.id} if label.id else {}),
                **({"font": _normalize_asset_path(label.font)} if label.font else {}),
                **({"color_index": label.color_index} if label.color_index >= 0 else {}),
                **({"scale": label.scale} if label.scale != 1.0 else {}),
                **({"align": label.align} if label.align != "left" else {}),
                **({"visible": False} if not label.visible else {}),
                **({"enabled": False} if not label.enabled else {}),
            }
            for label in gui_layer.text_labels
        ],
        "tiled_rects": [
            {
                "id": rect.id,
                "prefab": _normalize_asset_path(rect.prefab),
                "x": rect.x,
                "y": rect.y,
                "width": rect.width,
                "height": rect.height,
                "number": rect.number,
                "max_number": rect.max_number,
                **({"visible": False} if not rect.visible else {}),
                **({"enabled": False} if not rect.enabled else {}),
            }
            for rect in gui_layer.tiled_rects
        ],
        "repeat_sprites": [
            {
                "id": rep.id,
                "prefab": _normalize_asset_path(rep.prefab),
                "x": rep.x,
                "y": rep.y,
                "number": rep.number,
                "max_number": rep.max_number,
                **({"visible": False} if not rep.visible else {}),
                **({"enabled": False} if not rep.enabled else {}),
            }
            for rep in gui_layer.repeat_sprites
        ],
        **({"script": _normalize_asset_path(gui_layer.script)} if gui_layer.script else {}),
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
