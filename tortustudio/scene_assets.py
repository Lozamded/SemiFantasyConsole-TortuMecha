"""Shared helpers for scene editor asset pickers and project tree filtering."""

from __future__ import annotations

from pathlib import Path

ENGINE_ASSET_SUFFIXES = frozenset(
    {
        ".tortusprite",
        ".tortutileset",
        ".tortubackground",
        ".tortuscene",
        ".tortuobject",
        ".tortufont",
        ".tortuspritefont",
        ".pal",
    }
)


def is_engine_asset(path: Path) -> bool:
    """True for Tortu asset files shown when the project tree filter is on."""
    if path.name == "tortu.project":
        return True
    return path.suffix.lower() in ENGINE_ASSET_SUFFIXES


def list_tileset_paths(project_root: Path) -> list[str]:
    tiles_dir = project_root / "assets" / "tiles"
    if not tiles_dir.is_dir():
        return []
    return sorted(p.relative_to(project_root).as_posix() for p in tiles_dir.glob("*.tortutileset"))


def list_background_paths(project_root: Path) -> list[str]:
    backgrounds_dir = project_root / "assets" / "backgrounds"
    if not backgrounds_dir.is_dir():
        return []
    return sorted(
        p.relative_to(project_root).as_posix()
        for p in backgrounds_dir.glob("*.tortubackground")
    )


def list_sprite_paths(project_root: Path) -> list[str]:
    sprites_dir = project_root / "assets" / "sprites"
    if not sprites_dir.is_dir():
        return []
    return sorted(
        p.relative_to(project_root).as_posix() for p in sprites_dir.glob("*.tortusprite")
    )


def list_object_paths(project_root: Path) -> list[str]:
    objects_dir = project_root / "assets" / "objects"
    if not objects_dir.is_dir():
        return []
    return sorted(
        p.relative_to(project_root).as_posix() for p in objects_dir.glob("*.tortuobject")
    )


def list_text_font_paths(project_root: Path) -> list[str]:
    fonts_dir = project_root / "assets" / "fonts"
    if not fonts_dir.is_dir():
        return []
    return sorted(
        p.relative_to(project_root).as_posix() for p in fonts_dir.glob("*.tortufont")
    )


def list_sprite_font_paths(project_root: Path) -> list[str]:
    fonts_dir = project_root / "assets" / "fonts"
    if not fonts_dir.is_dir():
        return []
    return sorted(
        p.relative_to(project_root).as_posix() for p in fonts_dir.glob("*.tortuspritefont")
    )


def list_scene_paths(project_root: Path) -> list[str]:
    scenes_dir = project_root / "scenes"
    if not scenes_dir.is_dir():
        return []
    return sorted(
        p.relative_to(project_root).as_posix() for p in scenes_dir.glob("*.tortuscene")
    )
