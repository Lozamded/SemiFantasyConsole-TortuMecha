"""Hello Tortu — mechaturtle player demo."""

import pygame
from pathlib import Path

from scripts import title as _title
from scripts import gameover as _gameover
from scripts import mechaturtle_player as _player
from scripts import save_scene as _save_scene
from scripts import load_scene as _load_scene
from scripts import game_state

ROOT = Path(__file__).parent

_engine = None
_state = "title"  # "title" -> "level" -> ("save" | "gameover") -> "title", or "title" -> "load" -> "level"
_current_scene_path = "scenes/level_01.tortuscene"


def _enter_title():
    global _state
    _state = "title"
    pygame.mixer.music.stop()
    _title.init(_engine)


def _enter_level(new_game: bool, scene_path: str | None = None):
    """new_game=True resets lives/energy/gears and always starts at level_01
    (title -> level); False keeps them as-is and defaults to whichever level
    is already current — a mid-run respawn after the defeat bounce — unless
    scene_path picks a new one (save_scene's Continue moving on to the next
    level)."""
    global _state, _current_scene_path
    _state = "level"
    if new_game:
        game_state.reset()
        _current_scene_path = "scenes/level_01.tortuscene"
    elif scene_path is not None:
        _current_scene_path = scene_path
    _player.init(_engine, _current_scene_path)
    if new_game:
        pygame.mixer.music.load(str(ROOT / "assets/audio/every Friday.ogg"))
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)


def _enter_gameover():
    global _state
    _state = "gameover"
    pygame.mixer.music.stop()
    _gameover.init(_engine)


def _enter_save_scene():
    global _state
    _state = "save"
    pygame.mixer.music.stop()
    _save_scene.init(_engine)


def _enter_load_scene():
    global _state
    _state = "load"
    pygame.mixer.music.stop()
    _load_scene.init(_engine)


def init(engine):
    global _engine
    _engine = engine
    _enter_title()


def update(dt):
    if _state == "title":
        _title.update(dt)
        if _title.target_scene == "scenes/level_01.tortuscene":
            _enter_level(new_game=True)
        elif _title.target_scene:
            _enter_load_scene()
    elif _state == "level":
        _player.update(dt)
        if _player.defeat_done:
            if game_state.lives <= 0:
                _enter_gameover()
            else:
                _enter_level(new_game=False)
        elif _player.finish_done:
            _enter_save_scene()
    elif _state == "save":
        _save_scene.update(dt)
        if _save_scene.target_scene:
            _enter_level(new_game=False, scene_path=_save_scene.target_scene)
    elif _state == "load":
        _load_scene.update(dt)
        if _load_scene.target_scene == "scenes/title.tortuscene":
            _enter_title()
        elif _load_scene.target_scene:
            _enter_level(new_game=False, scene_path=_load_scene.target_scene)
    else:
        _gameover.update(dt)
        if _gameover.start_pressed:
            _enter_title()


def draw(engine):
    if _state == "title":
        _title.draw(engine)
    elif _state == "level":
        _player.draw(engine)
    elif _state == "save":
        _save_scene.draw(engine)
    elif _state == "load":
        _load_scene.draw(engine)
    else:
        _gameover.draw(engine)
