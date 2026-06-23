"""Font editor — text fonts (.tortufont) and sprite fonts (coming soon)."""

from __future__ import annotations

import json
from pathlib import Path

import pygame
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from tortuengine.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from tortuengine.palette import PAINTABLE_INDICES, list_palette_names, load_palette, palette_path
from tortuengine.text_font import (
    CHARSET_ASCII,
    CHARSET_CUSTOM,
    CHARSET_LATIN1,
    CHARSET_PRESETS,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    TortuFont,
    install_ttf_source,
    load_tortu_font,
    rebuild_font_glyphs,
    render_text_line,
    save_tortu_font,
)
from tortustudio.new_text_font_dialog import NewTextFontDialog
from tortustudio.sprite_font_editor import SpriteFontEditorWidget


class TextFontPreviewCanvas(QWidget):
    """Preview text inside a scaled 264×198 console screen frame."""

    SCREEN_BG = (30, 30, 40)
    FRAME_COLOR = (0, 220, 255)
    TEXT_MARGIN = 8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not pygame.get_init():
            pygame.init()
        self._screen_image: QImage | None = None
        self._scale = 2
        self._show_screen_frame = True
        self._update_minimum_size()

    def set_scale(self, scale: int) -> None:
        self._scale = max(1, min(4, scale))
        self._update_minimum_size()
        self.update()

    def set_show_screen_frame(self, visible: bool) -> None:
        self._show_screen_frame = visible
        self.update()

    def _update_minimum_size(self) -> None:
        self.setMinimumSize(
            SCREEN_WIDTH * self._scale + 32,
            SCREEN_HEIGHT * self._scale + 32,
        )

    def set_screen_preview(self, screen: pygame.Surface | None) -> None:
        if screen is None:
            screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            screen.fill((*self.SCREEN_BG, 255))
        data = pygame.image.tobytes(screen, "RGBA")
        self._screen_image = QImage(
            data,
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            SCREEN_WIDTH * 4,
            QImage.Format.Format_RGBA8888,
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)

        sw = SCREEN_WIDTH * self._scale
        sh = SCREEN_HEIGHT * self._scale
        ox = max(0, (self.width() - sw) // 2)
        oy = max(0, (self.height() - sh) // 2)

        if self._screen_image is not None:
            scaled = self._screen_image.scaled(
                sw,
                sh,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            painter.drawImage(ox, oy, scaled)
        else:
            painter.fillRect(ox, oy, sw, sh, QColor(*self.SCREEN_BG))

        if self._show_screen_frame:
            painter.fillRect(ox, oy, sw, sh, QColor(*self.FRAME_COLOR, 24))
            pen = QPen(QColor(*self.FRAME_COLOR, 230))
            pen.setWidth(2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(ox, oy, sw, sh)

            font = QFont()
            font.setPixelSize(max(10, min(14, 8 + self._scale)))
            painter.setFont(font)
            label = f"{SCREEN_WIDTH}×{SCREEN_HEIGHT}"
            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(label) + 8
            text_h = metrics.height() + 4
            label_x = ox + 4
            label_y = oy + 4
            painter.fillRect(label_x, label_y, text_w, text_h, QColor(20, 20, 28, 200))
            painter.setPen(QColor(*self.FRAME_COLOR, 255))
            painter.drawText(label_x + 4, label_y + metrics.ascent() + 2, label)

        painter.end()


class TextFontEditorWidget(QWidget):
    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_font_requested = pyqtSignal()
    open_font_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.file_path: Path | None = None
        self.tortu_font: TortuFont | None = None
        self._palette_colors: list[tuple[int, int, int]] = []
        self._preview_fore_index = 1
        self._preview_swatch_buttons: list[QPushButton] = []
        self._dirty = False
        self._syncing_fields = False

        self.btn_new = QPushButton("New Text Font…")
        self.btn_new.clicked.connect(self.new_font_requested.emit)
        self.btn_open = QPushButton("Open…")
        self.btn_open.clicked.connect(self.open_font_requested.emit)
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save)
        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.clicked.connect(self._rename_font)
        self.btn_rebuild = QPushButton("Rebuild glyphs")
        self.btn_rebuild.setToolTip("Rasterize charset from the source TTF")
        self.btn_rebuild.clicked.connect(self._rebuild_glyphs)

        self.status_label = QLabel("No text font open")
        self.glyph_count_label = QLabel("Glyphs: —")

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_fields_changed)

        self.source_label = QLabel("—")
        self.source_label.setWordWrap(True)
        self.btn_change_ttf = QPushButton("Change TTF…")
        self.btn_change_ttf.clicked.connect(self._change_ttf)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE)
        self.size_spin.setToolTip("Pixel size — glyphs rebuild automatically")
        self.size_spin.valueChanged.connect(self._on_size_changed)

        self.line_height_spin = QSpinBox()
        self.line_height_spin.setRange(MIN_FONT_SIZE, MAX_FONT_SIZE * 2)
        self.line_height_spin.setToolTip("Vertical spacing between preview lines")
        self.line_height_spin.valueChanged.connect(self._on_line_height_changed)

        self.charset_combo = QComboBox()
        self.charset_combo.addItem("Latin-1 (Spanish, etc.)", CHARSET_LATIN1)
        self.charset_combo.addItem("ASCII", CHARSET_ASCII)
        self.charset_combo.addItem("Custom", CHARSET_CUSTOM)
        self.charset_combo.currentIndexChanged.connect(self._on_charset_preset_changed)

        self.custom_charset = QPlainTextEdit()
        self.custom_charset.setPlaceholderText("Characters to bake when charset is Custom")
        self.custom_charset.setMaximumHeight(72)
        self.custom_charset.textChanged.connect(self._on_charset_text_changed)

        self.palette_combo = QComboBox()
        self.palette_combo.currentTextChanged.connect(self._on_palette_changed)

        self.preview_text = QPlainTextEdit()
        self.preview_text.setPlainText("¡Hola!\nScore: 42 — ñáéíóú")
        self.preview_text.setMaximumHeight(72)
        self.preview_text.setPlaceholderText("Preview lines (one per row)")
        self.preview_text.textChanged.connect(self._refresh_preview)

        self.preview_scale_spin = QSpinBox()
        self.preview_scale_spin.setRange(1, 4)
        self.preview_scale_spin.setValue(2)
        self.preview_scale_spin.setToolTip("Zoom the console screen preview")
        self.preview_scale_spin.valueChanged.connect(self._on_preview_scale_changed)

        self.show_screen_frame = QCheckBox("Show screen frame")
        self.show_screen_frame.setChecked(True)
        self.show_screen_frame.setToolTip(
            f"Outline the {SCREEN_WIDTH}×{SCREEN_HEIGHT} game viewport"
        )
        self.show_screen_frame.toggled.connect(self._on_show_screen_frame_toggled)

        self.preview_canvas = TextFontPreviewCanvas()

        self._build_layout()
        self.preview_canvas.set_scale(self.preview_scale_spin.value())
        self._refresh_preview()

    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        file_row = QHBoxLayout()
        file_row.addWidget(self.btn_new)
        file_row.addWidget(self.btn_open)
        file_row.addWidget(self.btn_save)
        file_row.addWidget(self.btn_rename)
        file_row.addWidget(self.btn_rebuild)
        file_row.addWidget(self.status_label)
        file_row.addStretch()
        outer.addLayout(file_row)

        body = QHBoxLayout()
        outer.addLayout(body, stretch=1)

        preview_group = QVBoxLayout()
        preview_group.addWidget(QLabel("Preview"))
        preview_group.addWidget(self.preview_canvas, stretch=1)

        preview_color_row = QHBoxLayout()
        preview_color_row.addWidget(QLabel("Text color:"))
        preview_color_row.addStretch()
        preview_group.addLayout(preview_color_row)

        self.preview_swatches_area = QScrollArea()
        self.preview_swatches_area.setWidgetResizable(True)
        self.preview_swatches_area.setMaximumHeight(88)
        self.preview_swatches_widget = QWidget()
        self.preview_swatches_grid = QGridLayout(self.preview_swatches_widget)
        self.preview_swatches_grid.setContentsMargins(0, 0, 0, 0)
        self.preview_swatches_area.setWidget(self.preview_swatches_widget)
        preview_group.addWidget(self.preview_swatches_area)

        preview_hint = QLabel("Preview only — does not change baked glyphs.")
        preview_hint.setStyleSheet("color: #aaa; font-size: 11px;")
        preview_group.addWidget(preview_hint)

        body.addLayout(preview_group, stretch=1)

        side_widget = QWidget()
        form = QFormLayout(side_widget)
        form.addRow("Name:", self.name_edit)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_label, stretch=1)
        source_row.addWidget(self.btn_change_ttf)
        form.addRow("Source:", source_row)
        form.addRow("Size (px):", self.size_spin)
        form.addRow("Line height:", self.line_height_spin)
        form.addRow("Charset:", self.charset_combo)
        form.addRow("Custom chars:", self.custom_charset)
        form.addRow("Bake palette:", self.palette_combo)
        form.addRow("Preview text:", self.preview_text)
        form.addRow("Preview zoom:", self.preview_scale_spin)
        form.addRow(self.show_screen_frame)
        form.addRow(self.glyph_count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(side_widget)
        scroll.setMinimumWidth(280)
        body.addWidget(scroll)

    def set_project_root(self, project_root: Path) -> None:
        self.project_root = project_root
        self._refresh_palette_combo()
        default_palette = palette_path(project_root, "default")
        if default_palette.is_file():
            self._palette_colors = load_palette(default_palette)
            self._build_preview_swatches()

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def new_font(self) -> None:
        dialog = NewTextFontDialog(self.project_root, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if dialog.ttf_path is None:
            return
        try:
            rel_source = install_ttf_source(
                self.project_root,
                dialog.ttf_path,
                dialog.font_name,
            )
            tortu_font = TortuFont.create(
                dialog.font_name,
                rel_source,
                size=dialog.font_size,
                palette=dialog.palette_name,
                charset_preset=dialog.charset_preset,
            )
            tortu_font.line_height = dialog.line_height
            self._palette_colors = load_palette(
                palette_path(self.project_root, dialog.palette_name)
            )
            rebuild_font_glyphs(tortu_font, self.project_root, preview_palette=self._palette_colors)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "New Text Font", str(exc))
            return

        dest = self.project_root / "assets" / "fonts" / f"{dialog.font_name}.tortufont"
        self.file_path = dest
        self.tortu_font = tortu_font
        self._dirty = True
        self._build_preview_swatches()
        self._sync_fields()
        self._refresh_preview()
        self.status_label.setText(f"New: {dest.name}")

    def open_font(self, path: Path) -> None:
        try:
            tortu_font = load_tortu_font(path)
            self._palette_colors = load_palette(
                palette_path(self.project_root, tortu_font.palette)
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Open Text Font", str(exc))
            return
        self.file_path = path.resolve()
        self.tortu_font = tortu_font
        self._dirty = False
        self._build_preview_swatches()
        self._sync_fields()
        self._refresh_preview()
        self.status_label.setText(path.name)

    def save(self) -> None:
        if not self.tortu_font or not self.file_path:
            QMessageBox.information(self, "Save Text Font", "Nothing to save.")
            return
        self._apply_fields()
        try:
            save_tortu_font(self.tortu_font, self.file_path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Save Text Font", str(exc))
            return
        self._dirty = False
        self.status_label.setText(f"Saved {self.file_path.name}")
        self.saved.emit(self.file_path)

    def _rename_font(self) -> None:
        if not self.tortu_font or not self.file_path:
            return
        old_path = self.file_path
        new_stem, ok = QInputDialog.getText(
            self, "Rename Text Font", "New name:", text=old_path.stem
        )
        if not ok:
            return
        new_stem = new_stem.strip()
        if not new_stem:
            return
        if not all(c.isalnum() or c in "_-" for c in new_stem):
            QMessageBox.warning(
                self, "Rename Text Font",
                "Name may only contain letters, digits, underscores, and hyphens."
            )
            return
        new_path = old_path.parent / f"{new_stem}.tortufont"
        if new_path.exists():
            QMessageBox.warning(self, "Rename Text Font", f"{new_path.name} already exists.")
            return
        for sidecar in sorted(old_path.parent.glob(f"{old_path.stem}.*")):
            if sidecar == old_path:
                continue
            sidecar.rename(sidecar.parent / sidecar.name.replace(old_path.stem, new_stem, 1))
        old_path.rename(new_path)
        self.file_path = new_path
        self.status_label.setText(new_path.name)
        self.renamed.emit(old_path, new_path)

    def _apply_fields(self) -> None:
        if not self.tortu_font:
            return
        self.tortu_font.name = self.name_edit.text().strip() or self.tortu_font.name
        self.tortu_font.size = self.size_spin.value()
        self.tortu_font.line_height = self.line_height_spin.value()
        self.tortu_font.palette = self.palette_combo.currentText()
        preset = str(self.charset_combo.currentData())
        self.tortu_font.charset_preset = preset if preset in CHARSET_PRESETS else CHARSET_LATIN1
        if self.tortu_font.charset_preset == CHARSET_CUSTOM:
            self.tortu_font.charset = self.custom_charset.toPlainText()

    def _sync_fields(self) -> None:
        if not self.tortu_font:
            return
        self._syncing_fields = True
        self._refresh_palette_combo()
        self.name_edit.blockSignals(True)
        self.size_spin.blockSignals(True)
        self.line_height_spin.blockSignals(True)
        self.charset_combo.blockSignals(True)
        self.custom_charset.blockSignals(True)
        self.palette_combo.blockSignals(True)

        self.name_edit.setText(self.tortu_font.name)
        self.source_label.setText(self.tortu_font.source)
        self.size_spin.setValue(self.tortu_font.size)
        self.line_height_spin.setValue(self.tortu_font.line_height)
        index = self.charset_combo.findData(self.tortu_font.charset_preset)
        if index >= 0:
            self.charset_combo.setCurrentIndex(index)
        self.custom_charset.setPlainText(self.tortu_font.charset)
        self.custom_charset.setEnabled(self.tortu_font.charset_preset == CHARSET_CUSTOM)
        palette_index = self.palette_combo.findText(self.tortu_font.palette)
        if palette_index >= 0:
            self.palette_combo.setCurrentIndex(palette_index)

        self.name_edit.blockSignals(False)
        self.size_spin.blockSignals(False)
        self.line_height_spin.blockSignals(False)
        self.charset_combo.blockSignals(False)
        self.custom_charset.blockSignals(False)
        self.palette_combo.blockSignals(False)

        self.glyph_count_label.setText(f"Glyphs: {len(self.tortu_font.glyphs)}")
        self._syncing_fields = False
        self._build_preview_swatches()
        self._refresh_preview()

    def _build_preview_swatches(self) -> None:
        while self.preview_swatches_grid.count():
            item = self.preview_swatches_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._preview_swatch_buttons.clear()

        if not self._palette_colors:
            return

        cols = 16
        for n, index in enumerate(PAINTABLE_INDICES):
            r, g, b = self._palette_colors[index]
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            selected = index == self._preview_fore_index
            border = "2px solid #00dcff" if selected else "1px solid #444"
            btn.setStyleSheet(
                f"background-color: rgb({r},{g},{b}); border: {border};"
            )
            btn.setToolTip(f"Preview text color — index {index}")
            btn.clicked.connect(lambda _checked, i=index: self._pick_preview_color(i))
            self.preview_swatches_grid.addWidget(btn, n // cols, n % cols)
            self._preview_swatch_buttons.append(btn)

    def _pick_preview_color(self, index: int) -> None:
        self._preview_fore_index = index
        self._build_preview_swatches()
        self._refresh_preview()

    def _on_size_changed(self, _value: int) -> None:
        if not self.tortu_font or self._syncing_fields:
            return
        self._apply_fields()
        self._rebuild_glyphs_internal()
        self._mark_dirty()

    def _on_line_height_changed(self, _value: int) -> None:
        if not self.tortu_font or self._syncing_fields:
            return
        self._apply_fields()
        self._refresh_preview()
        self._mark_dirty()

    def _on_charset_text_changed(self) -> None:
        if not self.tortu_font or self._syncing_fields:
            return
        if self.tortu_font.charset_preset != CHARSET_CUSTOM:
            return
        self._apply_fields()
        self._rebuild_glyphs_internal()
        self._mark_dirty()

    def _refresh_palette_combo(self) -> None:
        current = self.palette_combo.currentText() if self.palette_combo.count() else "default"
        names = list_palette_names(self.project_root)
        if not names:
            names = ["default"]
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(names)
        if self.tortu_font:
            current = self.tortu_font.palette
        idx = self.palette_combo.findText(current)
        if idx >= 0:
            self.palette_combo.setCurrentIndex(idx)
        self.palette_combo.blockSignals(False)

    def _on_fields_changed(self) -> None:
        if not self.tortu_font:
            return
        self._apply_fields()
        self._mark_dirty()

    def _on_charset_preset_changed(self) -> None:
        if not self.tortu_font:
            return
        custom = str(self.charset_combo.currentData()) == CHARSET_CUSTOM
        self.custom_charset.setEnabled(custom)
        if self._syncing_fields:
            return
        self._apply_fields()
        self._rebuild_glyphs_internal()
        self._mark_dirty()

    def _on_palette_changed(self, _name: str) -> None:
        if not self.tortu_font or self._syncing_fields:
            return
        path = palette_path(self.project_root, self.palette_combo.currentText())
        if path.is_file():
            self._palette_colors = load_palette(path)
        self.tortu_font.palette = self.palette_combo.currentText()
        self._build_preview_swatches()
        self._rebuild_glyphs_internal()
        self._mark_dirty()

    def _change_ttf(self) -> None:
        if not self.tortu_font:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select TrueType Font",
            "",
            "Font files (*.ttf *.otf);;All files (*)",
        )
        if not path:
            return
        try:
            rel = install_ttf_source(self.project_root, Path(path), self.tortu_font.name)
            self.tortu_font.source = rel
            self.source_label.setText(rel)
            self._rebuild_glyphs_internal()
            self._mark_dirty()
        except OSError as exc:
            QMessageBox.warning(self, "Change TTF", str(exc))

    def _rebuild_glyphs_internal(self) -> bool:
        if not self.tortu_font:
            return False
        try:
            if not self._palette_colors:
                self._palette_colors = load_palette(
                    palette_path(self.project_root, self.tortu_font.palette)
                )
            rebuild_font_glyphs(
                self.tortu_font,
                self.project_root,
                preview_palette=self._palette_colors,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Rebuild Glyphs", str(exc))
            return False
        self._sync_line_height_spin()
        self.glyph_count_label.setText(f"Glyphs: {len(self.tortu_font.glyphs)}")
        self._refresh_preview()
        return True

    def _sync_line_height_spin(self) -> None:
        if not self.tortu_font:
            return
        if self.line_height_spin.value() == self.tortu_font.line_height:
            return
        self.line_height_spin.blockSignals(True)
        self.line_height_spin.setValue(self.tortu_font.line_height)
        self.line_height_spin.blockSignals(False)

    def _rebuild_glyphs(self) -> None:
        if not self.tortu_font:
            return
        self._apply_fields()
        if self._rebuild_glyphs_internal():
            self._mark_dirty()

    def _refresh_preview(self) -> None:
        screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        screen.fill((TextFontPreviewCanvas.SCREEN_BG[0], TextFontPreviewCanvas.SCREEN_BG[1], TextFontPreviewCanvas.SCREEN_BG[2], 255))

        if self.tortu_font and self._palette_colors:
            lines = self.preview_text.toPlainText().splitlines() or ["Aa"]
            y = TextFontPreviewCanvas.TEXT_MARGIN
            for line in lines:
                if y + self.tortu_font.line_height > SCREEN_HEIGHT:
                    break
                if line:
                    try:
                        line_surface = render_text_line(
                            self.tortu_font,
                            line,
                            self._palette_colors,
                            fore_index=self._preview_fore_index,
                        )
                        screen.blit(line_surface, (TextFontPreviewCanvas.TEXT_MARGIN, y))
                    except (KeyError, IndexError):
                        pass
                y += self.tortu_font.line_height

        self.preview_canvas.set_screen_preview(screen)

    def _on_preview_scale_changed(self, value: int) -> None:
        self.preview_canvas.set_scale(value)

    def _on_show_screen_frame_toggled(self, checked: bool) -> None:
        self.preview_canvas.set_show_screen_frame(checked)

    def _mark_dirty(self) -> None:
        self._dirty = True
        if self.file_path:
            self.status_label.setText(f"{self.file_path.name} *")


class FontEditorWidget(QWidget):
    """Font Editor tab with Text fonts and Sprite fonts subtabs."""

    saved = pyqtSignal(Path)
    renamed = pyqtSignal(Path, Path)  # (old_path, new_path)
    new_font_requested = pyqtSignal()
    open_font_requested = pyqtSignal()
    new_sprite_font_requested = pyqtSignal()
    open_sprite_font_requested = pyqtSignal()

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.text_editor = TextFontEditorWidget(project_root)
        self.text_editor.saved.connect(self.saved.emit)
        self.text_editor.renamed.connect(self.renamed.emit)
        self.text_editor.new_font_requested.connect(self.new_font_requested.emit)
        self.text_editor.open_font_requested.connect(self.open_font_requested.emit)

        self.sprite_editor = SpriteFontEditorWidget(project_root)
        self.sprite_editor.saved.connect(self.saved.emit)
        self.sprite_editor.renamed.connect(self.renamed.emit)
        self.sprite_editor.new_font_requested.connect(self.new_sprite_font_requested.emit)
        self.sprite_editor.open_font_requested.connect(self.open_sprite_font_requested.emit)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.text_editor, "Text fonts")
        self.tabs.addTab(self.sprite_editor, "Sprite fonts")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def set_project_root(self, project_root: Path) -> None:
        self.text_editor.set_project_root(project_root)
        self.sprite_editor.set_project_root(project_root)

    def _active_subtab(self) -> QWidget:
        return self.tabs.currentWidget()

    def has_unsaved_changes(self) -> bool:
        return self.text_editor.has_unsaved_changes() or self.sprite_editor.has_unsaved_changes()

    def new_text_font(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.text_editor.new_font()

    def new_sprite_font(self) -> None:
        self.tabs.setCurrentIndex(1)
        self.sprite_editor.new_font()

    def open_text_font(self, path: Path) -> None:
        self.tabs.setCurrentIndex(0)
        self.text_editor.open_font(path)

    def open_sprite_font(self, path: Path) -> None:
        self.tabs.setCurrentIndex(1)
        self.sprite_editor.open_font(path)

    def save(self) -> None:
        widget = self._active_subtab()
        if widget is self.sprite_editor:
            self.sprite_editor.save()
        else:
            self.text_editor.save()
