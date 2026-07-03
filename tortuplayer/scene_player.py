"""Run an exported .tortucart start scene in a pygame window."""

from __future__ import annotations

import pygame

from tortuengine.cart import load_game_module
from tortuengine.cart_manifest import CartManifest
from tortuengine.constants import DEFAULT_FPS
from tortuengine.engine import TortuEngine
from tortuengine.scene import load_scene
from tortuengine.scene_renderer import SceneRenderer
from tortuplayer.display import Display


class CartScenePlayer:
    def __init__(
        self,
        cart_root,
        manifest: CartManifest,
        *,
        scale: int = 3,
        title: str = "TortuPlayer",
        fps: int = DEFAULT_FPS,
        fullscreen: bool = False,
    ) -> None:
        if not pygame.get_init():
            pygame.init()

        self.cart_root = cart_root
        self.manifest = manifest
        self.scale = scale
        self.title = title
        self.fps = fps
        self.fullscreen = fullscreen
        self.running = False
        self.display: Display | None = None
        self._game_module = None
        self._engine: TortuEngine | None = None

        scene_id = manifest.resolve_start_scene()
        scene_path = manifest.scene_path(scene_id)
        self.scene = load_scene(scene_path, project_root=cart_root)
        self.renderer = SceneRenderer.from_cart(cart_root, manifest)
        self.camera_x = 0
        self.camera_y = 0

        entry = manifest.game.get("entry", "main.py")
        main_py = cart_root / entry
        if main_py.is_file():
            game = load_game_module(cart_root, entry)
            engine = TortuEngine()
            engine.cart_root = cart_root  # type: ignore[attr-defined]
            engine.manifest = manifest    # type: ignore[attr-defined]
            self._game_module = game
            self._engine = engine
            if hasattr(game, "init"):
                game.init(engine)

    def _ensure_window(self) -> pygame.Surface:
        if self.display is None:
            self.display = Display(self.scale, self.fullscreen, self.title)
            if self._engine is not None:
                self._engine.framebuffer = self._engine.framebuffer.convert(self.display.window)
        return self.display.window

    def run(self) -> None:
        self._ensure_window()
        clock = pygame.time.Clock()
        self.running = True

        while self.running:
            dt = clock.tick(self.fps) / 1000.0

            dt = min(dt, 0.05)  # cap at 50 ms — prevents physics tunnelling on slow frames

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False

            if self._game_module and self._engine:
                game = self._game_module
                engine = self._engine
                if hasattr(game, "update"):
                    game.update(dt)
                self.renderer.tick(self.scene, dt)
                frame = self.renderer.render(
                    self.scene,
                    camera_x=self.camera_x,
                    camera_y=self.camera_y,
                )
                engine.framebuffer.blit(frame, (0, 0))
                if hasattr(game, "draw"):
                    game.draw(engine)
                self.display.present(engine.framebuffer)
            else:
                self.renderer.tick(self.scene, dt)
                frame = self.renderer.render(
                    self.scene,
                    camera_x=self.camera_x,
                    camera_y=self.camera_y,
                )
                self.display.present(frame)

        pygame.quit()
