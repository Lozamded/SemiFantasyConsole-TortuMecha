"""Script for scene save_scene — shown after a level finishes."""

from __future__ import annotations

from pathlib import Path

from tortuengine import instance_api
from tortuengine.scene import load_scene
from tortuengine.scene_renderer import SceneRenderer

ROOT = Path(__file__).parent.parent

_scene = None
_renderer: SceneRenderer | None = None
_engine = None

# Set by update() once Save_hud.py's Continue item asks to move on (see
# instance_api.request_scene_transition); main.py watches this to know when
# to switch from save_scene to the next level.
target_scene = ""


def init(engine) -> None:
    global _scene, _renderer, _engine, target_scene
    _engine = engine
    target_scene = ""
    _scene = load_scene(ROOT / "scenes/save_scene.tortuscene", project_root=ROOT)

    cart_manifest = getattr(engine, "manifest", None)
    cart_root = getattr(engine, "cart_root", None)
    if cart_manifest is not None and cart_root is not None:
        _renderer = SceneRenderer.from_cart(cart_root, cart_manifest)
    else:
        _renderer = SceneRenderer(ROOT)


def update(dt: float) -> None:
    global target_scene
    if _renderer and _scene:
        _renderer.tick(_scene, dt, _engine)
    request = instance_api.take_scene_transition_request()
    if request:
        target_scene = request


def draw(engine) -> None:
    if _renderer and _scene:
        frame = _renderer.render(_scene)
        engine.blit(frame, (0, 0))
    else:
        engine.clear((12, 18, 32))
