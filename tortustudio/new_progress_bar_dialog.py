"""Dialog to create a new .tortuprogressbar prefab."""

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


class NewProgressBarDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Progress Bar")

        self.name_edit = QLineEdit("progress_bar")
        self.texture_combo = QComboBox()
        sprites = list_sprite_paths(project_root)
        if sprites:
            for rel in sprites:
                self.texture_combo.addItem(rel, rel)
        else:
            self.texture_combo.addItem("(no sprites — create one first)", "")

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Texture:", self.texture_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def progress_bar_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def texture_path(self) -> str:
        rel = self.texture_combo.currentData()
        return str(rel) if rel else ""
