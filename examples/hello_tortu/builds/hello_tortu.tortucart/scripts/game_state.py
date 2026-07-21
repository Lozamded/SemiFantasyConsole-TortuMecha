"""Persistent player game state — lives, energy, gears.

Single source of truth for stats that need to survive across scenes
(level, gameover, title). mechaturtle_player.py mutates it during
gameplay and pushes it into instance_api each frame for the HUD/renderer;
other scripts (e.g. gameover.py) can read it directly.
"""

MAX_ENERGY = 3
MAX_LIVES = 6
GEARS_PER_LIFE = 100

energy = MAX_ENERGY
lives = MAX_LIVES
gears = 0


def reset() -> None:
    """Call when starting a new game (title -> level)."""
    global energy, lives, gears
    energy = MAX_ENERGY
    lives = MAX_LIVES
    gears = 0


def damage() -> bool:
    """Apply one hit: drain energy, losing a life once energy is empty.

    Returns True if this hit cost a life (energy just hit zero).
    """
    global energy, lives
    if lives <= 0:
        return False
    energy = max(0, energy - 1)
    if energy <= 0:
        lives -= 1
        energy = MAX_ENERGY if lives > 0 else 0
        return True
    return False


def lose_life() -> None:
    """Force the loss of one full life (e.g. falling into a bottomless pit) —
    bypasses the energy-pip mechanic that damage() uses for enemy touches."""
    global energy, lives
    if lives <= 0:
        return
    lives -= 1
    energy = MAX_ENERGY if lives > 0 else 0


def add_gear() -> None:
    """Collect one gear, granting an extra life every GEARS_PER_LIFE."""
    global gears, lives
    gears += 1
    if gears % GEARS_PER_LIFE == 0:
        lives += 1
