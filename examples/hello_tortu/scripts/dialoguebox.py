"""Script for the dialog GUI layer — steps through a dialogue, which may
branch through player-selected options.

Runs as dialog.tortuguilayer's own instance script (an isolated module, see
tortuengine/instance_scripts.py), so it never touches other scripts directly
— a prefab script (e.g. robot.py) asks for a dialogue via
instance_api.request_dialogue(path), and this script picks that request up,
loads the referenced dialogues/*.json (see tortuengine/dialogue.py), and
steps through its lines on the action button (X/Shift/C — the same button
that started it). Text/speaker are left as their raw `[<[key]>]` placeholders
— the renderer resolves them through tortuengine.localization every frame,
same as any other GuiTextLabel. A CSV cell can also embed `[var<[name]>]` to
read scripts/dialogue_vars.py live (see localization.bind_variables, wired
below) — e.g. dialogues/robot2_lv1.json's last line.

A line with `options` pauses on a decision instead of auto-advancing: Up/Down
(mirroring pause_menu.py's cursor convention) move the highlighted choice —
both the text color and the `select_arrow` GUI object — across up to 4
pre-placed option labels, and the action button confirms it. A plain line
instead shows `dialog_end_arrow`, a "press to continue" hint; the two arrows
are mutually exclusive since a decision and a continue prompt never apply to
the same line. Confirming an option can assign a variable (`set_var`) and/or
jump to another dialogue (`next_dialogue`) — both applied against
scripts/dialogue_vars.py, the same shared vars module a line's
`end_action`/`action_values` are resolved against when that line is
dismissed.
"""

import pygame

from tortuengine import instance_api, localization
from tortuengine.dialogue import load_dialogue
from scripts import dialogue_vars

SPEAKER_LABEL = "dialog_speaker"
TEXT_LABEL = "dialog_text"
DECISION_INDICATOR_LABEL = "dialog_decision_indicator"
OPTION_LABELS = ("dialog_option_1", "dialog_option_2", "dialog_option_3", "dialog_option_4")
SELECT_ARROW = "select_arrow"
CONTINUE_ARROW = "dialog_end_arrow"
# select_arrow's placed (x, y) in dialog.tortuguilayer was authored pointing
# at dialog_option_1 — this is that offset, reused to aim it at whichever
# option label is currently selected.
SELECT_ARROW_OFFSET = (-18, 8)

# Golden yellow — same accent pause_menu.py uses to highlight the selected
# menu item (see its HIGHLIGHT_COLOR), reused here for the selected option.
HIGHLIGHT_COLOR = 18

_lines = []
_index = 0
_active = False
_option_index = 0
_prev_action = False
_prev_up = False
_prev_down = False


def _action_held() -> bool:
    keys = pygame.key.get_pressed()
    return keys[pygame.K_x] or keys[pygame.K_LSHIFT] or keys[pygame.K_c]


def init(engine) -> None:
    localization.bind_variables(lambda name: getattr(dialogue_vars, name, None))


def _hide_options() -> None:
    instance_api.set_gui_text_label_visible(SELF_ID, DECISION_INDICATOR_LABEL, False)
    instance_api.set_gui_object_visible(SELF_ID, SELECT_ARROW, False)
    for label_id in OPTION_LABELS:
        instance_api.set_gui_text_label_visible(SELF_ID, label_id, False)


def _move_select_arrow(label_id: str) -> None:
    pos = instance_api.gui_text_label_position(SELF_ID, label_id)
    if pos is None:
        return
    instance_api.set_gui_object_position(
        SELF_ID, SELECT_ARROW, pos[0] + SELECT_ARROW_OFFSET[0], pos[1] + SELECT_ARROW_OFFSET[1]
    )


def _show_options(options) -> None:
    global _option_index
    _option_index = 0
    instance_api.set_gui_text_label_visible(SELF_ID, DECISION_INDICATOR_LABEL, True)
    instance_api.set_gui_object_visible(SELF_ID, SELECT_ARROW, True)
    for i, label_id in enumerate(OPTION_LABELS):
        if i < len(options):
            instance_api.set_gui_text_label_text(SELF_ID, label_id, options[i].text)
            instance_api.set_gui_text_label_visible(SELF_ID, label_id, True)
            instance_api.set_gui_text_label_color(SELF_ID, label_id, HIGHLIGHT_COLOR if i == 0 else -1)
        else:
            instance_api.set_gui_text_label_visible(SELF_ID, label_id, False)
    _move_select_arrow(OPTION_LABELS[0])


def _move_option(options, step: int) -> None:
    global _option_index
    old_index = _option_index
    _option_index = (_option_index + step) % len(options)
    instance_api.set_gui_text_label_color(SELF_ID, OPTION_LABELS[old_index], -1)
    instance_api.set_gui_text_label_color(SELF_ID, OPTION_LABELS[_option_index], HIGHLIGHT_COLOR)
    _move_select_arrow(OPTION_LABELS[_option_index])


def _show_line() -> None:
    line = _lines[_index]
    instance_api.set_gui_text_label_text(SELF_ID, SPEAKER_LABEL, line.speaker)
    instance_api.set_gui_text_label_text(SELF_ID, TEXT_LABEL, line.text)
    instance_api.set_gui_object_visible(SELF_ID, CONTINUE_ARROW, not line.options)
    if line.options:
        _show_options(line.options)
    else:
        _hide_options()


def _run_end_action(line) -> None:
    if not line.end_action:
        return
    fn = getattr(dialogue_vars, line.end_action, None)
    if fn is None:
        return
    args = [
        getattr(dialogue_vars, av.value, None) if av.type == "variable" else av.value
        for av in line.action_values
    ]
    fn(*args)


def _end() -> None:
    global _active, _lines, _index
    _active = False
    _lines = []
    _index = 0
    instance_api.set_gui_layer_visible(SELF_ID, False)
    instance_api.set_dialogue_active(False)


def _start(path: str) -> None:
    global _lines, _index, _active, _prev_action, _prev_up, _prev_down
    root = instance_api.project_root()
    if root is None:
        return
    dialogue = load_dialogue(root / path)
    if not dialogue.lines:
        return
    _lines = dialogue.lines
    _index = 0
    _active = True
    instance_api.set_dialogue_active(True)
    instance_api.set_gui_layer_visible(SELF_ID, True)
    _show_line()
    # The action press that triggered this dialogue (either the button that
    # opened it, or the one that confirmed an option jumping here) is still
    # held on this same frame — seed the edge-detectors so it isn't also
    # read as an advance or a decision move.
    _prev_action = _action_held()
    keys = pygame.key.get_pressed()
    _prev_up = keys[pygame.K_UP]
    _prev_down = keys[pygame.K_DOWN]


def _go_to_next_line() -> None:
    global _index
    _index += 1
    if _index >= len(_lines):
        _end()
    else:
        _show_line()


def _advance() -> None:
    _run_end_action(_lines[_index])
    _go_to_next_line()


def _choose_option(line, option) -> None:
    if option.set_var:
        setattr(dialogue_vars, option.set_var, option.value)
    _run_end_action(line)
    if option.next_dialogue:
        _start(option.next_dialogue)
    else:
        _go_to_next_line()


def update(dt: float) -> None:
    global _prev_action, _prev_up, _prev_down

    if not _active:
        path = instance_api.take_dialogue_request()
        if path:
            _start(path)
        return

    action_held = _action_held()
    action_pressed = action_held and not _prev_action
    _prev_action = action_held

    keys = pygame.key.get_pressed()
    up_held, down_held = keys[pygame.K_UP], keys[pygame.K_DOWN]
    up_pressed = up_held and not _prev_up
    down_pressed = down_held and not _prev_down
    _prev_up, _prev_down = up_held, down_held

    line = _lines[_index]
    if line.options:
        if up_pressed or down_pressed:
            _move_option(line.options, 1 if down_pressed else -1)
        if action_pressed:
            _choose_option(line, line.options[_option_index])
    elif action_pressed:
        _advance()


def draw(engine) -> None:
    pass
