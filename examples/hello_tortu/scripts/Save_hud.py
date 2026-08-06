"""Script for GUI layer Save_hud — the save-slot picker shown after a level
finishes (see save_scene.tortuscene, main.py's "save" state).

Runs as Save_hud.tortuguilayer's own instance script (an isolated module,
see tortuengine/instance_scripts.py). Layout is 3 slot rows + a Continue
row, moved between with Up/Down and select_arrow (same convention as
pause_menu.py/dialoguebox.py). Enter on an empty slot saves immediately; on
an occupied slot it opens the Save_overwrite.tortuguilayer popup for a
Yes/No confirm, driven directly by this script via its explicit
gui_layer_path — the same way mechaturtle_player.py drives the HUD from
outside its own layer — rather than giving the popup its own script. Enter
on Continue skips saving and asks save_scene.py to move on to level_02 via
instance_api.request_scene_transition().
"""

from pathlib import Path

import pygame

from tortuengine import instance_api, localization
from scripts import audio_settings, save_system, save_vars

ROOT = Path(__file__).parent.parent

SAVE_OVERWRITE_PATH = "assets/gui/Save_overwrite.tortuguilayer"
NEXT_LEVEL_ID = "level_02"
NEXT_LEVEL_SCENE = "scenes/level_02.tortuscene"

SLOT_LABELS = ("slot_label_1", "slot_label_2", "slot_label_3")
CONTINUE_LABEL = "continue_label"
MENU_ITEMS = SLOT_LABELS + (CONTINUE_LABEL,)
SAVING_LABEL = "saving_label"
CURSOR = "select_arrow"
# Matches select_arrow's placed (x, y) in Save_hud.tortuguilayer relative to
# slot_label_1, the item it was authored pointing at.
CURSOR_OFFSET = (-19, 8)

OVERWRITE_ITEMS = ("yes_label", "no_label")
# Matches select_arrow's placed (x, y) in Save_overwrite.tortuguilayer
# relative to no_label — the popup was authored defaulting to "No".
OVERWRITE_CURSOR_OFFSET = (-20, 7)

# Same accent pause_menu.py/dialoguebox.py use to highlight a selection.
HIGHLIGHT_COLOR = 18
SAVING_FLASH_DUR = 0.6

_menu_index = 0
_has_saved = False  # once true, the Continue label drops its "without Save" caveat
_confirm_active = False
_confirm_slot = 0
_confirm_index = 1  # 0 = yes, 1 = no
_saving_timer = 0.0
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
    localization.bind_variables(lambda name: getattr(save_vars, name, None))
    _refresh_slot_labels()
    _select_menu(0, 0)
    instance_api.set_gui_layer_visible(SAVE_OVERWRITE_PATH, False)
    # Whatever key just triggered the level finish (or a prior scene's
    # confirm) may still be physically held on this same frame — seed the
    # edge-detectors so it isn't also read as a menu move or confirm (see
    # pause_menu.py's _reset_menu for the same idiom).
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
    pos = instance_api.gui_text_label_position(SAVE_OVERWRITE_PATH, label_id)
    if pos is None:
        return
    instance_api.set_gui_object_position(
        SAVE_OVERWRITE_PATH, CURSOR,
        pos[0] + OVERWRITE_CURSOR_OFFSET[0], pos[1] + OVERWRITE_CURSOR_OFFSET[1],
    )


def _select_overwrite(old_index: int, new_index: int) -> None:
    global _confirm_index
    _confirm_index = new_index
    instance_api.set_gui_text_label_color(SAVE_OVERWRITE_PATH, OVERWRITE_ITEMS[old_index], -1)
    instance_api.set_gui_text_label_color(
        SAVE_OVERWRITE_PATH, OVERWRITE_ITEMS[new_index], HIGHLIGHT_COLOR
    )
    _move_overwrite_cursor(OVERWRITE_ITEMS[new_index])


def _start_confirm(slot_index: int) -> None:
    global _confirm_active, _confirm_slot
    _confirm_active = True
    _confirm_slot = slot_index
    save_vars.current_slot = slot_index
    instance_api.set_gui_layer_visible(SAVE_OVERWRITE_PATH, True)
    _select_overwrite(_confirm_index, 1)  # default to "no"


def _end_confirm() -> None:
    global _confirm_active
    _confirm_active = False
    instance_api.set_gui_layer_visible(SAVE_OVERWRITE_PATH, False)


def _do_save(slot_index: int) -> None:
    global _saving_timer, _has_saved
    save_system.write_slot(slot_index, NEXT_LEVEL_ID)
    _refresh_slot_labels()
    instance_api.set_gui_text_label_visible(SELF_ID, SAVING_LABEL, True)
    _saving_timer = SAVING_FLASH_DUR
    if not _has_saved:
        _has_saved = True
        instance_api.set_gui_text_label_text(SELF_ID, CONTINUE_LABEL, "[<[continue]>]")


def update(dt: float) -> None:
    global _prev_up, _prev_down, _prev_left, _prev_right, _prev_enter, _saving_timer

    if _saving_timer > 0.0:
        _saving_timer -= dt
        if _saving_timer <= 0.0:
            instance_api.set_gui_text_label_visible(SELF_ID, SAVING_LABEL, False)
        return

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
                _do_save(_confirm_slot)
            _end_confirm()
        return

    if up_pressed or down_pressed:
        old_index = _menu_index
        new_index = (_menu_index + (1 if down_pressed else -1)) % len(MENU_ITEMS)
        _select_menu(old_index, new_index)
        if _sfx_navigate:
            _sfx_navigate.play()

    if enter_pressed:
        if _sfx_accept:
            _sfx_accept.play()
        if _menu_index < len(SLOT_LABELS):
            slot_index = _menu_index + 1
            slots = save_system.read_slots()
            if slots[_menu_index] is None:
                _do_save(slot_index)
            else:
                _start_confirm(slot_index)
        else:
            instance_api.request_scene_transition(NEXT_LEVEL_SCENE)


def draw(engine) -> None:
    pass
