"""TortoiseEngine — shared runtime for TortoisePlayer and TortoiseStudio."""

from tortoisengine.constants import MAX_COLORS, SCREEN_HEIGHT, SCREEN_WIDTH
from tortoisengine.engine import TortoiseEngine
from tortoisengine.game_settings import GameSettings, MAX_GAME_FPS, MIN_GAME_FPS
from tortoisengine.project import Project, load_project, save_project
from tortoisengine.palette import TRANSPARENT_INDEX, load_palette, closest_index
from tortoisengine.background import (
    Background,
    load_background,
    save_background,
)
from tortoisengine.scene import (
    EMPTY_TILE,
    MAX_SCENE_TILE_LAYERS,
    MAX_SCENE_BG_LAYERS,
    MIN_SCENE_TILE_LAYERS,
    Scene,
    SceneBgLayer,
    SceneBgParallaxBand,
    SceneObject,
    SceneTileLayer,
    load_scene,
    save_scene,
)
from tortoisengine.object import (
    CUSTOM_VAR_TYPES,
    MAX_OBJECT_COLLIDERS,
    MAX_OBJECT_CUSTOM_VARS,
    CustomVarDef,
    ObjectAnimation,
    ObjectCollider,
    ObjectOrigin,
    TortoiseObject,
    default_for_custom_var_type,
    format_custom_var_value,
    load_object,
    parse_custom_var_text,
    save_object,
)
from tortoisengine.sprite import Sprite, load_sprite, save_sprite

__all__ = [
    "SCREEN_WIDTH",
    "SCREEN_HEIGHT",
    "MAX_COLORS",
    "TRANSPARENT_INDEX",
    "EMPTY_TILE",
    "MIN_SCENE_TILE_LAYERS",
    "MAX_SCENE_TILE_LAYERS",
    "MAX_SCENE_BG_LAYERS",
    "SceneTileLayer",
    "SceneBgLayer",
    "SceneBgParallaxBand",
    "SceneObject",
    "TortoiseEngine",
    "Project",
    "load_project",
    "save_project",
    "GameSettings",
    "MIN_GAME_FPS",
    "MAX_GAME_FPS",
    "load_palette",
    "closest_index",
    "Sprite",
    "load_sprite",
    "save_sprite",
    "MAX_OBJECT_COLLIDERS",
    "MAX_OBJECT_CUSTOM_VARS",
    "CUSTOM_VAR_TYPES",
    "CustomVarDef",
    "default_for_custom_var_type",
    "parse_custom_var_text",
    "format_custom_var_value",
    "TortoiseObject",
    "ObjectAnimation",
    "ObjectCollider",
    "ObjectOrigin",
    "load_object",
    "save_object",
    "Background",
    "load_background",
    "save_background",
    "Scene",
    "load_scene",
    "save_scene",
]
