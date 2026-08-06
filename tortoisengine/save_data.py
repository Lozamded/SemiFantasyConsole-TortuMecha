"""Save-file slots: a project declares N fixed slots, each one JSON blob.

Slot files live in whatever directory the caller passes (by convention a
`Saves/` folder next to `main.py`) and are named `slot<N>.json`, 1-indexed.
The payload shape is entirely up to the caller — this module only handles
the "N fixed slots, read/write one JSON blob each" bookkeeping, so a project
can declare its own slot count and save schema on top of it (see
examples/hello_tortu/scripts/save_system.py).
"""

from __future__ import annotations

import json
from pathlib import Path


def slot_path(saves_dir: Path, index: int) -> Path:
    return saves_dir / f"slot{index}.json"


def read_slot(saves_dir: Path, index: int) -> dict | None:
    """Return the slot's saved data, or None if it's empty or unreadable."""
    path = slot_path(saves_dir, index)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_slots(saves_dir: Path, count: int) -> list[dict | None]:
    """Return `count` slots (index 1..count) in order, each read_slot()'s result."""
    return [read_slot(saves_dir, i) for i in range(1, count + 1)]


def write_slot(saves_dir: Path, index: int, data: dict) -> None:
    saves_dir.mkdir(parents=True, exist_ok=True)
    slot_path(saves_dir, index).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
