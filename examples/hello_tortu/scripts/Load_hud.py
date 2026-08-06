"""Script for GUI layer Load_hud — the save-slot picker shown from the
title screen's Load Game item (see load_scene.tortuscene, main.py's "load"
state).

Runs as Load_hud.tortuguilayer's own instance script (an isolated module,
see tortoisengine/instance_scripts.py). Load_hud.tortuguilayer is authored as
a 3-panel wide canvas (pick a slot / load-or-erase actions / a "select
console save" panel) but only panel 1 — the slot picker plus Back — is
wired up here; the other two panels are future work (erase, "move
console") and are simply never scrolled to. Enter on an occupied slot opens
the Load_areyousure.tortuguilayer popup for a Yes/No confirm, driven
directly by this script via its explicit gui_layer_path (same technique as
Save_hud.py's Save_overwrite popup). Enter on an empty slot is a no-op —
there's nothing to load. Yes resets game_state to fresh lives/energy,
restores the slot's saved gears, and asks load_scene.py to move on to the
saved current_lvl via instance_api.request_scene_transition(). Enter on
Back returns to the title screen.
"""

from pathlib import Path

import pygame

from tortoisengine import instance_api
from scripts import audio_settings, game_state, save_system

ROOT = Path(__file__).parent.parent

LOAD_AREYOUSURE_PATH = "assets/gui/Load_areyousure.tortuguilayer"
TITLE_SCENE = "scenes/title.tortuscene"

SLOT_LABELS = ("slot_label_1", "slot_label_2", "slot_label_3")
BACK_LABEL = "back_label"
MENU_ITEMS = SLOT_LABELS + (BACK_LABEL,)
CURSOR = "select_arrow"
# Matches select_arrow's placed (x, y) in Load_hud.tortuguilayer relative to
# slot_label_1, the item it was authored pointing at.
CURSOR_OFFSET = (-25, 9)

OVERWRITE_ITEMS = ("yes_label", "no_label")
# Matches select_arrow's placed (x, y) in Load_areyousure.tortuguilayer
# relative to no_label — the popup was authored defaulting to "No".
OVERWRITE_CURSOR_OFFSET = (-20, 7)

# Same accent pause_menu.py/Save_hud.py use to highlight a selection.
HIGHLIGHT_COLOR = 18

_menu_index = 0
_confirm_active = False
_confirm_slot = 0
_confirm_index = 1  # 0 = yes, 1 = no
_prev_up = False
_prev_down = False
_prev_left = False
_prev_right = False
_prev_enter = False

_sfx_navigate: pygame.mixer.Sound | None = None
_sfx_accept: pygame.mixer.Sound | None = None


def init(engine) -> None:
    global _prev_up, _prev_down, _prev_left, _prev_right, _prev_enter
    global _sfx_navigate, _sfx_accept
    try:
        _sfx_navigate = audio_settings.load_sound("assets/audio/Menu_Navigate.ogg")
        _sfx_accept = audio_settings.load_sound("assets/audio/MenuAccept.ogg")
    except Exception:
        pass
    _refresh_slot_labels()
    _select_menu(0, 0)
    instance_api.set_gui_layer_visible(LOAD_AREYOUSURE_PATH, False)
    # The Enter that picked "Load Game" on the title screen is still
    # physically held on this same frame — seed the edge-detectors so it
    # isn't also read as an immediate confirm on slot 1 (see pause_menu.py's
    # _reset_menu for the same idiom).
    keys = pygame.key.get_pressed()
    _prev_up, _prev_down = keys[pygame.K_UP], keys[pygame.K_DOWN]
    _prev_left, _prev_right = keys[pygame.K_LEFT], keys[pygame.K_RIGHT]
    _prev_enter = keys[pygame.K_RETURN]


def _slot_text(index: int, data: dict | None) -> str:
    if data is None:
        return f"[<[slot]>] {index} - [<[empty]>]"
    return f"[<[slot]>] {index}"


def _refresh_slot_labels() -> None:
    slots = save_system.read_slots()
    for i, label_id in enumerate(SLOT_LABELS):
        instance_api.set_gui_text_label_text(SELF_ID, label_id, _slot_text(i + 1, slots[i]))


def _move_cursor(label_id: str) -> None:
    pos = instance_api.gui_text_label_position(SELF_ID, label_id)
    if pos is None:
        return
    instance_api.set_gui_object_position(
        SELF_ID, CURSOR, pos[0] + CURSOR_OFFSET[0], pos[1] + CURSOR_OFFSET[1]
    )


def _select_menu(old_index: int, new_index: int) -> None:
    global _menu_index
    _menu_index = new_index
    instance_api.set_gui_text_label_color(SELF_ID, MENU_ITEMS[old_index], -1)
    instance_api.set_gui_text_label_color(SELF_ID, MENU_ITEMS[new_index], HIGHLIGHT_COLOR)
    _move_cursor(MENU_ITEMS[new_index])


def _move_overwrite_cursor(label_id: str) -> None:
    pos = instance_api.gui_text_label_position(LOAD_AREYOUSURE_PATH, label_id)
    if pos is None:
        return
    instance_api.set_gui_object_position(
        LOAD_AREYOUSURE_PATH, CURSOR,
        pos[0] + OVERWRITE_CURSOR_OFFSET[0], pos[1] + OVERWRITE_CURSOR_OFFSET[1],
    )


def _select_overwrite(old_index: int, new_index: int) -> None:
    global _confirm_index
    _confirm_index = new_index
    instance_api.set_gui_text_label_color(LOAD_AREYOUSURE_PATH, OVERWRITE_ITEMS[old_index], -1)
    instance_api.set_gui_text_label_color(
        LOAD_AREYOUSURE_PATH, OVERWRITE_ITEMS[new_index], HIGHLIGHT_COLOR
    )
    _move_overwrite_cursor(OVERWRITE_ITEMS[new_index])


def _start_confirm(slot_index: int) -> None:
    global _confirm_active, _confirm_slot
    _confirm_active = True
    _confirm_slot = slot_index
    instance_api.set_gui_layer_visible(LOAD_AREYOUSURE_PATH, True)
    _select_overwrite(_confirm_index, 1)  # default to "no"


def _end_confirm() -> None:
    global _confirm_active
    _confirm_active = False
    instance_api.set_gui_layer_visible(LOAD_AREYOUSURE_PATH, False)


def _do_load(slot_index: int) -> None:
    data = save_system.read_slot(slot_index)
    if data is None:
        return
    gamedata = data.get("gamedata", {})
    game_state.reset()
    game_state.gears = gamedata.get("gears", 0)
    current_lvl = gamedata.get("current_lvl", "level_01")
    instance_api.request_scene_transition(f"scenes/{current_lvl}.tortuscene")


def update(dt: float) -> None:
    global _prev_up, _prev_down, _prev_left, _prev_right, _prev_enter

    keys = pygame.key.get_pressed()
    up_held, down_held = keys[pygame.K_UP], keys[pygame.K_DOWN]
    left_held, right_held = keys[pygame.K_LEFT], keys[pygame.K_RIGHT]
    enter_held = keys[pygame.K_RETURN]
    up_pressed = up_held and not _prev_up
    down_pressed = down_held and not _prev_down
    left_pressed = left_held and not _prev_left
    right_pressed = right_held and not _prev_right
    enter_pressed = enter_held and not _prev_enter
    _prev_up, _prev_down = up_held, down_held
    _prev_left, _prev_right = left_held, right_held
    _prev_enter = enter_held

    if _confirm_active:
        if left_pressed or right_pressed:
            _select_overwrite(_confirm_index, 0 if _confirm_index == 1 else 1)
            if _sfx_navigate:
                _sfx_navigate.play()
        if enter_pressed:
            if _sfx_accept:
                _sfx_accept.play()
            if _confirm_index == 0:
                _do_load(_confirm_slot)
            _end_confirm()
        return

    if up_pressed or down_pressed:
        old_index = _menu_index
        new_index = (_menu_index + (1 if down_pressed else -1)) % len(MENU_ITEMS)
        _select_menu(old_index, new_index)
        if _sfx_navigate:
            _sfx_navigate.play()

    if enter_pressed:
        if _menu_index < len(SLOT_LABELS):
            slot_index = _menu_index + 1
            if save_system.read_slot(slot_index) is not None:
                if _sfx_accept:
                    _sfx_accept.play()
                _start_confirm(slot_index)
        else:
            if _sfx_accept:
                _sfx_accept.play()
            instance_api.request_scene_transition(TITLE_SCENE)


def draw(engine) -> None:
    pass
