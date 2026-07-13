"""Runtime query API shared by per-instance object scripts.

Object scripts (see instance_scripts.py) never touch the Scene or the
player controller directly — they go through these functions instead, so
the same script keeps working whether it runs in TortuStudio's preview,
TortuPlayer, or an exported cart.
"""

from __future__ import annotations

from pathlib import Path

from tortuengine.scene import Scene
from tortuengine.tileset import COLLISION_NONE, Tileset, load_tileset

_scene: Scene | None = None
_project_root: Path | None = None
_player_x: float = 0.0
_player_y: float = 0.0
_player_crouching: bool = False
# World-space (left, right, top, bottom) of the player's current active
# hitbox — crouch-aware, since it swaps between stand/crouch bounds.
_player_hitbox: tuple[float, float, float, float] | None = None
_tileset_cache: dict[str, Tileset] = {}


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
