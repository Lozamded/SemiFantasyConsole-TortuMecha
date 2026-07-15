"""Script for red_slime — patrols left/right, falls under gravity, and
reverses direction whenever it touches an enemycollider trigger object.
"""

from __future__ import annotations

from pathlib import Path

from tortuengine import instance_api
from tortuengine.object import TortuObject, load_object
from tortuengine.sprite import load_sprite
from scripts._generated import red_slime_auto as auto
from scripts.mechaturtle_player import ATTACK_COLLIDER_ID

ROOT = Path(__file__).parent.parent
SLIME_PREFAB = "assets/objects/red_slime.tortuobject"
ENEMYCOLLIDER_PREFAB = "assets/objects/enemycollider.tortuobject"
ATTACK_COLLIDER_PREFAB = "assets/objects/collider_mechaturtle_attack.tortuobject"

GRAVITY = 400.0
MAX_FALL_SPEED = 400.0
PATROL_SPEED = 30.0

# Hitbox / trigger bounds, offsets from each object's origin — resolved in
# init() from the prefabs' own colliders, not hand-copied numbers.
_hb_l = _hb_r = _hb_t = _hb_b = 0
_trig_l = _trig_r = _trig_t = _trig_b = 0
_atk_l = _atk_r = _atk_t = _atk_b = 0

_px = 0.0
_py = 0.0
_vy = 0.0
_direction = -1  # -1 = left, 1 = right

_dead = False
_defeat_timer = 0.0
_defeat_duration = 0.0  # seconds — resolved in init() from the defeat sprite's own frame_count/fps


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
    global _atk_l, _atk_r, _atk_t, _atk_b
    global _px, _py, _vy, _direction
    global _dead, _defeat_timer, _defeat_duration

    slime_obj = load_object(ROOT / SLIME_PREFAB)
    slime_sprite = load_sprite(ROOT / slime_obj.default_sprite)
    _hb_l, _hb_r, _hb_t, _hb_b = _resolve_bounds(
        slime_obj, slime_sprite.pixel_width, slime_sprite.pixel_height
    )

    defeat_sprite = load_sprite(ROOT / slime_obj.sprite_for(auto.ANIM_DEFEAT))
    _defeat_duration = defeat_sprite.frame_count / max(1, defeat_sprite.fps)
    _dead = False
    _defeat_timer = 0.0

    trig_obj = load_object(ROOT / ENEMYCOLLIDER_PREFAB)
    trig_sprite = load_sprite(ROOT / trig_obj.default_sprite)
    _trig_l, _trig_r, _trig_t, _trig_b = _resolve_bounds(
        trig_obj, trig_sprite.pixel_width, trig_sprite.pixel_height
    )

    atk_obj = load_object(ROOT / ATTACK_COLLIDER_PREFAB)
    atk_sprite = load_sprite(ROOT / atk_obj.default_sprite)
    _atk_l, _atk_r, _atk_t, _atk_b = _resolve_bounds(
        atk_obj, atk_sprite.pixel_width, atk_sprite.pixel_height
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


def _walk(distance: float) -> bool:
    """Move horizontally by distance, stopping at the first solid tile. Returns True if blocked."""
    global _px
    step_dir = 1 if distance >= 0 else -1
    remaining = abs(distance)
    while remaining > 0:
        step = min(1.0, remaining)
        x = _px + step_dir * step + (_hb_r - 1 if step_dir > 0 else _hb_l)
        if instance_api.tile_solid_at(x, _py + _hb_t) or instance_api.tile_solid_at(x, _py + _hb_b - 1):
            return True
        _px += step_dir * step
        remaining -= step
    return False


def _overlaps(l1: float, r1: float, t1: float, b1: float, l2: float, r2: float, t2: float, b2: float) -> bool:
    return l1 < r2 and r1 > l2 and t1 < b2 and b1 > t2


def update(dt: float) -> None:
    global _px, _py, _vy, _direction, _dead, _defeat_timer

    if _dead:
        _defeat_timer -= dt
        if _defeat_timer <= 0:
            instance_api.set_enabled(SELF_ID, False)
            instance_api.set_visible(SELF_ID, False)
        return

    _vy = min(_vy + GRAVITY * dt, MAX_FALL_SPEED)
    if _fall(_vy * dt):
        _vy = 0.0

    if _walk(_direction * PATROL_SPEED * dt):
        _direction *= -1

    left, right = _px + _hb_l, _px + _hb_r
    top, bottom = _py + _hb_t, _py + _hb_b

    for tx, ty in instance_api.prefab_positions(ENEMYCOLLIDER_PREFAB):
        trig_left, trig_right = tx + _trig_l, tx + _trig_r
        trig_top, trig_bottom = ty + _trig_t, ty + _trig_b
        if _overlaps(left, right, top, bottom, trig_left, trig_right, trig_top, trig_bottom):
            _direction *= -1
            break

    if instance_api.player_is_crouching():
        p_hb = instance_api.player_hitbox()
        if p_hb is not None:
            p_left, p_right, p_top, p_bottom = p_hb
            if _overlaps(left, right, top, bottom, p_left, p_right, p_top, p_bottom):
                _direction *= -1

    for ox, oy in instance_api.prefab_positions(SLIME_PREFAB, exclude_id=SELF_ID):
        other_left, other_right = ox + _hb_l, ox + _hb_r
        other_top, other_bottom = oy + _hb_t, oy + _hb_b
        if _overlaps(left, right, top, bottom, other_left, other_right, other_top, other_bottom):
            _direction *= -1
            break

    if instance_api.is_enabled(ATTACK_COLLIDER_ID):
        atk_pos = instance_api.get_position(ATTACK_COLLIDER_ID)
        if atk_pos:
            ax, ay = atk_pos
            atk_left, atk_right = ax + _atk_l, ax + _atk_r
            atk_top, atk_bottom = ay + _atk_t, ay + _atk_b
            if _overlaps(left, right, top, bottom, atk_left, atk_right, atk_top, atk_bottom):
                _dead = True
                _defeat_timer = _defeat_duration
                instance_api.set_animation(SELF_ID, auto.ANIM_DEFEAT)
                instance_api.set_position(SELF_ID, _px, _py)
                return

    instance_api.set_position(SELF_ID, _px, _py)


def draw(engine) -> None:
    pass
