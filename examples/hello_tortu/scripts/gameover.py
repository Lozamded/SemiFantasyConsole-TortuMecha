"""Script for scene gameover."""

from __future__ import annotations

from pathlib import Path

import pygame

from tortuengine.scene import load_scene
from tortuengine.scene_renderer import SceneRenderer

ROOT = Path(__file__).parent.parent

_scene = None
_renderer: SceneRenderer | None = None
_engine = None

# Set to True by update() once start is pressed; main.py watches this to
# know when to switch from the game-over scene back to the title screen.
start_pressed = False


def init(engine) -> None:
    global _scene, _renderer, _engine, start_pressed
    _engine = engine
    start_pressed = False
    _scene = load_scene(ROOT / "scenes/gameover.tortuscene", project_root=ROOT)

    cart_manifest = getattr(engine, "manifest", None)
    cart_root = getattr(engine, "cart_root", None)
    if cart_manifest is not None and cart_root is not None:
        _renderer = SceneRenderer.from_cart(cart_root, cart_manifest)
    else:
        _renderer = SceneRenderer(ROOT)


def update(dt: float) -> None:
    global start_pressed
    keys = pygame.key.get_pressed()
    if keys[pygame.K_RETURN] or keys[pygame.K_SPACE] or keys[pygame.K_z]:
        start_pressed = True

    if _renderer and _scene:
        _renderer.tick(_scene, dt, _engine)


def draw(engine) -> None:
    if _renderer and _scene:
        frame = _renderer.render(_scene)
        engine.blit(frame, (0, 0))
    else:
        engine.clear((12, 18, 32))
