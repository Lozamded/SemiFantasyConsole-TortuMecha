"""Tab bar under the menu — fixed workspace tabs (Preview, Sprite Editor)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QTabBar, QWidget


class TabKind(str, Enum):
    PREVIEW = "preview"
    SPRITE_EDITOR = "sprite_editor"
    TILESET_EDITOR = "tileset_editor"


@dataclass
class TabRef:
    kind: TabKind


class WorkspaceTabs(QWidget):
    """Tab strip placed directly under the menu bar."""

    tab_selected = pyqtSignal(TabRef)

    PREVIEW_LABEL = "Game Preview"
    SPRITE_EDITOR_LABEL = "Sprite Editor"
    TILESET_EDITOR_LABEL = "Tileset Editor"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._refs: list[TabRef] = []

        self.tab_bar = QTabBar()
        self.tab_bar.setMovable(False)
        self.tab_bar.setTabsClosable(False)
        self.tab_bar.setExpanding(False)
        self.tab_bar.currentChanged.connect(self._on_current_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 0)
        layout.addWidget(self.tab_bar)

        self._add_preview_tab()
        self._add_sprite_editor_tab()
        self._add_tileset_editor_tab()

    @property
    def preview_index(self) -> int:
        return 0

    @property
    def sprite_editor_index(self) -> int:
        return 1

    @property
    def tileset_editor_index(self) -> int:
        return 2

    @property
    def current_ref(self) -> TabRef | None:
        index = self.tab_bar.currentIndex()
        if 0 <= index < len(self._refs):
            return self._refs[index]
        return None

    def _add_preview_tab(self) -> None:
        self.tab_bar.addTab(self.PREVIEW_LABEL)
        self._refs.append(TabRef(kind=TabKind.PREVIEW))

    def _add_sprite_editor_tab(self) -> None:
        self.tab_bar.addTab(self.SPRITE_EDITOR_LABEL)
        self._refs.append(TabRef(kind=TabKind.SPRITE_EDITOR))

    def _add_tileset_editor_tab(self) -> None:
        self.tab_bar.addTab(self.TILESET_EDITOR_LABEL)
        self._refs.append(TabRef(kind=TabKind.TILESET_EDITOR))

    def reset(self) -> None:
        while self.tab_bar.count() > 0:
            self.tab_bar.removeTab(0)
        self._refs.clear()
        self._add_preview_tab()
        self._add_sprite_editor_tab()
        self._add_tileset_editor_tab()

    def select_preview(self) -> None:
        self.tab_bar.setCurrentIndex(self.preview_index)

    def select_sprite_editor(self) -> None:
        self.tab_bar.setCurrentIndex(self.sprite_editor_index)

    def select_tileset_editor(self) -> None:
        self.tab_bar.setCurrentIndex(self.tileset_editor_index)

    def _on_current_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._refs):
            return
        self.tab_selected.emit(self._refs[index])
