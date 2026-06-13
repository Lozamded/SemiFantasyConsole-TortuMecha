"""Dialog to create a new .tortuscene asset."""

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

from tortuengine.palette import list_palette_names


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

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
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
    def scene_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def palette_name(self) -> str:
        return self.palette_combo.currentText()
