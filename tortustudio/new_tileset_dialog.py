"""Dialog to create a new .tortutileset asset."""

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


class NewTilesetDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Tileset")

        self.name_edit = QLineEdit("terrain")
        self.tile_size = QSpinBox()
        self.tile_size.setRange(4, 64)
        self.tile_size.setValue(TILE_BLOCK)
        self.tile_size.setSuffix(" px")

        self.palette_combo = QComboBox()
        names = list_palette_names(project_root)
        if not names:
            names = ["default"]
        self.palette_combo.addItems(names)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Tile size:", self.tile_size)
        form.addRow("Palette:", self.palette_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def tileset_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def palette_name(self) -> str:
        return self.palette_combo.currentText()
