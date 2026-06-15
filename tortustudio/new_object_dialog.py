"""Dialog to create a new .tortuobject prefab."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from tortustudio.scene_assets import list_sprite_paths


class NewObjectDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Object")

        self.name_edit = QLineEdit("object")
        self.animation_name_edit = QLineEdit("idle")
        self.sprite_combo = QComboBox()
        sprites = list_sprite_paths(project_root)
        if sprites:
            for rel in sprites:
                self.sprite_combo.addItem(rel, rel)
        else:
            self.sprite_combo.addItem("(no sprites — create one first)", "")

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("First animation:", self.animation_name_edit)
        form.addRow("Sprite:", self.sprite_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def object_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def animation_name(self) -> str:
        return self.animation_name_edit.text().strip().replace(" ", "_") or "idle"

    @property
    def sprite_path(self) -> str:
        rel = self.sprite_combo.currentData()
        return str(rel) if rel else ""
