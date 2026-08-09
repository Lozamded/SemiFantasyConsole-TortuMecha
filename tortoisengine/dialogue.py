"""Dialogue assets — sequences of speaker lines (dialogues/*.json) that may
branch through player-selected options.

A line's `speaker`/`text` may embed a `[<[key]>]` placeholder resolved
through `tortoisengine.localization`, exactly like a GuiTextLabel — so dialogue
copy lives in the same languages/*.csv files as everything else instead of a
separate lookup convention.

A line can carry `options`: presenting it turns it into a decision point.
Each option may carry its own `action` — run when it's picked — exactly like
a line's action; the decision line's own action (if any) then also runs,
regardless of which option was picked. Neither redirecting control flow
(`jumpdialog`/`finishdialog`/`changedialog`, or a compare branch that
resolves to one of those) falls through to the dialogue's default
next-line advance.

A line or an option can carry an `action`: a JSON envelope of the shape
`{"action": true, "type": "<type>", "action_content": {...}}` (an absent or
`false` "action" key means "no action" — `action_content` is then omitted
too). `action_content`'s shape depends on `type`:

- `var_set` — `{"var": "<name>", "value": <literal>}`. Assigns `value` to
  `<name>` on the dialogue's paired vars script (dialogues/foo.json is paired
  with scripts/foo_vars.py by convention — see dialoguebox.py).
- `do_action` — `{"function": "<name>", "value": [<arg>, ...]}`. Calls
  `<name>` (looked up on the vars script) with positional args built from
  `value`; each arg entry is `{"type": "literal", "value": <v>}` (a literal,
  the default when `type` is omitted) or `{"type": "var", "value": "<name>"}`
  (looked up on the vars script at call time).
- `jumpdialog` — `{"id": "<line id>"}`. Jumps to the line carrying that `id`
  within the *same* dialogue file (see `DialogueLine.id`). Line ids may be
  declared anywhere in the file, including after the line that jumps to
  them.
- `changedialog` — `{"path": "<project-relative path>"}`, e.g.
  "dialogues/foo.json". jumpdialog's cross-file sibling: ends the current
  dialogue file's line sequence and starts the one at `path` from its first
  line.
- `finishdialog` — `{}`. Ends the dialogue immediately.
- `var_compare_text` — `{"var": "<name>", "values": {<value>: <action>, ...}}`.
  Reads `<name>` from the vars script and runs the nested action envelope
  keyed by its current value (itself an `{"action": ..., "type": ...,
  "action_content": ...}` dict, e.g. `{"action": false}` for "do nothing").
  A value with no matching key is treated the same as `{"action": false}`.
- `var_compare_number` — `{"var": "<name>", "cases": [{"op": "<op>",
  "threshold": <number>, "action": <action>}, ...], "default": <action>}`.
  Reads `<name>` from the vars script, coerces it to a number, and walks
  `cases` in order — the first entry whose `op` (one of `<`, `<=`, `==`,
  `!=`, `>=`, `>`) holds against `threshold` runs its nested action envelope
  (same shape as var_compare_text's). No match falls through to `default`
  (or does nothing if `default` is absent).

Only `var_set` and `do_action` are pure side effects; `jumpdialog`,
`changedialog`, `finishdialog`, and whatever a `var_compare_text`/
`var_compare_number` branch resolves to affect control flow, so
dialoguebox.py — not this module — is what actually interprets and runs
them. This module only loads/saves the data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Action:
    type: str = ""
    content: dict = field(default_factory=dict)


@dataclass
class DialogueOption:
    text: str = ""
    action: Action | None = None


@dataclass
class DialogueLine:
    speaker: str = ""
    text: str = ""
    icon: str = ""
    id: str = ""
    options: list[DialogueOption] = field(default_factory=list)
    action: Action | None = None


@dataclass
class Dialogue:
    lines: list[DialogueLine] = field(default_factory=list)


def load_action(raw: dict) -> Action | None:
    if not raw.get("action"):
        return None
    return Action(str(raw.get("type", "")), raw.get("action_content", {}) or {})


def _load_option(raw: dict) -> DialogueOption:
    return DialogueOption(
        str(raw.get("text", "")),
        load_action(raw),
    )


def _load_line(raw: dict) -> DialogueLine:
    return DialogueLine(
        str(raw.get("speaker", "")),
        str(raw.get("text", "")),
        str(raw.get("icon", "")),
        str(raw.get("id", "")),
        [_load_option(opt) for opt in raw.get("options", [])],
        load_action(raw),
    )


def load_dialogue(path: Path) -> Dialogue:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Dialogue([_load_line(raw) for raw in data.get("lines", [])])


def _save_action(data: dict, action: Action | None) -> None:
    if action is None:
        return
    data["action"] = True
    data["type"] = action.type
    data["action_content"] = action.content


def _save_option(option: DialogueOption) -> dict:
    data: dict[str, Any] = {"text": option.text}
    _save_action(data, option.action)
    return data


def _save_line(line: DialogueLine) -> dict:
    data: dict[str, Any] = {"speaker": line.speaker, "text": line.text}
    if line.icon:
        data["icon"] = line.icon
    if line.id:
        data["id"] = line.id
    if line.options:
        data["options"] = [_save_option(o) for o in line.options]
    _save_action(data, line.action)
    return data


def save_dialogue(dialogue: Dialogue, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"lines": [_save_line(line) for line in dialogue.lines]}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
