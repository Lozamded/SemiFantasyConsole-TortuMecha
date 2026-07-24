"""Script for robot — reveals its linked dialogue icon when the player is
close, and starts its dialogue (the "dialogue" custom var, a dialogues/*.json
path) on the action button while in range — the same button prompted by the
visible dialogue icon.

SELF_ID and LINKS are injected by the instance-script runtime (see
tortuengine/instance_scripts.py): SELF_ID is this placed robot's own scene
id, LINKS is the tuple of ids it references — here, its paired dialogue
icon set up in the scene editor's object link list.
"""

import pygame

from tortuengine import instance_api
from scripts._generated import robot_auto as auto

PROXIMITY_RANGE = 45.0

_prev_action = False


def init(engine):
    for link_id in LINKS:
        instance_api.set_visible(link_id, False)


def update(dt):
    global _prev_action

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
