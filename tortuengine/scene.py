"""Scene assets (.tortuscene) — multi-layer tile maps referencing a tileset."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_BLOCK, TILE_LAYERS

# Empty cell — not a tileset index.
EMPTY_TILE = -1

MIN_SCENE_LAYERS = 1
MAX_SCENE_LAYERS = TILE_LAYERS

DEFAULT_SCENE_WIDTH_TILES = SCREEN_WIDTH // TILE_BLOCK
DEFAULT_SCENE_HEIGHT_TILES = (SCREEN_HEIGHT + TILE_BLOCK - 1) // TILE_BLOCK

DEFAULT_LAYER_NAMES = tuple(f"layer_{i}" for i in range(MAX_SCENE_LAYERS))


def _blank_layer(width_tiles: int, height_tiles: int) -> list[int]:
    return [EMPTY_TILE] * (width_tiles * height_tiles)


@dataclass
class SceneLayer:
    """One tile layer in a scene."""

    name: str
    tiles: list[int]
    visible: bool = True

    def copy(self) -> SceneLayer:
        return SceneLayer(self.name, self.tiles.copy(), self.visible)


@dataclass
class Scene:
    """Tile map with 1–4 layers; one layer drives collision from the tileset."""

    palette: str
    tileset: str
    width_tiles: int
    height_tiles: int
    layers: list[SceneLayer] = field(default_factory=list)
    collision_layer: int = 0

    @property
    def cell_count(self) -> int:
        return self.width_tiles * self.height_tiles

    @property
    def layer_count(self) -> int:
        return len(self.layers)

    @classmethod
    def create(
        cls,
        palette: str,
        tileset: str,
        width_tiles: int = DEFAULT_SCENE_WIDTH_TILES,
        height_tiles: int = DEFAULT_SCENE_HEIGHT_TILES,
        *,
        layer_count: int = MIN_SCENE_LAYERS,
        collision_layer: int = 0,
    ) -> Scene:
        if width_tiles < 1 or height_tiles < 1:
            raise ValueError("Scene must be at least 1×1 tiles")
        if not (MIN_SCENE_LAYERS <= layer_count <= MAX_SCENE_LAYERS):
            raise ValueError(f"Layer count must be {MIN_SCENE_LAYERS}–{MAX_SCENE_LAYERS}")
        layers = [
            SceneLayer(DEFAULT_LAYER_NAMES[i], _blank_layer(width_tiles, height_tiles))
            for i in range(layer_count)
        ]
        scene = cls(
            palette,
            _normalize_asset_path(tileset),
            width_tiles,
            height_tiles,
            layers,
        )
        scene.set_collision_layer(collision_layer)
        return scene

    def _validate_coords(self, x: int, y: int) -> None:
        if not (0 <= x < self.width_tiles and 0 <= y < self.height_tiles):
            raise IndexError(f"Tile coordinate out of range: ({x}, {y})")

    def _validate_layer(self, layer_index: int) -> None:
        if not (0 <= layer_index < len(self.layers)):
            raise IndexError(f"Layer index out of range: {layer_index}")

    def _validate_layer_count(self) -> None:
        count = len(self.layers)
        if not (MIN_SCENE_LAYERS <= count <= MAX_SCENE_LAYERS):
            raise ValueError(f"Scene must have {MIN_SCENE_LAYERS}–{MAX_SCENE_LAYERS} layers")

    def _cell_index(self, x: int, y: int) -> int:
        return y * self.width_tiles + x

    def get_tile(self, layer_index: int, x: int, y: int) -> int:
        self._validate_layer(layer_index)
        self._validate_coords(x, y)
        return self.layers[layer_index].tiles[self._cell_index(x, y)]

    def set_tile(self, layer_index: int, x: int, y: int, tile_index: int) -> None:
        if tile_index < EMPTY_TILE:
            raise ValueError(f"Invalid tile index: {tile_index}")
        self._validate_layer(layer_index)
        self._validate_coords(x, y)
        self.layers[layer_index].tiles[self._cell_index(x, y)] = tile_index

    def set_collision_layer(self, layer_index: int) -> None:
        self._validate_layer(layer_index)
        self.collision_layer = layer_index

    def add_layer(self, *, copy_from: int | None = None) -> int:
        if len(self.layers) >= MAX_SCENE_LAYERS:
            raise ValueError(f"Scene cannot have more than {MAX_SCENE_LAYERS} layers")
        index = len(self.layers)
        if copy_from is not None:
            self._validate_layer(copy_from)
            source = self.layers[copy_from]
            tiles = source.tiles.copy()
            visible = source.visible
            name = f"{source.name}_copy"
        else:
            tiles = _blank_layer(self.width_tiles, self.height_tiles)
            visible = True
            name = DEFAULT_LAYER_NAMES[index]
        self.layers.append(SceneLayer(name, tiles, visible))
        return index

    def remove_layer(self, layer_index: int) -> None:
        if len(self.layers) <= MIN_SCENE_LAYERS:
            raise ValueError(f"Scene must keep at least {MIN_SCENE_LAYERS} layer")
        self._validate_layer(layer_index)
        self.layers.pop(layer_index)
        if self.collision_layer == layer_index:
            self.collision_layer = 0
        elif self.collision_layer > layer_index:
            self.collision_layer -= 1

    def resize(self, width_tiles: int, height_tiles: int) -> None:
        """Resample all layers to a new map size (nearest-neighbour)."""
        if width_tiles < 1 or height_tiles < 1:
            raise ValueError("Scene must be at least 1×1 tiles")
        if width_tiles == self.width_tiles and height_tiles == self.height_tiles:
            return

        old_w, old_h = self.width_tiles, self.height_tiles
        new_layers: list[SceneLayer] = []
        for layer in self.layers:
            out = _blank_layer(width_tiles, height_tiles)
            for ny in range(height_tiles):
                for nx in range(width_tiles):
                    sx = int(nx * old_w / width_tiles)
                    sy = int(ny * old_h / height_tiles)
                    out[ny * width_tiles + nx] = layer.tiles[sy * old_w + sx]
            new_layers.append(SceneLayer(layer.name, out, layer.visible))

        self.width_tiles = width_tiles
        self.height_tiles = height_tiles
        self.layers = new_layers

    def tileset_path(self, project_root: Path) -> Path:
        return (project_root / self.tileset).resolve()


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


def _normalize_layer(
    raw: dict,
    layer_index: int,
    width_tiles: int,
    height_tiles: int,
    path: Path,
) -> SceneLayer:
    expected = width_tiles * height_tiles
    name = str(raw.get("name", DEFAULT_LAYER_NAMES[layer_index]))
    visible = bool(raw.get("visible", True))
    tiles = [int(v) for v in raw["tiles"]]
    if len(tiles) != expected:
        raise ValueError(
            f"Layer {layer_index} tile count mismatch in {path.name}: "
            f"expected {expected}, got {len(tiles)}"
        )
    for value in tiles:
        if value < EMPTY_TILE:
            raise ValueError(f"Invalid tile index {value} in layer {layer_index} of {path.name}")
    return SceneLayer(name, tiles, visible)


def _normalize_layers(
    raw_layers: list[dict],
    width_tiles: int,
    height_tiles: int,
    path: Path,
) -> list[SceneLayer]:
    if not raw_layers:
        return [SceneLayer(DEFAULT_LAYER_NAMES[0], _blank_layer(width_tiles, height_tiles))]
    if len(raw_layers) > MAX_SCENE_LAYERS:
        raise ValueError(
            f"Scene has {len(raw_layers)} layers in {path.name}; "
            f"maximum is {MAX_SCENE_LAYERS}"
        )
    return [
        _normalize_layer(raw, i, width_tiles, height_tiles, path)
        for i, raw in enumerate(raw_layers)
    ]


def _normalize_collision_layer(collision_layer: int, layer_count: int, path: Path) -> int:
    if not (0 <= collision_layer < layer_count):
        raise ValueError(
            f"collision_layer {collision_layer} out of range for "
            f"{layer_count} layer(s) in {path.name}"
        )
    return collision_layer


def load_scene(path: Path) -> Scene:
    data = json.loads(path.read_text(encoding="utf-8"))
    palette = str(data["palette"])
    tileset = _normalize_asset_path(str(data["tileset"]))
    width_tiles = int(data["width_tiles"])
    height_tiles = int(data["height_tiles"])

    if width_tiles < 1 or height_tiles < 1:
        raise ValueError(f"Scene size must be at least 1×1 in {path.name}")

    layers = _normalize_layers(data.get("layers", []), width_tiles, height_tiles, path)
    collision_layer = _normalize_collision_layer(
        int(data.get("collision_layer", 0)),
        len(layers),
        path,
    )

    return Scene(
        palette,
        tileset,
        width_tiles,
        height_tiles,
        layers,
        collision_layer,
    )


def save_scene(scene: Scene, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scene._validate_layer_count()
    scene.set_collision_layer(scene.collision_layer)
    data = {
        "palette": scene.palette,
        "tileset": _normalize_asset_path(scene.tileset),
        "width_tiles": scene.width_tiles,
        "height_tiles": scene.height_tiles,
        "collision_layer": scene.collision_layer,
        "layers": [
            {
                "name": layer.name,
                "visible": layer.visible,
                "tiles": layer.tiles,
            }
            for layer in scene.layers
        ],
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
