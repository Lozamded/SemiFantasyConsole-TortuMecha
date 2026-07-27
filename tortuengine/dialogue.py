"""Dialogue assets — sequences of speaker lines (dialogues/*.json) that may
branch through player-selected options.

A line's `speaker`/`text` may embed a `[<[key]>]` placeholder resolved
through `tortuengine.localization`, exactly like a GuiTextLabel — so dialogue
copy lives in the same languages/*.csv files as everything else instead of a
separate lookup convention.

A line can carry `options`: presenting it turns it into a decision point.
Selecting an option can jump to another dialogue (`next_dialogue`, a
project-relative path such as "dialogues/foo.json" — empty means "stay in
this dialogue and continue to the next line") and/or assign `value` to the
dialogue variable named `set_var` (empty means "don't set a variable").

A line can also carry `end_action`, the name of a function (in the
dialogue's paired vars script) to call once the dialogue finishes.
`action_values` supplies its positional arguments: each entry is either a
literal (`type: "literal"`, the default) or a dialogue variable to look up by
name at call time (`type: "variable"`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ActionValue:
    value: Any = ""
    type: str = "literal"


@dataclass
class DialogueOption:
    text: str = ""
    next_dialogue: str = ""
    set_var: str = ""
    value: Any = None


@dataclass
class DialogueLine:
    speaker: str = ""
    text: str = ""
    icon: str = ""
    options: list[DialogueOption] = field(default_factory=list)
    end_action: str = ""
    action_values: list[ActionValue] = field(default_factory=list)


@dataclass
class Dialogue:
    lines: list[DialogueLine] = field(default_factory=list)


def _load_option(raw: dict) -> DialogueOption:
    return DialogueOption(
        str(raw.get("text", "")),
        str(raw.get("next_dialogue", "")),
        str(raw.get("set_var", "")),
        raw.get("value"),
    )


def _load_action_value(raw: dict) -> ActionValue:
    return ActionValue(raw.get("value", ""), str(raw.get("type", "literal")))


def load_dialogue(path: Path) -> Dialogue:
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        DialogueLine(
            str(raw.get("speaker", "")),
            str(raw.get("text", "")),
            str(raw.get("icon", "")),
            [_load_option(opt) for opt in raw.get("options", [])],
            str(raw.get("end_action", "")),
            [_load_action_value(av) for av in raw.get("action_values", [])],
        )
        for raw in data.get("lines", [])
    ]
    return Dialogue(lines)


def _save_option(option: DialogueOption) -> dict:
    return {
        "text": option.text,
        **({"next_dialogue": option.next_dialogue} if option.next_dialogue else {}),
        **({"set_var": option.set_var} if option.set_var else {}),
        **({"value": option.value} if option.value is not None else {}),
    }


def _save_action_value(action_value: ActionValue) -> dict:
    return {
        "value": action_value.value,
        **({"type": action_value.type} if action_value.type != "literal" else {}),
    }


def save_dialogue(dialogue: Dialogue, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "lines": [
            {
                "speaker": line.speaker,
                "text": line.text,
                **({"icon": line.icon} if line.icon else {}),
                **({"options": [_save_option(o) for o in line.options]} if line.options else {}),
                **({"end_action": line.end_action} if line.end_action else {}),
                **(
                    {"action_values": [_save_action_value(a) for a in line.action_values]}
                    if line.action_values
                    else {}
                ),
            }
            for line in dialogue.lines
        ]
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
