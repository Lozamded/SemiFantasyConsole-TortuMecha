"""Dialog to create a new .tortuspritefont asset."""

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
from tortuengine.sprite_font import (
    DEFAULT_GLYPH_BLOCKS_H,
    DEFAULT_GLYPH_BLOCKS_W,
    MAX_GLYPH_BLOCKS,
    MIN_GLYPH_BLOCKS,
)


class NewSpriteFontDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Sprite Font")

        self.name_edit = QLineEdit("hud")
        self.blocks_w = QSpinBox()
        self.blocks_w.setRange(MIN_GLYPH_BLOCKS, MAX_GLYPH_BLOCKS)
        self.blocks_w.setValue(DEFAULT_GLYPH_BLOCKS_W)
        self.blocks_h = QSpinBox()
        self.blocks_h.setRange(MIN_GLYPH_BLOCKS, MAX_GLYPH_BLOCKS)
        self.blocks_h.setValue(DEFAULT_GLYPH_BLOCKS_H)

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
        form.addRow("Glyph blocks wide:", self.blocks_w)
        form.addRow("Glyph blocks tall:", self.blocks_h)
        form.addRow("Glyph pixel size:", self.size_label)
        form.addRow("Palette:", self.palette_combo)

        hint = QLabel(
            "Starts with A–Z, a–z, 0–9, space, and common HUD punctuation.\n"
            "Add extra characters (ñ, 字, …) from the editor."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #aaa; font-size: 11px;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self._update_size_label()

    def _update_size_label(self) -> None:
        w = self.blocks_w.value() * SPRITE_BLOCK
        h = self.blocks_h.value() * SPRITE_BLOCK
        self.size_label.setText(f"{w} × {h} px ({self.blocks_w.value()}×{self.blocks_h.value()} blocks)")

    def _on_accept(self) -> None:
        if not self.font_name:
            self.name_edit.setFocus()
            return
        self.accept()

    @property
    def font_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def glyph_blocks_w(self) -> int:
        return self.blocks_w.value()

    @property
    def glyph_blocks_h(self) -> int:
        return self.blocks_h.value()

    @property
    def palette_name(self) -> str:
        return self.palette_combo.currentText()
