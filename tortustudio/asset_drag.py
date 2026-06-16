"""Drag-and-drop helpers for project assets (tree → editors)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QMimeData, pyqtSignal
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QComboBox, QTreeWidget

MIME_TORTU_ASSET = "application/x-tortu-asset-path"


def asset_path_from_mime(mime: QMimeData) -> str | None:
    if mime.hasFormat(MIME_TORTU_ASSET):
        raw = bytes(mime.data(MIME_TORTU_ASSET)).decode("utf-8").strip()
        return raw or None
    text = mime.text().strip()
    if text and "/" in text:
        return text
    return None


def mime_carries_suffix(mime: QMimeData, suffix: str) -> bool:
    rel = asset_path_from_mime(mime)
    if not rel:
        return False
    return Path(rel).suffix.lower() == suffix.lower()


def make_asset_mime(rel_path: str) -> QMimeData:
    mime = QMimeData()
    mime.setData(MIME_TORTU_ASSET, rel_path.encode("utf-8"))
    mime.setText(rel_path)
    return mime


class DraggableProjectTree(QTreeWidget):
    """Project tree that can drag asset file paths to editor drop targets."""

    def __init__(self, drag_suffixes: tuple[str, ...] = (".tortusprite",), parent=None) -> None:
        super().__init__(parent)
        self._drag_suffixes = tuple(s.lower() for s in drag_suffixes)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DragOnly)

    def startDrag(self, supportedActions) -> None:  # noqa: N802
        item = self.currentItem()
        if item is None:
            return
        rel = item.text(0)
        if "/" not in rel:
            return
        suffix = Path(rel).suffix.lower()
        if suffix not in self._drag_suffixes:
            return
        drag = QDrag(self)
        drag.setMimeData(make_asset_mime(rel))
        drag.exec(Qt.DropAction.CopyAction)


class SpriteDropCombo(QComboBox):
    """Sprite picker that accepts .tortusprite paths dragged from the project tree."""

    sprite_dropped = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setToolTip("Pick a sprite or drag one from the project tree")

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if mime_carries_suffix(event.mimeData(), ".tortusprite"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if mime_carries_suffix(event.mimeData(), ".tortusprite"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        rel = asset_path_from_mime(event.mimeData())
        if not rel or Path(rel).suffix.lower() != ".tortusprite":
            event.ignore()
            return
        self.sprite_dropped.emit(rel)
        event.acceptProposedAction()
