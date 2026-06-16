"""Render a .tortuscene into a pygame surface (game preview / runtime)."""

from __future__ import annotations

from pathlib import Path

import pygame

from tortuengine.background import Background, load_background
from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.object import TortuObject, load_object
from tortuengine.palette import TRANSPARENT_INDEX, load_palette, palette_path
from tortuengine.scene import EMPTY_TILE, Scene, SceneObject, tile_size_for_tile_layer
from tortuengine.sprite import Sprite, load_sprite
from tortuengine.tileset import Tileset, load_tileset

MAP_BG = (30, 30, 40)


class SceneRenderer:
    """Caches assets while rendering scenes for TortuPlayer / TortuStudio preview."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._tilesets: dict[str, Tileset] = {}
        self._backgrounds: dict[str, Background] = {}
        self._bg_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self._tile_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self._sprites: dict[str, Sprite] = {}
        self._sprite_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self._objects: dict[str, TortuObject] = {}

    def _tileset(self, rel_path: str) -> Tileset | None:
        if not rel_path:
            return None
        if rel_path in self._tilesets:
            return self._tilesets[rel_path]
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_tileset(path)
        self._tilesets[rel_path] = loaded
        return loaded

    def _background(self, rel_path: str) -> Background | None:
        if not rel_path:
            return None
        if rel_path in self._backgrounds:
            return self._backgrounds[rel_path]
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_background(path)
        self._backgrounds[rel_path] = loaded
        return loaded

    def _palette(self, palette_name: str) -> list[tuple[int, int, int]] | None:
        if palette_name in self._bg_palettes:
            return self._bg_palettes[palette_name]
        path = palette_path(self.project_root, palette_name)
        if not path.is_file():
            return None
        colors = load_palette(path)
        self._bg_palettes[palette_name] = colors
        return colors

    def _tile_palette(self, scene: Scene) -> list[tuple[int, int, int]] | None:
        if scene.palette in self._tile_palettes:
            return self._tile_palettes[scene.palette]
        colors = self._palette(scene.palette)
        if colors is not None:
            self._tile_palettes[scene.palette] = colors
        return colors

    def _background_palette(self, background: Background) -> list[tuple[int, int, int]] | None:
        return self._palette(background.palette)

    def _tortu_object(self, prefab_path: str) -> TortuObject | None:
        if not prefab_path:
            return None
        if prefab_path in self._objects:
            return self._objects[prefab_path]
        path = (self.project_root / prefab_path).resolve()
        if not path.is_file():
            return None
        loaded = load_object(path)
        self._objects[prefab_path] = loaded
        return loaded

    def _sprite(self, sprite_path: str) -> Sprite | None:
        if not sprite_path:
            return None
        if sprite_path in self._sprites:
            return self._sprites[sprite_path]
        path = (self.project_root / sprite_path).resolve()
        if not path.is_file():
            return None
        loaded = load_sprite(path)
        self._sprites[sprite_path] = loaded
        return loaded

    def _sprite_palette(self, palette_name: str) -> list[tuple[int, int, int]] | None:
        return self._palette(palette_name)

    def _tile_surface(
        self,
        tileset: Tileset,
        tile_index: int,
        palette: list[tuple[int, int, int]],
    ) -> pygame.Surface | None:
        if tile_index < 0 or tile_index >= tileset.tile_count:
            return None
        size = tileset.tile_size
        tile = tileset.get_tile(tile_index)
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        for ly in range(size):
            for lx in range(size):
                index = tile[ly * size + lx]
                if index == TRANSPARENT_INDEX:
                    continue
                rgb = palette[index]
                surface.set_at((lx, ly), (*rgb, 255))
        return surface

    def _object_surface(self, inst: SceneObject) -> pygame.Surface | None:
        tortu_object = self._tortu_object(inst.prefab)
        if tortu_object is None:
            return None
        anim = inst.animation or tortu_object.default_animation
        sprite_path = tortu_object.sprite_for(anim) or tortu_object.default_sprite
        sprite = self._sprite(sprite_path)
        if sprite is None:
            return None
        palette = self._sprite_palette(sprite.palette)
        if palette is None:
            return None
        return sprite.to_surface(palette, frame_index=0)

    def render(
        self,
        scene: Scene,
        *,
        camera_x: int = 0,
        camera_y: int = 0,
        view_width: int = SCREEN_WIDTH,
        view_height: int = SCREEN_HEIGHT,
    ) -> pygame.Surface:
        """Composite the scene and return the camera viewport."""
        map_w = scene.width
        map_h = scene.height
        composite = pygame.Surface((map_w, map_h))
        composite.fill(MAP_BG)

        for scene_bg in scene.scene_bg_layers:
            if not scene_bg.visible or not scene_bg.background:
                continue
            bg = self._background(scene_bg.background)
            if bg is None:
                continue
            bg_palette = self._background_palette(bg)
            if bg_palette is None:
                continue
            if scene_bg.band_parallax and scene_bg.parallax_bands:
                bg.draw_parallax_bands(
                    composite,
                    bg_palette,
                    scene_bg.parallax_bands,
                    parallax_y=scene_bg.parallax_y,
                    camera_x=float(camera_x),
                    camera_y=float(camera_y),
                )
            else:
                bg.draw_parallax(
                    composite,
                    bg_palette,
                    parallax_x=scene_bg.parallax_x,
                    parallax_y=scene_bg.parallax_y,
                    camera_x=float(camera_x),
                    fixed=scene_bg.fixed,
                    repeat_x=scene_bg.repeat_x,
                    repeat_y=scene_bg.repeat_y,
                )

        tile_palette = self._tile_palette(scene)
        if tile_palette is not None:
            for tile_layer in scene.tile_layers:
                if not tile_layer.visible or not tile_layer.tileset:
                    continue
                tileset = self._tileset(tile_layer.tileset)
                if tileset is None:
                    continue
                tile_size = tileset.tile_size
                cols = scene.grid_columns(tile_size)
                rows = scene.grid_rows(tile_size)
                for ty in range(rows):
                    for tx in range(cols):
                        px = tx * tile_size
                        py = ty * tile_size
                        if px >= map_w or py >= map_h:
                            continue
                        tile_index = tile_layer.tiles[ty * cols + tx]
                        if tile_index == EMPTY_TILE:
                            continue
                        tile_surface = self._tile_surface(tileset, tile_index, tile_palette)
                        if tile_surface is None:
                            continue
                        composite.blit(tile_surface, (px, py))

        for inst in scene.objects:
            surface = self._object_surface(inst)
            if surface is None:
                continue
            tortu_object = self._tortu_object(inst.prefab)
            if tortu_object is None:
                continue
            draw_x = inst.x - tortu_object.origin.x
            draw_y = inst.y - tortu_object.origin.y
            composite.blit(surface, (draw_x, draw_y))

        view = pygame.Surface((view_width, view_height))
        view.fill(MAP_BG)
        max_x = max(0, map_w - view_width)
        max_y = max(0, map_h - view_height)
        cx = max(0, min(camera_x, max_x))
        cy = max(0, min(camera_y, max_y))
        view.blit(composite, (0, 0), pygame.Rect(cx, cy, view_width, view_height))
        return view
