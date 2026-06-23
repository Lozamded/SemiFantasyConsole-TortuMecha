"""Per-project game / cart settings stored in tortu.project."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tortuengine.constants import DEFAULT_FPS

MIN_GAME_FPS = 1
MAX_GAME_FPS = 120

_CART_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def slugify_cart_name(value: str) -> str:
    """Turn a display name into a safe cart filename slug."""
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "_", slug)
    slug = slug.strip("_")
    if not slug:
        return "untitled"
    if not slug[0].isalnum():
        slug = f"cart_{slug}"
    return slug[:64]


@dataclass
class GameSettings:
    """Developer-facing game metadata and runtime options."""

    game_name: str = "Untitled Game"
    cart_name: str = "untitled"
    fps: int = DEFAULT_FPS
    start_scene: str = ""  # project-relative path, e.g. scenes/level_01.tortuscene
    author: str = ""
    description: str = ""
    audio_channels: list[str] = field(default_factory=lambda: ["music", "sfx_1", "sfx_2", "sfx_3"])

    def validate(self) -> None:
        if not self.game_name.strip():
            raise ValueError("Game name cannot be empty")
        cart = self.cart_name.strip()
        if not cart:
            raise ValueError("Cart name cannot be empty")
        if not _CART_NAME_RE.match(cart):
            raise ValueError(
                "Cart name must start with a letter or digit and use only "
                "lowercase letters, digits, underscores, or hyphens"
            )
        if not (MIN_GAME_FPS <= self.fps <= MAX_GAME_FPS):
            raise ValueError(f"FPS must be {MIN_GAME_FPS}–{MAX_GAME_FPS}")

    @classmethod
    def from_dict(cls, raw: dict | None, *, fallback_name: str = "Untitled Game") -> GameSettings:
        data = raw or {}
        game_name = str(data.get("game_name", data.get("title", fallback_name))).strip() or fallback_name
        cart_raw = str(data.get("cart_name", "")).strip()
        cart_name = cart_raw or slugify_cart_name(game_name)
        fps = int(data.get("fps", DEFAULT_FPS))
        raw_channels = data.get("audio_channels")
        if isinstance(raw_channels, list) and raw_channels:
            audio_channels = [str(c) for c in raw_channels if str(c).strip()]
        else:
            audio_channels = ["music", "sfx_1", "sfx_2", "sfx_3"]
        return cls(
            game_name=game_name,
            cart_name=cart_name,
            fps=fps,
            start_scene=str(data.get("start_scene", "")).replace("\\", "/").strip(),
            author=str(data.get("author", "")).strip(),
            description=str(data.get("description", "")).strip(),
            audio_channels=audio_channels,
        )

    def to_dict(self) -> dict:
        self.validate()
        data = {
            "game_name": self.game_name.strip(),
            "cart_name": self.cart_name.strip(),
            "fps": self.fps,
        }
        if self.start_scene:
            data["start_scene"] = self.start_scene
        if self.author:
            data["author"] = self.author
        if self.description:
            data["description"] = self.description
        if self.audio_channels:
            data["audio_channels"] = list(self.audio_channels)
        return data
