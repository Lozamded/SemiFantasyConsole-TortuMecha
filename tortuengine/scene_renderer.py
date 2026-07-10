"""Render a .tortuscene into a pygame surface (game preview / runtime)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

from tortuengine.background import Background, load_background
from tortuengine.bake import (
    bake_background,
    bake_background_band,
    bake_sprite_frame,
    bake_tile,
    blit_parallax,
    blit_parallax_bands,
    build_tiled_surface,
)
from tortuengine.cart_manifest import CartManifest, tileset_manifest_key
from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.gui_layer import GuiLayer, GuiTextLabel, load_gui_layer
from tortuengine.image import load_image
from tortuengine import instance_api
from tortuengine.instance_scripts import InstanceScript, load_instance_script
from tortuengine.object import TortuObject, load_object
from tortuengine.palette import load_palette, palette_path
from tortuengine.scene import EMPTY_TILE, Scene, SceneObject, tile_size_for_tile_layer
from tortuengine.sprite import Sprite, load_sprite
from tortuengine.sprite_font import TortuSpriteFont, load_sprite_font, render_sprite_text_line
from tortuengine.text_font import TortuFont, load_tortu_font, render_text_line
from tortuengine.tileset import Tileset, load_tileset

MAP_BG = (30, 30, 40)


class _LRUCache(OrderedDict):
    """OrderedDict-backed LRU cache. Oldest entry is evicted when maxsize is reached."""

    def __init__(self, maxsize: int) -> None:
        super().__init__()
        self._maxsize = maxsize

    def get(self, key: Any, default: Any = None) -> Any:
        if key not in self:
            return default
        self.move_to_end(key)
        return super().__getitem__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self._maxsize:
            self.popitem(last=False)


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
        self._gui_layers: dict[str, GuiLayer] = {}
        self._text_fonts: dict[str, TortuFont] = {}
        self._sprite_fonts: dict[str, TortuSpriteFont] = {}
        self._object_anim: list[_ObjectAnimState] = []
        self._instance_scripts: list[InstanceScript | None] = []
        self._instance_keys: list[tuple[str, str]] = []
        # Baked surface caches: LRU-bounded to prevent unbounded RAM growth.
        # Source-asset dicts above are bounded by project size and don't need eviction.
        self._sprite_frame_cache: _LRUCache = _LRUCache(256)
        self._tile_cache: _LRUCache = _LRUCache(256)
        self._bg_cache: _LRUCache = _LRUCache(8)   # full bgs are ~418KB each
        self._bg_tiled_cache: _LRUCache = _LRUCache(16)
        self._bg_band_cache: _LRUCache = _LRUCache(32)
        self._png_cache: _LRUCache = _LRUCache(128)
        self._scaled_frame_cache: _LRUCache = _LRUCache(128)

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
        self._bg_tiled_cache.clear()
        self._bg_band_cache.clear()
        self._png_cache.clear()

    def reset_animations(self) -> None:
        self._object_anim = []
        self._instance_scripts = []
        self._instance_keys = []

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

    def _sync_instance_scripts(self, scene: Scene, engine) -> None:
        synced: list[InstanceScript | None] = []
        synced_keys: list[tuple[str, str]] = []
        for index, inst in enumerate(scene.objects):
            key = (inst.prefab, inst.id)
            if index < len(self._instance_keys) and self._instance_keys[index] == key:
                synced.append(self._instance_scripts[index])
            else:
                script = self._load_instance_script(inst)
                if script is not None:
                    script.init(engine)
                synced.append(script)
            synced_keys.append(key)
        self._instance_scripts = synced
        self._instance_keys = synced_keys

    def _load_instance_script(self, inst: SceneObject) -> InstanceScript | None:
        if self._cart_mode():
            return None  # instance scripts aren't part of the baked cart manifest yet
        tortu_object = self._tortu_object(inst.prefab)
        if tortu_object is None or not tortu_object.script:
            return None
        script_path = (self.project_root / tortu_object.script).resolve()
        return load_instance_script(script_path, self_id=inst.id, links=inst.links)

    def tick(self, scene: Scene, dt: float, engine=None) -> None:
        """Advance sprite frame playback and object-instance scripts for placed objects."""
        if dt <= 0:
            return

        instance_api.bind_scene(scene)
        self._sync_instance_scripts(scene, engine)
        for script in self._instance_scripts:
            if script is not None:
                script.update(dt)

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
            from tortuengine.object import ObjectAnimation, ObjectCollider, ObjectOrigin

            animations = [
                ObjectAnimation(name, sprite)
                for name, sprite in raw.get("animations", {}).items()
            ]
            origin = raw.get("origin", {})
            colliders_raw = raw.get("colliders")
            if colliders_raw and isinstance(colliders_raw, list):
                colliders = [
                    ObjectCollider(
                        name=str(c.get("name", "main")),
                        x=int(c.get("x", 0)),
                        y=int(c.get("y", 0)),
                        w=int(c.get("w", 0)),
                        h=int(c.get("h", 0)),
                        active=bool(c.get("active", True)),
                    )
                    for c in colliders_raw
                    if isinstance(c, dict)
                ]
            else:
                legacy = raw.get("hitbox", {})
                colliders = [ObjectCollider(
                    "main",
                    int(legacy.get("x", 0)),
                    int(legacy.get("y", 0)),
                    int(legacy.get("w", 0)),
                    int(legacy.get("h", 0)),
                    True,
                )]
            if not colliders:
                colliders = [ObjectCollider("main")]
            return TortuObject(
                name=str(raw.get("name", Path(prefab_path).stem)),
                animations=animations,
                default_animation=str(raw.get("default_animation", "")),
                script=str(raw.get("script", "")),
                solid=bool(raw.get("solid", False)),
                origin=ObjectOrigin(int(origin.get("x", 0)), int(origin.get("y", 0))),
                colliders=colliders,
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

    def _tiled_background(
        self,
        bg_path: str,
        baked: pygame.Surface,
        *,
        repeat_x: bool,
        repeat_y: bool,
        target_w: int,
        target_h: int,
    ) -> pygame.Surface:
        """Return a pre-tiled surface for *baked*, building and caching it on first use."""
        cache_key = (bg_path, repeat_x, repeat_y, target_w, target_h)
        cached = self._bg_tiled_cache.get(cache_key)
        if cached is not None:
            return cached
        tiled = build_tiled_surface(
            baked,
            repeat_x=repeat_x,
            repeat_y=repeat_y,
            target_w=target_w,
            target_h=target_h,
        )
        self._bg_tiled_cache[cache_key] = tiled
        return tiled

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
        base = self._baked_sprite_frame(sprite_path, sprite, frame_index)
        if base is None or inst.scale == 1.0:
            return base
        return self._scaled_surface(base, (sprite_path, frame_index, round(inst.scale, 3)), inst.scale)

    def _scaled_surface(
        self, surface: pygame.Surface, cache_key: tuple, scale: float
    ) -> pygame.Surface:
        cached = self._scaled_frame_cache.get(cache_key)
        if cached is not None:
            return cached
        width = max(1, round(surface.get_width() * scale))
        height = max(1, round(surface.get_height() * scale))
        scaled = pygame.transform.scale(surface, (width, height))
        self._scaled_frame_cache[cache_key] = scaled
        return scaled

    def _gui_layer(self, rel_path: str) -> GuiLayer | None:
        if not rel_path or self._cart_mode():
            return None
        if rel_path in self._gui_layers:
            return self._gui_layers[rel_path]
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_gui_layer(path, project_root=self.project_root)
        self._gui_layers[rel_path] = loaded
        return loaded

    def _text_font(self, rel_path: str) -> TortuFont | None:
        if not rel_path:
            return None
        if rel_path in self._text_fonts:
            return self._text_fonts[rel_path]
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_tortu_font(path)
        self._text_fonts[rel_path] = loaded
        return loaded

    def _sprite_font(self, rel_path: str) -> TortuSpriteFont | None:
        if not rel_path:
            return None
        if rel_path in self._sprite_fonts:
            return self._sprite_fonts[rel_path]
        path = (self.project_root / rel_path).resolve()
        if not path.is_file():
            return None
        loaded = load_sprite_font(path)
        self._sprite_fonts[rel_path] = loaded
        return loaded

    def _gui_label_surface(self, label: GuiTextLabel) -> pygame.Surface | None:
        if not label.text or not label.font:
            return None
        if label.font.endswith(".tortuspritefont"):
            sprite_font = self._sprite_font(label.font)
            if sprite_font is None:
                return None
            colors = self._palette(sprite_font.palette)
            if colors is None:
                return None
            return render_sprite_text_line(sprite_font, label.text, colors)
        text_font = self._text_font(label.font)
        if text_font is None:
            return None
        colors = self._palette(text_font.palette)
        if colors is None:
            return None
        return render_text_line(text_font, label.text, colors)

    def _draw_gui_layer(
        self, target: pygame.Surface, gui_layer: GuiLayer, *, ox: int = 0, oy: int = 0
    ) -> None:
        if gui_layer.tile_layer_visible and gui_layer.tileset:
            tileset = self._tileset(gui_layer.tileset, palette_name=gui_layer.palette)
            palette = self._palette(gui_layer.palette)
            if tileset is not None and palette is not None:
                tile_size = tileset.tile_size
                cols = gui_layer.grid_columns(tile_size)
                rows = gui_layer.grid_rows(tile_size)
                for ty in range(rows):
                    for tx in range(cols):
                        px = tx * tile_size
                        py = ty * tile_size
                        if px >= gui_layer.width or py >= gui_layer.height:
                            continue
                        tile_index = gui_layer.tiles[ty * cols + tx]
                        if tile_index == EMPTY_TILE:
                            continue
                        tile_surface = self._baked_tile(
                            gui_layer.tileset, tileset, tile_index, gui_layer.palette, palette
                        )
                        if tile_surface is not None:
                            target.blit(tile_surface, (ox + px, oy + py))

        for inst in gui_layer.objects:
            surface = self._object_surface(inst)
            if surface is None:
                continue
            tortu_object = self._tortu_object(inst.prefab)
            if tortu_object is None:
                continue
            draw_x = ox + inst.x - tortu_object.origin.x * inst.scale
            draw_y = oy + inst.y - tortu_object.origin.y * inst.scale
            target.blit(surface, (round(draw_x), round(draw_y)))

        for label in gui_layer.text_labels:
            surface = self._gui_label_surface(label)
            if surface is not None:
                target.blit(surface, (ox + label.x, oy + label.y))

    def render(
        self,
        scene: Scene,
        *,
        camera_x: int = 0,
        camera_y: int = 0,
        view_width: int = SCREEN_WIDTH,
        view_height: int = SCREEN_HEIGHT,
        z_max: int | None = None,
    ) -> pygame.Surface:
        """Composite the scene and return the camera viewport.

        `z_max`, if set, excludes objects and GUI layers with z_index above it.
        Backgrounds and tile layers are unaffected — they have no z_index and
        always form the base of the composite. Pair with `render_overlay()`
        when a script draws something (e.g. a player sprite) between the
        world and a foreground GUI layer, outside the normal object list.
        """
        self._sync_anim_states(scene)
        map_w = scene.width
        map_h = scene.height
        max_x = max(0, map_w - view_width)
        max_y = max(0, map_h - view_height)
        cx = max(0, min(camera_x, max_x))
        cy = max(0, min(camera_y, max_y))
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
                tiled_bg = None
                if scene_bg.repeat_x or scene_bg.repeat_y:
                    tiled_bg = self._tiled_background(
                        scene_bg.background,
                        baked_bg,
                        repeat_x=scene_bg.repeat_x,
                        repeat_y=scene_bg.repeat_y,
                        target_w=map_w,
                        target_h=map_h,
                    )
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
                    _tiled=tiled_bg,
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

        # Objects and GUI layers share one z-ordered draw pass onto the world-space
        # composite, so a GUI layer's z_index can place it behind or in front of
        # objects (z_index 0), not just behind/in front of other GUI layers. Ties
        # put the object before the GUI layer, so a default (z_index 0) GUI layer
        # still draws on top of default objects, preserving prior "always on top"
        # behavior. GUI layers are offset by the clamped camera position so their
        # camera-locked content lands at the same screen position after the final
        # viewport crop below.
        draw_items = [(inst.z_index, 0, i, inst) for i, inst in enumerate(scene.objects)]
        draw_items += [(g.z_index, 1, i, g) for i, g in enumerate(scene.gui_layers)]
        if z_max is not None:
            draw_items = [item for item in draw_items if item[0] <= z_max]
        draw_items.sort(key=lambda item: item[:3])

        for z_index, kind, index, payload in draw_items:
            if kind == 0:
                inst = payload
                if not inst.visible:
                    continue
                frame_index = 0
                if index < len(self._object_anim):
                    frame_index = self._object_anim[index].frame_index
                surface = self._object_surface(inst, frame_index=frame_index)
                if surface is None:
                    continue
                tortu_object = self._tortu_object(inst.prefab)
                if tortu_object is None:
                    continue
                draw_x = inst.x - tortu_object.origin.x * inst.scale
                draw_y = inst.y - tortu_object.origin.y * inst.scale
                composite.blit(surface, (round(draw_x), round(draw_y)))
            else:
                scene_gui = payload
                if not scene_gui.visible or not scene_gui.gui_layer:
                    continue
                gui_layer = self._gui_layer(scene_gui.gui_layer)
                if gui_layer is None:
                    continue
                self._draw_gui_layer(composite, gui_layer, ox=cx, oy=cy)

        view = pygame.Surface((view_width, view_height))
        view.fill(MAP_BG)
        view.blit(composite, (0, 0), pygame.Rect(cx, cy, view_width, view_height))

        return view

    def render_overlay(
        self,
        scene: Scene,
        *,
        camera_x: int = 0,
        camera_y: int = 0,
        view_width: int = SCREEN_WIDTH,
        view_height: int = SCREEN_HEIGHT,
        z_min: int,
    ) -> pygame.Surface:
        """Transparent, camera-locked overlay of objects/GUI layers with z_index >= z_min.

        Pairs with `render(..., z_max=z_min - 1)`: draw that first, blit anything
        the script itself controls (e.g. a manually-drawn player sprite) on top,
        then blit this overlay last so foreground GUI layers land above it.
        """
        max_x = max(0, scene.width - view_width)
        max_y = max(0, scene.height - view_height)
        cx = max(0, min(camera_x, max_x))
        cy = max(0, min(camera_y, max_y))

        view = pygame.Surface((view_width, view_height), pygame.SRCALPHA)

        draw_items = [
            (inst.z_index, 0, i, inst)
            for i, inst in enumerate(scene.objects)
            if inst.z_index >= z_min
        ]
        draw_items += [
            (g.z_index, 1, i, g) for i, g in enumerate(scene.gui_layers) if g.z_index >= z_min
        ]
        draw_items.sort(key=lambda item: item[:3])

        for _z_index, kind, index, payload in draw_items:
            if kind == 0:
                inst = payload
                if not inst.visible:
                    continue
                frame_index = 0
                if index < len(self._object_anim):
                    frame_index = self._object_anim[index].frame_index
                surface = self._object_surface(inst, frame_index=frame_index)
                if surface is None:
                    continue
                tortu_object = self._tortu_object(inst.prefab)
                if tortu_object is None:
                    continue
                draw_x = inst.x - tortu_object.origin.x * inst.scale - cx
                draw_y = inst.y - tortu_object.origin.y * inst.scale - cy
                view.blit(surface, (round(draw_x), round(draw_y)))
            else:
                scene_gui = payload
                if not scene_gui.visible or not scene_gui.gui_layer:
                    continue
                gui_layer = self._gui_layer(scene_gui.gui_layer)
                if gui_layer is None:
                    continue
                self._draw_gui_layer(view, gui_layer)

        return view
