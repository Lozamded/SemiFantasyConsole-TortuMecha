"""Color-key transparency widget — lets artists pick a color that imports as transparent."""

from __future__ import annotations

import pygame
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QCheckBox, QColorDialog, QHBoxLayout, QPushButton, QWidget

from tortuengine.image import apply_color_key


class ColorKeyWidget(QWidget):
    """Checkbox + color swatch; call apply_to(surface) before palette conversion."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color: tuple[int, int, int] | None = None

        self._check = QCheckBox("Color key")
        self._check.setToolTip(
            "Treat a specific color as transparent during import\n"
            "(useful for sprites from sites like The Sprite Resource or OpenGameArt\n"
            "that use a solid color instead of PNG transparency)"
        )

        self._btn = QPushButton()
        self._btn.setFixedSize(24, 24)
        self._btn.setEnabled(False)
        self._btn.setToolTip("Click to pick the transparent color")
        self._btn.clicked.connect(self._pick_color)
        self._check.toggled.connect(self._btn.setEnabled)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._check)
        layout.addWidget(self._btn)
        layout.addStretch()

    def _pick_color(self) -> None:
        initial = QColor(*self._color) if self._color else QColor(3, 88, 0)
        color = QColorDialog.getColor(initial, self, "Pick Transparent Color Key")
        if color.isValid():
            self._color = (color.red(), color.green(), color.blue())
            r, g, b = self._color
            self._btn.setStyleSheet(
                f"background-color: rgb({r},{g},{b}); border: 1px solid #666;"
            )

    @property
    def color_key_rgb(self) -> tuple[int, int, int] | None:
        """Return the active color key RGB, or None if disabled or not set."""
        if self._check.isChecked() and self._color is not None:
            return self._color
        return None

    def apply_to(self, surface: pygame.Surface) -> pygame.Surface:
        """Return surface with the color key applied, or the original if disabled."""
        if self._check.isChecked() and self._color is not None:
            return apply_color_key(surface, self._color)
        return surface
