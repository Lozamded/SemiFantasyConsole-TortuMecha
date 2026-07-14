"""Dialog to create a new .tortupipbar prefab."""

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


class NewPipBarDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Pip Bar")

        self.name_edit = QLineEdit("pip_bar")
        self.full_sprite_combo = QComboBox()
        sprites = list_sprite_paths(project_root)
        if sprites:
            for rel in sprites:
                self.full_sprite_combo.addItem(rel, rel)
        else:
            self.full_sprite_combo.addItem("(no sprites — create one first)", "")

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Full sprite:", self.full_sprite_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def pip_bar_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def full_sprite_path(self) -> str:
        rel = self.full_sprite_combo.currentData()
        return str(rel) if rel else ""
