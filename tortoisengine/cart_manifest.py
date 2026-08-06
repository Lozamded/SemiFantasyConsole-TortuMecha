"""Runtime manifest for an exported .tortucart bundle."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CART_FORMAT_VERSION = 1
CART_MANIFEST_NAME = "cart.json"


def is_cart_folder(path: Path) -> bool:
    path = path.resolve()
    return path.is_dir() and (path / CART_MANIFEST_NAME).is_file()


def tileset_manifest_key(tileset_path: str, palette_name: str) -> str:
    return f"{tileset_path}@{palette_name}"


def cart_scene_key(project_relative_scene: str) -> str:
    """Map project scene path to cart scene id (no extension)."""
    rel = project_relative_scene.replace("\\", "/").strip()
    path = Path(rel)
    if path.suffix == ".tortuscene":
        path = path.with_suffix("")
    return str(path).replace("\\", "/")


@dataclass
class CartManifest:
    format_version: int
    root: Path
    game: dict
    start_scene: str
    sprites: dict[str, dict] = field(default_factory=dict)
    tilesets: dict[str, dict] = field(default_factory=dict)
    backgrounds: dict[str, dict] = field(default_factory=dict)
    objects: dict[str, dict] = field(default_factory=dict)
    scenes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, cart_root: Path) -> CartManifest:
        cart_root = cart_root.resolve()
        manifest_path = cart_root / CART_MANIFEST_NAME
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        version = int(data.get("format", 0))
        if version != CART_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported cart format {version} (expected {CART_FORMAT_VERSION})"
            )
        return cls(
            format_version=version,
            root=cart_root,
            game=dict(data.get("game", {})),
            start_scene=str(data.get("start_scene", "")).replace("\\", "/").strip(),
            sprites=dict(data.get("sprites", {})),
            tilesets=dict(data.get("tilesets", {})),
            backgrounds=dict(data.get("backgrounds", {})),
            objects=dict(data.get("objects", {})),
            scenes=dict(data.get("scenes", {})),
        )

    def scene_path(self, scene_id: str) -> Path:
        rel = self.scenes.get(scene_id)
        if not rel:
            raise KeyError(f"Scene not in cart: {scene_id}")
        return self.root / rel

    def resolve_start_scene(self) -> str:
        if not self.start_scene:
            raise ValueError("Cart has no start_scene configured")
        if self.start_scene in self.scenes:
            return self.start_scene
        alt = cart_scene_key(self.start_scene)
        if alt in self.scenes:
            return alt
        raise KeyError(f"Start scene not found in cart: {self.start_scene}")
