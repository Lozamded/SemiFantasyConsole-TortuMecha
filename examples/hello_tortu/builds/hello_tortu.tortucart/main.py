"""Hello Tortu — mechaturtle player demo."""

import pygame
from pathlib import Path

from scripts import title as _title
from scripts import gameover as _gameover
from scripts import mechaturtle_player as _player
from scripts import game_state

ROOT = Path(__file__).parent

_engine = None
_state = "title"  # "title" -> "level" -> "gameover" -> "title"


def _enter_title():
    global _state
    _state = "title"
    pygame.mixer.music.stop()
    _title.init(_engine)


def _enter_level(new_game: bool):
    """new_game=True resets lives/energy/gears (title -> level); False keeps
    them as-is, for a mid-run respawn after the defeat bounce."""
    global _state
    _state = "level"
    if new_game:
        game_state.reset()
    _player.init(_engine)
    if new_game:
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
            _enter_level(new_game=True)
    elif _state == "level":
        _player.update(dt)
        if _player.defeat_done:
            if game_state.lives <= 0:
                _enter_gameover()
            else:
                _enter_level(new_game=False)
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
