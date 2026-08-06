"""Script for brick_block — a solid block the player can smash with an attack.

Solidity against the player is generic engine-side (tortoisengine/instance_api.py
object_solid_at(), driven by this prefab's own `solid: true`). This script's
only job re: solidity is to clear it the instant the block starts breaking —
via set_object_solid(SELF_ID, False) — while staying enabled so its own
break-timer update() keeps running until the animation finishes.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from tortoisengine import instance_api
from tortoisengine.object import load_object
from tortoisengine.sprite import load_sprite
from scripts import audio_settings
from scripts._generated import brick_block_auto as auto
from scripts.mechaturtle_player import ATTACK_COLLIDER_ID

ROOT = Path(__file__).parent.parent
BLOCK_PREFAB = "assets/objects/brick_block.tortuobject"
ATTACK_COLLIDER_PREFAB = "assets/objects/collider_mechaturtle_attack.tortuobject"

# Hitbox / attack-hitbox bounds, offsets from this object's origin — resolved
# in init() from the prefabs' own colliders, not hand-copied numbers.
_hb_l = _hb_r = _hb_t = _hb_b = 0
_atk_l = _atk_r = _atk_t = _atk_b = 0

_broken = False
_break_timer = 0.0
_break_duration = 0.0  # seconds — resolved in init() from the break sprite's own frame_count/fps

_sfx_break: pygame.mixer.Sound | None = None


def _resolve_bounds(colliders, ox: int, oy: int, sw: int, sh: int) -> tuple[int, int, int, int]:
    res = [c.resolved(sw, sh) for c in colliders]
    return (
        min(x for x, y, w, h in res) - ox,
        max(x + w for x, y, w, h in res) - ox,
        min(y for x, y, w, h in res) - oy,
        max(y + h for x, y, w, h in res) - oy,
    )


def init(engine) -> None:
    global _hb_l, _hb_r, _hb_t, _hb_b
    global _atk_l, _atk_r, _atk_t, _atk_b
    global _broken, _break_timer, _break_duration
    global _sfx_break

    try:
        _sfx_break = audio_settings.load_sound("assets/audio/break_block.ogg")
    except Exception:
        pass

    block_obj = load_object(ROOT / BLOCK_PREFAB)
    block_sprite = load_sprite(ROOT / block_obj.default_sprite)
    _hb_l, _hb_r, _hb_t, _hb_b = _resolve_bounds(
        block_obj.colliders, block_obj.origin.x, block_obj.origin.y,
        block_sprite.pixel_width, block_sprite.pixel_height,
    )

    break_sprite = load_sprite(ROOT / block_obj.sprite_for(auto.ANIM_BREAK))
    _break_duration = break_sprite.frame_count / max(1, break_sprite.fps)

    atk_obj = load_object(ROOT / ATTACK_COLLIDER_PREFAB)
    atk_sprite = load_sprite(ROOT / atk_obj.default_sprite)
    _atk_l, _atk_r, _atk_t, _atk_b = _resolve_bounds(
        atk_obj.colliders, atk_obj.origin.x, atk_obj.origin.y,
        atk_sprite.pixel_width, atk_sprite.pixel_height,
    )

    _broken = False
    _break_timer = 0.0


def _overlaps(l1: float, r1: float, t1: float, b1: float, l2: float, r2: float, t2: float, b2: float) -> bool:
    return l1 < r2 and r1 > l2 and t1 < b2 and b1 > t2


def update(dt: float) -> None:
    global _broken, _break_timer

    if _broken:
        _break_timer -= dt
        if _break_timer <= 0:
            instance_api.set_enabled(SELF_ID, False)
            instance_api.set_visible(SELF_ID, False)
        return

    pos = instance_api.get_position(SELF_ID)
    if pos is None:
        return
    px, py = pos
    left, right = px + _hb_l, px + _hb_r
    top, bottom = py + _hb_t, py + _hb_b

    if instance_api.is_enabled(ATTACK_COLLIDER_ID):
        atk_pos = instance_api.get_position(ATTACK_COLLIDER_ID)
        if atk_pos:
            ax, ay = atk_pos
            atk_left, atk_right = ax + _atk_l, ax + _atk_r
            atk_top, atk_bottom = ay + _atk_t, ay + _atk_b
            if _overlaps(left, right, top, bottom, atk_left, atk_right, atk_top, atk_bottom):
                _broken = True
                _break_timer = _break_duration
                instance_api.set_animation(SELF_ID, auto.ANIM_BREAK)
                instance_api.set_object_solid(SELF_ID, False)
                if _sfx_break:
                    _sfx_break.play()


def draw(engine) -> None:
    pass
