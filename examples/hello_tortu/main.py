"""Demo cart — bouncing block at 264×198."""

import math

_t = 0.0


def init(engine):
    pass


def update(dt):
    global _t
    _t += dt


def draw(engine):
    engine.clear((12, 18, 32))
    x = int(120 + 80 * math.sin(_t * 2))
    engine.rect((80, 200, 120), (x, 80, 24, 24))
    engine.text("Hello Tortu", 68, 16, (240, 240, 255), 16)
    engine.text("264x198", 96, 180, (120, 130, 160), 12)
