"""TortuStudio project file (.tortu.project)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Project:
    root: Path
    name: str = "Untitled"
    version: str = "0.1.0"
    entry: str = "main.py"
    editor_command: str = "xdg-open {file}"

    def entry_path(self) -> Path:
        return self.root / self.entry

    def scenes_dir(self) -> Path:
        return self.root / "scenes"

    def assets_dir(self) -> Path:
        return self.root / "assets"

    def scripts_dir(self) -> Path:
        return self.root / "scripts"

    def palettes_dir(self) -> Path:
        return self.root / "palettes"

    def sprites_dir(self) -> Path:
        return self.root / "assets" / "sprites"

    def tiles_dir(self) -> Path:
        return self.root / "assets" / "tiles"

    def objects_dir(self) -> Path:
        return self.root / "assets" / "objects"


def load_project(path: Path) -> Project:
    if path.is_file() and path.name == "tortu.project":
        project_file = path
    else:
        project_file = path / "tortu.project"
    if not project_file.is_file():
        raise FileNotFoundError(f"Project file not found: {project_file}")

    data = json.loads(project_file.read_text(encoding="utf-8"))
    return Project(
        root=project_file.parent,
        name=data.get("name", "Untitled"),
        version=data.get("version", "0.1.0"),
        entry=data.get("entry", "main.py"),
        editor_command=data.get("editor_command", "xdg-open {file}"),
    )


def save_project(project: Project) -> None:
    project_file = project.root / "tortu.project"
    data = {
        "name": project.name,
        "version": project.version,
        "entry": project.entry,
        "editor_command": project.editor_command,
    }
    project_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


from tortuengine.palette import default_palette_colors, save_palette


def create_project(root: Path, name: str = "Untitled") -> Project:
    root.mkdir(parents=True, exist_ok=True)
    for sub in (
        "palettes",
        "scenes",
        "assets/sprites",
        "assets/tiles",
        "assets/objects",
        "assets/audio",
        "scripts",
    ):
        (root / sub).mkdir(parents=True, exist_ok=True)

    default_pal = root / "palettes" / "default.pal"
    if not default_pal.exists():
        save_palette(default_pal, default_palette_colors())

    project = Project(root=root.resolve(), name=name)
    save_project(project)
    return project
