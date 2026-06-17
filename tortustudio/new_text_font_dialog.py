"""Dialog to create a new .tortufont text font asset."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from tortuengine.palette import list_palette_names
from tortuengine.text_font import (
    CHARSET_CUSTOM,
    CHARSET_LATIN1,
    DEFAULT_FONT_SIZE,
    DEFAULT_LINE_HEIGHT,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
)


class NewTextFontDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Text Font")
        self._ttf_path: Path | None = None

        self.name_edit = QLineEdit("dialog")
        self.size_spin = QSpinBox()
        self.size_spin.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE)
        self.size_spin.setValue(DEFAULT_FONT_SIZE)

        self.line_height_spin = QSpinBox()
        self.line_height_spin.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE * 2)
        self.line_height_spin.setValue(DEFAULT_LINE_HEIGHT)

        self.charset_combo = QComboBox()
        self.charset_combo.addItem("Latin-1 (Spanish, etc.)", CHARSET_LATIN1)
        self.charset_combo.addItem("ASCII", "ascii")
        self.charset_combo.addItem("Custom", CHARSET_CUSTOM)

        self.palette_combo = QComboBox()
        names = list_palette_names(project_root)
        if not names:
            names = ["default"]
        self.palette_combo.addItems(names)

        self.source_label = QLabel("No TTF selected")
        self.source_label.setWordWrap(True)
        browse_btn = QPushButton("Browse TTF…")
        browse_btn.clicked.connect(self._browse_ttf)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_label, stretch=1)
        source_row.addWidget(browse_btn)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Source TTF:", source_row)
        form.addRow("Size (px):", self.size_spin)
        form.addRow("Line height:", self.line_height_spin)
        form.addRow("Charset:", self.charset_combo)
        form.addRow("Bake palette:", self.palette_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_ttf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select TrueType Font",
            "",
            "Font files (*.ttf *.otf);;All files (*)",
        )
        if not path:
            return
        self._ttf_path = Path(path)
        self.source_label.setText(self._ttf_path.name)

    def _on_accept(self) -> None:
        if self._ttf_path is None or not self._ttf_path.is_file():
            self.source_label.setText("Select a .ttf or .otf file")
            return
        if not self.font_name:
            self.name_edit.setFocus()
            return
        self.accept()

    @property
    def font_name(self) -> str:
        return self.name_edit.text().strip().replace(" ", "_")

    @property
    def ttf_path(self) -> Path | None:
        return self._ttf_path

    @property
    def font_size(self) -> int:
        return self.size_spin.value()

    @property
    def line_height(self) -> int:
        return self.line_height_spin.value()

    @property
    def charset_preset(self) -> str:
        return str(self.charset_combo.currentData())

    @property
    def palette_name(self) -> str:
        return self.palette_combo.currentText()
