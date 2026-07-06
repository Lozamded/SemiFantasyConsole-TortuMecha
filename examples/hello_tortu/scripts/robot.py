"""Script for robot — reveals its linked dialogue icon when the player is close.

SELF_ID and LINKS are injected by the instance-script runtime (see
tortuengine/instance_scripts.py): SELF_ID is this placed robot's own scene
id, LINKS is the tuple of ids it references — here, its paired dialogue
icon set up in the scene editor's object link list.
"""

from tortuengine import instance_api

PROXIMITY_RANGE = 40.0


def init(engine):
    for link_id in LINKS:
        instance_api.set_visible(link_id, False)


def update(dt):
    position = instance_api.get_position(SELF_ID)
    if position is None:
        return
    rx, ry = position
    px, py = instance_api.player_position()
    near = ((px - rx) ** 2 + (py - ry) ** 2) ** 0.5 <= PROXIMITY_RANGE
    for link_id in LINKS:
        instance_api.set_visible(link_id, near)


def draw(engine):
    pass
