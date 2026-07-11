"""Script for red_slime — patrols left/right, falls under gravity, and
reverses direction whenever it touches an enemycollider trigger object.
"""

from __future__ import annotations

from pathlib import Path

from tortuengine import instance_api
from tortuengine.object import TortuObject, load_object
from tortuengine.sprite import load_sprite
from scripts._generated import red_slime_auto as auto

ROOT = Path(__file__).parent.parent
ENEMYCOLLIDER_PREFAB = "assets/objects/enemycollider.tortuobject"

GRAVITY = 400.0
MAX_FALL_SPEED = 400.0
PATROL_SPEED = 30.0

# Hitbox / trigger bounds, offsets from each object's origin — resolved in
# init() from the prefabs' own colliders, not hand-copied numbers.
_hb_l = _hb_r = _hb_t = _hb_b = 0
_trig_l = _trig_r = _trig_t = _trig_b = 0

_px = 0.0
_py = 0.0
_vy = 0.0
_direction = -1  # -1 = left, 1 = right


def _resolve_bounds(obj: TortuObject, sprite_w: int, sprite_h: int) -> tuple[int, int, int, int]:
    res = [c.resolved(sprite_w, sprite_h) for c in obj.colliders]
    ox, oy = obj.origin.x, obj.origin.y
    return (
        min(x for x, y, w, h in res) - ox,
        max(x + w for x, y, w, h in res) - ox,
        min(y for x, y, w, h in res) - oy,
        max(y + h for x, y, w, h in res) - oy,
    )


def init(engine) -> None:
    global _hb_l, _hb_r, _hb_t, _hb_b
    global _trig_l, _trig_r, _trig_t, _trig_b
    global _px, _py, _vy, _direction

    slime_obj = load_object(ROOT / "assets/objects/red_slime.tortuobject")
    slime_sprite = load_sprite(ROOT / slime_obj.default_sprite)
    _hb_l, _hb_r, _hb_t, _hb_b = _resolve_bounds(
        slime_obj, slime_sprite.pixel_width, slime_sprite.pixel_height
    )

    trig_obj = load_object(ROOT / ENEMYCOLLIDER_PREFAB)
    trig_sprite = load_sprite(ROOT / trig_obj.default_sprite)
    _trig_l, _trig_r, _trig_t, _trig_b = _resolve_bounds(
        trig_obj, trig_sprite.pixel_width, trig_sprite.pixel_height
    )

    pos = instance_api.get_position(SELF_ID)
    _px, _py = pos if pos else (0.0, 0.0)
    _vy = 0.0
    _direction = -1


def _fall(distance: float) -> bool:
    """Move down by distance, stopping at the first solid tile below. Returns True if grounded."""
    global _py
    remaining = max(0.0, distance)
    while remaining > 0:
        step = min(1.0, remaining)
        y = _py + step + _hb_b
        if instance_api.tile_solid_at(_px + _hb_l, y) or instance_api.tile_solid_at(_px + _hb_r - 1, y):
            return True
        _py += step
        remaining -= step
    return False


def update(dt: float) -> None:
    global _px, _py, _vy, _direction

    _vy = min(_vy + GRAVITY * dt, MAX_FALL_SPEED)
    if _fall(_vy * dt):
        _vy = 0.0

    _px += _direction * PATROL_SPEED * dt

    left, right = _px + _hb_l, _px + _hb_r
    top, bottom = _py + _hb_t, _py + _hb_b
    for tx, ty in instance_api.prefab_positions(ENEMYCOLLIDER_PREFAB):
        trig_left, trig_right = tx + _trig_l, tx + _trig_r
        trig_top, trig_bottom = ty + _trig_t, ty + _trig_b
        if left < trig_right and right > trig_left and top < trig_bottom and bottom > trig_top:
            _direction *= -1
            break

    instance_api.set_position(SELF_ID, _px, _py)


def draw(engine) -> None:
    pass
