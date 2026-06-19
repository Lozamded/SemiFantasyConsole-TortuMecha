"""Run an exported .tortucart start scene in a pygame window."""

from __future__ import annotations

import pygame

from tortuengine.cart_manifest import CartManifest
from tortuengine.constants import DEFAULT_FPS, SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.scene import load_scene
from tortuengine.scene_renderer import SceneRenderer


class CartScenePlayer:
    def __init__(
        self,
        cart_root,
        manifest: CartManifest,
        *,
        scale: int = 3,
        title: str = "TortuPlayer",
        fps: int = DEFAULT_FPS,
    ) -> None:
        if not pygame.get_init():
            pygame.init()

        self.cart_root = cart_root
        self.manifest = manifest
        self.scale = scale
        self.title = title
        self.fps = fps
        self.running = False
        self.window: pygame.Surface | None = None

        scene_id = manifest.resolve_start_scene()
        scene_path = manifest.scene_path(scene_id)
        self.scene = load_scene(scene_path, project_root=cart_root)
        self.renderer = SceneRenderer.from_cart(cart_root, manifest)
        self.camera_x = 0
        self.camera_y = 0

    def _ensure_window(self) -> pygame.Surface:
        if self.window is None:
            self.window = pygame.display.set_mode(
                (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED
            )
            pygame.display.set_caption(self.title)
        return self.window

    def run(self) -> None:
        window = self._ensure_window()
        clock = pygame.time.Clock()
        self.running = True

        while self.running:
            dt = clock.tick(self.fps) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    self.running = False

            self.renderer.tick(self.scene, dt)
            frame = self.renderer.render(
                self.scene,
                camera_x=self.camera_x,
                camera_y=self.camera_y,
            )
            window.blit(frame, (0, 0))
            pygame.display.flip()

        pygame.quit()
