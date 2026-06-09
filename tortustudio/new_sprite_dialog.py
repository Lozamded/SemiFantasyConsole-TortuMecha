"""Dialog to create a new .tortusprite asset."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from tortuengine.constants import SPRITE_BLOCK
from tortuengine.palette import list_palette_names


class NewSpriteDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Sprite")

        self.name_edit = QLineEdit("hero")
        self.blocks_w = QSpinBox()
        self.blocks_w.setRange(1, 32)
        self.blocks_w.setValue(4)
        self.blocks_h = QSpinBox()
        self.blocks_h.setRange(1, 32)
        self.blocks_h.setValue(4)

        self.size_label = QLabel()
        self.blocks_w.valueChanged.connect(self._update_size_label)
        self.blocks_h.valueChanged.connect(self._update_size_label)

        self.palette_combo = QComboBox()
        names = list_palette_names(project_root)
        if not names:
            names = ["default"]
        self.palette_combo.addItems(names)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Blocks wide:", self.blocks_w)
        form.addRow("Blocks tall:", self.blocks_h)
        form.addRow("Pixel size:", self.size_label)
        form.addRow("Palette:", self.palette_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._update_size_label()

    def _update_size_label(self) -> None:
        w = self.blocks_w.value() * SPRITE_BLOCK
        h = self.blocks_h.value() * SPRITE_BLOCK
        self.size_label.setText(f"{w} × {h} px ({self.blocks_w.value()}×{self.blocks_h.value()} blocks)")

    @property
    def sprite_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def palette_name(self) -> str:
        return self.palette_combo.currentText()
