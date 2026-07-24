"""Script for the dialog GUI layer — steps through a linear dialogue.

Runs as dialog.tortuguilayer's own instance script (an isolated module, see
tortuengine/instance_scripts.py), so it never touches other scripts directly
— a prefab script (e.g. robot.py) asks for a dialogue via
instance_api.request_dialogue(path), and this script picks that request up,
loads the referenced dialogues/*.json (see tortuengine/dialogue.py), and
steps through its lines on the action button (X/Shift/C — the same button
that started it). Text/speaker are left as their raw `[<[key]>]` placeholders
— the renderer resolves them through tortuengine.localization every frame,
same as any other GuiTextLabel.
"""

import pygame

from tortuengine import instance_api
from tortuengine.dialogue import load_dialogue

SPEAKER_LABEL = "dialog_speaker"
TEXT_LABEL = "dialog_text"

_lines = []
_index = 0
_active = False
_prev_action = False


def _action_held() -> bool:
    keys = pygame.key.get_pressed()
    return keys[pygame.K_x] or keys[pygame.K_LSHIFT] or keys[pygame.K_c]


def init(engine) -> None:
    pass


def _show_line() -> None:
    line = _lines[_index]
    instance_api.set_gui_text_label_text(SELF_ID, SPEAKER_LABEL, line.speaker)
    instance_api.set_gui_text_label_text(SELF_ID, TEXT_LABEL, line.text)


def _end() -> None:
    global _active, _lines, _index
    _active = False
    _lines = []
    _index = 0
    instance_api.set_gui_layer_visible(SELF_ID, False)
    instance_api.set_dialogue_active(False)


def _start(path: str) -> None:
    global _lines, _index, _active, _prev_action
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
    # The action press that triggered this dialogue is still held on this
    # same frame — seed the edge-detector so it isn't also read as an advance.
    _prev_action = _action_held()


def update(dt: float) -> None:
    global _index, _prev_action

    if not _active:
        path = instance_api.take_dialogue_request()
        if path:
            _start(path)
        return

    action_held = _action_held()
    action_pressed = action_held and not _prev_action
    _prev_action = action_held

    if action_pressed:
        _index += 1
        if _index >= len(_lines):
            _end()
        else:
            _show_line()


def draw(engine) -> None:
    pass
