"""Scene assets (.tortuscene) — multi tile-layer maps with per-tile-layer tilesets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tortuengine.constants import (
    BACKGROUND_LAYERS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TILE_BLOCK,
    TILE_LAYERS,
)

# Empty cell — not a tileset index.
EMPTY_TILE = -1

MIN_SCENE_TILE_LAYERS = 1
MAX_SCENE_TILE_LAYERS = TILE_LAYERS

DEFAULT_SCENE_WIDTH = SCREEN_WIDTH
DEFAULT_SCENE_HEIGHT = SCREEN_HEIGHT

DEFAULT_TILE_LAYER_NAMES = tuple(f"tile_layer_{i}" for i in range(MAX_SCENE_TILE_LAYERS))

MIN_SCENE_BG_LAYERS = 0
MAX_SCENE_BG_LAYERS = BACKGROUND_LAYERS

DEFAULT_SCENE_BG_LAYER_NAMES = tuple(f"scene_bg_{i}" for i in range(MAX_SCENE_BG_LAYERS))

MAX_PARALLAX_BANDS = 8
MAX_SCENE_OBJECTS = 256


@dataclass
class SceneObject:
    """Placed object instance in a scene (prefab path + origin position)."""

    prefab: str
    x: int
    y: int
    animation: str = ""

    def copy(self) -> SceneObject:
        return SceneObject(self.prefab, self.x, self.y, self.animation)


@dataclass
class SceneBgParallaxBand:
    """Horizontal Y strip on a background with its own X-scroll settings."""

    y0: int
    y1: int
    parallax_x: float = 0.5
    fixed: bool = False
    repeat_x: bool = False
    repeat_y: bool = False

    def copy(self) -> SceneBgParallaxBand:
        return SceneBgParallaxBand(
            self.y0,
            self.y1,
            self.parallax_x,
            self.fixed,
            self.repeat_x,
            self.repeat_y,
        )


def find_parallax_band(y: int, bands: list[SceneBgParallaxBand]) -> SceneBgParallaxBand | None:
    for band in bands:
        if band.y0 <= y <= band.y1:
            return band
    return None


def default_parallax_band(height: int, *, parallax_x: float = 0.5) -> SceneBgParallaxBand:
    y1 = max(0, height - 1)
    return SceneBgParallaxBand(0, y1, parallax_x=parallax_x)


def grid_columns(width_px: int, tile_size: int) -> int:
    if tile_size < 1:
        raise ValueError("Tile size must be at least 1 px")
    return (width_px + tile_size - 1) // tile_size


def grid_rows(height_px: int, tile_size: int) -> int:
    if tile_size < 1:
        raise ValueError("Tile size must be at least 1 px")
    return (height_px + tile_size - 1) // tile_size


def _blank_tile_layer_grid(cols: int, rows: int) -> list[int]:
    return [EMPTY_TILE] * (cols * rows)


@dataclass
class SceneTileLayer:
    """One tile layer in a scene."""

    name: str
    tiles: list[int]
    visible: bool = True
    tileset: str = ""

    def copy(self) -> SceneTileLayer:
        return SceneTileLayer(self.name, self.tiles.copy(), self.visible, self.tileset)


def tile_size_for_tile_layer(tile_layer: SceneTileLayer, project_root: Path | None) -> int:
    if tile_layer.tileset and project_root is not None:
        path = (project_root / tile_layer.tileset).resolve()
        if path.is_file():
            from tortuengine.tileset import load_tileset

            return load_tileset(path).tile_size
    return TILE_BLOCK


@dataclass
class SceneBgLayer:
    """Scene slot referencing a .tortubackground asset with parallax."""

    name: str
    background: str = ""
    visible: bool = True
    parallax_x: float = 0.5
    parallax_y: float = 0.0
    fixed: bool = False
    repeat_x: bool = False
    repeat_y: bool = False
    band_parallax: bool = False
    parallax_bands: list[SceneBgParallaxBand] = field(default_factory=list)

    def copy(self) -> SceneBgLayer:
        return SceneBgLayer(
            self.name,
            self.background,
            self.visible,
            self.parallax_x,
            self.parallax_y,
            self.fixed,
            self.repeat_x,
            self.repeat_y,
            self.band_parallax,
            [band.copy() for band in self.parallax_bands],
        )

    def ensure_parallax_bands(self, bg_height: int) -> None:
        if not self.parallax_bands:
            self.parallax_bands = [default_parallax_band(bg_height, parallax_x=self.parallax_x)]
            return
        y1 = max(0, bg_height - 1)
        for band in self.parallax_bands:
            band.y0 = max(0, min(band.y0, y1))
            band.y1 = max(band.y0, min(band.y1, y1))


@dataclass
class Scene:
    """Tile map sized in pixels; each tile layer may reference its own tileset."""

    palette: str
    width: int
    height: int
    tile_layers: list[SceneTileLayer] = field(default_factory=list)
    scene_bg_layers: list[SceneBgLayer] = field(default_factory=list)
    objects: list[SceneObject] = field(default_factory=list)
    collision_tile_layer: int = 0
    script: str = ""
    camera_script: str = ""
    camera_target: str = ""

    @property
    def tile_layer_count(self) -> int:
        return len(self.tile_layers)

    @property
    def scene_bg_layer_count(self) -> int:
        return len(self.scene_bg_layers)

    def grid_columns(self, tile_size: int) -> int:
        return grid_columns(self.width, tile_size)

    def grid_rows(self, tile_size: int) -> int:
        return grid_rows(self.height, tile_size)

    def cell_count(self, tile_size: int) -> int:
        return self.grid_columns(tile_size) * self.grid_rows(tile_size)

    @classmethod
    def create(
        cls,
        palette: str,
        width: int = DEFAULT_SCENE_WIDTH,
        height: int = DEFAULT_SCENE_HEIGHT,
        *,
        tile_size: int = TILE_BLOCK,
    ) -> Scene:
        if width < 1 or height < 1:
            raise ValueError("Scene must be at least 1×1 pixels")
        cols = grid_columns(width, tile_size)
        rows = grid_rows(height, tile_size)
        tile_layers = [
            SceneTileLayer(DEFAULT_TILE_LAYER_NAMES[0], _blank_tile_layer_grid(cols, rows))
        ]
        return cls(palette, width, height, tile_layers, [], collision_tile_layer=0)

    def add_object(
        self,
        prefab: str,
        x: int,
        y: int,
        *,
        animation: str = "",
    ) -> int:
        if len(self.objects) >= MAX_SCENE_OBJECTS:
            raise ValueError(f"Scene cannot have more than {MAX_SCENE_OBJECTS} objects")
        self.objects.append(SceneObject(prefab, x, y, animation))
        return len(self.objects) - 1

    def remove_object(self, object_index: int) -> None:
        if not (0 <= object_index < len(self.objects)):
            raise IndexError(f"Object index out of range: {object_index}")
        self.objects.pop(object_index)

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

    def _validate_scene_bg_layer(self, scene_bg_layer_index: int) -> None:
        if not (0 <= scene_bg_layer_index < len(self.scene_bg_layers)):
            raise IndexError(f"Scene bg layer index out of range: {scene_bg_layer_index}")

    def _validate_scene_bg_layer_count(self) -> None:
        count = len(self.scene_bg_layers)
        if count > MAX_SCENE_BG_LAYERS:
            raise ValueError(
                f"Scene cannot have more than {MAX_SCENE_BG_LAYERS} background layers"
            )

    def add_scene_bg_layer(self, *, copy_from: int | None = None) -> int:
        if len(self.scene_bg_layers) >= MAX_SCENE_BG_LAYERS:
            raise ValueError(
                f"Scene cannot have more than {MAX_SCENE_BG_LAYERS} background layers"
            )
        index = len(self.scene_bg_layers)
        if copy_from is not None:
            self._validate_scene_bg_layer(copy_from)
            source = self.scene_bg_layers[copy_from]
            self.scene_bg_layers.append(source.copy())
            self.scene_bg_layers[-1].name = f"{source.name}_copy"
        else:
            self.scene_bg_layers.append(
                SceneBgLayer(DEFAULT_SCENE_BG_LAYER_NAMES[index])
            )
        return index

    def remove_scene_bg_layer(self, scene_bg_layer_index: int) -> None:
        self._validate_scene_bg_layer(scene_bg_layer_index)
        self.scene_bg_layers.pop(scene_bg_layer_index)

    def _validate_coords(self, x: int, y: int, tile_size: int) -> None:
        cols = self.grid_columns(tile_size)
        rows = self.grid_rows(tile_size)
        if not (0 <= x < cols and 0 <= y < rows):
            raise IndexError(f"Tile coordinate out of range: ({x}, {y})")

    def _validate_tile_layer(self, tile_layer_index: int) -> None:
        if not (0 <= tile_layer_index < len(self.tile_layers)):
            raise IndexError(f"Tile layer index out of range: {tile_layer_index}")

    def _validate_tile_layer_count(self) -> None:
        count = len(self.tile_layers)
        if not (MIN_SCENE_TILE_LAYERS <= count <= MAX_SCENE_TILE_LAYERS):
            raise ValueError(
                f"Scene must have {MIN_SCENE_TILE_LAYERS}–{MAX_SCENE_TILE_LAYERS} tile layers"
            )

    def _cell_index(self, x: int, y: int, tile_size: int) -> int:
        cols = self.grid_columns(tile_size)
        return y * cols + x

    def get_tile(self, tile_layer_index: int, x: int, y: int, tile_size: int) -> int:
        self._validate_tile_layer(tile_layer_index)
        self._validate_coords(x, y, tile_size)
        return self.tile_layers[tile_layer_index].tiles[self._cell_index(x, y, tile_size)]

    def set_tile(
        self, tile_layer_index: int, x: int, y: int, tile_index: int, tile_size: int
    ) -> None:
        if tile_index < EMPTY_TILE:
            raise ValueError(f"Invalid tile index: {tile_index}")
        self._validate_tile_layer(tile_layer_index)
        self._validate_coords(x, y, tile_size)
        self.tile_layers[tile_layer_index].tiles[self._cell_index(x, y, tile_size)] = tile_index

    def set_collision_tile_layer(self, tile_layer_index: int) -> None:
        self._validate_tile_layer(tile_layer_index)
        self.collision_tile_layer = tile_layer_index

    def ensure_tile_layer_grid(self, tile_layer_index: int, tile_size: int) -> None:
        """Resize one tile layer's grid to match pixel bounds at *tile_size*."""
        self._validate_tile_layer(tile_layer_index)
        tile_layer = self.tile_layers[tile_layer_index]
        cols = self.grid_columns(tile_size)
        rows = self.grid_rows(tile_size)
        expected = cols * rows
        if len(tile_layer.tiles) == expected:
            return

        old_cols = 0
        old_rows = 0
        for try_size in (tile_size, TILE_BLOCK, 16, 4, 32, 64):
            try_cols = grid_columns(self.width, try_size)
            try_rows = grid_rows(self.height, try_size)
            if try_cols * try_rows == len(tile_layer.tiles):
                old_cols, old_rows = try_cols, try_rows
                break
        if old_cols == 0:
            old_cols = max(1, cols)
            old_rows = max(1, len(tile_layer.tiles) // old_cols)

        out = _blank_tile_layer_grid(cols, rows)
        for ny in range(rows):
            for nx in range(cols):
                sx = min(old_cols - 1, int(nx * old_cols / cols)) if cols else 0
                sy = min(old_rows - 1, int(ny * old_rows / rows)) if rows else 0
                out[ny * cols + nx] = tile_layer.tiles[sy * old_cols + sx]
        self.tile_layers[tile_layer_index] = SceneTileLayer(
            tile_layer.name, out, tile_layer.visible, tile_layer.tileset
        )

    def ensure_all_tile_layer_grids(self, project_root: Path | None) -> None:
        for index in range(len(self.tile_layers)):
            self.ensure_tile_layer_grid(
                index, tile_size_for_tile_layer(self.tile_layers[index], project_root)
            )

    def add_tile_layer(self, tile_size: int, *, copy_from: int | None = None) -> int:
        if len(self.tile_layers) >= MAX_SCENE_TILE_LAYERS:
            raise ValueError(f"Scene cannot have more than {MAX_SCENE_TILE_LAYERS} tile layers")
        index = len(self.tile_layers)
        cols = self.grid_columns(tile_size)
        rows = self.grid_rows(tile_size)
        if copy_from is not None:
            self._validate_tile_layer(copy_from)
            source = self.tile_layers[copy_from]
            tiles = source.tiles.copy()
            visible = source.visible
            name = f"{source.name}_copy"
            tileset = source.tileset
        else:
            tiles = _blank_tile_layer_grid(cols, rows)
            visible = True
            name = DEFAULT_TILE_LAYER_NAMES[index]
            tileset = ""
        self.tile_layers.append(SceneTileLayer(name, tiles, visible, tileset))
        self.ensure_tile_layer_grid(index, tile_size)
        return index

    def remove_tile_layer(self, tile_layer_index: int) -> None:
        if len(self.tile_layers) <= MIN_SCENE_TILE_LAYERS:
            raise ValueError(f"Scene must keep at least {MIN_SCENE_TILE_LAYERS} tile layer")
        self._validate_tile_layer(tile_layer_index)
        self.tile_layers.pop(tile_layer_index)
        if self.collision_tile_layer == tile_layer_index:
            self.collision_tile_layer = 0
        elif self.collision_tile_layer > tile_layer_index:
            self.collision_tile_layer -= 1

    def resize_pixels(self, width: int, height: int, project_root: Path | None) -> None:
        """Resample all tile layers after changing the scene size in pixels."""
        if width < 1 or height < 1:
            raise ValueError("Scene must be at least 1×1 pixels")
        if width == self.width and height == self.height:
            return

        new_tile_layers: list[SceneTileLayer] = []
        for tile_layer in self.tile_layers:
            tile_size = tile_size_for_tile_layer(tile_layer, project_root)
            old_cols = self.grid_columns(tile_size)
            old_rows = self.grid_rows(tile_size)
            new_cols = grid_columns(width, tile_size)
            new_rows = grid_rows(height, tile_size)
            out = _blank_tile_layer_grid(new_cols, new_rows)
            for ny in range(new_rows):
                for nx in range(new_cols):
                    sx = int(nx * old_cols / new_cols) if new_cols else 0
                    sy = int(ny * old_rows / new_rows) if new_rows else 0
                    if sx < old_cols and sy < old_rows:
                        out[ny * new_cols + nx] = tile_layer.tiles[sy * old_cols + sx]
            new_tile_layers.append(
                SceneTileLayer(tile_layer.name, out, tile_layer.visible, tile_layer.tileset)
            )

        self.width = width
        self.height = height
        self.tile_layers = new_tile_layers


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


def _normalize_tile_layer(
    raw: dict,
    tile_layer_index: int,
    tile_size: int,
    width: int,
    height: int,
    path: Path,
    *,
    default_tileset: str = "",
) -> SceneTileLayer:
    cols = grid_columns(width, tile_size)
    rows = grid_rows(height, tile_size)
    expected = cols * rows
    name = str(raw.get("name", DEFAULT_TILE_LAYER_NAMES[tile_layer_index]))
    visible = bool(raw.get("visible", True))
    tileset = _normalize_asset_path(str(raw.get("tileset", default_tileset)))
    tiles = [int(v) for v in raw["tiles"]]
    if len(tiles) != expected:
        raise ValueError(
            f"Tile layer {tile_layer_index} tile count mismatch in {path.name}: "
            f"expected {expected}, got {len(tiles)}"
        )
    for value in tiles:
        if value < EMPTY_TILE:
            raise ValueError(
                f"Invalid tile index {value} in tile layer {tile_layer_index} of {path.name}"
            )
    return SceneTileLayer(name, tiles, visible, tileset)


def _normalize_tile_layers(
    raw_tile_layers: list[dict],
    width: int,
    height: int,
    path: Path,
    project_root: Path | None,
    *,
    legacy_tileset: str = "",
) -> list[SceneTileLayer]:
    if not raw_tile_layers:
        return [
            SceneTileLayer(
                DEFAULT_TILE_LAYER_NAMES[0],
                _blank_tile_layer_grid(
                    grid_columns(width, TILE_BLOCK), grid_rows(height, TILE_BLOCK)
                ),
            )
        ]
    if len(raw_tile_layers) > MAX_SCENE_TILE_LAYERS:
        raise ValueError(
            f"Scene has {len(raw_tile_layers)} tile layers in {path.name}; "
            f"maximum is {MAX_SCENE_TILE_LAYERS}"
        )

    tile_layers: list[SceneTileLayer] = []
    for i, raw in enumerate(raw_tile_layers):
        tileset = _normalize_asset_path(str(raw.get("tileset", legacy_tileset)))
        probe = SceneTileLayer("", [], tileset=tileset)
        tile_size = tile_size_for_tile_layer(probe, project_root)
        tile_layers.append(
            _normalize_tile_layer(
                raw,
                i,
                tile_size,
                width,
                height,
                path,
                default_tileset=legacy_tileset,
            )
        )
    return tile_layers


def _normalize_collision_tile_layer(
    collision_tile_layer: int, tile_layer_count: int, path: Path
) -> int:
    if not (0 <= collision_tile_layer < tile_layer_count):
        raise ValueError(
            f"collision_tile_layer {collision_tile_layer} out of range for "
            f"{tile_layer_count} tile layer(s) in {path.name}"
        )
    return collision_tile_layer


def _normalize_parallax_band(raw: dict) -> SceneBgParallaxBand:
    y0 = int(raw.get("y0", raw.get("y_start", 0)))
    y1 = int(raw.get("y1", raw.get("y_end", y0)))
    if y1 < y0:
        y0, y1 = y1, y0
    return SceneBgParallaxBand(
        y0,
        y1,
        float(raw.get("parallax_x", 0.5)),
        bool(raw.get("fixed", False)),
        bool(raw.get("repeat_x", False)),
        bool(raw.get("repeat_y", False)),
    )


def _normalize_parallax_bands(raw_bands: list[dict]) -> list[SceneBgParallaxBand]:
    if len(raw_bands) > MAX_PARALLAX_BANDS:
        raise ValueError(f"Scene bg layer has {len(raw_bands)} parallax bands; maximum is {MAX_PARALLAX_BANDS}")
    return [_normalize_parallax_band(raw) for raw in raw_bands]


def _normalize_scene_bg_layer(raw: dict, scene_bg_layer_index: int) -> SceneBgLayer:
    name = str(raw.get("name", DEFAULT_SCENE_BG_LAYER_NAMES[scene_bg_layer_index]))
    background = _normalize_asset_path(str(raw.get("background", "")))
    visible = bool(raw.get("visible", True))
    parallax_x = float(raw.get("parallax_x", 0.5))
    parallax_y = float(raw.get("parallax_y", 0.0))
    fixed = bool(raw.get("fixed", False))
    legacy_repeat = bool(raw.get("repeat", False))
    repeat_x = bool(raw.get("repeat_x", legacy_repeat))
    repeat_y = bool(raw.get("repeat_y", legacy_repeat))
    band_parallax = bool(raw.get("band_parallax", False))
    parallax_bands = _normalize_parallax_bands(raw.get("parallax_bands", []))
    return SceneBgLayer(
        name,
        background,
        visible,
        parallax_x,
        parallax_y,
        fixed,
        repeat_x,
        repeat_y,
        band_parallax,
        parallax_bands,
    )


def _normalize_scene_bg_layers(raw_scene_bg_layers: list[dict]) -> list[SceneBgLayer]:
    if len(raw_scene_bg_layers) > MAX_SCENE_BG_LAYERS:
        raise ValueError(
            f"Scene has {len(raw_scene_bg_layers)} background layers; "
            f"maximum is {MAX_SCENE_BG_LAYERS}"
        )
    return [
        _normalize_scene_bg_layer(raw, i) for i, raw in enumerate(raw_scene_bg_layers)
    ]


def _normalize_scene_object(raw: dict, path: Path) -> SceneObject:
    prefab = _normalize_asset_path(str(raw.get("object", raw.get("prefab", ""))))
    if not prefab:
        raise ValueError(f"Scene object missing prefab path in {path.name}")
    animation = str(raw.get("animation", "")).strip()
    return SceneObject(prefab, int(raw.get("x", 0)), int(raw.get("y", 0)), animation)


def _normalize_scene_objects(raw_objects: list[dict], path: Path) -> list[SceneObject]:
    if len(raw_objects) > MAX_SCENE_OBJECTS:
        raise ValueError(
            f"Scene has {len(raw_objects)} objects in {path.name}; "
            f"maximum is {MAX_SCENE_OBJECTS}"
        )
    return [_normalize_scene_object(raw, path) for raw in raw_objects]


def _read_scene_size(data: dict, path: Path, tile_size: int) -> tuple[int, int]:
    if "width" in data and "height" in data:
        width = int(data["width"])
        height = int(data["height"])
    elif "width_tiles" in data and "height_tiles" in data:
        legacy_tile_size = int(data.get("tile_size", tile_size))
        width = int(data["width_tiles"]) * legacy_tile_size
        height = int(data["height_tiles"]) * legacy_tile_size
    else:
        raise ValueError(f"Scene size missing in {path.name}")
    if width < 1 or height < 1:
        raise ValueError(f"Scene size must be at least 1×1 in {path.name}")
    return width, height


def load_scene(path: Path, *, project_root: Path | None = None) -> Scene:
    data = json.loads(path.read_text(encoding="utf-8"))
    palette = str(data["palette"])
    legacy_tileset = _normalize_asset_path(str(data.get("tileset", "")))
    width, height = _read_scene_size(data, path, TILE_BLOCK)

    raw_tile_layers = data.get("tile_layers", data.get("layers", []))
    tile_layers = _normalize_tile_layers(
        raw_tile_layers,
        width,
        height,
        path,
        project_root,
        legacy_tileset=legacy_tileset,
    )
    collision_tile_layer = _normalize_collision_tile_layer(
        int(data.get("collision_tile_layer", data.get("collision_layer", 0))),
        len(tile_layers),
        path,
    )
    scene_bg_layers = _normalize_scene_bg_layers(data.get("bg_layers", []))
    objects = _normalize_scene_objects(data.get("objects", []), path)

    script = _normalize_asset_path(str(data.get("script", "")))
    camera_script = _normalize_asset_path(str(data.get("camera_script", "")))
    camera_target = _normalize_asset_path(str(data.get("camera_target", "")))
    scene = Scene(
        palette, width, height, tile_layers, scene_bg_layers, objects,
        collision_tile_layer, script, camera_script, camera_target,
    )
    scene.ensure_all_tile_layer_grids(project_root)
    return scene


def save_scene(scene: Scene, path: Path, *, project_root: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scene._validate_tile_layer_count()
    scene._validate_scene_bg_layer_count()
    scene.ensure_all_tile_layer_grids(project_root)
    scene.set_collision_tile_layer(scene.collision_tile_layer)
    data = {
        "palette": scene.palette,
        "width": scene.width,
        "height": scene.height,
        "collision_tile_layer": scene.collision_tile_layer,
        **({"script": _normalize_asset_path(scene.script)} if scene.script.strip() else {}),
        **({"camera_script": _normalize_asset_path(scene.camera_script)} if scene.camera_script.strip() else {}),
        **({"camera_target": _normalize_asset_path(scene.camera_target)} if scene.camera_target.strip() else {}),
        "bg_layers": [
            {
                "name": scene_bg_layer.name,
                "visible": scene_bg_layer.visible,
                "parallax_x": scene_bg_layer.parallax_x,
                "parallax_y": scene_bg_layer.parallax_y,
                **({"fixed": True} if scene_bg_layer.fixed else {}),
                **({"repeat_x": True} if scene_bg_layer.repeat_x else {}),
                **({"repeat_y": True} if scene_bg_layer.repeat_y else {}),
                **({"band_parallax": True} if scene_bg_layer.band_parallax else {}),
                **(
                    {
                        "parallax_bands": [
                            {
                                "y0": band.y0,
                                "y1": band.y1,
                                "parallax_x": band.parallax_x,
                                **({"fixed": True} if band.fixed else {}),
                                **({"repeat_x": True} if band.repeat_x else {}),
                                **({"repeat_y": True} if band.repeat_y else {}),
                            }
                            for band in scene_bg_layer.parallax_bands
                        ]
                    }
                    if scene_bg_layer.band_parallax and scene_bg_layer.parallax_bands
                    else {}
                ),
                **(
                    {"background": _normalize_asset_path(scene_bg_layer.background)}
                    if scene_bg_layer.background
                    else {}
                ),
            }
            for scene_bg_layer in scene.scene_bg_layers
        ],
        "tile_layers": [
            {
                "name": tile_layer.name,
                "visible": tile_layer.visible,
                **(
                    {"tileset": _normalize_asset_path(tile_layer.tileset)}
                    if tile_layer.tileset
                    else {}
                ),
                "tiles": tile_layer.tiles,
            }
            for tile_layer in scene.tile_layers
        ],
        "objects": [
            {
                "object": _normalize_asset_path(inst.prefab),
                "x": inst.x,
                "y": inst.y,
                **({"animation": inst.animation} if inst.animation else {}),
            }
            for inst in scene.objects
        ],
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
