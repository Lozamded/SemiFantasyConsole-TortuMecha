"""Runtime audio-channel volume mixer.

Games define channel names in TortoiseStudio (see game_settings.py's
audio_channels / audio_channel_map, and script_codegen's
generate_audio_auto_script) — this module is the runtime counterpart: it
holds each channel's current 0..1 volume, applies it to every Sound loaded
through load_sound(), and re-applies it live to already-loaded sounds
whenever a channel's volume changes, so a pause-menu slider takes effect
immediately rather than only on the next sound load.

pygame.mixer.music is a single global stream with no per-instance object, so
there's nothing here to "register" it against the way load_sound() registers
Sound objects — callers drive pygame.mixer.music.set_volume() themselves,
scaling by get_channel_volume() for whichever channel their track belongs to.
"""

from __future__ import annotations

import json
from pathlib import Path

import pygame

SETTINGS_FILENAME = "audio_settings.json"

_channel_volumes: dict[str, float] = {}
_sounds_by_channel: dict[str, set[pygame.mixer.Sound]] = {}
_sound_cache: dict[str, pygame.mixer.Sound] = {}


def get_channel_volume(channel: str) -> float:
    return _channel_volumes.get(channel, 1.0)


def set_channel_volume(channel: str, volume: float) -> None:
    volume = max(0.0, min(1.0, volume))
    _channel_volumes[channel] = volume
    for sound in _sounds_by_channel.get(channel, ()):
        sound.set_volume(volume)


def load_sound(root: Path, rel_path: str, channel: str) -> pygame.mixer.Sound:
    """Load (or reuse a cached) Sound at `root / rel_path`, register it under
    `channel` so future set_channel_volume() calls reach it live, and apply
    the channel's current volume immediately."""
    key = str((root / rel_path).resolve())
    sound = _sound_cache.get(key)
    if sound is None:
        sound = pygame.mixer.Sound(key)
        _sound_cache[key] = sound
    sound.set_volume(get_channel_volume(channel))
    _sounds_by_channel.setdefault(channel, set()).add(sound)
    return sound


def _settings_path(project_root: Path) -> Path:
    return project_root / SETTINGS_FILENAME


def load_settings(project_root: Path) -> None:
    """Load persisted channel volumes, if any. Call once at game startup,
    before any sound is loaded, so the very first playback already reflects
    whatever the player last chose."""
    path = _settings_path(project_root)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(data, dict):
        for channel, volume in data.items():
            if isinstance(volume, (int, float)):
                _channel_volumes[str(channel)] = max(0.0, min(1.0, float(volume)))


def save_settings(project_root: Path) -> None:
    path = _settings_path(project_root)
    try:
        path.write_text(json.dumps(_channel_volumes, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
