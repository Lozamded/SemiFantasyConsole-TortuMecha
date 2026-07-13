"""Runtime query API shared by per-instance object scripts.

Object scripts (see instance_scripts.py) never touch the Scene or the
player controller directly — they go through these functions instead, so
the same script keeps working whether it runs in TortuStudio's preview,
TortuPlayer, or an exported cart.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from tortuengine.scene import Scene
from tortuengine.tileset import COLLISION_NONE, Tileset, load_tileset

if TYPE_CHECKING:
    from tortuengine.gui_layer import GuiLayer

_scene: Scene | None = None
_project_root: Path | None = None
_player_x: float = 0.0
_player_y: float = 0.0
_player_crouching: bool = False
# World-space (left, right, top, bottom) of the player's current active
# hitbox — crouch-aware, since it swaps between stand/crouch bounds.
_player_hitbox: tuple[float, float, float, float] | None = None
_tileset_cache: dict[str, Tileset] = {}
# Renderer-owned GuiLayer loader (rel_path -> live, cached GuiLayer), so
# scripts can drive HUD elements (health bars, pip counters) without
# instance_api duplicating gui-layer loading/caching itself.
_gui_layer_loader: Callable[[str], "GuiLayer | None"] | None = None


def bind_scene(scene: Scene, project_root: Path | None = None) -> None:
    """Call once when a scene is loaded, before any instance script runs."""
    global _scene, _project_root
    _scene = scene
    if project_root is not None:
        _project_root = project_root


def set_player_position(x: float, y: float) -> None:
    """Call every frame from the player controller script."""
    global _player_x, _player_y
    _player_x, _player_y = x, y


def player_position() -> tuple[float, float]:
    return _player_x, _player_y


def set_player_crouching(crouching: bool) -> None:
    """Call every frame from the player controller script."""
    global _player_crouching
    _player_crouching = crouching


def player_is_crouching() -> bool:
    return _player_crouching


def set_player_hitbox(left: float, right: float, top: float, bottom: float) -> None:
    """Call every frame from the player controller script with its current active hitbox."""
    global _player_hitbox
    _player_hitbox = (left, right, top, bottom)


def player_hitbox() -> tuple[float, float, float, float] | None:
    return _player_hitbox


def bind_gui_layers(loader: Callable[[str], "GuiLayer | None"]) -> None:
    """Call once per scene load with a callable(rel_path) -> GuiLayer | None."""
    global _gui_layer_loader
    _gui_layer_loader = loader


def _find_gui_element(gui_layer_path: str, element_id: str, attr: str):
    if _gui_layer_loader is None or not gui_layer_path or not element_id:
        return None
    layer = _gui_layer_loader(gui_layer_path)
    if layer is None:
        return None
    for element in getattr(layer, attr):
        if element.id == element_id:
            return element
    return None


def set_gui_tiled_rect_value(gui_layer_path: str, rect_id: str, value: float) -> None:
    """Set a `.tortuguilayer` tiled rect's fill fraction (0..1) — e.g. a health bar."""
    rect = _find_gui_element(gui_layer_path, rect_id, "tiled_rects")
    if rect is not None:
        rect.value = max(0.0, min(1.0, value))


def gui_tiled_rect_value(gui_layer_path: str, rect_id: str) -> float | None:
    rect = _find_gui_element(gui_layer_path, rect_id, "tiled_rects")
    return rect.value if rect is not None else None


def set_gui_repeat_sprite_count(gui_layer_path: str, sprite_id: str, count: int) -> None:
    """Set a `.tortuguilayer` repeat sprite's filled count — e.g. remaining life pips."""
    rep = _find_gui_element(gui_layer_path, sprite_id, "repeat_sprites")
    if rep is not None:
        rep.count = max(0, count)


def gui_repeat_sprite_count(gui_layer_path: str, sprite_id: str) -> int | None:
    rep = _find_gui_element(gui_layer_path, sprite_id, "repeat_sprites")
    return rep.count if rep is not None else None


def _find(instance_id: str):
    if not _scene or not instance_id:
        return None
    for inst in _scene.objects:
        if inst.id == instance_id:
            return inst
    return None


def get_position(instance_id: str) -> tuple[float, float] | None:
    inst = _find(instance_id)
    return (inst.x, inst.y) if inst else None


def set_position(instance_id: str, x: float, y: float) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.x, inst.y = x, y


def set_animation(instance_id: str, animation: str) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.animation = animation


def prefab_positions(prefab: str, exclude_id: str = "") -> list[tuple[float, float]]:
    """World positions of every enabled scene object instancing the given prefab path.

    Pass `exclude_id` (typically SELF_ID) to leave out one instance — e.g. so a script
    can find *other* instances of its own prefab without matching itself.
    """
    if not _scene:
        return []
    return [
        (inst.x, inst.y) for inst in _scene.objects
        if inst.prefab == prefab and inst.enabled and (not exclude_id or inst.id != exclude_id)
    ]


def is_visible(instance_id: str) -> bool:
    inst = _find(instance_id)
    return inst.visible if inst else False


def set_visible(instance_id: str, visible: bool) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.visible = visible


def is_enabled(instance_id: str) -> bool:
    """False means the instance is off — skip it in collision checks too, not just rendering."""
    inst = _find(instance_id)
    return inst.enabled if inst else False


def set_enabled(instance_id: str, enabled: bool) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.enabled = enabled


def _active_collision_tileset() -> Tileset | None:
    if _scene is None or _project_root is None:
        return None
    layer = _scene.tile_layers[_scene.collision_tile_layer]
    if not layer.tileset:
        return None
    cached = _tileset_cache.get(layer.tileset)
    if cached is not None:
        return cached
    path = (_project_root / layer.tileset).resolve()
    if not path.is_file():
        return None
    tileset = load_tileset(path)
    _tileset_cache[layer.tileset] = tileset
    return tileset


def tile_solid_at(x: float, y: float) -> bool:
    """True if the world pixel (x, y) lands on a solid tile in the scene's active collision layer."""
    if _scene is None:
        return False
    tileset = _active_collision_tileset()
    if tileset is None:
        return False
    layer = _scene.tile_layers[_scene.collision_tile_layer]
    tile_size = tileset.tile_size
    cols = _scene.width // tile_size
    col, row = int(x // tile_size), int(y // tile_size)
    if col < 0 or col >= cols or row < 0:
        return False
    idx = row * cols + col
    if idx >= len(layer.tiles):
        return False
    tile_index = layer.tiles[idx]
    if tile_index < 0:
        return False
    return tileset.get_collision(tile_index) != COLLISION_NONE
