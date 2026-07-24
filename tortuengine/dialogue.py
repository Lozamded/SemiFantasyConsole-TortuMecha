"""Dialogue assets — linear sequences of speaker lines (dialogues/*.json).

v1 is intentionally simple: a dialogue is just an ordered list of lines. Each
line's `speaker`/`text` may embed a `[<[key]>]` placeholder resolved through
`tortuengine.localization`, exactly like a GuiTextLabel — so dialogue copy
lives in the same languages/*.csv files as everything else instead of a
separate lookup convention.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DialogueLine:
    speaker: str = ""
    text: str = ""
    icon: str = ""


@dataclass
class Dialogue:
    lines: list[DialogueLine] = field(default_factory=list)


def load_dialogue(path: Path) -> Dialogue:
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        DialogueLine(
            str(raw.get("speaker", "")),
            str(raw.get("text", "")),
            str(raw.get("icon", "")),
        )
        for raw in data.get("lines", [])
    ]
    return Dialogue(lines)


def save_dialogue(dialogue: Dialogue, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "lines": [
            {
                "speaker": line.speaker,
                "text": line.text,
                **({"icon": line.icon} if line.icon else {}),
            }
            for line in dialogue.lines
        ]
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
