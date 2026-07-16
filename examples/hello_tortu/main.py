"""Hello Tortu — mechaturtle player demo."""

import pygame
from pathlib import Path

from scripts import title as _title
from scripts import mechaturtle_player as _player

ROOT = Path(__file__).parent

_engine = None
_state = "title"  # "title" -> "level"


def init(engine):
    global _engine, _state
    _engine = engine
    _state = "title"
    _title.init(engine)


def update(dt):
    global _state
    if _state == "title":
        _title.update(dt)
        if _title.start_pressed:
            _state = "level"
            _player.init(_engine)
            pygame.mixer.music.load(str(ROOT / "assets/audio/every Friday.ogg"))
            pygame.mixer.music.set_volume(0.5)
            pygame.mixer.music.play(-1)
    else:
        _player.update(dt)


def draw(engine):
    if _state == "title":
        _title.draw(engine)
    else:
        _player.draw(engine)
