"""Save file schema and slot bookkeeping for Hello Tortoise.

Declares how many save slots this project offers and what a save's
`gamedata` payload looks like, on top of tortoisengine.save_data's generic
N-slot JSON bookkeeping. Slots live in Saves/slot<N>.json next to main.py.
"""

from __future__ import annotations

from pathlib import Path

from tortoisengine import save_data
from scripts import game_state

ROOT = Path(__file__).parent.parent
SAVES_DIR = ROOT / "Saves"
SLOT_COUNT = 3

GAME_ID = "mechaturtle_d01"
GAME_NAME = "Mecha Turtle Demo"


def read_slot(index: int) -> dict | None:
    return save_data.read_slot(SAVES_DIR, index)


def read_slots() -> list[dict | None]:
    return save_data.read_slots(SAVES_DIR, SLOT_COUNT)


def write_slot(index: int, current_lvl: str) -> None:
    save_data.write_slot(SAVES_DIR, index, {
        "slot_id": index,
        "game_id": GAME_ID,
        "game name": GAME_NAME,
        "gamedata": {
            "gears": game_state.gears,
            "current_lvl": current_lvl,
            "faviorite_cokie": "not_decided",
        },
    })
