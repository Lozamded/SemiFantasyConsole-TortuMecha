"""Script for robot — reveals its linked dialogue icon when the player is
close, and starts its dialogue (the "dialogue" custom var, a dialogues/*.json
path) on the action button while in range — the same button prompted by the
visible dialogue icon.

Also plays a small cosmetic hop when instance_api.request_object_hop(SELF_ID)
is asked for (see dialogue_vars.action_Do_DR2Action, called from robot2's
dialogue as an `end_action` when the player picks the "jump" option) — a
fixed-duration parabolic arc, not physics, since this NPC never otherwise
moves.

SELF_ID and LINKS are injected by the instance-script runtime (see
tortuengine/instance_scripts.py): SELF_ID is this placed robot's own scene
id, LINKS is the tuple of ids it references — here, its paired dialogue
icon set up in the scene editor's object link list.
"""

import pygame

from tortuengine import instance_api
from scripts._generated import robot_auto as auto

PROXIMITY_RANGE = 45.0

HOP_DURATION = 0.5  # seconds, full up-and-down arc
HOP_HEIGHT = 12.0  # px risen at the arc's peak

_prev_action = False
_hopping = False
_hop_timer = 0.0
_hop_x = 0.0
_hop_base_y = 0.0


def init(engine):
    for link_id in LINKS:
        instance_api.set_visible(link_id, False)


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
    for link_id in LINKS:
        instance_api.set_visible(link_id, near)

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
