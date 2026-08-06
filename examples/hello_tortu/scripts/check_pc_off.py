"""Script for check_pc_off — a level checkpoint flag.

Runs as this placed object's own instance script (an isolated module, see
tortuengine/instance_scripts.py) — a scene can have several checkpoints, each
tracking its own on/off sprite independently. game_state.checkpoint (a plain
module, not instance-isolated) is the single shared source of truth for where
the player actually respawns, so whichever checkpoint was touched most
recently always wins over any touched earlier.

Touching one while enabled sets game_state.checkpoint to this instance's own
position — mechaturtle_player.py's init() spawns there instead of the
scene's authored player start on the next respawn — flips this flag's own
sprite from "off" to "on", and plays Jingle_checkpoint once for the
activation. On scene (re)load, init() re-derives on/off by comparing this
instance's position against game_state.checkpoint, so a checkpoint already
passed still shows "on" after a respawn reloads the scene fresh.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from tortuengine import instance_api
from tortuengine.object import load_object
from tortuengine.sprite import load_sprite
from scripts import game_state
from scripts._generated import check_pc_off_auto as auto

ROOT = Path(__file__).parent.parent
CHECKPOINT_PREFAB = "assets/objects/check_pc_off.tortuobject"

# Hitbox offsets from the object's origin — resolved in init() from the
# prefab's own collider, not hand-copied numbers.
_hb_l = _hb_r = _hb_t = _hb_b = 0

_sfx_checkpoint: pygame.mixer.Sound | None = None


def _resolve_bounds(colliders, ox: int, oy: int, sw: int, sh: int) -> tuple[int, int, int, int]:
    res = [c.resolved(sw, sh) for c in colliders]
    return (
        min(x for x, y, w, h in res) - ox,
        max(x + w for x, y, w, h in res) - ox,
        min(y for x, y, w, h in res) - oy,
        max(y + h for x, y, w, h in res) - oy,
    )


def init(engine) -> None:
    global _hb_l, _hb_r, _hb_t, _hb_b, _sfx_checkpoint

    obj = load_object(ROOT / CHECKPOINT_PREFAB)
    sprite = load_sprite(ROOT / obj.default_sprite)
    _hb_l, _hb_r, _hb_t, _hb_b = _resolve_bounds(
        obj.colliders, obj.origin.x, obj.origin.y,
        sprite.pixel_width, sprite.pixel_height,
    )

    try:
        _sfx_checkpoint = pygame.mixer.Sound(str(ROOT / "assets/audio/Jingle_checkpoint.ogg"))
    except Exception:
        pass

    pos = instance_api.get_position(SELF_ID)
    is_active = pos is not None and game_state.checkpoint == pos
    instance_api.set_animation(SELF_ID, auto.ANIM_ON if is_active else auto.ANIM_OFF)


def update(dt: float) -> None:
    if not instance_api.is_enabled(SELF_ID):
        return
    pos = instance_api.get_position(SELF_ID)
    if pos is None or game_state.checkpoint == pos:
        return

    px, py = pos
    left, right = px + _hb_l, px + _hb_r
    top, bottom = py + _hb_t, py + _hb_b

    p_hb = instance_api.player_hitbox()
    if p_hb is None:
        return
    p_left, p_right, p_top, p_bottom = p_hb
    if left < p_right and right > p_left and top < p_bottom and bottom > p_top:
        game_state.set_checkpoint(px, py)
        instance_api.set_animation(SELF_ID, auto.ANIM_ON)
        if _sfx_checkpoint:
            _sfx_checkpoint.play()


def draw(engine) -> None:
    pass
