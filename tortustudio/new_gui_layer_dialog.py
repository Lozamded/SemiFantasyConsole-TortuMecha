"""Dialog to create a new .tortuguilayer asset."""

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

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.palette import list_palette_names


class NewGuiLayerDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New GUI Layer")

        self.name_edit = QLineEdit("hud")

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 2048)
        self.width_spin.setValue(SCREEN_WIDTH)
        self.width_spin.setSuffix(" px")

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 2048)
        self.height_spin.setValue(SCREEN_HEIGHT)
        self.height_spin.setSuffix(" px")

        self.palette_combo = QComboBox()
        names = list_palette_names(project_root)
        if not names:
            names = ["default"]
        self.palette_combo.addItems(names)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Width:", self.width_spin)
        form.addRow("Height:", self.height_spin)
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
    def gui_layer_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def layer_width(self) -> int:
        return self.width_spin.value()

    @property
    def layer_height(self) -> int:
        return self.height_spin.value()

    @property
    def palette_name(self) -> str:
        return self.palette_combo.currentText()
