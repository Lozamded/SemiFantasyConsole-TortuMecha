"""Asset browser panel — filterable list of project assets shown below the tree."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class AssetBrowserPanel(QWidget):
    """Searchable list of project assets for the active editor tab."""

    asset_activated = pyqtSignal(str)  # relative path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_paths: list[str] = []

        self._label = QLabel()
        self._label.setStyleSheet("font-weight: bold; padding: 2px 0;")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.itemDoubleClicked.connect(self._on_item_activated)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._label)
        layout.addWidget(self._search)
        layout.addWidget(self._list)

    def populate(self, label: str, paths: list[str]) -> None:
        """Replace the list with a new set of asset paths and reset the filter."""
        self._label.setText(label)
        self._all_paths = paths
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        self._apply_filter("")

    def clear(self) -> None:
        self._label.setText("")
        self._all_paths = []
        self._list.clear()

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        self._list.clear()
        for path in self._all_paths:
            stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if query and query not in stem.lower() and query not in path.lower():
                continue
            item = QListWidgetItem(stem)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self._list.addItem(item)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.asset_activated.emit(str(path))
