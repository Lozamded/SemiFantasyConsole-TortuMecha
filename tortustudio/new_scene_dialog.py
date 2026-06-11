"""Dialog to create a new .tortuscene asset."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from tortuengine.constants import TILE_BLOCK
from tortuengine.palette import list_palette_names
from tortuengine.scene import (
    DEFAULT_SCENE_HEIGHT_TILES,
    DEFAULT_SCENE_WIDTH_TILES,
    MAX_SCENE_LAYERS,
    MIN_SCENE_LAYERS,
)


def list_tileset_paths(project_root: Path) -> list[str]:
    tiles_dir = project_root / "assets" / "tiles"
    if not tiles_dir.is_dir():
        return []
    paths = sorted(p.relative_to(project_root).as_posix() for p in tiles_dir.glob("*.tortutileset"))
    return paths


class NewSceneDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Scene")

        self.name_edit = QLineEdit("level_01")
        self.palette_combo = QComboBox()
        names = list_palette_names(project_root)
        if not names:
            names = ["default"]
        self.palette_combo.addItems(names)

        self.tileset_combo = QComboBox()
        tilesets = list_tileset_paths(project_root)
        if tilesets:
            self.tileset_combo.addItems(tilesets)
        else:
            self.tileset_combo.addItem("assets/tiles/terrain.tortutileset")

        self.width_tiles = QSpinBox()
        self.width_tiles.setRange(1, 256)
        self.width_tiles.setValue(DEFAULT_SCENE_WIDTH_TILES)
        self.width_tiles.setSuffix(" tiles")

        self.height_tiles = QSpinBox()
        self.height_tiles.setRange(1, 256)
        self.height_tiles.setValue(DEFAULT_SCENE_HEIGHT_TILES)
        self.height_tiles.setSuffix(" tiles")

        self.layer_count = QSpinBox()
        self.layer_count.setRange(MIN_SCENE_LAYERS, MAX_SCENE_LAYERS)
        self.layer_count.setValue(MIN_SCENE_LAYERS)

        self.collision_layer = QSpinBox()
        self.collision_layer.setRange(0, MAX_SCENE_LAYERS - 1)
        self.collision_layer.setValue(0)
        self.layer_count.valueChanged.connect(self._sync_collision_layer_max)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Palette:", self.palette_combo)
        form.addRow("Tileset:", self.tileset_combo)
        form.addRow("Width:", self.width_tiles)
        form.addRow("Height:", self.height_tiles)
        form.addRow("Layers:", self.layer_count)
        form.addRow("Collision layer:", self.collision_layer)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._sync_collision_layer_max(self.layer_count.value())

    def _sync_collision_layer_max(self, layer_count: int) -> None:
        self.collision_layer.setMaximum(max(0, layer_count - 1))
        if self.collision_layer.value() > self.collision_layer.maximum():
            self.collision_layer.setValue(self.collision_layer.maximum())

    @property
    def scene_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def palette_name(self) -> str:
        return self.palette_combo.currentText()

    @property
    def tileset_path(self) -> str:
        return self.tileset_combo.currentText()
