"""Save-file slots: a project declares N fixed slots, each one JSON blob.

Slot files live in whatever directory the caller passes (by convention a
`Saves/` folder next to `main.py`) and are named `slot<N>.json`, 1-indexed.
The payload shape is entirely up to the caller — this module only handles
the "N fixed slots, read/write one JSON blob each" bookkeeping, so a project
can declare its own slot count and save schema on top of it (see
examples/hello_tortu/scripts/save_system.py).

A physical cartridge (see sdcart_reader.py) is mounted read-only, so writing
`Saves/` next to `main.py` fails on real hardware even though it works fine
for a local project or a cart copied to a writable folder. write_slot()
falls back to a per-cart directory under the user's home when the requested
saves_dir can't be created/written to; read_slot() checks that same fallback
so saves keep round-tripping once the fallback kicks in.
"""

from __future__ import annotations

import json
from pathlib import Path

_FALLBACK_ROOT = Path.home() / "console" / "saves"


def slot_path(saves_dir: Path, index: int) -> Path:
    return saves_dir / f"slot{index}.json"


def _fallback_dir(saves_dir: Path) -> Path:
    """A writable per-cart directory to use when saves_dir itself isn't writable.

    Keyed by the cart's own folder name (saves_dir's parent, since saves_dir
    is conventionally <cart_root>/Saves) so different carts sharing this
    console don't collide in the fallback location.
    """
    cart_name = saves_dir.parent.name
    if cart_name.endswith(".tortucart"):
        cart_name = cart_name[: -len(".tortucart")]
    return _FALLBACK_ROOT / (cart_name or "game")


def read_slot(saves_dir: Path, index: int) -> dict | None:
    """Return the slot's saved data, or None if it's empty or unreadable."""
    for candidate_dir in (saves_dir, _fallback_dir(saves_dir)):
        path = slot_path(candidate_dir, index)
        if not path.is_file():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def read_slots(saves_dir: Path, count: int) -> list[dict | None]:
    """Return `count` slots (index 1..count) in order, each read_slot()'s result."""
    return [read_slot(saves_dir, i) for i in range(1, count + 1)]


def write_slot(saves_dir: Path, index: int, data: dict) -> None:
    text = json.dumps(data, indent=2) + "\n"
    try:
        saves_dir.mkdir(parents=True, exist_ok=True)
        slot_path(saves_dir, index).write_text(text, encoding="utf-8")
    except OSError:
        fallback_dir = _fallback_dir(saves_dir)
        fallback_dir.mkdir(parents=True, exist_ok=True)
        slot_path(fallback_dir, index).write_text(text, encoding="utf-8")
