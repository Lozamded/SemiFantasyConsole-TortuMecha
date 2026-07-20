"""Mechaturtle player controller — Alex Kidd style movement."""

from __future__ import annotations

from pathlib import Path

import pygame

from tortuengine.bake import bake_sprite_frame
from tortuengine import instance_api
from tortuengine.object import load_object
from scripts import game_state
from scripts._generated import mechaturtle_player_auto as auto
from scripts._generated import red_slime_auto as slime_auto
from tortuengine.palette import load_palette, palette_path
from tortuengine.scene import SceneObject, load_scene
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
PAUSE_GUI_LAYER = "assets/gui/pause_menu.tortuguilayer"
ATTACK_COLLIDER_PREFAB = "assets/objects/collider_mechaturtle_attack.tortuobject"
ATTACK_COLLIDER_ID = "mechaturtle_attack_hitbox"
SLIME_PREFAB = "assets/objects/red_slime.tortuobject"
GEAR_PREFAB = "assets/objects/gear.tortuobject"
SOUL_PREFAB = "assets/objects/mechaturtle_soul.tortuobject"

SCREEN_W, SCREEN_H = 264, 198
TILE_SIZE = 16
GRAVITY = 400.0
WALK_SPEED = 80.0
JUMP_VEL = -210.0
JUMP_CUT = 0.35     # velocity multiplier on early jump-button release
COYOTE_TIME = 0.1
JUMP_BUFFER = 0.1
ATTACK_DUR = 0.4
HURT_DUR = 0.4
KNOCKBACK_SPEED = 140.0
DEFEAT_POP_VEL = -220.0  # initial upward pop when the player is defeated (Mario-style)
DEFEAT_OFFSCREEN_Y = SCREEN_H + 40  # falls this far below the top of the screen before respawn
SOUL_RISE_SPEED = 60.0  # px/sec the soul continuously drifts upward once spawned
# Life system: each enemy touch costs one energy pip (life_bar); losing the
# last pip costs one life (lives_label) and refills energy. power_bar isn't
# wired into the life system yet — reserved for a future shoot/attack meter.
# Current values live in scripts/game_state.py, not here.

# Hitbox offsets from the character origin. Resolved in init() from the
# auto.COLLIDER_BODY + auto.COLLIDER_HEAD colliders (stand) and
# auto.COLLIDER_BODY alone (crouch) — see mechaturtle.tortuobject in TortuStudio.
STAND_HB_L = STAND_HB_R = STAND_HB_T = STAND_HB_B = 0
CROUCH_HB_L = CROUCH_HB_R = CROUCH_HB_T = CROUCH_HB_B = 0
ATK_HB_L = ATK_HB_R = ATK_HB_T = ATK_HB_B = 0
SLIME_HB_L = SLIME_HB_R = SLIME_HB_T = SLIME_HB_B = 0
GEAR_HB_L = GEAR_HB_R = GEAR_HB_T = GEAR_HB_B = 0

_scene = None
# Attack hitbox scene object — spawned once in init(), repositioned and
# shown/hidden each frame in update() rather than added/removed per swing.
_attack_obj: SceneObject | None = None
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
_hurt_timer = 0.0
_knockback_dir = 1  # -1 = pushed left, 1 = pushed right; set when a hit lands
_defeated = False  # True while playing the death-bounce that follows losing a life
# Set True once the defeat bounce has carried the player off the bottom of the
# screen — main.py watches this to know when to respawn or go to game over.
defeat_done = False
# Spawned once the defeat bounce reaches its apex (vy crosses from rising to
# falling) — floats upward on its own while the body keeps falling.
_soul_obj: SceneObject | None = None
# World-Y threshold below which falling (e.g. into a bottomless pit) triggers
# defeat — resolved per scene in init() from the mechaturtle instance's
# kill_plane_y custom var (see mechaturtle.tortuobject in TortuStudio).
_kill_plane_y = 0.0

_sfx_jump: pygame.mixer.Sound | None = None
_sfx_shell: pygame.mixer.Sound | None = None
_sfx_attack: pygame.mixer.Sound | None = None
_sfx_coin: pygame.mixer.Sound | None = None

_camera = None
_is_camera_target: bool = True
_engine = None

_paused = False
_prev_pause_held = False


def set_camera(cam) -> None:
    global _camera
    _camera = cam


def _set_pause_gui_visible(visible: bool) -> None:
    if _scene is None:
        return
    for g in _scene.gui_layers:
        if g.gui_layer == PAUSE_GUI_LAYER:
            g.visible = visible

_ANIM_FPS: dict[str, int] = {
    auto.ANIM_IDLE: 8, auto.ANIM_WALK: 8, auto.ANIM_JUMP: 6, auto.ANIM_FALL: 8,
    auto.ANIM_ATTACK: 5, auto.ANIM_AIR_ATTACK: 5, auto.ANIM_CROUCH: 3, auto.ANIM_DAMAGE: 8,
    auto.ANIM_DEFEATED: 8,
}
_ANIM_NOLOOP: frozenset[str] = frozenset({
    auto.ANIM_JUMP, auto.ANIM_ATTACK, auto.ANIM_AIR_ATTACK, auto.ANIM_CROUCH, auto.ANIM_DAMAGE,
    auto.ANIM_DEFEATED,
})
_ANIMS = (
    auto.ANIM_IDLE, auto.ANIM_WALK, auto.ANIM_JUMP, auto.ANIM_FALL,
    auto.ANIM_ATTACK, auto.ANIM_AIR_ATTACK, auto.ANIM_CROUCH, auto.ANIM_DAMAGE,
    auto.ANIM_DEFEATED,
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


def _resolve_bounds(colliders, ox: int, oy: int, sw: int, sh: int) -> tuple[int, int, int, int]:
    res = [c.resolved(sw, sh) for c in colliders]
    return (
        min(x for x, y, w, h in res) - ox,
        max(x + w for x, y, w, h in res) - ox,
        min(y for x, y, w, h in res) - oy,
        max(y + h for x, y, w, h in res) - oy,
    )


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


def _enter_defeated() -> None:
    """Transition into the defeat bounce (Mario-style pop-up-then-fall).

    Triggered either by the touch-damage hit that empties the last energy
    pip, or by falling past _kill_plane_y (e.g. into a bottomless pit) —
    both call this, then bail out of the rest of that frame's update() so
    the freshly-set defeated state isn't immediately overwritten by the
    normal jump/fall animation-state logic later in the same frame.
    """
    global _vx, _vy, _state, _prev_state, _anim_frame, _anim_elapsed, _defeated
    _defeated = True
    _vx, _vy = 0.0, DEFEAT_POP_VEL
    _state = _prev_state = auto.ANIM_DEFEATED
    _anim_frame, _anim_elapsed = 0, 0.0
    if _attack_obj is not None:
        _attack_obj.enabled = False


def _push_defeated_frame_state(dt: float) -> None:
    """Shared HUD/renderer push for the frame a defeat trigger fires on."""
    instance_api.set_player_position(_px, _py)
    instance_api.set_player_energy(game_state.energy, game_state.MAX_ENERGY)
    instance_api.set_player_lives(game_state.lives, game_state.MAX_LIVES)
    instance_api.set_player_gears(game_state.gears)
    if _renderer and _scene:
        _renderer.tick(_scene, dt, _engine)


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
    global ATK_HB_L, ATK_HB_R, ATK_HB_T, ATK_HB_B
    global SLIME_HB_L, SLIME_HB_R, SLIME_HB_T, SLIME_HB_B
    global GEAR_HB_L, GEAR_HB_R, GEAR_HB_T, GEAR_HB_B
    global _sfx_jump, _sfx_shell, _sfx_attack, _sfx_coin, _is_camera_target
    global _engine, _attack_obj, _hurt_timer, _knockback_dir
    global _defeated, defeat_done, _soul_obj, _kill_plane_y
    global _paused, _prev_pause_held

    _engine = engine
    _paused, _prev_pause_held = False, False
    _px, _py = 34.0, 191.0
    _vx, _vy = 0.0, 0.0
    _facing, _on_ground = 1, False
    _state = _prev_state = auto.DEFAULT_ANIMATION
    _anim_frame, _anim_elapsed = 0, 0.0
    _attack_timer, _coyote_timer, _jump_buffer_timer = 0.0, 0.0, 0.0
    _prev_jump, _prev_attack = False, False
    _was_on_ground = False
    _crouching, _prev_down = False, False
    _hurt_timer, _knockback_dir = 0.0, 1
    _defeated, defeat_done, _soul_obj = False, False, None

    scene_path = ROOT / "scenes/level_01.tortuscene"
    _scene = load_scene(scene_path, project_root=ROOT)
    player_instances = [o for o in _scene.objects if o.prefab == _PREFAB_PATH]
    _kill_plane_y = float(
        player_instances[0].custom_var_overrides.get(
            auto.CUSTOMVAR_KILL_PLANE_Y, auto.CUSTOMVAR_KILL_PLANE_Y_DEFAULT
        )
        if player_instances else auto.CUSTOMVAR_KILL_PLANE_Y_DEFAULT
    )
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
        return _resolve_bounds(cols, ox, oy, sw, sh)

    STAND_HB_L, STAND_HB_R, STAND_HB_T, STAND_HB_B = _bounds(
        {auto.COLLIDER_BODY, auto.COLLIDER_HEAD}
    )
    CROUCH_HB_L, CROUCH_HB_R, CROUCH_HB_T, CROUCH_HB_B = _bounds({auto.COLLIDER_BODY})

    # Attack hitbox bounds, resolved from its own prefab the same way — and
    # the hitbox scene object itself, spawned once and repositioned/shown
    # per swing in update() rather than added/removed every attack.
    atk_obj = load_object(ROOT / ATTACK_COLLIDER_PREFAB)
    atk_sprite = load_sprite(ROOT / atk_obj.default_sprite)
    ATK_HB_L, ATK_HB_R, ATK_HB_T, ATK_HB_B = _resolve_bounds(
        atk_obj.colliders, atk_obj.origin.x, atk_obj.origin.y,
        atk_sprite.pixel_width, atk_sprite.pixel_height,
    )
    atk_idx = _scene.add_object(
        ATTACK_COLLIDER_PREFAB, 0, 0, z_index=1, obj_id=ATTACK_COLLIDER_ID
    )
    _attack_obj = _scene.objects[atk_idx]
    _attack_obj.visible = False

    # Enemy contact hitbox — resolved from the red_slime prefab the same way,
    # used to detect touch-damage against live (enabled) slime instances.
    slime_obj = load_object(ROOT / SLIME_PREFAB)
    slime_sprite = load_sprite(ROOT / slime_obj.default_sprite)
    SLIME_HB_L, SLIME_HB_R, SLIME_HB_T, SLIME_HB_B = _resolve_bounds(
        slime_obj.colliders, slime_obj.origin.x, slime_obj.origin.y,
        slime_sprite.pixel_width, slime_sprite.pixel_height,
    )

    # Gear (coin) pickup hitbox, resolved from the gear prefab the same way.
    gear_obj = load_object(ROOT / GEAR_PREFAB)
    gear_sprite = load_sprite(ROOT / gear_obj.default_sprite)
    GEAR_HB_L, GEAR_HB_R, GEAR_HB_T, GEAR_HB_B = _resolve_bounds(
        gear_obj.colliders, gear_obj.origin.x, gear_obj.origin.y,
        gear_sprite.pixel_width, gear_sprite.pixel_height,
    )

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
        _sfx_coin = pygame.mixer.Sound(str(ROOT / "assets/audio/sfx_coin.ogg"))
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
    global _hurt_timer, _knockback_dir
    global _defeated, defeat_done, _soul_obj
    global _paused, _prev_pause_held

    pause_held = pygame.key.get_pressed()[pygame.K_RETURN]
    if pause_held and not _prev_pause_held:
        _paused = not _paused
        _set_pause_gui_visible(_paused)
    _prev_pause_held = pause_held

    if _paused:
        return

    if _defeated:
        was_rising = _vy < 0
        _vy += GRAVITY * dt
        _py += _vy * dt

        # Spawn the soul once the bounce hits its apex (vy flips from rising
        # to falling) — it then drifts upward on its own, independent of the
        # body continuing to fall.
        if was_rising and _vy >= 0 and _soul_obj is None and _scene is not None:
            idx = _scene.add_object(SOUL_PREFAB, int(_px), int(_py), z_index=1)
            _soul_obj = _scene.objects[idx]
        if _soul_obj is not None:
            _soul_obj.y -= SOUL_RISE_SPEED * dt

        fps = _ANIM_FPS.get(_state, 8)
        n = len(_frames[_state][0]) if _state in _frames else 1
        _anim_elapsed += dt
        adv = int(_anim_elapsed * fps)
        if adv:
            _anim_frame = min(_anim_frame + adv, n - 1)
            _anim_elapsed -= adv / fps
        instance_api.set_player_position(_px, _py)
        if _renderer and _scene:
            _renderer.tick(_scene, dt, _engine)
        # Require the bounce to already be past its apex (falling, not still
        # rising) before allowing completion — otherwise a pit-fall trigger
        # (which starts at or below DEFEAT_OFFSCREEN_Y already) would finish
        # instantly, skipping the pop-up and the soul spawn entirely.
        if _vy >= 0 and _py > DEFEAT_OFFSCREEN_Y:
            defeat_done = True
        return

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

    if _hurt_timer > 0:
        _hurt_timer = max(0.0, _hurt_timer - dt)
    hurt = _hurt_timer > 0

    px_l, px_r = _px + hb_l, _px + hb_r
    py_t, py_b = _py + hb_t, _py + hb_b

    # Touch-damage: only look for a new hit while not already reeling from one.
    # Crouching is immune — red_slime.py bounces off a crouched turtle instead
    # (see its own player_hitbox()/player_is_crouching() check).
    if not hurt and not _crouching and _scene is not None:
        for inst in _scene.objects:
            if inst.prefab != SLIME_PREFAB or not inst.enabled:
                continue
            if inst.animation == slime_auto.ANIM_DEFEAT:
                continue  # already defeated, mid death-animation — harmless
            s_l, s_r = inst.x + SLIME_HB_L, inst.x + SLIME_HB_R
            s_t, s_b = inst.y + SLIME_HB_T, inst.y + SLIME_HB_B
            if px_l < s_r and px_r > s_l and py_t < s_b and py_b > s_t:
                _knockback_dir = -1 if _px < inst.x else 1
                if game_state.damage():
                    _enter_defeated()
                else:
                    _hurt_timer = HURT_DUR
                    hurt = True
                break

    if _defeated:
        # Skip the rest of this frame's normal input/physics/animation so the
        # defeat pop isn't immediately overwritten by the jump/fall state logic
        # below — the early-return branch at the top of update() takes over
        # starting next frame.
        _push_defeated_frame_state(dt)
        return

    # Gear pickup — a coin-style collectible; always active regardless of
    # hurt/crouch state, unlike enemy touch-damage above.
    if _scene is not None:
        for inst in _scene.objects:
            if inst.prefab != GEAR_PREFAB or not inst.enabled:
                continue
            g_l, g_r = inst.x + GEAR_HB_L, inst.x + GEAR_HB_R
            g_t, g_b = inst.y + GEAR_HB_T, inst.y + GEAR_HB_B
            if px_l < g_r and px_r > g_l and py_t < g_b and py_b > g_t:
                inst.enabled = False
                if _sfx_coin:
                    _sfx_coin.play()
                game_state.add_gear()

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

    if atk_pressed and not attacking and not _crouching and not hurt:
        _attack_timer = ATTACK_DUR
        attacking = True
        if _sfx_attack:
            _sfx_attack.play()
        if _on_ground:
            _vx = 0.0

    # Horizontal input — knockback overrides input while hurt; otherwise
    # suppressed on ground while attacking or crouching
    if hurt:
        _vx = _knockback_dir * KNOCKBACK_SPEED
    elif not (attacking and _on_ground) and not _crouching:
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

    # Jump — not allowed while crouching or reeling from a hit
    can_jump = (_on_ground or _coyote_timer > 0) and not _crouching and not hurt
    if can_jump and _jump_buffer_timer > 0:
        _vy = JUMP_VEL
        _on_ground = False
        _coyote_timer = 0.0
        _jump_buffer_timer = 0.0
        if _sfx_jump:
            _sfx_jump.play()

    _physics(dt, hb_l, hb_r, hb_t, hb_b)

    # Fell past the kill plane (e.g. into a bottomless pit) — same defeat
    # bounce as a lethal hit, but a full life is lost outright rather than
    # draining energy pips (there's no "surviving" a pit).
    if _py > _kill_plane_y:
        game_state.lose_life()
        _enter_defeated()
        _push_defeated_frame_state(dt)
        return

    if _attack_obj is not None:
        # Stays invisible always — it's a hit-detection volume, not a drawn
        # effect. `enabled` is the "is the swing currently active" signal
        # red_slime.py checks via instance_api.is_enabled().
        _attack_obj.enabled = attacking
        if attacking:
            if _facing == 1:
                atk_x = _px + STAND_HB_R - ATK_HB_L
            else:
                atk_x = _px + STAND_HB_L - ATK_HB_R
            atk_y = _py + (STAND_HB_T + STAND_HB_B) / 2 - (ATK_HB_T + ATK_HB_B) / 2
            _attack_obj.x, _attack_obj.y = atk_x, atk_y

    # Animation state
    new_state: str
    if hurt:
        new_state = auto.ANIM_DAMAGE
    elif _crouching:
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
    instance_api.set_player_crouching(_crouching)
    instance_api.set_player_hitbox(_px + hb_l, _px + hb_r, _py + hb_t, _py + hb_b)
    instance_api.set_player_energy(game_state.energy, game_state.MAX_ENERGY)
    instance_api.set_player_lives(game_state.lives, game_state.MAX_LIVES)
    instance_api.set_player_gears(game_state.gears)
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
