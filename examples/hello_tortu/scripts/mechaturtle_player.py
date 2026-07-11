"""Mechaturtle player controller — Alex Kidd style movement."""

from __future__ import annotations

from pathlib import Path

import pygame

from tortuengine.bake import bake_sprite_frame
from tortuengine import instance_api
from tortuengine.object import load_object
from scripts._generated import mechaturtle_player_auto as auto
from tortuengine.palette import load_palette, palette_path
from tortuengine.scene import load_scene
from tortuengine.scene_renderer import SceneRenderer
from tortuengine.sprite import load_sprite
from tortuengine.tileset import (
    COLLISION_NONE,
    COLLISION_SOLID,
    ONE_WAY_DOWN,
    ONE_WAY_LEFT,
    ONE_WAY_NONE,
    ONE_WAY_RIGHT,
    ONE_WAY_UP,
    load_tileset,
)

ROOT = Path(__file__).parent.parent
_PREFAB_PATH = "assets/objects/mechaturtle.tortuobject"

SCREEN_W, SCREEN_H = 264, 198
TILE_SIZE = 16
GRAVITY = 400.0
WALK_SPEED = 80.0
JUMP_VEL = -210.0
JUMP_CUT = 0.35     # velocity multiplier on early jump-button release
COYOTE_TIME = 0.1
JUMP_BUFFER = 0.1
ATTACK_DUR = 0.4

# Hitbox offsets from the character origin. Resolved in init() from the
# auto.COLLIDER_BODY + auto.COLLIDER_HEAD colliders (stand) and
# auto.COLLIDER_BODY alone (crouch) — see mechaturtle.tortuobject in TortuStudio.
STAND_HB_L = STAND_HB_R = STAND_HB_T = STAND_HB_B = 0
CROUCH_HB_L = CROUCH_HB_R = CROUCH_HB_T = CROUCH_HB_B = 0

_scene = None
_collision_tileset = None
_renderer: SceneRenderer | None = None
# _frames[anim] = (normal_list, flipped_list), pre-baked at init
_frames: dict[str, tuple[list[pygame.Surface], list[pygame.Surface]]] = {}

_px, _py = 34.0, 191.0
_vx, _vy = 0.0, 0.0
_facing = 1          # 1 = right, -1 = left
_on_ground = False
_state = auto.DEFAULT_ANIMATION
_prev_state = auto.DEFAULT_ANIMATION
_anim_frame = 0
_anim_elapsed = 0.0
_attack_timer = 0.0
_coyote_timer = 0.0
_jump_buffer_timer = 0.0
_prev_jump = False
_prev_attack = False
_was_on_ground = False
_crouching = False
_prev_down = False

_sfx_jump: pygame.mixer.Sound | None = None
_sfx_shell: pygame.mixer.Sound | None = None
_sfx_attack: pygame.mixer.Sound | None = None

_camera = None
_is_camera_target: bool = True
_engine = None


def set_camera(cam) -> None:
    global _camera
    _camera = cam

_ANIM_FPS: dict[str, int] = {
    auto.ANIM_IDLE: 8, auto.ANIM_WALK: 8, auto.ANIM_JUMP: 6, auto.ANIM_FALL: 8,
    auto.ANIM_ATTACK: 5, auto.ANIM_AIR_ATTACK: 5, auto.ANIM_CROUCH: 3,
}
_ANIM_NOLOOP: frozenset[str] = frozenset({
    auto.ANIM_JUMP, auto.ANIM_ATTACK, auto.ANIM_AIR_ATTACK, auto.ANIM_CROUCH,
})
_ANIMS = (
    auto.ANIM_IDLE, auto.ANIM_WALK, auto.ANIM_JUMP, auto.ANIM_FALL,
    auto.ANIM_ATTACK, auto.ANIM_AIR_ATTACK, auto.ANIM_CROUCH,
)


# ---------------------------------------------------------------------------
# Tile collision helpers
# ---------------------------------------------------------------------------

def _tile_solid_at(col: int, row: int, local_x: int, local_y: int) -> bool:
    if _scene is None:
        return False
    layer = _scene.tile_layers[_scene.collision_tile_layer]
    cols = _scene.width // TILE_SIZE
    if col < 0 or col >= cols or row < 0:
        return False
    idx = row * cols + col
    if idx >= len(layer.tiles):
        return False
    tile_index = layer.tiles[idx]
    if tile_index < 0:
        return False
    if _collision_tileset is None:
        return True
    if _collision_tileset.get_one_way(tile_index) != ONE_WAY_NONE:
        return False
    collision = _collision_tileset.get_collision(tile_index)
    if collision == COLLISION_NONE:
        return False
    if collision == COLLISION_SOLID:
        return True
    ts = _collision_tileset.tile_size
    lx = max(0, min(local_x, ts - 1))
    ly = max(0, min(local_y, ts - 1))
    return bool(_collision_tileset.collision_shapes[tile_index][ly * ts + lx])


def _tile_one_way(col: int, row: int) -> str:
    if _scene is None or _collision_tileset is None:
        return ONE_WAY_NONE
    layer = _scene.tile_layers[_scene.collision_tile_layer]
    cols = _scene.width // TILE_SIZE
    if col < 0 or col >= cols or row < 0:
        return ONE_WAY_NONE
    idx = row * cols + col
    if idx >= len(layer.tiles):
        return ONE_WAY_NONE
    tile_index = layer.tiles[idx]
    if tile_index < 0:
        return ONE_WAY_NONE
    return _collision_tileset.get_one_way(tile_index)


def _scan_h_one_way(col: int, t_row: int, b_row: int, direction: str) -> bool:
    return any(_tile_one_way(col, r) == direction for r in range(t_row, b_row + 1))


def _scan_v_one_way(row: int, l_col: int, r_col: int, direction: str) -> bool:
    return any(_tile_one_way(c, row) == direction for c in range(l_col, r_col + 1))


def _scan_h(
    col: int, t_row: int, b_row: int,
    edge_wx: float, mid_wy: float,
    hb_t: int, hb_b: int,
) -> bool:
    """Check if any tile in the vertical column blocks a horizontal edge."""
    local_x = int(edge_wx) % TILE_SIZE
    for r in range(t_row, b_row + 1):
        y_lo = max(int(mid_wy + hb_t), r * TILE_SIZE)
        y_hi = min(int(mid_wy + hb_b - 1), (r + 1) * TILE_SIZE - 1)
        for wy in range(y_lo, y_hi + 1):
            if _tile_solid_at(col, r, local_x, wy % TILE_SIZE):
                return True
    return False


def _scan_v(
    row: int, l_col: int, r_col: int,
    mid_wx: float, edge_wy: float,
    hb_l: int, hb_r: int,
) -> bool:
    """Check if any tile in the horizontal row blocks a vertical edge."""
    local_y = int(edge_wy) % TILE_SIZE
    for c in range(l_col, r_col + 1):
        x_lo = max(int(mid_wx + hb_l), c * TILE_SIZE)
        x_hi = min(int(mid_wx + hb_r - 1), (c + 1) * TILE_SIZE - 1)
        for wx in range(x_lo, x_hi + 1):
            if _tile_solid_at(c, row, wx % TILE_SIZE, local_y):
                return True
    return False


def _can_uncrouch() -> bool:
    """True if the tiles in the head zone are clear enough to stand up."""
    if STAND_HB_T >= CROUCH_HB_T:
        return True
    t_row = max(0, int((_py + STAND_HB_T) / TILE_SIZE))
    b_row = max(0, int((_py + CROUCH_HB_T) / TILE_SIZE) - 1)
    l_col = max(0, int((_px + STAND_HB_L) / TILE_SIZE))
    r_col = max(l_col, int((_px + STAND_HB_R - 1) / TILE_SIZE))
    if b_row < t_row:
        return True
    for row in range(t_row, b_row + 1):
        for col in range(l_col, r_col + 1):
            if _tile_solid_at(col, row, TILE_SIZE // 2, TILE_SIZE // 2):
                return False
    return True


def _physics(dt: float, hb_l: int, hb_r: int, hb_t: int, hb_b: int) -> None:
    global _px, _py, _vx, _vy, _on_ground

    _vy = min(_vy + GRAVITY * dt, 400.0)

    # --- Horizontal ---
    prev_right = _px + hb_r - 1
    prev_left  = _px + hb_l
    new_px = _px + _vx * dt
    t_row = max(0, int((_py + hb_t) / TILE_SIZE))
    b_row = max(0, int((_py + hb_b - 1) / TILE_SIZE))

    if _vx > 0:
        col = int((new_px + hb_r - 1) / TILE_SIZE)
        tile_left = col * TILE_SIZE
        blocked = _scan_h(col, t_row, b_row, new_px + hb_r - 1, _py, hb_t, hb_b)
        if not blocked and prev_right < tile_left:
            blocked = _scan_h_one_way(col, t_row, b_row, ONE_WAY_LEFT)
        if blocked:
            new_px = tile_left - hb_r
            _vx = 0.0
    elif _vx < 0:
        col = int((new_px + hb_l) / TILE_SIZE)
        tile_right = (col + 1) * TILE_SIZE
        blocked = _scan_h(col, t_row, b_row, new_px + hb_l, _py, hb_t, hb_b)
        if not blocked and prev_left >= tile_right:
            blocked = _scan_h_one_way(col, t_row, b_row, ONE_WAY_RIGHT)
        if blocked:
            new_px = tile_right - hb_l
            _vx = 0.0

    if _scene:
        new_px = max(float(-hb_l), min(new_px, float(_scene.width - hb_r)))
    _px = new_px

    # --- Vertical ---
    prev_bottom = _py + hb_b
    prev_top    = _py + hb_t
    new_py = _py + _vy * dt
    l_col = max(0, int((_px + hb_l) / TILE_SIZE))
    r_col = int((_px + hb_r - 1) / TILE_SIZE)

    if _vy >= 0:
        row = int((new_py + hb_b) / TILE_SIZE)
        tile_top = row * TILE_SIZE
        blocked = _scan_v(row, l_col, r_col, _px, new_py + hb_b, hb_l, hb_r)
        if not blocked and prev_bottom <= tile_top:
            blocked = _scan_v_one_way(row, l_col, r_col, ONE_WAY_UP)
        if blocked:
            new_py = tile_top - hb_b
            _vy = 0.0
    else:
        row = max(0, int((new_py + hb_t) / TILE_SIZE))
        tile_bottom = (row + 1) * TILE_SIZE
        blocked = _scan_v(row, l_col, r_col, _px, new_py + hb_t, hb_l, hb_r)
        if not blocked and prev_top >= tile_bottom:
            blocked = _scan_v_one_way(row, l_col, r_col, ONE_WAY_DOWN)
        if blocked:
            new_py = tile_bottom - hb_t
            _vy = 0.0

    _py = new_py

    gnd_row = int((_py + hb_b) / TILE_SIZE)
    _on_ground = (
        _scan_v(gnd_row, l_col, r_col, _px, _py + hb_b, hb_l, hb_r)
        or _scan_v_one_way(gnd_row, l_col, r_col, ONE_WAY_UP)
    )


# ---------------------------------------------------------------------------
# Public init / update / draw
# ---------------------------------------------------------------------------

def init(engine) -> None:
    global _scene, _collision_tileset, _renderer, _frames
    global _px, _py, _vx, _vy, _facing, _on_ground
    global _state, _prev_state, _anim_frame, _anim_elapsed
    global _attack_timer, _coyote_timer, _jump_buffer_timer
    global _prev_jump, _prev_attack, _was_on_ground
    global _crouching, _prev_down
    global STAND_HB_L, STAND_HB_R, STAND_HB_T, STAND_HB_B
    global CROUCH_HB_L, CROUCH_HB_R, CROUCH_HB_T, CROUCH_HB_B
    global _sfx_jump, _sfx_shell, _sfx_attack, _is_camera_target
    global _engine

    _engine = engine
    _px, _py = 34.0, 191.0
    _vx, _vy = 0.0, 0.0
    _facing, _on_ground = 1, False
    _state = _prev_state = auto.DEFAULT_ANIMATION
    _anim_frame, _anim_elapsed = 0, 0.0
    _attack_timer, _coyote_timer, _jump_buffer_timer = 0.0, 0.0, 0.0
    _prev_jump, _prev_attack = False, False
    _was_on_ground = False
    _crouching, _prev_down = False, False

    scene_path = ROOT / "scenes/level_01.tortuscene"
    _scene = load_scene(scene_path, project_root=ROOT)
    _scene.objects = [o for o in _scene.objects if o.prefab != _PREFAB_PATH]
    _is_camera_target = not _scene.camera_target or _scene.camera_target == _PREFAB_PATH

    collision_layer = _scene.tile_layers[_scene.collision_tile_layer]
    if collision_layer.tileset:
        _collision_tileset = load_tileset(ROOT / collision_layer.tileset)
    else:
        _collision_tileset = None

    cart_manifest = getattr(engine, 'manifest', None)
    cart_root = getattr(engine, 'cart_root', None)
    if cart_manifest is not None and cart_root is not None:
        _renderer = SceneRenderer.from_cart(cart_root, cart_manifest)
    else:
        _renderer = SceneRenderer(ROOT)

    idle_spr = load_sprite(ROOT / "assets/sprites/mechaturtle_idle.tortusprite")
    pal = load_palette(palette_path(ROOT, idle_spr.palette))
    sw, sh = idle_spr.pixel_width, idle_spr.pixel_height

    # Resolve hitbox offsets from the object's colliders — auto.COLLIDER_BODY /
    # auto.COLLIDER_HEAD are the source of truth, not hand-copied numbers, so
    # renaming or resizing a collider in TortuStudio can't silently go stale here.
    obj = load_object(ROOT / "assets/objects/mechaturtle.tortuobject")
    ox, oy = auto.ORIGIN

    def _bounds(names: set[str]) -> tuple[int, int, int, int]:
        cols = [c for c in obj.colliders if c.name in names]
        if not cols:
            raise ValueError(
                f"mechaturtle.tortuobject is missing collider(s) {sorted(names)!r} "
                "expected by mechaturtle_player.py — check the collider names in TortuStudio."
            )
        res = [c.resolved(sw, sh) for c in cols]
        return (
            min(x for x, y, w, h in res) - ox,
            max(x + w for x, y, w, h in res) - ox,
            min(y for x, y, w, h in res) - oy,
            max(y + h for x, y, w, h in res) - oy,
        )

    STAND_HB_L, STAND_HB_R, STAND_HB_T, STAND_HB_B = _bounds(
        {auto.COLLIDER_BODY, auto.COLLIDER_HEAD}
    )
    CROUCH_HB_L, CROUCH_HB_R, CROUCH_HB_T, CROUCH_HB_B = _bounds({auto.COLLIDER_BODY})

    _frames.clear()
    for anim in _ANIMS:
        sp = load_sprite(ROOT / f"assets/sprites/mechaturtle_{anim}.tortusprite")
        normal: list[pygame.Surface] = []
        flipped: list[pygame.Surface] = []
        for i in range(sp.frame_count):
            s = bake_sprite_frame(sp, pal, i)
            normal.append(s)
            flipped.append(pygame.transform.flip(s, True, False))
        _frames[anim] = (normal, flipped)

    try:
        _sfx_jump = pygame.mixer.Sound(str(ROOT / "assets/audio/sfx_jump.ogg"))
        _sfx_shell = pygame.mixer.Sound(str(ROOT / "assets/audio/sfx_shell.ogg"))
        _sfx_attack = pygame.mixer.Sound(str(ROOT / "assets/audio/sfx_attack.ogg"))
    except Exception:
        pass

    # Auto-wire camera from scene metadata when not set explicitly by main.py
    if _camera is None and _scene and _scene.camera_script:
        try:
            import importlib
            mod_name = _scene.camera_script.removesuffix(".py").replace("\\", "/").replace("/", ".")
            set_camera(importlib.import_module(mod_name))
        except Exception:
            pass

    if _camera and _scene:
        _camera.init(_scene.width, _scene.height)


def update(dt: float) -> None:
    global _px, _py, _vx, _vy, _facing, _on_ground
    global _state, _prev_state, _anim_frame, _anim_elapsed
    global _attack_timer, _coyote_timer, _jump_buffer_timer
    global _prev_jump, _prev_attack, _was_on_ground
    global _crouching, _prev_down

    keys = pygame.key.get_pressed()
    jump_held  = keys[pygame.K_z] or keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]
    atk_held   = keys[pygame.K_x] or keys[pygame.K_LSHIFT] or keys[pygame.K_c]
    left       = keys[pygame.K_LEFT]  or keys[pygame.K_a]
    right      = keys[pygame.K_RIGHT] or keys[pygame.K_d]
    down_held  = keys[pygame.K_DOWN]  or keys[pygame.K_s]

    jump_pressed  = jump_held and not _prev_jump
    jump_released = not jump_held and _prev_jump
    atk_pressed   = atk_held and not _prev_attack
    _prev_jump    = jump_held
    _prev_attack  = atk_held
    _prev_down    = down_held

    # Crouch: only on the ground, suppressed while attacking
    attacking = _attack_timer > 0
    if _on_ground and not attacking:
        if down_held:
            if not _crouching and _sfx_shell:
                _sfx_shell.play()
            _crouching = True
        elif _crouching and _can_uncrouch():
            _crouching = False
    elif not _on_ground:
        _crouching = False  # auto-stand when airborne

    # Pick active hitbox based on crouch state
    if _crouching:
        hb_l, hb_r, hb_t, hb_b = CROUCH_HB_L, CROUCH_HB_R, CROUCH_HB_T, CROUCH_HB_B
    else:
        hb_l, hb_r, hb_t, hb_b = STAND_HB_L, STAND_HB_R, STAND_HB_T, STAND_HB_B

    if jump_released and _vy < 0:
        _vy *= JUMP_CUT

    if _was_on_ground and not _on_ground and _vy >= 0:
        _coyote_timer = COYOTE_TIME
    if _coyote_timer > 0:
        _coyote_timer = max(0.0, _coyote_timer - dt)
    _was_on_ground = _on_ground

    if jump_pressed:
        _jump_buffer_timer = JUMP_BUFFER
    if _jump_buffer_timer > 0:
        _jump_buffer_timer = max(0.0, _jump_buffer_timer - dt)

    if _attack_timer > 0:
        _attack_timer = max(0.0, _attack_timer - dt)
    attacking = _attack_timer > 0

    if atk_pressed and not attacking and not _crouching:
        _attack_timer = ATTACK_DUR
        attacking = True
        if _sfx_attack:
            _sfx_attack.play()
        if _on_ground:
            _vx = 0.0

    # Horizontal input — suppressed on ground while attacking or crouching
    if not (attacking and _on_ground) and not _crouching:
        if right:
            _vx = WALK_SPEED
            _facing = 1
        elif left:
            _vx = -WALK_SPEED
            _facing = -1
        else:
            _vx = 0.0
    elif _crouching:
        _vx = 0.0

    # Jump — not allowed while crouching
    can_jump = (_on_ground or _coyote_timer > 0) and not _crouching
    if can_jump and _jump_buffer_timer > 0:
        _vy = JUMP_VEL
        _on_ground = False
        _coyote_timer = 0.0
        _jump_buffer_timer = 0.0
        if _sfx_jump:
            _sfx_jump.play()

    _physics(dt, hb_l, hb_r, hb_t, hb_b)

    # Animation state
    new_state: str
    if _crouching:
        new_state = auto.ANIM_CROUCH
    elif attacking:
        new_state = auto.ANIM_ATTACK if _on_ground else auto.ANIM_AIR_ATTACK
    elif not _on_ground:
        new_state = auto.ANIM_FALL if _vy >= 0 else auto.ANIM_JUMP
    elif _vx != 0:
        new_state = auto.ANIM_WALK
    else:
        new_state = auto.ANIM_IDLE

    if new_state != _prev_state:
        _anim_frame = 0
        _anim_elapsed = 0.0
    _state = _prev_state = new_state

    fps = _ANIM_FPS.get(_state, 8)
    if fps > 0:
        n = len(_frames[_state][0]) if _state in _frames else 1
        _anim_elapsed += dt
        adv = int(_anim_elapsed * fps)
        if adv:
            if _state in _ANIM_NOLOOP:
                _anim_frame = min(_anim_frame + adv, n - 1)
            else:
                _anim_frame = (_anim_frame + adv) % n
            _anim_elapsed -= adv / fps
    else:
        _anim_frame = 0

    if _camera and _is_camera_target:
        _camera.update(dt, _px, _py)
    instance_api.set_player_position(_px, _py)
    if _renderer and _scene:
        _renderer.tick(_scene, dt, _engine)


def draw(engine) -> None:
    cam_x, cam_y = _camera.get() if _camera else (0.0, 0.0)
    if _renderer and _scene:
        # The player isn't in _scene.objects (see init()), so it can't take part
        # in the renderer's normal z-ordered draw pass. Instead we render the
        # world up through z_index 0 first, blit the player sprite by hand
        # (implicitly z_index 0 — on top of same-z scene objects/GUI layers,
        # same as any other z=0 item drawn last), then overlay whatever GUI
        # layers are above it (e.g. a z_index 1 dialog box).
        frame = _renderer.render(_scene, camera_x=int(cam_x), camera_y=int(cam_y), z_max=0)
        engine.blit(frame, (0, 0))
    else:
        engine.clear((12, 18, 32))

    anim_data = _frames.get(_state)
    if anim_data:
        normal, flipped = anim_data
        pool = flipped if _facing == -1 else normal
        fi = _anim_frame % len(pool)
        surf = pool[fi]
        screen_x = int(_px - auto.ORIGIN[0] - cam_x)
        screen_y = int(_py - auto.ORIGIN[1])
        engine.blit(surf, (screen_x, screen_y))

    if _renderer and _scene:
        overlay = _renderer.render_overlay(
            _scene, camera_x=int(cam_x), camera_y=int(cam_y), z_min=1
        )
        engine.blit(overlay, (0, 0))

    engine.text(f"{_state}", 4, 4, (200, 220, 255), 8)
