"""Runtime query API shared by per-instance object scripts.

Object scripts (see instance_scripts.py) never touch the Scene or the
player controller directly — they go through these functions instead, so
the same script keeps working whether it runs in TortuStudio's preview,
TortuPlayer, or an exported cart.
"""

from __future__ import annotations

from tortuengine.scene import Scene

_scene: Scene | None = None
_player_x: float = 0.0
_player_y: float = 0.0


def bind_scene(scene: Scene) -> None:
    """Call once when a scene is loaded, before any instance script runs."""
    global _scene
    _scene = scene


def set_player_position(x: float, y: float) -> None:
    """Call every frame from the player controller script."""
    global _player_x, _player_y
    _player_x, _player_y = x, y


def player_position() -> tuple[float, float]:
    return _player_x, _player_y


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


def is_visible(instance_id: str) -> bool:
    inst = _find(instance_id)
    return inst.visible if inst else False


def set_visible(instance_id: str, visible: bool) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.visible = visible
