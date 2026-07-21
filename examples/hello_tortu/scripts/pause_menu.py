"""Script for GUI layer pause_menu — Resume/Options navigation.

Runs as the pause_menu.tortuguilayer's own instance script (an isolated
module, see tortuengine/instance_scripts.py), so it never touches the Scene
or mechaturtle_player.py directly — only through instance_api. SELF_ID is
injected by the loader and equals this GUI layer's own asset path, i.e.
mechaturtle_player.PAUSE_GUI_LAYER.

The pause_menu asset is one wide (528x198) canvas: the Pause panel occupies
x 0..264, the Options panel x 264..528. Switching screens slides the whole
canvas via instance_api.set_gui_layer_scroll instead of swapping layers.
"""

import pygame

from tortuengine import instance_api

MAIN_ITEMS = ("option_resume", "option_options")
OPTIONS_ITEMS = ("option_2_language", "option_2_volSFX", "option_volMusic", "option_back")

CURSOR_MAIN = "cursor_main"
CURSOR_OPTIONS = "cursor_options"
# Matches the y-offset the cursors were authored with relative to their
# first target label (Resume / Language) in pause_menu.tortuguilayer.
CURSOR_Y_OFFSET = 8

# Golden yellow — same accent used for the "PAUSE" title (see
# pause_menu.tortuguilayer). Applied to whichever label is currently selected.
HIGHLIGHT_COLOR = 18

PANEL_WIDTH = 264
SLIDE_DURATION = 0.25  # seconds to pan one full panel width

_screen = "main"  # "main" | "options"
_main_index = 0
_options_index = 0
_scroll = 0.0
_scroll_target = 0.0
_was_paused = False
_prev_up = False
_prev_down = False
_prev_enter = False


def init(engine) -> None:
    pass


def _move_cursor(cursor_id: str, label_id: str) -> None:
    pos = instance_api.gui_text_label_position(SELF_ID, label_id)
    cursor_pos = instance_api.gui_object_position(SELF_ID, cursor_id)
    if pos is None or cursor_pos is None:
        return
    instance_api.set_gui_object_position(SELF_ID, cursor_id, cursor_pos[0], pos[1] + CURSOR_Y_OFFSET)


def _select(cursor_id: str, items: tuple[str, ...], old_index: int, new_index: int) -> None:
    instance_api.set_gui_text_label_color(SELF_ID, items[old_index], -1)
    instance_api.set_gui_text_label_color(SELF_ID, items[new_index], HIGHLIGHT_COLOR)
    _move_cursor(cursor_id, items[new_index])


def _reset_menu() -> None:
    global _screen, _main_index, _options_index, _scroll, _scroll_target
    _screen = "main"
    _scroll = 0.0
    _scroll_target = 0.0
    instance_api.set_gui_layer_scroll(SELF_ID, 0, 0)
    # Clear any highlight left over from wherever the menu was last closed,
    # then land fresh on the first item of each panel.
    for label_id in MAIN_ITEMS + OPTIONS_ITEMS:
        instance_api.set_gui_text_label_color(SELF_ID, label_id, -1)
    _main_index = 0
    _options_index = 0
    _select(CURSOR_MAIN, MAIN_ITEMS, 0, 0)
    _select(CURSOR_OPTIONS, OPTIONS_ITEMS, 0, 0)


def update(dt: float) -> None:
    global _was_paused, _prev_up, _prev_down, _prev_enter
    global _screen, _main_index, _options_index, _scroll, _scroll_target

    paused = instance_api.is_game_paused()
    if paused and not _was_paused:
        _reset_menu()
        # The Enter press that opened the menu is still held on this same
        # frame — seed the edge-detectors so it isn't also read as a confirm.
        keys = pygame.key.get_pressed()
        _prev_up = keys[pygame.K_UP]
        _prev_down = keys[pygame.K_DOWN]
        _prev_enter = keys[pygame.K_RETURN]
    _was_paused = paused

    if not paused:
        return

    if _scroll != _scroll_target:
        step = (PANEL_WIDTH / SLIDE_DURATION) * dt
        if _scroll < _scroll_target:
            _scroll = min(_scroll_target, _scroll + step)
        else:
            _scroll = max(_scroll_target, _scroll - step)
        instance_api.set_gui_layer_scroll(SELF_ID, round(_scroll), 0)
        return  # ignore input while the panel is sliding

    keys = pygame.key.get_pressed()
    up_held, down_held, enter_held = keys[pygame.K_UP], keys[pygame.K_DOWN], keys[pygame.K_RETURN]
    up_pressed = up_held and not _prev_up
    down_pressed = down_held and not _prev_down
    enter_pressed = enter_held and not _prev_enter
    _prev_up, _prev_down, _prev_enter = up_held, down_held, enter_held

    if _screen == "main":
        if up_pressed or down_pressed:
            old_index = _main_index
            _main_index = (_main_index + (1 if down_pressed else -1)) % len(MAIN_ITEMS)
            _select(CURSOR_MAIN, MAIN_ITEMS, old_index, _main_index)
        if enter_pressed:
            if MAIN_ITEMS[_main_index] == "option_resume":
                instance_api.set_game_paused(False)
                instance_api.set_gui_layer_visible(SELF_ID, False)
            else:
                _screen = "options"
                _scroll_target = float(PANEL_WIDTH)
    else:
        if up_pressed or down_pressed:
            old_index = _options_index
            _options_index = (_options_index + (1 if down_pressed else -1)) % len(OPTIONS_ITEMS)
            _select(CURSOR_OPTIONS, OPTIONS_ITEMS, old_index, _options_index)
        if enter_pressed and OPTIONS_ITEMS[_options_index] == "option_back":
            _screen = "main"
            _scroll_target = 0.0


def draw(engine) -> None:
    pass
