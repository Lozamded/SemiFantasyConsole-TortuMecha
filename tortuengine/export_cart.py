"""Export a Tortu project to a pre-baked .tortucart folder."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from tortuengine.background import load_background
from tortuengine.bake import (
    bake_background,
    bake_background_band,
    bake_sprite_frame,
    bake_tile,
)
from tortuengine.cart_manifest import (
    CART_FORMAT_VERSION,
    CART_MANIFEST_NAME,
    cart_scene_key,
    tileset_manifest_key,
)
from tortuengine.object import TortuObject, load_object
from tortuengine.palette import load_palette, palette_path
from tortuengine.project import Project
from tortuengine.scene import Scene, load_scene, save_scene
from tortuengine.sprite import load_sprite
from tortuengine.tileset import load_tileset


def _asset_slug(rel_path: str) -> str:
    path = Path(rel_path.replace("\\", "/"))
    if path.suffix.startswith(".tortu"):
        path = path.with_suffix("")
    return str(path).replace("\\", "/")


def _rel_to_project(project: Project, path: Path) -> str:
    return path.resolve().relative_to(project.root.resolve()).as_posix()


@dataclass
class _ExportPlan:
    scene_paths: list[str] = field(default_factory=list)
    sprites: set[str] = field(default_factory=set)
    tilesets: set[tuple[str, str]] = field(default_factory=set)
    backgrounds: set[str] = field(default_factory=set)
    objects: set[str] = field(default_factory=set)


def _collect_scene_assets(project: Project, scene: Scene, scene_rel: str, plan: _ExportPlan) -> None:
    if scene_rel not in plan.scene_paths:
        plan.scene_paths.append(scene_rel)

    for layer in scene.tile_layers:
        if layer.tileset:
            plan.tilesets.add((layer.tileset, scene.palette))

    for bg_layer in scene.scene_bg_layers:
        if bg_layer.background:
            plan.backgrounds.add(bg_layer.background)

    for inst in scene.objects:
        if inst.prefab:
            plan.objects.add(inst.prefab)


def _collect_object_sprites(project: Project, object_path: str, plan: _ExportPlan) -> TortuObject:
    path = (project.root / object_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Object not found for export: {object_path}")
    tortu_object = load_object(path)
    for anim in tortu_object.animations:
        if anim.sprite:
            plan.sprites.add(anim.sprite)
    return tortu_object


def _collect_object_dependencies(project: Project, plan: _ExportPlan) -> None:
    """Pull in objects a prefab may spawn at runtime (e.g. bullets) though never placed."""
    queue = list(plan.objects)
    seen = set(plan.objects)
    while queue:
        object_path = queue.pop()
        tortu_object = _collect_object_sprites(project, object_path, plan)
        for dep in tortu_object.spawnable_objects:
            if dep and dep not in seen:
                seen.add(dep)
                plan.objects.add(dep)
                queue.append(dep)


def build_export_plan(project: Project) -> _ExportPlan:
    plan = _ExportPlan()
    scenes_dir = project.scenes_dir()
    if not scenes_dir.is_dir():
        return plan

    scene_files = sorted(scenes_dir.glob("*.tortuscene"))
    if not scene_files:
        return plan

    for scene_file in scene_files:
        scene_rel = _rel_to_project(project, scene_file)
        scene = load_scene(scene_file, project_root=project.root)
        _collect_scene_assets(project, scene, scene_rel, plan)

    _collect_object_dependencies(project, plan)

    return plan


def _write_png(surface: pygame.Surface, path: Path, *, cart_root: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(path))
    return path.resolve().relative_to(cart_root.resolve()).as_posix()


def _export_sprite(
    project: Project,
    cart_root: Path,
    sprite_rel: str,
    manifest_sprites: dict[str, dict],
) -> None:
    if sprite_rel in manifest_sprites:
        return
    path = (project.root / sprite_rel).resolve()
    sprite = load_sprite(path)
    palette = load_palette(palette_path(project.root, sprite.palette))
    slug = _asset_slug(sprite_rel)
    frame_paths: list[str] = []
    for frame_index in range(sprite.frame_count):
        baked = bake_sprite_frame(sprite, palette, frame_index)
        rel_out = _write_png(
            baked,
            cart_root / "baked" / slug / f"f{frame_index}.png",
            cart_root=cart_root,
        )
        frame_paths.append(rel_out)
    manifest_sprites[sprite_rel] = {
        "fps": sprite.fps,
        "width": sprite.pixel_width,
        "height": sprite.pixel_height,
        "frames": frame_paths,
    }


def _export_tileset(
    project: Project,
    cart_root: Path,
    tileset_rel: str,
    palette_name: str,
    manifest_tilesets: dict[str, dict],
) -> None:
    key = tileset_manifest_key(tileset_rel, palette_name)
    if key in manifest_tilesets:
        return
    path = (project.root / tileset_rel).resolve()
    tileset = load_tileset(path)
    palette = load_palette(palette_path(project.root, palette_name))
    slug = _asset_slug(tileset_rel)
    tile_paths: list[str] = []
    for tile_index in range(tileset.tile_count):
        baked = bake_tile(tileset, palette, tile_index)
        rel_out = _write_png(
            baked,
            cart_root / "baked" / slug / palette_name / f"t{tile_index}.png",
            cart_root=cart_root,
        )
        tile_paths.append(rel_out)
    manifest_tilesets[key] = {
        "tile_size": tileset.tile_size,
        "tiles": tile_paths,
    }


def _export_background(
    project: Project,
    cart_root: Path,
    bg_rel: str,
    manifest_backgrounds: dict[str, dict],
    *,
    band_specs: list[tuple[int, int]],
) -> None:
    if bg_rel in manifest_backgrounds:
        entry = manifest_backgrounds[bg_rel]
        existing_bands = entry.get("bands", {})
        for y0, y1 in band_specs:
            band_key = f"{y0}:{y1}"
            if band_key not in existing_bands:
                path = (project.root / bg_rel).resolve()
                background = load_background(path)
                palette = load_palette(palette_path(project.root, background.palette))
                slug = _asset_slug(bg_rel)
                strip = bake_background_band(background, palette, y0, y1)
                rel_out = _write_png(
                    strip,
                    cart_root / "baked" / slug / f"band_{y0}_{y1}.png",
                    cart_root=cart_root,
                )
                existing_bands[band_key] = rel_out
        entry["bands"] = existing_bands
        return

    path = (project.root / bg_rel).resolve()
    background = load_background(path)
    palette = load_palette(palette_path(project.root, background.palette))
    slug = _asset_slug(bg_rel)
    full_path = _write_png(
        bake_background(background, palette),
        cart_root / "baked" / slug / "full.png",
        cart_root=cart_root,
    )
    bands: dict[str, str] = {}
    for y0, y1 in band_specs:
        strip = bake_background_band(background, palette, y0, y1)
        band_key = f"{y0}:{y1}"
        bands[band_key] = _write_png(
            strip,
            cart_root / "baked" / slug / f"band_{y0}_{y1}.png",
            cart_root=cart_root,
        )
    manifest_backgrounds[bg_rel] = {
        "width": background.width,
        "height": background.height,
        "full": full_path,
        "bands": bands,
    }


def _export_object(project: Project, object_rel: str, manifest_objects: dict[str, dict]) -> None:
    if object_rel in manifest_objects:
        return
    path = (project.root / object_rel).resolve()
    tortu_object = load_object(path)
    manifest_objects[object_rel] = {
        "name": tortu_object.name,
        "default_animation": tortu_object.default_animation,
        "animations": {anim.name: anim.sprite for anim in tortu_object.animations},
        "solid": tortu_object.solid,
        "origin": {"x": tortu_object.origin.x, "y": tortu_object.origin.y},
        "colliders": [
            {"name": c.name, "x": c.x, "y": c.y, "w": c.w, "h": c.h, "active": c.active}
            for c in tortu_object.colliders
        ],
        "script": tortu_object.script,
        "spawnable_objects": list(tortu_object.spawnable_objects),
    }


def _collect_background_bands(project: Project, plan: _ExportPlan) -> dict[str, list[tuple[int, int]]]:
    bands_by_bg: dict[str, list[tuple[int, int]]] = {}
    for scene_rel in plan.scene_paths:
        scene = load_scene(project.root / scene_rel, project_root=project.root)
        for bg_layer in scene.scene_bg_layers:
            if not bg_layer.background:
                continue
            if bg_layer.band_parallax and bg_layer.parallax_bands:
                specs = bands_by_bg.setdefault(bg_layer.background, [])
                for band in bg_layer.parallax_bands:
                    pair = (band.y0, band.y1)
                    if pair not in specs:
                        specs.append(pair)
    return bands_by_bg


def export_cart(project: Project, dest: Path) -> Path:
    """Bake assets and write a .tortucart folder at *dest*."""
    if not pygame.get_init():
        pygame.init()

    project.game.validate()
    dest = dest.resolve()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    (dest / "scenes").mkdir()

    plan = build_export_plan(project)
    if not plan.scene_paths:
        raise ValueError("No scenes found to export")

    manifest_sprites: dict[str, dict] = {}
    manifest_tilesets: dict[str, dict] = {}
    manifest_backgrounds: dict[str, dict] = {}
    manifest_objects: dict[str, dict] = {}
    manifest_scenes: dict[str, str] = {}

    for sprite_rel in sorted(plan.sprites):
        _export_sprite(project, dest, sprite_rel, manifest_sprites)

    for tileset_rel, palette_name in sorted(plan.tilesets):
        _export_tileset(project, dest, tileset_rel, palette_name, manifest_tilesets)

    bands_by_bg = _collect_background_bands(project, plan)
    for bg_rel in sorted(plan.backgrounds):
        _export_background(
            project,
            dest,
            bg_rel,
            manifest_backgrounds,
            band_specs=bands_by_bg.get(bg_rel, []),
        )

    for object_rel in sorted(plan.objects):
        _export_object(project, object_rel, manifest_objects)

    for scene_rel in plan.scene_paths:
        scene = load_scene(project.root / scene_rel, project_root=project.root)
        scene_id = cart_scene_key(scene_rel)
        out_rel = f"scenes/{Path(scene_id).name}.tortuscene"
        save_scene(scene, dest / out_rel, project_root=project.root)
        manifest_scenes[scene_id] = out_rel
        legacy_key = scene_rel
        if legacy_key not in manifest_scenes:
            manifest_scenes[legacy_key] = out_rel

    start_scene = ""
    if project.game.start_scene.strip():
        start_scene = cart_scene_key(project.game.start_scene)

    manifest = {
        "format": CART_FORMAT_VERSION,
        "game": project.game.to_dict(),
        "start_scene": start_scene,
        "sprites": manifest_sprites,
        "tilesets": manifest_tilesets,
        "backgrounds": manifest_backgrounds,
        "objects": manifest_objects,
        "scenes": manifest_scenes,
    }

    # Optional meta folder (titlecard.png, icon.png, manual.pdf)
    meta_src = project.root / "meta"
    if meta_src.is_dir():
        shutil.copytree(meta_src, dest / "meta")
        meta_entry: dict[str, str] = {}
        for fname, key in [
            ("titlecard.png", "titlecard"),
            ("icon.png", "icon"),
            ("manual.pdf", "manual"),
        ]:
            if (meta_src / fname).is_file():
                meta_entry[key] = f"meta/{fname}"
        if meta_entry:
            manifest["meta"] = meta_entry

    (dest / CART_MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    entry_path = project.root / project.entry
    if entry_path.is_file():
        shutil.copy2(entry_path, dest / project.entry)

    scripts_dir = project.scripts_dir()
    if scripts_dir.is_dir():
        shutil.copytree(scripts_dir, dest / "scripts")

    audio_dir = project.audio_dir()
    if audio_dir.is_dir():
        shutil.copytree(audio_dir, dest / "assets" / "audio")

    # Copy source asset files so game scripts can load them directly
    # (sprites for frame metadata, tilesets for collision, objects for hitboxes)
    palettes_dir = project.palettes_dir()
    if palettes_dir.is_dir():
        shutil.copytree(palettes_dir, dest / "palettes")

    for sprite_rel in sorted(plan.sprites):
        src = project.root / sprite_rel
        dst = dest / sprite_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for tileset_rel, _ in sorted(plan.tilesets):
        src = project.root / tileset_rel
        dst = dest / tileset_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for object_rel in sorted(plan.objects):
        src = project.root / object_rel
        dst = dest / object_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    return dest
