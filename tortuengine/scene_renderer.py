"""Render a .tortuscene into a pygame surface (game preview / runtime)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from tortuengine.background import Background, load_background
from tortuengine.bake import (
    bake_background,
    bake_background_band,
    bake_sprite_frame,
    bake_tile,
    blit_parallax,
    blit_parallax_bands,
)
from tortuengine.cart_manifest import CartManifest, tileset_manifest_key
from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.image import load_image
from tortuengine.object import TortuObject, load_object
from tortuengine.palette import load_palette, palette_path
from tortuengine.scene import EMPTY_TILE, Scene, SceneObject, tile_size_for_tile_layer
from tortuengine.sprite import Sprite, load_sprite
from tortuengine.tileset import Tileset, load_tileset

MAP_BG = (30, 30, 40)


@dataclass
class _ObjectAnimState:
    animation: str
    frame_index: int = 0
    elapsed: float = 0.0


class SceneRenderer:
    """Caches baked assets while rendering scenes for TortuPlayer / TortuStudio preview."""

    def __init__(self, project_root: Path, *, cart_manifest: CartManifest | None = None) -> None:
        self.project_root = project_root.resolve()
        self._cart_manifest = cart_manifest
        self._tilesets: dict[str, Tileset] = {}
        self._backgrounds: dict[str, Background] = {}
        self._bg_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self._tile_palettes: dict[str, list[tuple[int, int, int]]] = {}
        self._sprites: dict[str, Sprite] = {}
        self._objects: dict[str, TortuObject] = {}
        self._object_anim: list[_ObjectAnimState] = []
        self._sprite_frame_cache: dict[tuple[str, int], pygame.Surface] = {}
        self._tile_cache: dict[tuple[str, int, str], pygame.Surface] = {}
        self._bg_cache: dict[str, pygame.Surface] = {}
        self._bg_band_cache: dict[tuple[str, int, int], pygame.Surface] = {}
        self._png_cache: dict[str, pygame.Surface] = {}

    @classmethod
    def from_cart(cls, cart_root: Path, manifest: CartManifest) -> SceneRenderer:
        return cls(cart_root, cart_manifest=manifest)

    def _cart_mode(self) -> bool:
        return self._cart_manifest is not None

    def _load_png(self, rel_path: str) -> pygame.Surface | None:
        rel_path = rel_path.replace("\\", "/")
        cached = self._png_cache.get(rel_path)
        if cached is not None:
            return cached
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        surface = load_image(path)
        self._png_cache[rel_path] = surface
        return surface

    def clear_baked_cache(self) -> None:
        """Drop baked surfaces (e.g. after asset edits). Loaded source assets are kept."""
        self._sprite_frame_cache.clear()
        self._tile_cache.clear()
        self._bg_cache.clear()
        self._bg_band_cache.clear()
        self._png_cache.clear()

    def reset_animations(self) -> None:
        self._object_anim = []

    def _animation_for(self, inst: SceneObject) -> str:
        tortu_object = self._tortu_object(inst.prefab)
        if tortu_object is None:
            return ""
        return inst.animation or tortu_object.default_animation

    def _sprite_for_instance(self, inst: SceneObject) -> Sprite | None:
        tortu_object = self._tortu_object(inst.prefab)
        if tortu_object is None:
            return None
        anim = inst.animation or tortu_object.default_animation
        sprite_path = tortu_object.sprite_for(anim) or tortu_object.default_sprite
        return self._sprite(sprite_path)

    def _sync_anim_states(self, scene: Scene) -> None:
        synced: list[_ObjectAnimState] = []
        for index, inst in enumerate(scene.objects):
            animation = self._animation_for(inst)
            if (
                index < len(self._object_anim)
                and self._object_anim[index].animation == animation
            ):
                synced.append(self._object_anim[index])
            else:
                synced.append(_ObjectAnimState(animation))
        self._object_anim = synced

    def tick(self, scene: Scene, dt: float) -> None:
        """Advance sprite frame playback for placed objects."""
        if dt <= 0:
            return
        self._sync_anim_states(scene)
        for index, inst in enumerate(scene.objects):
            if index >= len(self._object_anim):
                break
            sprite = self._sprite_for_instance(inst)
            if sprite is None or sprite.frame_count <= 1:
                continue
            fps = max(1, sprite.fps)
            state = self._object_anim[index]
            state.elapsed += dt
            frame_interval = 1.0 / fps
            while state.elapsed >= frame_interval:
                state.elapsed -= frame_interval
                state.frame_index = (state.frame_index + 1) % sprite.frame_count

    def _tileset(self, rel_path: str, *, palette_name: str = "") -> Tileset | None:
        if not rel_path:
            return None
        if self._cart_mode():
            manifest = self._cart_manifest
            assert manifest is not None
            key = tileset_manifest_key(rel_path, palette_name)
            cache_key = f"__cart__{key}"
            if cache_key in self._tilesets:
                return self._tilesets[cache_key]
            entry = manifest.tilesets.get(key)
            if entry is None:
                return None
            tile_size = int(entry.get("tile_size", 8))
            tile_count = len(entry.get("tiles", []))
            stub = Tileset(
                palette=palette_name,
                tile_size=tile_size,
                tiles=[[] for _ in range(max(tile_count, 1))],
            )
            self._tilesets[cache_key] = stub
            return stub
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
        if self._cart_mode():
            manifest = self._cart_manifest
            assert manifest is not None
            if rel_path in self._backgrounds:
                return self._backgrounds[rel_path]
            entry = manifest.backgrounds.get(rel_path)
            if entry is None:
                return None
            stub = Background(
                palette="",
                width=int(entry.get("width", 1)),
                height=int(entry.get("height", 1)),
            )
            self._backgrounds[rel_path] = stub
            return stub
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
        if self._cart_mode():
            return [(0, 0, 0)]
        if scene.palette in self._tile_palettes:
            return self._tile_palettes[scene.palette]
        colors = self._palette(scene.palette)
        if colors is not None:
            self._tile_palettes[scene.palette] = colors
        return colors

    def _background_palette(self, background: Background) -> list[tuple[int, int, int]] | None:
        if self._cart_mode():
            return [(0, 0, 0)]
        return self._palette(background.palette)

    def _tortu_object(self, prefab_path: str) -> TortuObject | None:
        if not prefab_path:
            return None
        if self._cart_mode():
            manifest = self._cart_manifest
            assert manifest is not None
            raw = manifest.objects.get(prefab_path)
            if raw is None:
                return None
            from tortuengine.object import ObjectAnimation, ObjectHitbox, ObjectOrigin

            animations = [
                ObjectAnimation(name, sprite)
                for name, sprite in raw.get("animations", {}).items()
            ]
            origin = raw.get("origin", {})
            hitbox = raw.get("hitbox", {})
            return TortuObject(
                name=str(raw.get("name", Path(prefab_path).stem)),
                animations=animations,
                default_animation=str(raw.get("default_animation", "")),
                script=str(raw.get("script", "")),
                solid=bool(raw.get("solid", False)),
                origin=ObjectOrigin(int(origin.get("x", 0)), int(origin.get("y", 0))),
                hitbox=ObjectHitbox(
                    int(hitbox.get("x", 0)),
                    int(hitbox.get("y", 0)),
                    int(hitbox.get("w", 0)),
                    int(hitbox.get("h", 0)),
                ),
            )
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
        if self._cart_mode():
            manifest = self._cart_manifest
            assert manifest is not None
            entry = manifest.sprites.get(sprite_path)
            if entry is None:
                return None
            if sprite_path in self._sprites:
                return self._sprites[sprite_path]
            frames = entry.get("frames", [])
            fps = int(entry.get("fps", 8))
            width = int(entry.get("width", 1))
            height = int(entry.get("height", 1))
            blocks_w = max(1, width // 4)
            blocks_h = max(1, height // 4)
            sprite = Sprite(blocks_w, blocks_h, "", [[]] * max(1, len(frames)), fps=fps)
            self._sprites[sprite_path] = sprite
            return sprite
        if sprite_path in self._sprites:
            return self._sprites[sprite_path]
        path = (self.project_root / sprite_path).resolve()
        if not path.is_file():
            return None
        loaded = load_sprite(path)
        self._sprites[sprite_path] = loaded
        return loaded

    def _baked_sprite_frame(
        self,
        sprite_path: str,
        sprite: Sprite,
        frame_index: int,
    ) -> pygame.Surface | None:
        if self._cart_mode():
            manifest = self._cart_manifest
            assert manifest is not None
            entry = manifest.sprites.get(sprite_path)
            if entry is None:
                return None
            frames = entry.get("frames", [])
            if not frames:
                return None
            if frame_index < 0 or frame_index >= len(frames):
                frame_index = 0
            return self._load_png(str(frames[frame_index]))
        cache_key = (sprite_path, frame_index)
        cached = self._sprite_frame_cache.get(cache_key)
        if cached is not None:
            return cached
        palette = self._palette(sprite.palette)
        if palette is None:
            return None
        baked = bake_sprite_frame(sprite, palette, frame_index)
        self._sprite_frame_cache[cache_key] = baked
        return baked

    def _baked_tile(
        self,
        tileset_path: str,
        tileset: Tileset,
        tile_index: int,
        palette_name: str,
        palette: list[tuple[int, int, int]],
    ) -> pygame.Surface | None:
        if self._cart_mode():
            manifest = self._cart_manifest
            assert manifest is not None
            key = tileset_manifest_key(tileset_path, palette_name)
            entry = manifest.tilesets.get(key)
            if entry is None:
                return None
            tiles = entry.get("tiles", [])
            if tile_index < 0 or tile_index >= len(tiles):
                return None
            return self._load_png(str(tiles[tile_index]))
        if tile_index < 0 or tile_index >= tileset.tile_count:
            return None
        cache_key = (tileset_path, tile_index, palette_name)
        cached = self._tile_cache.get(cache_key)
        if cached is not None:
            return cached
        baked = bake_tile(tileset, palette, tile_index)
        self._tile_cache[cache_key] = baked
        return baked

    def _baked_background(
        self,
        bg_path: str,
        background: Background,
        palette: list[tuple[int, int, int]],
    ) -> pygame.Surface:
        if self._cart_mode():
            manifest = self._cart_manifest
            assert manifest is not None
            entry = manifest.backgrounds.get(bg_path)
            if entry is None:
                return pygame.Surface((1, 1), pygame.SRCALPHA)
            full = entry.get("full")
            if full:
                loaded = self._load_png(str(full))
                if loaded is not None:
                    return loaded
        cached = self._bg_cache.get(bg_path)
        if cached is not None:
            return cached
        baked = bake_background(background, palette)
        self._bg_cache[bg_path] = baked
        return baked

    def _baked_background_bands(
        self,
        bg_path: str,
        background: Background,
        palette: list[tuple[int, int, int]],
        bands: list,
    ) -> dict[tuple[int, int], pygame.Surface]:
        if self._cart_mode():
            manifest = self._cart_manifest
            assert manifest is not None
            entry = manifest.backgrounds.get(bg_path, {})
            baked: dict[tuple[int, int], pygame.Surface] = {}
            raw_bands = entry.get("bands", {})
            for band in bands:
                band_key = f"{band.y0}:{band.y1}"
                rel = raw_bands.get(band_key)
                if rel is None:
                    continue
                strip = self._load_png(str(rel))
                if strip is not None:
                    baked[(band.y0, band.y1)] = strip
            return baked
        baked: dict[tuple[int, int], pygame.Surface] = {}
        for band in bands:
            key = (bg_path, band.y0, band.y1)
            cached = self._bg_band_cache.get(key)
            if cached is not None:
                baked[(band.y0, band.y1)] = cached
                continue
            strip = bake_background_band(background, palette, band.y0, band.y1)
            self._bg_band_cache[key] = strip
            baked[(band.y0, band.y1)] = strip
        return baked

    def _object_surface(self, inst: SceneObject, *, frame_index: int = 0) -> pygame.Surface | None:
        tortu_object = self._tortu_object(inst.prefab)
        if tortu_object is None:
            return None
        anim = inst.animation or tortu_object.default_animation
        sprite_path = tortu_object.sprite_for(anim) or tortu_object.default_sprite
        sprite = self._sprite(sprite_path)
        if sprite is None:
            return None
        if frame_index < 0 or frame_index >= sprite.frame_count:
            frame_index = 0
        return self._baked_sprite_frame(sprite_path, sprite, frame_index)

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
        self._sync_anim_states(scene)
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
                band_surfaces = self._baked_background_bands(
                    scene_bg.background,
                    bg,
                    bg_palette,
                    scene_bg.parallax_bands,
                )
                blit_parallax_bands(
                    composite,
                    scene_bg.parallax_bands,
                    band_surfaces,
                    bg_height=bg.height,
                    parallax_y=scene_bg.parallax_y,
                    camera_x=float(camera_x),
                    camera_y=float(camera_y),
                )
            else:
                baked_bg = self._baked_background(scene_bg.background, bg, bg_palette)
                blit_parallax(
                    composite,
                    baked_bg,
                    parallax_x=scene_bg.parallax_x,
                    parallax_y=scene_bg.parallax_y,
                    camera_x=float(camera_x),
                    camera_y=float(camera_y),
                    fixed=scene_bg.fixed,
                    repeat_x=scene_bg.repeat_x,
                    repeat_y=scene_bg.repeat_y,
                )

        tile_palette = self._tile_palette(scene)
        if tile_palette is not None:
            for tile_layer in scene.tile_layers:
                if not tile_layer.visible or not tile_layer.tileset:
                    continue
                tileset = self._tileset(tile_layer.tileset, palette_name=scene.palette)
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
                        tile_surface = self._baked_tile(
                            tile_layer.tileset,
                            tileset,
                            tile_index,
                            scene.palette,
                            tile_palette,
                        )
                        if tile_surface is None:
                            continue
                        composite.blit(tile_surface, (px, py))

        for index, inst in enumerate(scene.objects):
            frame_index = 0
            if index < len(self._object_anim):
                frame_index = self._object_anim[index].frame_index
            surface = self._object_surface(inst, frame_index=frame_index)
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
