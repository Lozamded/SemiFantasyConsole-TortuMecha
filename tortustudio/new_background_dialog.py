"""Dialog to create a new .tortubackground asset from a reference image."""

from __future__ import annotations

from pathlib import Path

import pygame
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from tortuengine.constants import SCREEN_WIDTH
from tortuengine.image import load_image
from tortuengine.palette import list_palette_names
from tortustudio.color_key_widget import ColorKeyWidget


class NewBackgroundDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Background")
        self._image_path: Path | None = None

        self.name_edit = QLineEdit("sky_bg")

        self.image_path_edit = QLineEdit()
        self.image_path_edit.setReadOnly(True)
        self.image_path_edit.setPlaceholderText("Choose a PNG or JPG…")

        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.clicked.connect(self._browse_image)

        image_row = QHBoxLayout()
        image_row.addWidget(self.image_path_edit, stretch=1)
        image_row.addWidget(self.btn_browse)

        self.image_info = QLabel("No image selected")
        self.image_info.setWordWrap(True)

        self.palette_combo = QComboBox()
        names = list_palette_names(project_root)
        if not names:
            names = ["default"]
        self.palette_combo.addItems(names)

        self.color_key = ColorKeyWidget()

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Source image:", image_row)
        form.addRow("", self.image_info)
        form.addRow("Palette:", self.palette_combo)
        form.addRow("", self.color_key)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_image(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Background Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if not path:
            return
        self._set_image_path(Path(path))

    def _set_image_path(self, path: Path) -> None:
        try:
            surface = load_image(path)
        except (FileNotFoundError, OSError, pygame.error) as exc:
            QMessageBox.warning(self, "Load Image", f"Could not load image:\n{exc}")
            return

        self._image_path = path.resolve()
        self.image_path_edit.setText(str(self._image_path))
        w, h = surface.get_size()
        screens = w / SCREEN_WIDTH
        self.image_info.setText(
            f"{w}×{h} px  ({screens:.1f}× screen width) — canvas size matches the image"
        )
        if self.name_edit.text() in ("", "sky_bg"):
            self.name_edit.setText(path.stem.replace(" ", "_"))

    def _try_accept(self) -> None:
        if self._image_path is None or not self._image_path.is_file():
            QMessageBox.warning(self, "New Background", "Choose a source image first.")
            return
        self.accept()

    @property
    def background_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def palette_name(self) -> str:
        return self.palette_combo.currentText()

    @property
    def image_path(self) -> Path:
        if self._image_path is None:
            raise ValueError("No image selected")
        return self._image_path

    @property
    def color_key_rgb(self) -> tuple[int, int, int] | None:
        return self.color_key.color_key_rgb
