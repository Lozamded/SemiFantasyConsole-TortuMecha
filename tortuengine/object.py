"""Object prefabs (.tortuobject) — animations, script, collision for scene placement."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

MAX_OBJECT_ANIMATIONS = 16
MAX_OBJECT_COLLIDERS = 8
MAX_OBJECT_CUSTOM_VARS = 16

CUSTOM_VAR_TYPES = ("float", "int", "string", "bool")


def default_for_custom_var_type(type_name: str) -> object:
    return {"float": 0.0, "int": 0, "string": "", "bool": False}.get(type_name, 0.0)


def parse_custom_var_scalar_text(type_name: str, text: str) -> object:
    """Parse one UI text-field value into a custom var's declared scalar type."""
    text = text.strip()
    if type_name == "float":
        try:
            return float(text)
        except ValueError:
            return 0.0
    if type_name == "int":
        try:
            return int(text)
        except ValueError:
            return 0
    if type_name == "bool":
        return text.lower() in ("1", "true", "yes", "on")
    return text


def parse_custom_var_text(type_name: str, is_array: bool, text: str) -> object:
    """Parse a UI text-field value (comma-separated if `is_array`) into a
    custom var's declared type."""
    if not is_array:
        return parse_custom_var_scalar_text(type_name, text)
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return [parse_custom_var_scalar_text(type_name, p) for p in parts]


def format_custom_var_value(is_array: bool, value: object) -> str:
    """Inverse of parse_custom_var_text — render a typed value back to UI text."""
    if is_array:
        return ", ".join(str(x) for x in value)
    return str(value)


@dataclass
class ObjectCollider:
    """Named axis-aligned collider in sprite pixel space. w/h of 0 means full sprite size."""

    name: str
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    active: bool = True  # default state at spawn

    def copy(self) -> ObjectCollider:
        return ObjectCollider(self.name, self.x, self.y, self.w, self.h, self.active)

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
class CustomVarDef:
    """A typed variable declared on an object prefab (Godot export-var /
    Unity public-field style) — its value can be overridden per placed
    scene instance, see SceneObject.custom_var_overrides."""

    name: str
    type: str = "float"  # one of CUSTOM_VAR_TYPES
    is_array: bool = False
    default: object = 0.0

    def copy(self) -> CustomVarDef:
        return CustomVarDef(self.name, self.type, self.is_array, self.default)

    def coerce(self, value: object) -> object:
        """Coerce a raw (e.g. JSON-decoded) value to this variable's declared type."""
        def _one(v: object) -> object:
            if self.type == "float":
                return float(v)
            if self.type == "int":
                return int(v)
            if self.type == "bool":
                return bool(v)
            return str(v)
        if self.is_array:
            return [_one(v) for v in (value or [])]
        return _one(value)


@dataclass
class TortuObject:
    name: str
    animations: list[ObjectAnimation] = field(default_factory=list)
    default_animation: str = ""
    script: str = ""
    solid: bool = False
    origin: ObjectOrigin = field(default_factory=ObjectOrigin)
    colliders: list[ObjectCollider] = field(default_factory=lambda: [ObjectCollider("main")])
    # Other .tortuobject prefabs this object may spawn at runtime (e.g. bullets)
    # even though they are never placed in a scene — keeps the export pipeline
    # from missing their assets.
    spawnable_objects: list[str] = field(default_factory=list)
    # Variables declared here become per-instance overridable fields in the
    # Scene Editor wherever this prefab is placed — see CustomVarDef.
    custom_vars: list[CustomVarDef] = field(default_factory=list)

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
            [c.copy() for c in self.colliders],
            list(self.spawnable_objects),
            [v.copy() for v in self.custom_vars],
        )


def _normalize_asset_path(path: str) -> str:
    return path.replace("\\", "/")


def _normalize_spawnable_objects(raw: list) -> list[str]:
    result: list[str] = []
    for entry in raw:
        path = _normalize_asset_path(str(entry)).strip()
        if path and path not in result:
            result.append(path)
    return result


def _load_origin(raw: dict | None) -> ObjectOrigin:
    if not raw:
        return ObjectOrigin()
    return ObjectOrigin(int(raw.get("x", 0)), int(raw.get("y", 0)))


def _normalize_colliders(raw: list) -> list[ObjectCollider]:
    colliders: list[ObjectCollider] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip() or "collider"
        colliders.append(ObjectCollider(
            name=name,
            x=int(entry.get("x", 0)),
            y=int(entry.get("y", 0)),
            w=int(entry.get("w", 0)),
            h=int(entry.get("h", 0)),
            active=bool(entry.get("active", True)),
        ))
    return colliders


def _normalize_custom_vars(raw: list) -> list[CustomVarDef]:
    custom_vars: list[CustomVarDef] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        type_name = str(entry.get("type", "float")).strip()
        if type_name not in CUSTOM_VAR_TYPES:
            type_name = "float"
        is_array = bool(entry.get("is_array", False))
        var = CustomVarDef(name=name, type=type_name, is_array=is_array)
        raw_default = entry.get("default", [] if is_array else default_for_custom_var_type(type_name))
        var.default = var.coerce(raw_default)
        custom_vars.append(var)
    return custom_vars


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

    colliders_raw = data.get("colliders")
    if colliders_raw and isinstance(colliders_raw, list):
        colliders = _normalize_colliders(colliders_raw)
    else:
        legacy = data.get("hitbox", {})
        colliders = [ObjectCollider(
            name="main",
            x=int(legacy.get("x", 0)),
            y=int(legacy.get("y", 0)),
            w=int(legacy.get("w", 0)),
            h=int(legacy.get("h", 0)),
            active=True,
        )]
    if not colliders:
        colliders = [ObjectCollider("main")]

    spawnable_raw = data.get("spawnable_objects", [])
    spawnable_objects = _normalize_spawnable_objects(spawnable_raw) if isinstance(spawnable_raw, list) else []

    custom_vars_raw = data.get("custom_vars", [])
    custom_vars = _normalize_custom_vars(custom_vars_raw) if isinstance(custom_vars_raw, list) else []

    return TortuObject(
        name=name,
        animations=animations,
        default_animation=default_animation,
        script=str(data.get("script", "")),
        solid=bool(data.get("solid", False)),
        origin=_load_origin(data.get("origin")),
        colliders=colliders,
        spawnable_objects=spawnable_objects,
        custom_vars=custom_vars,
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
    data["colliders"] = [
        {"name": c.name, "x": c.x, "y": c.y, "w": c.w, "h": c.h, "active": c.active}
        for c in obj.colliders
    ]
    if obj.spawnable_objects:
        data["spawnable_objects"] = [_normalize_asset_path(p) for p in obj.spawnable_objects]
    if obj.custom_vars:
        data["custom_vars"] = [
            {"name": v.name, "type": v.type, "is_array": v.is_array, "default": v.default}
            for v in obj.custom_vars
        ]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
