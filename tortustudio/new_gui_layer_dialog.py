"""Dialog to create a new GUI layer on a scene."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH


class NewGuiLayerDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New GUI Layer")

        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 2048)
        self.width_spin.setValue(SCREEN_WIDTH)
        self.width_spin.setSuffix(" px")

        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 2048)
        self.height_spin.setValue(SCREEN_HEIGHT)
        self.height_spin.setSuffix(" px")

        form = QFormLayout()
        form.addRow("Width:", self.width_spin)
        form.addRow("Height:", self.height_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def layer_width(self) -> int:
        return self.width_spin.value()

    @property
    def layer_height(self) -> int:
        return self.height_spin.value()
