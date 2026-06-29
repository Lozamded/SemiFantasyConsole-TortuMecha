"""Smooth horizontal follow camera — clamps to scene bounds."""

from __future__ import annotations

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH

SMOOTHING = 8.0

_cam_x: float = 0.0
_cam_y: float = 0.0
_scene_w: int = 0
_scene_h: int = 0


def init(scene_width: int, scene_height: int) -> None:
    global _cam_x, _cam_y, _scene_w, _scene_h
    _cam_x = 0.0
    _cam_y = 0.0
    _scene_w = scene_width
    _scene_h = scene_height


def update(dt: float, target_x: float, target_y: float) -> None:
    global _cam_x
    tx = target_x - SCREEN_WIDTH / 2.0
    tx = max(0.0, min(tx, float(_scene_w - SCREEN_WIDTH)))
    _cam_x += (tx - _cam_x) * min(1.0, dt * SMOOTHING)


def get() -> tuple[float, float]:
    return _cam_x, _cam_y
