"""Shared helpers for scene editor asset pickers."""

from __future__ import annotations

from pathlib import Path


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
