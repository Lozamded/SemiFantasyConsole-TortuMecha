"""Script for GUI layer title_hud — the title screen's main menu
(Start Game / Load Game / Language).

Runs as title_hud.tortuguilayer's own instance script (an isolated module,
see tortoisengine/instance_scripts.py). Up/Down move select_arrow between the
three rows (same convention as pause_menu.py/Save_hud.py). Enter on Start
requests a transition straight to level_01 — title.py reads that specific
path as "begin a new game" (see main.py's title-state branch) rather than a
generic scene switch. Enter on Load requests a transition to load_scene.
Left/Right on the Language row cycle the active language in place, exactly
like pause_menu.py's options screen — no Enter needed.
"""

from pathlib import Path

import pygame

from tortoisengine import instance_api, localization
from scripts import audio_settings

ROOT = Path(__file__).parent.parent

START_SCENE = "scenes/level_01.tortuscene"
LOAD_SCENE = "scenes/load_scene.tortuscene"

START_LABEL = "start_label"
LOAD_LABEL = "load_label"
LANGUAGE_LABEL = "language_label"
MENU_ITEMS = (START_LABEL, LOAD_LABEL, LANGUAGE_LABEL)
CURSOR = "select_arrow"
# Matches select_arrow's placed (x, y) in title_hud.tortuguilayer relative to
# start_label, the item it was authored pointing at.
CURSOR_OFFSET = (-20, 7)

# Language names are shown in their own language regardless of the current
# UI language (a convention, not a languages/strings.csv lookup) — same
# choice pause_menu.py makes for its own language row.
LANGUAGE_NAMES = {"en": "English", "es": "Espanol"}

# Same accent pause_menu.py/Save_hud.py use to highlight a selection.
HIGHLIGHT_COLOR = 18

_menu_index = 0
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
    _update_language_label()
    _select_menu(0, 0)
    # Whatever key just brought us back to the title screen (e.g. Enter on
    # Load_hud's Back item) is often still physically held on this same
    # frame — seed the edge-detectors so it isn't also read as a menu move
    # or confirm (see pause_menu.py's _reset_menu for the same idiom).
    keys = pygame.key.get_pressed()
    _prev_up, _prev_down = keys[pygame.K_UP], keys[pygame.K_DOWN]
    _prev_left, _prev_right = keys[pygame.K_LEFT], keys[pygame.K_RIGHT]
    _prev_enter = keys[pygame.K_RETURN]


def _update_language_label() -> None:
    code = instance_api.get_language()
    prefix = localization.translate("option_2_language")
    instance_api.set_gui_text_label_text(
        SELF_ID, LANGUAGE_LABEL, f"{prefix} {LANGUAGE_NAMES.get(code, code)}"
    )


def _cycle_language(step: int) -> None:
    langs = instance_api.available_languages()
    if not langs:
        return
    current = instance_api.get_language()
    index = langs.index(current) if current in langs else 0
    instance_api.set_language(langs[(index + step) % len(langs)])
    _update_language_label()


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

    if up_pressed or down_pressed:
        old_index = _menu_index
        new_index = (_menu_index + (1 if down_pressed else -1)) % len(MENU_ITEMS)
        _select_menu(old_index, new_index)
        if _sfx_navigate:
            _sfx_navigate.play()

    if _menu_index == MENU_ITEMS.index(LANGUAGE_LABEL) and (left_pressed or right_pressed):
        _cycle_language(1 if right_pressed else -1)
        if _sfx_navigate:
            _sfx_navigate.play()
    elif enter_pressed:
        if _menu_index == MENU_ITEMS.index(START_LABEL):
            if _sfx_accept:
                _sfx_accept.play()
            instance_api.request_scene_transition(START_SCENE)
        elif _menu_index == MENU_ITEMS.index(LOAD_LABEL):
            if _sfx_accept:
                _sfx_accept.play()
            instance_api.request_scene_transition(LOAD_SCENE)


def draw(engine) -> None:
    pass
