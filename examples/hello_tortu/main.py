"""Hello Tortu — mechaturtle player demo."""

import pygame
from pathlib import Path

from tortuengine import instance_api
from scripts import title as _title
from scripts import gameover as _gameover
from scripts import mechaturtle_player as _player

ROOT = Path(__file__).parent

_engine = None
_state = "title"  # "title" -> "level" -> "gameover" -> "title"


def _enter_title():
    global _state
    _state = "title"
    pygame.mixer.music.stop()
    _title.init(_engine)


def _enter_level():
    global _state
    _state = "level"
    _player.init(_engine)
    pygame.mixer.music.load(str(ROOT / "assets/audio/every Friday.ogg"))
    pygame.mixer.music.set_volume(0.5)
    pygame.mixer.music.play(-1)


def _enter_gameover():
    global _state
    _state = "gameover"
    pygame.mixer.music.stop()
    _gameover.init(_engine)


def init(engine):
    global _engine
    _engine = engine
    _enter_title()


def update(dt):
    if _state == "title":
        _title.update(dt)
        if _title.start_pressed:
            _enter_level()
    elif _state == "level":
        _player.update(dt)
        lives = instance_api.player_lives()
        if lives is not None and lives[0] <= 0:
            _enter_gameover()
    else:
        _gameover.update(dt)
        if _gameover.start_pressed:
            _enter_title()


def draw(engine):
    if _state == "title":
        _title.draw(engine)
    elif _state == "level":
        _player.draw(engine)
    else:
        _gameover.draw(engine)
