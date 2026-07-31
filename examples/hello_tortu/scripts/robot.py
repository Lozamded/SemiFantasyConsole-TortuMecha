"""Script for robot — reveals its linked dialogue icon when the player is
close, and starts its dialogue (the "dialogue" custom var, a dialogues/*.json
path) on the action button while in range — the same button prompted by the
visible dialogue icon. While visible, the icon is repositioned to track the
robot using the offset it was originally placed at relative to the robot in
the scene editor (icon_pos - robot_pos at init), so it still hovers over the
robot's head even if the robot has since walked away from its spawn point.

Also plays a small cosmetic hop when instance_api.request_object_hop(SELF_ID)
is asked for (see dialogue_vars.action_Do_DR2Action, called from robot2's
dialogue as an `end_action` when the player picks the "jump" option) — a
fixed-duration parabolic arc, not physics, since this NPC never otherwise
moves.

If the "patrol" custom var is set (robot3 in level_02, not the other,
stationary robot placements), the robot instead walks back and forth,
reversing direction on any solid tile or enemycollider trigger it touches —
the same enemycollider-based turn used by red_slime, reused here even though
this instance isn't an enemy, just because it's the project's existing
"reverse at this trigger" convention. The sprite is mirrored (instance_api
.set_flip_x) to face the way it's currently walking; the robot's default art
faces right, so flip_x is set whenever _direction is -1 (left). No gravity:
this NPC is only ever placed standing on solid ground.

A patrolling robot also stops and switches to its idle animation whenever
the player is in proximity range (the same range that reveals the dialogue
icon), so it isn't still walking mid-conversation.

SELF_ID and LINKS are injected by the instance-script runtime (see
tortuengine/instance_scripts.py): SELF_ID is this placed robot's own scene
id, LINKS is the tuple of ids it references — here, its paired dialogue
icon set up in the scene editor's object link list.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from tortuengine import instance_api
from tortuengine.object import TortuObject, load_object
from tortuengine.sprite import load_sprite
from scripts._generated import robot_auto as auto

ROOT = Path(__file__).parent.parent
ROBOT_PREFAB = "assets/objects/robot.tortuobject"
ENEMYCOLLIDER_PREFAB = "assets/objects/enemycollider.tortuobject"

PROXIMITY_RANGE = 45.0

HOP_DURATION = 0.5  # seconds, full up-and-down arc
HOP_HEIGHT = 12.0  # px risen at the arc's peak

PATROL_SPEED = 20.0

_prev_action = False
_hopping = False
_hop_timer = 0.0
_hop_x = 0.0
_hop_base_y = 0.0

_patrol = False
_px = 0.0
_py = 0.0
_direction = 1  # -1 = left, 1 = right

# link_id -> (icon_x - robot_x, icon_y - robot_y) at init, so a followed icon
# keeps whatever offset it was placed at in the scene editor.
_link_offsets: dict[str, tuple[float, float]] = {}

# Hitbox / trigger bounds, offsets from each object's origin — resolved in
# init() from the prefabs' own colliders, not hand-copied numbers. Only
# resolved when patrol is on, since stationary robots never need them.
_hb_l = _hb_r = _hb_t = _hb_b = 0
_trig_l = _trig_r = _trig_t = _trig_b = 0


def _resolve_bounds(obj: TortuObject, sprite_w: int, sprite_h: int) -> tuple[int, int, int, int]:
    res = [c.resolved(sprite_w, sprite_h) for c in obj.colliders]
    ox, oy = obj.origin.x, obj.origin.y
    return (
        min(x for x, y, w, h in res) - ox,
        max(x + w for x, y, w, h in res) - ox,
        min(y for x, y, w, h in res) - oy,
        max(y + h for x, y, w, h in res) - oy,
    )


def init(engine):
    global _patrol, _px, _py, _direction
    global _hb_l, _hb_r, _hb_t, _hb_b
    global _trig_l, _trig_r, _trig_t, _trig_b
    global _link_offsets

    for link_id in LINKS:
        instance_api.set_visible(link_id, False)

    _link_offsets = {}
    robot_pos = instance_api.get_position(SELF_ID)
    if robot_pos is not None:
        rx0, ry0 = robot_pos
        for link_id in LINKS:
            link_pos = instance_api.get_position(link_id)
            if link_pos is not None:
                _link_offsets[link_id] = (link_pos[0] - rx0, link_pos[1] - ry0)

    _patrol = bool(instance_api.custom_var(SELF_ID, auto.CUSTOMVAR_PATROL, auto.CUSTOMVAR_PATROL_DEFAULT))
    if not _patrol:
        return

    robot_obj = load_object(ROOT / ROBOT_PREFAB)
    robot_sprite = load_sprite(ROOT / robot_obj.default_sprite)
    _hb_l, _hb_r, _hb_t, _hb_b = _resolve_bounds(
        robot_obj, robot_sprite.pixel_width, robot_sprite.pixel_height
    )

    trig_obj = load_object(ROOT / ENEMYCOLLIDER_PREFAB)
    trig_sprite = load_sprite(ROOT / trig_obj.default_sprite)
    _trig_l, _trig_r, _trig_t, _trig_b = _resolve_bounds(
        trig_obj, trig_sprite.pixel_width, trig_sprite.pixel_height
    )

    pos = instance_api.get_position(SELF_ID)
    _px, _py = pos if pos else (0.0, 0.0)
    _direction = 1


def _start_hop() -> None:
    global _hopping, _hop_timer, _hop_x, _hop_base_y
    position = instance_api.get_position(SELF_ID)
    if position is None:
        return
    _hopping = True
    _hop_timer = 0.0
    _hop_x, _hop_base_y = position
    instance_api.set_animation(SELF_ID, auto.ANIM_JUMP)


def _update_hop(dt: float) -> None:
    global _hopping, _hop_timer
    _hop_timer += dt
    t = min(_hop_timer / HOP_DURATION, 1.0)
    # Parabolic arc: 0 at t=0 and t=1, HOP_HEIGHT at t=0.5.
    offset = HOP_HEIGHT * 4.0 * t * (1.0 - t)
    instance_api.set_position(SELF_ID, _hop_x, _hop_base_y - offset)
    if t >= 1.0:
        _hopping = False
        instance_api.set_animation(SELF_ID, auto.ANIM_IDLE)
    else:
        instance_api.set_animation(SELF_ID, auto.ANIM_FALL if t >= 0.5 else auto.ANIM_JUMP)


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


def _update_patrol(dt: float) -> None:
    global _direction

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

    instance_api.set_position(SELF_ID, _px, _py)
    instance_api.set_animation(SELF_ID, auto.ANIM_WALK)
    instance_api.set_flip_x(SELF_ID, _direction < 0)


def update(dt):
    global _prev_action

    if not _hopping and instance_api.take_object_hop_request(SELF_ID):
        _start_hop()
    if _hopping:
        _update_hop(dt)

    position = instance_api.get_position(SELF_ID)
    if position is None:
        return
    rx, ry = position
    px, py = instance_api.player_position()
    near = ((px - rx) ** 2 + (py - ry) ** 2) ** 0.5 <= PROXIMITY_RANGE

    if _patrol and not _hopping:
        if near:
            instance_api.set_animation(SELF_ID, auto.ANIM_IDLE)
        else:
            _update_patrol(dt)

    for link_id in LINKS:
        instance_api.set_visible(link_id, near)
        if near:
            ox, oy = _link_offsets.get(link_id, (0.0, 0.0))
            instance_api.set_position(link_id, rx + ox, ry + oy)

    keys = pygame.key.get_pressed()
    action_held = keys[pygame.K_x] or keys[pygame.K_LSHIFT] or keys[pygame.K_c]
    action_pressed = action_held and not _prev_action
    _prev_action = action_held

    if (
        near and action_pressed
        and not instance_api.is_game_paused()
        and not instance_api.is_dialogue_active()
    ):
        path = instance_api.custom_var(
            SELF_ID, auto.CUSTOMVAR_DIALOGUE, auto.CUSTOMVAR_DIALOGUE_DEFAULT
        )
        if path:
            instance_api.request_dialogue(path)


def draw(engine):
    pass
