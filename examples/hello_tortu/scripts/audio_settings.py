"""Project-level audio-volume helpers — thin wrapper around tortoisengine.audio
using this project's own channel names (see scripts/_generated/audio_auto.py,
regenerated from the Sound Editor in TortoiseStudio whenever channels or
per-file assignments are saved).

The pause menu exposes two sliders, not one per channel: "SFX" drives both
CHANNEL_GAME_SFX and CHANNEL_UI_SFX together, "Music" drives CHANNEL_MUSIC
alone — matching this project's current game_sfx / ui_sfx / music channel
split. load_sound() looks up each file's channel from AUDIO_CHANNELS
automatically, so scripts never have to guess or hand-copy which channel a
sound belongs to.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from tortoisengine import audio
from scripts._generated import audio_auto as auto

ROOT = Path(__file__).parent.parent

# Music plays at this authored base level (see main.py) — the "Music" slider
# is a 0..1 multiplier on top of it, so the default 100% reproduces today's
# mix exactly rather than suddenly boosting music louder than it was ever
# balanced against SFX.
MUSIC_BASE_LEVEL = 0.5

VOLUME_STEP = 0.1


def load() -> None:
    """Load persisted volume levels. Call once at game startup, before any
    sound is loaded, so the first thing played already reflects them."""
    audio.load_settings(ROOT)


def load_sound(rel_path: str) -> pygame.mixer.Sound:
    """Load a sound under assets/audio/, routed to whichever channel it's
    assigned to in the Sound Editor (defaulting to game_sfx if unassigned)."""
    channel = auto.AUDIO_CHANNELS.get(rel_path, auto.CHANNEL_GAME_SFX)
    return audio.load_sound(ROOT, rel_path, channel)


def sfx_volume() -> float:
    return audio.get_channel_volume(auto.CHANNEL_GAME_SFX)


def music_volume() -> float:
    return audio.get_channel_volume(auto.CHANNEL_MUSIC)


def set_sfx_volume(value: float) -> None:
    value = max(0.0, min(1.0, value))
    audio.set_channel_volume(auto.CHANNEL_GAME_SFX, value)
    audio.set_channel_volume(auto.CHANNEL_UI_SFX, value)
    audio.save_settings(ROOT)


def set_music_volume(value: float) -> None:
    audio.set_channel_volume(auto.CHANNEL_MUSIC, max(0.0, min(1.0, value)))
    audio.save_settings(ROOT)
    apply_music_volume()


def apply_music_volume() -> None:
    """Re-push the current music volume onto pygame.mixer.music — call after
    loading/starting a new track, and whenever the Music slider changes."""
    pygame.mixer.music.set_volume(MUSIC_BASE_LEVEL * music_volume())
