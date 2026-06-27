"""Mechaturtle player controller — Alex Kidd style movement."""

from __future__ import annotations

from pathlib import Path

import pygame

from tortuengine.bake import bake_sprite_frame
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

SCREEN_W, SCREEN_H = 264, 198
TILE_SIZE = 16
GRAVITY = 400.0
WALK_SPEED = 80.0
JUMP_VEL = -210.0
JUMP_CUT = 0.35     # velocity multiplier applied on early jump-button release
COYOTE_TIME = 0.1   # seconds you can still jump after walking off a ledge
JUMP_BUFFER = 0.1   # seconds a jump press is remembered before landing
ATTACK_DUR = 0.4

# Hitbox offsets from origin (18, 31) in sprite pixels.
# Sprite is 40x32. Hitbox (x=9, y=5, w=19, h=27) → world offsets:
HB_L, HB_R = -9, 10    # left/right pixel offsets (right is exclusive)
HB_T, HB_B = -26, 1    # top/bottom pixel offsets (bottom is exclusive)

_scene = None
_collision_tileset = None
_renderer: SceneRenderer | None = None
# _frames[anim] = (normal_list, flipped_list), pre-baked at init
_frames: dict[str, tuple[list[pygame.Surface], list[pygame.Surface]]] = {}

_px, _py = 34.0, 191.0
_vx, _vy = 0.0, 0.0
_facing = 1          # 1 = right, -1 = left
_on_ground = False
_state = "idle"
_prev_state = "idle"
_anim_frame = 0
_anim_elapsed = 0.0
_attack_timer = 0.0
_coyote_timer = 0.0
_jump_buffer_timer = 0.0
_cam_x = 0.0
_prev_jump = False
_prev_attack = False
_was_on_ground = False

_ANIM_FPS: dict[str, int] = {"idle": 8, "walk": 8, "jump": 6, "fall": 0, "attack": 0, "air_attack": 0}
_ANIM_NOLOOP: frozenset[str] = frozenset({"jump", "attack", "air_attack"})
_ANIMS = ("idle", "walk", "jump", "fall", "attack", "air_attack")


# ---------------------------------------------------------------------------
# Tile collision
# ---------------------------------------------------------------------------

def _tile_solid_at(col: int, row: int, local_x: int, local_y: int) -> bool:
    """True if tile (col, row) blocks at local pixel (local_x, local_y).

    SOLID  → always True (whole tile blocks).
    NONE   → always False.
    POLYGON → samples the per-pixel mask at the exact contact point.
    """
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
    # One-way tiles are handled exclusively by the one-way scan — never by solid scan.
    if _collision_tileset.get_one_way(tile_index) != ONE_WAY_NONE:
        return False
    collision = _collision_tileset.get_collision(tile_index)
    if collision == COLLISION_NONE:
        return False
    if collision == COLLISION_SOLID:
        return True
    # POLYGON: sample the mask at the clamped contact pixel
    ts = _collision_tileset.tile_size
    lx = max(0, min(local_x, ts - 1))
    ly = max(0, min(local_y, ts - 1))
    return bool(_collision_tileset.collision_shapes[tile_index][ly * ts + lx])


def _tile_one_way(col: int, row: int) -> str:
    """Return the one-way passable direction of tile (col, row), or ONE_WAY_NONE."""
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
    """True if any tile in the column has a one-way arrow matching direction."""
    return any(_tile_one_way(col, r) == direction for r in range(t_row, b_row + 1))


def _scan_v_one_way(row: int, l_col: int, r_col: int, direction: str) -> bool:
    """True if any tile in the row has a one-way arrow matching direction."""
    return any(_tile_one_way(c, row) == direction for c in range(l_col, r_col + 1))


def _scan_h(col: int, t_row: int, b_row: int, edge_wx: float, mid_wy: float) -> bool:
    """Check if any tile in the vertical column (col, t_row..b_row) blocks a horizontal edge.

    edge_wx  — world x of the hitbox edge being pushed.
    mid_wy   — current player world y (used to derive the y-overlap per row).
    """
    local_x = int(edge_wx) % TILE_SIZE
    for r in range(t_row, b_row + 1):
        y_lo = max(int(mid_wy + HB_T), r * TILE_SIZE)
        y_hi = min(int(mid_wy + HB_B - 1), (r + 1) * TILE_SIZE - 1)
        for wy in range(y_lo, y_hi + 1):
            if _tile_solid_at(col, r, local_x, wy % TILE_SIZE):
                return True
    return False


def _scan_v(row: int, l_col: int, r_col: int, mid_wx: float, edge_wy: float) -> bool:
    """Check if any tile in the horizontal row (l_col..r_col, row) blocks a vertical edge.

    edge_wy  — world y of the hitbox edge being pushed.
    mid_wx   — current player world x (used to derive the x-overlap per column).
    """
    local_y = int(edge_wy) % TILE_SIZE
    for c in range(l_col, r_col + 1):
        x_lo = max(int(mid_wx + HB_L), c * TILE_SIZE)
        x_hi = min(int(mid_wx + HB_R - 1), (c + 1) * TILE_SIZE - 1)
        for wx in range(x_lo, x_hi + 1):
            if _tile_solid_at(c, row, wx % TILE_SIZE, local_y):
                return True
    return False


def _physics(dt: float) -> None:
    global _px, _py, _vx, _vy, _on_ground

    _vy = min(_vy + GRAVITY * dt, 400.0)

    # --- Horizontal movement ---
    # Capture pre-frame edges for one-way entry-direction checks.
    prev_right = _px + HB_R - 1
    prev_left  = _px + HB_L
    new_px = _px + _vx * dt
    t_row = max(0, int((_py + HB_T) / TILE_SIZE))
    b_row = max(0, int((_py + HB_B - 1) / TILE_SIZE))

    if _vx > 0:
        col = int((new_px + HB_R - 1) / TILE_SIZE)
        tile_left = col * TILE_SIZE
        blocked = _scan_h(col, t_row, b_row, new_px + HB_R - 1, _py)
        # ONE_WAY_LEFT arrow = passable going left → blocks rightward entry.
        if not blocked and prev_right < tile_left:
            blocked = _scan_h_one_way(col, t_row, b_row, ONE_WAY_LEFT)
        if blocked:
            new_px = tile_left - HB_R
            _vx = 0.0
    elif _vx < 0:
        col = int((new_px + HB_L) / TILE_SIZE)
        tile_right = (col + 1) * TILE_SIZE
        blocked = _scan_h(col, t_row, b_row, new_px + HB_L, _py)
        # ONE_WAY_RIGHT arrow = passable going right → blocks leftward entry.
        if not blocked and prev_left >= tile_right:
            blocked = _scan_h_one_way(col, t_row, b_row, ONE_WAY_RIGHT)
        if blocked:
            new_px = tile_right - HB_L
            _vx = 0.0

    if _scene:
        new_px = max(float(-HB_L), min(new_px, float(_scene.width - HB_R)))
    _px = new_px

    # --- Vertical movement ---
    prev_bottom = _py + HB_B
    prev_top    = _py + HB_T
    new_py = _py + _vy * dt
    l_col = max(0, int((_px + HB_L) / TILE_SIZE))
    r_col = int((_px + HB_R - 1) / TILE_SIZE)

    if _vy >= 0:  # falling or neutral
        row = int((new_py + HB_B) / TILE_SIZE)
        tile_top = row * TILE_SIZE
        blocked = _scan_v(row, l_col, r_col, _px, new_py + HB_B)
        # ONE_WAY_UP arrow = passable going up → blocks downward entry.
        if not blocked and prev_bottom <= tile_top:
            blocked = _scan_v_one_way(row, l_col, r_col, ONE_WAY_UP)
        if blocked:
            new_py = tile_top - HB_B
            _vy = 0.0
    else:  # rising — ceiling check
        row = max(0, int((new_py + HB_T) / TILE_SIZE))
        tile_bottom = (row + 1) * TILE_SIZE
        blocked = _scan_v(row, l_col, r_col, _px, new_py + HB_T)
        # ONE_WAY_DOWN arrow = passable going down → blocks upward entry.
        if not blocked and prev_top >= tile_bottom:
            blocked = _scan_v_one_way(row, l_col, r_col, ONE_WAY_DOWN)
        if blocked:
            new_py = tile_bottom - HB_T
            _vy = 0.0

    _py = new_py

    # Ground check: solid pixel or one-way-up tile directly below?
    gnd_row = int((_py + HB_B) / TILE_SIZE)
    _on_ground = (
        _scan_v(gnd_row, l_col, r_col, _px, _py + HB_B)
        or _scan_v_one_way(gnd_row, l_col, r_col, ONE_WAY_UP)
    )


# ---------------------------------------------------------------------------
# Public init / update / draw
# ---------------------------------------------------------------------------

def init(engine) -> None:
    global _scene, _collision_tileset, _renderer, _frames
    global _px, _py, _vx, _vy, _facing, _on_ground
    global _state, _prev_state, _anim_frame, _anim_elapsed
    global _attack_timer, _cam_x, _prev_jump, _prev_attack

    _px, _py = 34.0, 191.0
    _vx, _vy = 0.0, 0.0
    _facing, _on_ground = 1, False
    _state = _prev_state = "idle"
    _anim_frame, _anim_elapsed = 0, 0.0
    _attack_timer, _coyote_timer, _jump_buffer_timer = 0.0, 0.0, 0.0
    _cam_x = 0.0
    _prev_jump, _prev_attack = False, False
    _was_on_ground = False

    scene_path = ROOT / "scenes/level_01.tortuscene"
    _scene = load_scene(scene_path, project_root=ROOT)
    # Clear scene objects: we draw the player manually to support sprite flipping
    _scene.objects.clear()

    collision_layer = _scene.tile_layers[_scene.collision_tile_layer]
    if collision_layer.tileset:
        _collision_tileset = load_tileset(ROOT / collision_layer.tileset)
    else:
        _collision_tileset = None

    _renderer = SceneRenderer(ROOT)

    # Load palette from the idle sprite
    idle_spr = load_sprite(ROOT / "assets/sprites/mechaturtle_idle.tortusprite")
    pal = load_palette(palette_path(ROOT, idle_spr.palette))

    # Pre-bake all animation frames (normal + horizontally flipped for left-facing)
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


def update(dt: float) -> None:
    global _px, _py, _vx, _vy, _facing, _on_ground
    global _state, _prev_state, _anim_frame, _anim_elapsed
    global _attack_timer, _coyote_timer, _jump_buffer_timer
    global _cam_x, _prev_jump, _prev_attack, _was_on_ground

    keys = pygame.key.get_pressed()
    jump_held = keys[pygame.K_z] or keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]
    atk_held = keys[pygame.K_x] or keys[pygame.K_LSHIFT] or keys[pygame.K_c]
    left = keys[pygame.K_LEFT] or keys[pygame.K_a]
    right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

    jump_pressed = jump_held and not _prev_jump
    jump_released = not jump_held and _prev_jump
    atk_pressed = atk_held and not _prev_attack
    _prev_jump = jump_held
    _prev_attack = atk_held

    # Variable jump height: cut upward velocity on early release
    if jump_released and _vy < 0:
        _vy *= JUMP_CUT

    # Coyote time: grace period after leaving a ledge
    if _was_on_ground and not _on_ground and _vy >= 0:
        _coyote_timer = COYOTE_TIME
    if _coyote_timer > 0:
        _coyote_timer = max(0.0, _coyote_timer - dt)
    _was_on_ground = _on_ground

    # Jump buffer: remember a press that arrives just before landing
    if jump_pressed:
        _jump_buffer_timer = JUMP_BUFFER
    if _jump_buffer_timer > 0:
        _jump_buffer_timer = max(0.0, _jump_buffer_timer - dt)

    # Tick attack timer
    if _attack_timer > 0:
        _attack_timer = max(0.0, _attack_timer - dt)

    attacking = _attack_timer > 0

    # Start a new attack
    if atk_pressed and not attacking:
        _attack_timer = ATTACK_DUR
        attacking = True
        if _on_ground:
            _vx = 0.0   # lock horizontal on ground while punching

    # Horizontal input (suppressed on ground during attack)
    if not (attacking and _on_ground):
        if right:
            _vx = WALK_SPEED
            _facing = 1
        elif left:
            _vx = -WALK_SPEED
            _facing = -1
        else:
            _vx = 0.0

    # Jump: ground OR coyote window, with optional buffered press
    can_jump = _on_ground or _coyote_timer > 0
    if can_jump and _jump_buffer_timer > 0:
        _vy = JUMP_VEL
        _on_ground = False
        _coyote_timer = 0.0
        _jump_buffer_timer = 0.0

    _physics(dt)

    # Determine animation state
    new_state: str
    if attacking:
        new_state = "attack" if _on_ground else "air_attack"
    elif not _on_ground:
        new_state = "fall" if _vy >= 0 else "jump"
    elif _vx != 0:
        new_state = "walk"
    else:
        new_state = "idle"

    if new_state != _prev_state:
        _anim_frame = 0
        _anim_elapsed = 0.0
    _state = _prev_state = new_state

    # Advance animation frame
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

    # Smooth camera follow — keep player horizontally centered
    target_cam = _px - SCREEN_W / 2.0
    if _scene:
        target_cam = max(0.0, min(target_cam, float(_scene.width - SCREEN_W)))
    _cam_x += (target_cam - _cam_x) * min(1.0, dt * 8.0)


def draw(engine) -> None:
    if _renderer and _scene:
        frame = _renderer.render(_scene, camera_x=int(_cam_x), camera_y=0)
        engine.blit(frame, (0, 0))
    else:
        engine.clear((12, 18, 32))

    # Draw mechaturtle at screen position
    anim_data = _frames.get(_state)
    if anim_data:
        normal, flipped = anim_data
        pool = flipped if _facing == -1 else normal
        fi = _anim_frame % len(pool)
        surf = pool[fi]
        screen_x = int(_px - 18 - _cam_x)
        screen_y = int(_py - 31)
        engine.blit(surf, (screen_x, screen_y))

    # HUD: state debug (remove when polished)
    engine.text(f"{_state}", 4, 4, (200, 220, 255), 8)
