"""TortuEngine — shared runtime for TortuPlayer and TortuStudio."""

from tortuengine.constants import MAX_COLORS, SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.engine import TortuEngine
from tortuengine.game_settings import GameSettings, MAX_GAME_FPS, MIN_GAME_FPS
from tortuengine.project import Project, load_project, save_project
from tortuengine.palette import TRANSPARENT_INDEX, load_palette, closest_index
from tortuengine.background import (
    Background,
    load_background,
    save_background,
)
from tortuengine.scene import (
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
from tortuengine.object import (
    MAX_OBJECT_COLLIDERS,
    ObjectAnimation,
    ObjectCollider,
    ObjectOrigin,
    TortuObject,
    load_object,
    save_object,
)
from tortuengine.sprite import Sprite, load_sprite, save_sprite

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
    "TortuEngine",
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
    "TortuObject",
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
