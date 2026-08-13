"""Translation editor — edit the translations/*.csv translation tables in a grid.

Each CSV has a header row of language codes (``key,en,es,...``) and one data
row per translatable key, exactly as read by ``tortoisengine.localization``.
"""

from __future__ import annotations

import csv
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

TRANSLATIONS_DIR = Path("translations")


class TranslationEditorWidget(QWidget):
    """File list of translations/*.csv on the left, a key/language grid on the right."""

    saved = pyqtSignal(Path)

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self._current_path: Path | None = None
        self._dirty = False
        self._loading = False

        self.file_list = QListWidget()
        self.file_list.setMaximumWidth(220)
        self.file_list.currentItemChanged.connect(self._on_file_selected)

        self.btn_new_file = QPushButton("New CSV…")
        self.btn_new_file.clicked.connect(self._new_file)
        self.btn_delete_file = QPushButton("Delete CSV")
        self.btn_delete_file.clicked.connect(self._delete_file)

        file_btn_row = QHBoxLayout()
        file_btn_row.addWidget(self.btn_new_file)
        file_btn_row.addWidget(self.btn_delete_file)

        file_col = QVBoxLayout()
        file_col.addWidget(QLabel("translations/*.csv"))
        file_col.addWidget(self.file_list, stretch=1)
        file_col.addLayout(file_btn_row)

        self.table = QTableWidget(0, 1)
        self.table.setHorizontalHeaderLabels(["key"])
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._on_item_changed)

        self.btn_add_row = QPushButton("+ Key")
        self.btn_add_row.clicked.connect(self._add_row)
        self.btn_remove_row = QPushButton("− Key")
        self.btn_remove_row.clicked.connect(self._remove_selected_rows)
        self.btn_add_language = QPushButton("+ Language")
        self.btn_add_language.clicked.connect(self._add_language)
        self.btn_remove_language = QPushButton("− Language")
        self.btn_remove_language.clicked.connect(self._remove_selected_language)
        self.btn_save = QPushButton("Save CSV")
        self.btn_save.clicked.connect(self.save)

        table_btn_row = QHBoxLayout()
        table_btn_row.addWidget(self.btn_add_row)
        table_btn_row.addWidget(self.btn_remove_row)
        table_btn_row.addWidget(self.btn_add_language)
        table_btn_row.addWidget(self.btn_remove_language)
        table_btn_row.addStretch()
        table_btn_row.addWidget(self.btn_save)

        self.status_label = QLabel("No project open")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")

        table_col = QVBoxLayout()
        table_col.addLayout(table_btn_row)
        table_col.addWidget(self.table, stretch=1)
        table_col.addWidget(self.status_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(file_col)
        layout.addLayout(table_col, stretch=1)

        self._set_table_enabled(False)

    # -- project / file list -------------------------------------------------

    def set_project_root(self, project_root: Path) -> None:
        self.project_root = project_root
        self._current_path = None
        self._dirty = False
        self.refresh()

    def refresh(self) -> None:
        translations_dir = self.project_root / TRANSLATIONS_DIR
        files = sorted(translations_dir.glob("*.csv")) if translations_dir.is_dir() else []

        previous = self._current_path
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for f in files:
            item = QListWidgetItem(f.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            item.setToolTip(f.relative_to(self.project_root).as_posix())
            self.file_list.addItem(item)
        self.file_list.blockSignals(False)

        restored = False
        if previous is not None:
            for row in range(self.file_list.count()):
                item = self.file_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == str(previous):
                    self.file_list.setCurrentItem(item)
                    restored = True
                    break
        if not restored:
            self._current_path = None
            self.table.setRowCount(0)
            self._set_table_enabled(False)
            if self.file_list.count():
                self.file_list.setCurrentRow(0)

        count = len(files)
        self.status_label.setText(
            f"{count} file{'s' if count != 1 else ''} in {TRANSLATIONS_DIR.as_posix()}"
        )

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    # -- loading / selecting a file -------------------------------------------

    def _on_file_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is previous:
            return
        if self._dirty and previous is not None:
            reply = QMessageBox.question(
                self,
                "Unsaved Translation File",
                "Save changes to the current CSV before switching?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self.save()
            elif reply == QMessageBox.StandardButton.Cancel:
                self.file_list.blockSignals(True)
                self.file_list.setCurrentItem(previous)
                self.file_list.blockSignals(False)
                return
        if current is None:
            self._current_path = None
            self.table.setRowCount(0)
            self._set_table_enabled(False)
            return
        path = Path(current.data(Qt.ItemDataRole.UserRole))
        self._load_csv(path)

    def _load_csv(self, path: Path) -> None:
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))

        languages = [code.strip() for code in rows[0][1:]] if rows else []
        data_rows = [row for row in rows[1:] if row and row[0].strip()] if rows else []

        self._loading = True
        self.table.setColumnCount(1 + len(languages))
        self.table.setHorizontalHeaderLabels(["key"] + languages)
        self.table.setRowCount(len(data_rows))
        for r, row in enumerate(data_rows):
            key_item = QTableWidgetItem(row[0].strip())
            self.table.setItem(r, 0, key_item)
            for c in range(len(languages)):
                text = row[c + 1].strip() if c + 1 < len(row) else ""
                self.table.setItem(r, c + 1, QTableWidgetItem(text))
        self._loading = False

        self._current_path = path
        self._dirty = False
        self._set_table_enabled(True)

    def _on_item_changed(self, _item: QTableWidgetItem) -> None:
        if self._loading:
            return
        self._dirty = True

    def _set_table_enabled(self, enabled: bool) -> None:
        for w in (
            self.table,
            self.btn_add_row,
            self.btn_remove_row,
            self.btn_add_language,
            self.btn_remove_language,
            self.btn_save,
        ):
            w.setEnabled(enabled)

    # -- row / column editing -------------------------------------------------

    def _add_row(self) -> None:
        if self._current_path is None:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._loading = True
        self.table.setItem(row, 0, QTableWidgetItem("new_key"))
        for c in range(1, self.table.columnCount()):
            self.table.setItem(row, c, QTableWidgetItem(""))
        self._loading = False
        self._dirty = True
        self.table.editItem(self.table.item(row, 0))

    def _remove_selected_rows(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.table.removeRow(row)
        self._dirty = True

    def _add_language(self) -> None:
        if self._current_path is None:
            return
        code, ok = QInputDialog.getText(self, "Add Language", "Language code (e.g. en, es, fr):")
        code = code.strip()
        if not ok or not code:
            return
        existing = [
            self.table.horizontalHeaderItem(c).text()
            for c in range(1, self.table.columnCount())
        ]
        if code in existing:
            QMessageBox.warning(self, "Add Language", f"'{code}' already exists in this file.")
            return
        col = self.table.columnCount()
        self.table.insertColumn(col)
        self.table.setHorizontalHeaderItem(col, QTableWidgetItem(code))
        self._loading = True
        for r in range(self.table.rowCount()):
            self.table.setItem(r, col, QTableWidgetItem(""))
        self._loading = False
        self._dirty = True

    def _remove_selected_language(self) -> None:
        col = self.table.currentColumn()
        if col <= 0:
            QMessageBox.information(self, "Remove Language", "Select a language column (not 'key') to remove.")
            return
        name = self.table.horizontalHeaderItem(col).text()
        reply = QMessageBox.question(
            self,
            "Remove Language",
            f"Remove the '{name}' column from this file? This deletes every translation for it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.table.removeColumn(col)
        self._dirty = True

    # -- file management --------------------------------------------------

    def _new_file(self) -> None:
        if not (self.project_root / "tortu.project").is_file():
            QMessageBox.warning(self, "New CSV", "Open a project first.")
            return
        name, ok = QInputDialog.getText(self, "New Translation File", "File name (without .csv):")
        name = name.strip()
        if not ok or not name:
            return
        translations_dir = self.project_root / TRANSLATIONS_DIR
        translations_dir.mkdir(parents=True, exist_ok=True)
        dest = translations_dir / f"{name}.csv"
        if dest.exists():
            QMessageBox.warning(self, "New CSV", f"{dest.name} already exists.")
            return
        with dest.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f, lineterminator="\n").writerow(["key", "en"])
        self.refresh()
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == str(dest):
                self.file_list.setCurrentItem(item)
                break

    def _delete_file(self) -> None:
        item = self.file_list.currentItem()
        if item is None:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        reply = QMessageBox.question(
            self,
            "Delete CSV",
            f"Delete {path.name} from the project? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Delete CSV", f"Could not delete {path.name}: {exc}")
            return
        self._current_path = None
        self._dirty = False
        self.refresh()

    # -- save ---------------------------------------------------------------

    def save(self) -> None:
        if self._current_path is None:
            return
        languages = [
            self.table.horizontalHeaderItem(c).text()
            for c in range(1, self.table.columnCount())
        ]
        rows: list[list[str]] = []
        for r in range(self.table.rowCount()):
            key_item = self.table.item(r, 0)
            key = key_item.text().strip() if key_item else ""
            if not key:
                continue
            row = [key]
            for c in range(1, self.table.columnCount()):
                cell = self.table.item(r, c)
                row.append(cell.text() if cell else "")
            rows.append(row)

        with self._current_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["key"] + languages)
            writer.writerows(rows)

        self._dirty = False
        self.saved.emit(self._current_path)
        self.status_label.setText(f"Saved {self._current_path.relative_to(self.project_root).as_posix()}")
