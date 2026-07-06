"""Runs a placed object's script in an isolated module namespace.

The same .tortuobject prefab (and therefore the same script file) can be
placed many times in a scene — two robots, say. Each placed instance gets
its own private copy of the module's globals so the script can keep using
plain module-level state (the project's "no subclassing" convention, see
mechaturtle_player.py) without instances stepping on each other.

SELF_ID and LINKS are injected as globals before the script body runs, so
the script can address itself and its linked instances (see
tortuengine.instance_api) without a scene-level codegen step.
"""

from __future__ import annotations

import types
from pathlib import Path


class InstanceScript:
    """One placed object instance's isolated script module."""

    def __init__(self, module: types.ModuleType) -> None:
        self._module = module

    def init(self, engine) -> None:
        fn = getattr(self._module, "init", None)
        if fn is not None:
            fn(engine)

    def update(self, dt: float) -> None:
        fn = getattr(self._module, "update", None)
        if fn is not None:
            fn(dt)

    def draw(self, engine) -> None:
        fn = getattr(self._module, "draw", None)
        if fn is not None:
            fn(engine)


def load_instance_script(
    script_path: Path, *, self_id: str, links: list[str]
) -> InstanceScript | None:
    if not script_path.is_file():
        return None
    source = script_path.read_text(encoding="utf-8")
    code = compile(source, str(script_path), "exec")
    module = types.ModuleType(f"tortu_instance::{script_path}::{self_id or id(script_path)}")
    module.__dict__["__file__"] = str(script_path)
    module.__dict__["SELF_ID"] = self_id
    module.__dict__["LINKS"] = tuple(links)
    exec(code, module.__dict__)
    return InstanceScript(module)
