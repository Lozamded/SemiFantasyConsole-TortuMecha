"""Runtime query API shared by per-instance object scripts.

Object scripts (see instance_scripts.py) never touch the Scene or the
player controller directly — they go through these functions instead, so
the same script keeps working whether it runs in TortuStudio's preview,
TortuPlayer, or an exported cart.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from tortuengine import localization
from tortuengine.object import load_object
from tortuengine.scene import Scene
from tortuengine.sprite import load_sprite
from tortuengine.tileset import COLLISION_NONE, Tileset, load_tileset

if TYPE_CHECKING:
    from tortuengine.gui_layer import GuiLayer

_scene: Scene | None = None
_project_root: Path | None = None
_player_x: float = 0.0
_player_y: float = 0.0
_player_crouching: bool = False
# World-space (left, right, top, bottom) of the player's current active
# hitbox — crouch-aware, since it swaps between stand/crouch bounds.
_player_hitbox: tuple[float, float, float, float] | None = None
_player_energy: tuple[float, float] | None = None  # (current, max)
_player_lives: tuple[int, int] | None = None  # (current, max)
_player_gears: int | None = None
_tileset_cache: dict[str, Tileset] = {}
# Renderer-owned GuiLayer loader (rel_path -> live, cached GuiLayer), so
# scripts can drive HUD elements (health bars, pip counters) without
# instance_api duplicating gui-layer loading/caching itself.
_gui_layer_loader: Callable[[str], "GuiLayer | None"] | None = None


def bind_scene(scene: Scene, project_root: Path | None = None) -> None:
    """Call once when a scene is loaded, before any instance script runs."""
    global _scene, _project_root
    if scene is not _scene:
        # A genuinely new Scene (fresh load_scene() call, e.g. on respawn) —
        # drop per-instance runtime state keyed by instance id, since ids are
        # reused across reloads but the old overrides no longer apply to the
        # freshly-loaded objects. Same-scene re-binds (every frame) must not
        # hit this, or e.g. set_object_solid() overrides would be wiped mid-tick.
        _solid_overrides.clear()
    _scene = scene
    if project_root is not None:
        _project_root = project_root
        localization.load(project_root)


def project_root() -> Path | None:
    """The current project (or cart) root — e.g. to resolve a dialogues/*.json path."""
    return _project_root


def set_language(code: str) -> None:
    """Switch the active language (must be one of available_languages())."""
    localization.set_language(code)


def get_language() -> str:
    return localization.get_language()


def available_languages() -> list[str]:
    return localization.available_languages()


def translate(key: str) -> str:
    """Look up a languages/strings.csv key directly (for script-built strings)."""
    return localization.translate(key)


def set_player_position(x: float, y: float) -> None:
    """Call every frame from the player controller script."""
    global _player_x, _player_y
    _player_x, _player_y = x, y


def player_position() -> tuple[float, float]:
    return _player_x, _player_y


def set_player_crouching(crouching: bool) -> None:
    """Call every frame from the player controller script."""
    global _player_crouching
    _player_crouching = crouching


def player_is_crouching() -> bool:
    return _player_crouching


def set_player_hitbox(left: float, right: float, top: float, bottom: float) -> None:
    """Call every frame from the player controller script with its current active hitbox."""
    global _player_hitbox
    _player_hitbox = (left, right, top, bottom)


def player_hitbox() -> tuple[float, float, float, float] | None:
    return _player_hitbox


def set_player_energy(current: float, max_energy: float) -> None:
    """Call every frame from the player controller script — drives HUD energy pips."""
    global _player_energy
    _player_energy = (current, max_energy)


def player_energy() -> tuple[float, float] | None:
    return _player_energy


def set_player_lives(current: int, max_lives: int) -> None:
    """Call every frame from the player controller script — drives the HUD lives counter."""
    global _player_lives
    _player_lives = (current, max_lives)


def player_lives() -> tuple[int, int] | None:
    return _player_lives


def set_player_gears(count: int) -> None:
    """Call every frame from the player controller script — drives the HUD gears counter."""
    global _player_gears
    _player_gears = count


def player_gears() -> int | None:
    return _player_gears


def bind_gui_layers(loader: Callable[[str], "GuiLayer | None"]) -> None:
    """Call once per scene load with a callable(rel_path) -> GuiLayer | None."""
    global _gui_layer_loader
    _gui_layer_loader = loader


def _find_gui_element(gui_layer_path: str, element_id: str, attr: str):
    if _gui_layer_loader is None or not gui_layer_path or not element_id:
        return None
    layer = _gui_layer_loader(gui_layer_path)
    if layer is None:
        return None
    for element in getattr(layer, attr):
        if element.id == element_id:
            return element
    return None


def set_gui_tiled_rect_number(
    gui_layer_path: str, rect_id: str, number: float, max_number: float | None = None
) -> None:
    """Set a `.tortuguilayer` tiled rect's current (and optionally max) value.

    The rendered fill fraction is always `number / max_number` — e.g. a
    health bar tracks current/max HP directly instead of a raw 0..1 fraction.
    """
    rect = _find_gui_element(gui_layer_path, rect_id, "tiled_rects")
    if rect is not None:
        rect.number = max(0.0, number)
        if max_number is not None:
            rect.max_number = max(0.0, max_number)


def gui_tiled_rect_number(gui_layer_path: str, rect_id: str) -> tuple[float, float] | None:
    """Return (number, max_number), or None if the rect isn't found."""
    rect = _find_gui_element(gui_layer_path, rect_id, "tiled_rects")
    return (rect.number, rect.max_number) if rect is not None else None


def set_gui_repeat_sprite_number(
    gui_layer_path: str, sprite_id: str, number: int, max_number: int | None = None
) -> None:
    """Set a `.tortuguilayer` repeat sprite's current (and optionally max) slot count."""
    rep = _find_gui_element(gui_layer_path, sprite_id, "repeat_sprites")
    if rep is not None:
        rep.number = max(0, number)
        if max_number is not None:
            rep.max_number = max(0, max_number)


def gui_repeat_sprite_number(gui_layer_path: str, sprite_id: str) -> tuple[int, int] | None:
    """Return (number, max_number), or None if the sprite isn't found."""
    rep = _find_gui_element(gui_layer_path, sprite_id, "repeat_sprites")
    return (rep.number, rep.max_number) if rep is not None else None


def set_gui_text_label_text(gui_layer_path: str, label_id: str, text: str) -> None:
    """Set a `.tortuguilayer` text label's displayed text — e.g. a lives counter."""
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    if label is not None:
        label.text = text


def gui_text_label_text(gui_layer_path: str, label_id: str) -> str | None:
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    return label.text if label is not None else None


def set_gui_text_label_color(gui_layer_path: str, label_id: str, color_index: int) -> None:
    """Override a `.tortufont` label's ink color — e.g. highlight a selected menu item.

    No-op for `.tortuspritefont` labels (pre-colored bitmaps, see GuiTextLabel.color_index).
    """
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    if label is not None:
        label.color_index = color_index


def gui_text_label_color(gui_layer_path: str, label_id: str) -> int | None:
    """Return the label's color override, or -1 if it's using the font's baked color."""
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    return label.color_index if label is not None else None


def set_gui_text_label_scale(gui_layer_path: str, label_id: str, scale: float) -> None:
    """Resize a label's already-baked glyphs — e.g. grow a selected menu item."""
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    if label is not None:
        label.scale = max(0.1, scale)


def gui_text_label_scale(gui_layer_path: str, label_id: str) -> float | None:
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    return label.scale if label is not None else None


def gui_text_label_position(gui_layer_path: str, label_id: str) -> tuple[int, int] | None:
    """Return a label's (x, y) inside its GUI layer — e.g. to place a selection cursor."""
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    return (label.x, label.y) if label is not None else None


def set_gui_text_label_visible(gui_layer_path: str, label_id: str, visible: bool) -> None:
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    if label is not None:
        label.visible = visible


def gui_text_label_visible(gui_layer_path: str, label_id: str) -> bool | None:
    label = _find_gui_element(gui_layer_path, label_id, "text_labels")
    return label.visible if label is not None else None


def set_gui_object_position(gui_layer_path: str, object_id: str, x: int, y: int) -> None:
    """Move a placed `.tortuguilayer` object — e.g. a menu selection cursor."""
    obj = _find_gui_element(gui_layer_path, object_id, "objects")
    if obj is not None:
        obj.x, obj.y = x, y


def gui_object_position(gui_layer_path: str, object_id: str) -> tuple[int, int] | None:
    obj = _find_gui_element(gui_layer_path, object_id, "objects")
    return (obj.x, obj.y) if obj is not None else None


def set_gui_object_visible(gui_layer_path: str, object_id: str, visible: bool) -> None:
    obj = _find_gui_element(gui_layer_path, object_id, "objects")
    if obj is not None:
        obj.visible = visible


def gui_object_visible(gui_layer_path: str, object_id: str) -> bool | None:
    obj = _find_gui_element(gui_layer_path, object_id, "objects")
    return obj.visible if obj is not None else None


def set_gui_layer_scroll(gui_layer_path: str, x: int, y: int = 0) -> None:
    """Pan a GUI layer's whole canvas — e.g. sliding between two panels laid
    out side by side on one wide `.tortuguilayer` (see pause_menu.tortuguilayer).
    Not persisted; resets to (0, 0) whenever the layer is freshly loaded.
    """
    if _gui_layer_loader is None or not gui_layer_path:
        return
    layer = _gui_layer_loader(gui_layer_path)
    if layer is not None:
        layer.scroll_x, layer.scroll_y = x, y


def gui_layer_scroll(gui_layer_path: str) -> tuple[int, int] | None:
    if _gui_layer_loader is None or not gui_layer_path:
        return None
    layer = _gui_layer_loader(gui_layer_path)
    return (layer.scroll_x, layer.scroll_y) if layer is not None else None


def _find_scene_gui_layer(gui_layer_path: str):
    if _scene is None or not gui_layer_path:
        return None
    for g in _scene.gui_layers:
        if g.gui_layer == gui_layer_path:
            return g
    return None


def set_gui_layer_visible(gui_layer_path: str, visible: bool) -> None:
    """Show/hide an entire GUI layer slot in the current scene by its asset path."""
    scene_gui = _find_scene_gui_layer(gui_layer_path)
    if scene_gui is not None:
        scene_gui.visible = visible


def is_gui_layer_visible(gui_layer_path: str) -> bool | None:
    scene_gui = _find_scene_gui_layer(gui_layer_path)
    return scene_gui.visible if scene_gui is not None else None


_game_paused: bool = False


def set_game_paused(paused: bool) -> None:
    """Freeze/unfreeze gameplay — the level script checks this every frame."""
    global _game_paused
    _game_paused = paused


def is_game_paused() -> bool:
    return _game_paused


_dialogue_active: bool = False
_dialogue_request: str = ""


def request_dialogue(path: str) -> None:
    """Ask the dialog GUI layer's script to start showing `path` (a dialogues/*.json
    asset, project-relative). No-op if a dialogue is already active."""
    global _dialogue_request
    if not _dialogue_active:
        _dialogue_request = path


def take_dialogue_request() -> str:
    """Consume and clear the pending dialogue request, if any — called by the
    dialog GUI layer's own script each frame it isn't already showing one."""
    global _dialogue_request
    path, _dialogue_request = _dialogue_request, ""
    return path


def set_dialogue_active(active: bool) -> None:
    """The dialog GUI layer's script calls this once it starts/finishes showing a dialogue."""
    global _dialogue_active
    _dialogue_active = active


def is_dialogue_active() -> bool:
    return _dialogue_active


_object_hop_request_id: str = ""


def request_object_hop(instance_id: str) -> None:
    """Ask `instance_id`'s own script to play a small cosmetic hop next update —
    e.g. a dialogue `end_action` reacting to a player choice (see
    dialogue_vars.action_Do_DR2Action)."""
    global _object_hop_request_id
    _object_hop_request_id = instance_id


def take_object_hop_request(instance_id: str) -> bool:
    """True once for the `instance_id` a hop was requested for; consumes it."""
    global _object_hop_request_id
    if _object_hop_request_id and _object_hop_request_id == instance_id:
        _object_hop_request_id = ""
        return True
    return False


def _find(instance_id: str):
    if not _scene or not instance_id:
        return None
    for inst in _scene.objects:
        if inst.id == instance_id:
            return inst
    return None


def get_position(instance_id: str) -> tuple[float, float] | None:
    inst = _find(instance_id)
    return (inst.x, inst.y) if inst else None


def set_position(instance_id: str, x: float, y: float) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.x, inst.y = x, y


def set_animation(instance_id: str, animation: str) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.animation = animation


def prefab_positions(prefab: str, exclude_id: str = "") -> list[tuple[float, float]]:
    """World positions of every enabled scene object instancing the given prefab path.

    Pass `exclude_id` (typically SELF_ID) to leave out one instance — e.g. so a script
    can find *other* instances of its own prefab without matching itself.
    """
    if not _scene:
        return []
    return [
        (inst.x, inst.y) for inst in _scene.objects
        if inst.prefab == prefab and inst.enabled and (not exclude_id or inst.id != exclude_id)
    ]


def is_visible(instance_id: str) -> bool:
    inst = _find(instance_id)
    return inst.visible if inst else False


def set_visible(instance_id: str, visible: bool) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.visible = visible


def custom_var(instance_id: str, name: str, default: object = None) -> object:
    """Read a custom-variable value for a scene instance.

    Returns the per-instance override set in TortuStudio (SceneObject
    .custom_var_overrides), or `default` if the instance has no override
    for this variable — callers typically pass the prefab's declared
    default (see the CUSTOMVAR_*_DEFAULT constant in the object's
    generated _auto.py module).
    """
    inst = _find(instance_id)
    if inst is None:
        return default
    return inst.custom_var_overrides.get(name, default)


def is_enabled(instance_id: str) -> bool:
    """False means the instance is off — skip it in collision checks too, not just rendering."""
    inst = _find(instance_id)
    return inst.enabled if inst else False


def set_enabled(instance_id: str, enabled: bool) -> None:
    inst = _find(instance_id)
    if inst is not None:
        inst.enabled = enabled


def _active_collision_tileset() -> Tileset | None:
    if _scene is None or _project_root is None:
        return None
    layer = _scene.tile_layers[_scene.collision_tile_layer]
    if not layer.tileset:
        return None
    cached = _tileset_cache.get(layer.tileset)
    if cached is not None:
        return cached
    path = (_project_root / layer.tileset).resolve()
    if not path.is_file():
        return None
    tileset = load_tileset(path)
    _tileset_cache[layer.tileset] = tileset
    return tileset


def tile_solid_at(x: float, y: float) -> bool:
    """True if the world pixel (x, y) lands on a solid tile in the scene's active collision layer."""
    if _scene is None:
        return False
    tileset = _active_collision_tileset()
    if tileset is None:
        return False
    layer = _scene.tile_layers[_scene.collision_tile_layer]
    tile_size = tileset.tile_size
    cols = _scene.width // tile_size
    col, row = int(x // tile_size), int(y // tile_size)
    if col < 0 or col >= cols or row < 0:
        return False
    idx = row * cols + col
    if idx >= len(layer.tiles):
        return False
    tile_index = layer.tiles[idx]
    if tile_index < 0:
        return False
    return tileset.get_collision(tile_index) != COLLISION_NONE


# Per-prefab (obj.solid, collider bounds) — resolved once from each prefab's
# own .tortuobject + default sprite, then reused for every placed instance.
# Bounds are (left, right, top, bottom) offsets from the instance's origin.
_prefab_solid_cache: dict[str, tuple[bool, tuple[int, int, int, int] | None]] = {}

# Per-instance solidity override, set via set_object_solid() — e.g. a
# brick_block instance clears this the moment it starts breaking, while
# staying enabled so its own break-timer update() keeps running. Cleared on
# a genuine scene reload (see bind_scene) since instance ids get reused.
_solid_overrides: dict[str, bool] = {}


def _prefab_solid_info(prefab: str) -> tuple[bool, tuple[int, int, int, int] | None]:
    cached = _prefab_solid_cache.get(prefab)
    if cached is not None:
        return cached
    info: tuple[bool, tuple[int, int, int, int] | None] = (False, None)
    if _project_root is not None and prefab:
        obj_path = (_project_root / prefab).resolve()
        if obj_path.is_file():
            obj = load_object(obj_path)
            bounds = None
            if obj.colliders:
                sprite_path = (_project_root / obj.default_sprite).resolve()
                if sprite_path.is_file():
                    sprite = load_sprite(sprite_path)
                    res = [c.resolved(sprite.pixel_width, sprite.pixel_height) for c in obj.colliders]
                    ox, oy = obj.origin.x, obj.origin.y
                    bounds = (
                        min(x for x, y, w, h in res) - ox,
                        max(x + w for x, y, w, h in res) - ox,
                        min(y for x, y, w, h in res) - oy,
                        max(y + h for x, y, w, h in res) - oy,
                    )
            info = (obj.solid, bounds)
    _prefab_solid_cache[prefab] = info
    return info


def _iter_solid_rects(exclude_id: str = ""):
    """Yield (left, right, top, bottom) world-space AABBs of every enabled scene
    object instance that's currently solid — either its prefab's own `solid`
    flag, or a per-instance override set via set_object_solid()."""
    if _scene is None:
        return
    for inst in _scene.objects:
        if not inst.enabled or (exclude_id and inst.id == exclude_id):
            continue
        declared_solid, bounds = _prefab_solid_info(inst.prefab)
        if bounds is None or not _solid_overrides.get(inst.id, declared_solid):
            continue
        l, r, t, b = bounds
        yield (inst.x + l, inst.x + r, inst.y + t, inst.y + b)


def object_solid_at(x: float, y: float, exclude_id: str = "") -> bool:
    """True if the world pixel (x, y) lands inside a currently-solid scene object.
    Mirrors tile_solid_at() but for placed objects (e.g. a destructible
    brick_block wall). Pass exclude_id (typically SELF_ID) to skip one instance."""
    return any(l <= x < r and t <= y < b for l, r, t, b in _iter_solid_rects(exclude_id))


def solid_object_rects(
    l: float, r: float, t: float, b: float, exclude_id: str = ""
) -> list[tuple[float, float, float, float]]:
    """The exact (left, right, top, bottom) world-space AABBs of every currently-
    solid scene object intersecting the given rect.

    Unlike object_solid_at() (a single-pixel point query), this returns each
    instance's real edges — needed so a swept collision resolver can snap a
    moving body to the object's actual boundary instead of a tile-grid line,
    which is wrong for objects that aren't tile-aligned (see mechaturtle_player
    .py's _physics(), which combines this with its tile scan)."""
    return [
        (ol, orr, ot, ob) for ol, orr, ot, ob in _iter_solid_rects(exclude_id)
        if ol < r and orr > l and ot < b and ob > t
    ]


def set_object_solid(instance_id: str, solid: bool | None) -> None:
    """Override a scene instance's solidity for object_solid_at(), independent of
    enabled/visible. Pass None to fall back to the prefab's own `solid` flag."""
    if solid is None:
        _solid_overrides.pop(instance_id, None)
    else:
        _solid_overrides[instance_id] = solid
