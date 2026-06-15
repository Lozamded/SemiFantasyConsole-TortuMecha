"""Object prefabs (.tortuobject) — animations, script, collision for scene placement."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MAX_OBJECT_ANIMATIONS = 16


@dataclass
class ObjectHitbox:
    """Axis-aligned hitbox in sprite pixel space. w/h of 0 means use full sprite size."""

    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0

    def copy(self) -> ObjectHitbox:
        return ObjectHitbox(self.x, self.y, self.w, self.h)

    def resolved(self, sprite_w: int, sprite_h: int) -> tuple[int, int, int, int]:
        w = self.w if self.w > 0 else sprite_w
        h = self.h if self.h > 0 else sprite_h
        return self.x, self.y, w, h


@dataclass
class ObjectOrigin:
    """Placement anchor in sprite pixel space (default top-left)."""

    x: int = 0
    y: int = 0

    def copy(self) -> ObjectOrigin:
        return ObjectOrigin(self.x, self.y)


@dataclass
class ObjectAnimation:
    name: str
    sprite: str

    def copy(self) -> ObjectAnimation:
        return ObjectAnimation(self.name, self.sprite)


@dataclass
class TortuObject:
    name: str
    animations: list[ObjectAnimation] = field(default_factory=list)
    default_animation: str = ""
    script: str = ""
    solid: bool = False
    origin: ObjectOrigin = field(default_factory=ObjectOrigin)
    hitbox: ObjectHitbox = field(default_factory=ObjectHitbox)

    @property
    def default_sprite(self) -> str:
        sprite = self.sprite_for(self.default_animation)
        if sprite:
            return sprite
        return self.animations[0].sprite if self.animations else ""

    def sprite_for(self, animation_name: str) -> str:
        for anim in self.animations:
            if anim.name == animation_name:
                return anim.sprite
        return ""

    @classmethod
    def create(cls, name: str, sprite: str, animation_name: str = "idle") -> TortuObject:
        if not sprite:
            raise ValueError("Object requires at least one animation sprite")
        anim_name = (animation_name or "idle").strip() or "idle"
        return cls(
            name=name or "object",
            animations=[ObjectAnimation(anim_name, sprite)],
            default_animation=anim_name,
        )

    def copy(self) -> TortuObject:
        return TortuObject(
            self.name,
            [anim.copy() for anim in self.animations],
            self.default_animation,
            self.script,
            self.solid,
            self.origin.copy(),
            self.hitbox.copy(),
        )


def _load_origin(raw: dict | None) -> ObjectOrigin:
    if not raw:
        return ObjectOrigin()
    return ObjectOrigin(int(raw.get("x", 0)), int(raw.get("y", 0)))


def _load_hitbox(raw: dict | None) -> ObjectHitbox:
    if not raw:
        return ObjectHitbox()
    return ObjectHitbox(
        int(raw.get("x", 0)),
        int(raw.get("y", 0)),
        int(raw.get("w", 0)),
        int(raw.get("h", 0)),
    )


def _normalize_animations(raw: list) -> list[ObjectAnimation]:
    animations: list[ObjectAnimation] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        sprite = str(entry.get("sprite", "")).strip()
        if name and sprite:
            animations.append(ObjectAnimation(name, sprite))
    return animations


def load_object(path: Path) -> TortuObject:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = str(data.get("name", path.stem))
    animations = _normalize_animations(data.get("animations", []))
    if not animations:
        legacy_sprite = str(data.get("sprite", "")).strip()
        if not legacy_sprite:
            raise ValueError(f"Object file has no animations: {path.name}")
        animations = [ObjectAnimation("idle", legacy_sprite)]
    default_animation = str(data.get("default_animation", "")).strip()
    if not default_animation or not any(a.name == default_animation for a in animations):
        default_animation = animations[0].name
    return TortuObject(
        name=name,
        animations=animations,
        default_animation=default_animation,
        script=str(data.get("script", "")),
        solid=bool(data.get("solid", False)),
        origin=_load_origin(data.get("origin")),
        hitbox=_load_hitbox(data.get("hitbox")),
    )


def save_object(obj: TortuObject, path: Path) -> None:
    if not obj.animations:
        raise ValueError("Object must have at least one animation")
    path.parent.mkdir(parents=True, exist_ok=True)
    default_animation = obj.default_animation
    if not default_animation or not any(a.name == default_animation for a in obj.animations):
        default_animation = obj.animations[0].name
    data: dict = {
        "name": obj.name,
        "default_animation": default_animation,
        "animations": [{"name": anim.name, "sprite": anim.sprite} for anim in obj.animations],
        "solid": obj.solid,
    }
    if obj.script:
        data["script"] = obj.script
    if obj.origin.x or obj.origin.y:
        data["origin"] = {"x": obj.origin.x, "y": obj.origin.y}
    hitbox = obj.hitbox
    if hitbox.x or hitbox.y or hitbox.w or hitbox.h:
        data["hitbox"] = {
            "x": hitbox.x,
            "y": hitbox.y,
            "w": hitbox.w,
            "h": hitbox.h,
        }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
