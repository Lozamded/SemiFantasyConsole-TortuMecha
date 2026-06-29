"""Hello Tortu — mechaturtle player demo."""

import pygame
from pathlib import Path

from scripts import mechaturtle_player as _player

ROOT = Path(__file__).parent


def init(engine):
    _player.init(engine)
    pygame.mixer.music.load(str(ROOT / "assets/audio/every Friday.ogg"))
    pygame.mixer.music.set_volume(0.5)
    pygame.mixer.music.play(-1)


def update(dt):
    _player.update(dt)


def draw(engine):
    _player.draw(engine)
