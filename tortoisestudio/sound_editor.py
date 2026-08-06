"""Sound editor — audio channels, import audio files (.ogg, .midi)."""

from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

AUDIO_SUFFIXES = (".ogg", ".midi", ".mid")
AUDIO_DIR = Path("assets") / "audio"


MAX_CHANNELS = 12


class ChannelsPanel(QWidget):
    """Named audio channel list — add, remove, and rename up to 12 channels."""

    channels_changed = pyqtSignal(list)  # list[str] of channel names

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from tortoisengine.game_settings import GameSettings
        self._channels: list[str] = list(GameSettings().audio_channels)
        self._ignore_item_changed = False

        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(130)
        self.list_widget.setToolTip("Double-click a channel to rename it")
        self.list_widget.itemChanged.connect(self._on_item_changed)

        self.btn_add = QPushButton("+")
        self.btn_add.setFixedWidth(32)
        self.btn_add.setToolTip("Add a new audio channel (max 12)")
        self.btn_add.clicked.connect(self._add_channel)

        self.btn_remove = QPushButton("−")
        self.btn_remove.setFixedWidth(32)
        self.btn_remove.setToolTip("Remove the selected channel")
        self.btn_remove.clicked.connect(self._remove_selected)

        self.count_label = QLabel()

        hint = QLabel("Double-click a channel name to rename it.")
        hint.setStyleSheet("color: #888; font-size: 11px;")

        btn_col = QVBoxLayout()
        btn_col.addWidget(self.btn_add)
        btn_col.addWidget(self.btn_remove)
        btn_col.addStretch()

        list_row = QHBoxLayout()
        list_row.addWidget(self.list_widget, stretch=1)
        list_row.addLayout(btn_col)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(list_row)
        layout.addWidget(self.count_label)
        layout.addWidget(hint)

        self._rebuild_list()

    def _rebuild_list(self) -> None:
        self._ignore_item_changed = True
        self.list_widget.clear()
        for name in self._channels:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.list_widget.addItem(item)
        self._ignore_item_changed = False
        self._update_count()

    def _update_count(self) -> None:
        n = len(self._channels)
        at_max = n >= MAX_CHANNELS
        color = "#e03131" if at_max else "#888"
        self.count_label.setText(
            f"<span style='color:{color}'>{n} / {MAX_CHANNELS} channels</span>"
        )
        self.btn_add.setEnabled(not at_max)

    def _add_channel(self) -> None:
        if len(self._channels) >= MAX_CHANNELS:
            return
        name = f"channel_{len(self._channels) + 1}"
        self._channels.append(name)
        self._rebuild_list()
        new_item = self.list_widget.item(self.list_widget.count() - 1)
        self.list_widget.setCurrentItem(new_item)
        self.list_widget.editItem(new_item)
        self.channels_changed.emit(list(self._channels))

    def _remove_selected(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        self._channels.pop(row)
        self._rebuild_list()
        self.channels_changed.emit(list(self._channels))

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._ignore_item_changed:
            return
        row = self.list_widget.row(item)
        if row < 0 or row >= len(self._channels):
            return
        new_name = item.text().strip()
        if not new_name:
            self._ignore_item_changed = True
            item.setText(self._channels[row])
            self._ignore_item_changed = False
            return
        self._channels[row] = new_name
        self._update_count()
        self.channels_changed.emit(list(self._channels))

    def set_channels(self, channels: list[str]) -> None:
        self._channels = list(channels)
        self._rebuild_list()

    @property
    def channels(self) -> list[str]:
        return list(self._channels)


class MusicCreatorPanel(QWidget):
    """Placeholder for the future in-app music sequencer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        banner = QLabel("Music Creator")
        banner.setStyleSheet("font-size: 22px; font-weight: bold; color: #868e96;")
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        soon = QLabel("Coming soon")
        soon.setStyleSheet("font-size: 15px; color: #495057;")
        soon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc = QLabel(
            "A step-sequencer and tracker-style music editor\n"
            "will be available here in a future release.\n\n"
            "In the meantime use the Import Audio tab to add\n"
            ".ogg music tracks and .midi files to your project."
        )
        desc.setStyleSheet("color: #868e96; font-size: 12px;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addStretch(2)
        layout.addWidget(banner)
        layout.addSpacing(8)
        layout.addWidget(soon)
        layout.addSpacing(16)
        layout.addWidget(desc)
        layout.addStretch(3)


class ImportAudioPanel(QWidget):
    """Copy .ogg / .midi files into assets/audio/, list them, and assign
    each one to an audio channel (see ChannelsPanel)."""

    # dict[str, str]: project-relative audio path -> assigned channel name.
    # Emitted whenever an assignment changes, a new file gets a default
    # assignment, or a removed/renamed channel forces a reassignment.
    channel_map_changed = pyqtSignal(dict)

    def __init__(
        self, project_root: Path, channels: list[str] | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self._channels: list[str] = list(channels) if channels else []
        self._channel_map: dict[str, str] = {}
        self._files: list[Path] = []
        self._updating_table = False

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["File", "Channel"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

        self.btn_import = QPushButton("Import audio file…")
        self.btn_import.setToolTip(
            "Copy a .ogg or .midi file into assets/audio/ inside the project"
        )
        self.btn_import.clicked.connect(self._import_files)

        self.btn_remove = QPushButton("Remove selected")
        self.btn_remove.setToolTip("Delete the selected file(s) from assets/audio/")
        self.btn_remove.clicked.connect(self._remove_selected)

        self.status_label = QLabel("No project open")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")

        hint = QLabel(
            "Supported formats: .ogg (recommended for music and SFX), .midi / .mid. "
            "Pick a channel per file — used for per-channel volume at runtime."
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_import)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Project audio files:"))
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(btn_row)
        layout.addWidget(hint)
        layout.addWidget(self.status_label)

    def set_project_root(self, project_root: Path) -> None:
        self.project_root = project_root
        self.refresh()

    def set_channel_map(self, channel_map: dict[str, str]) -> None:
        """Seed the assignment map (e.g. from the just-opened project) before refresh()."""
        self._channel_map = dict(channel_map)

    @property
    def channel_map(self) -> dict[str, str]:
        return dict(self._channel_map)

    def set_channels(self, channels: list[str]) -> None:
        """Called when ChannelsPanel's channel list changes — reassigns any
        file pointing at a channel that no longer exists to the first
        remaining channel, then rebuilds the per-row combo boxes."""
        self._channels = list(channels)
        changed = False
        fallback = self._channels[0] if self._channels else ""
        for path, chan in list(self._channel_map.items()):
            if chan not in self._channels:
                self._channel_map[path] = fallback
                changed = True
        self._rebuild_table()
        if changed:
            self.channel_map_changed.emit(dict(self._channel_map))

    def _relpath(self, f: Path) -> str:
        return f.relative_to(self.project_root).as_posix()

    def refresh(self) -> None:
        audio_dir = self.project_root / AUDIO_DIR
        if not audio_dir.is_dir():
            self.table.setRowCount(0)
            self.status_label.setText(f"Audio folder not found: {AUDIO_DIR}")
            return
        files = sorted(
            f for f in audio_dir.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_SUFFIXES
        )
        rel_paths = {self._relpath(f) for f in files}

        changed = False
        for stale in set(self._channel_map) - rel_paths:
            del self._channel_map[stale]
            changed = True
        fallback = self._channels[0] if self._channels else ""
        for rel in rel_paths - set(self._channel_map):
            self._channel_map[rel] = fallback
            changed = True

        self._files = files
        self._rebuild_table()

        count = len(files)
        self.status_label.setText(
            f"{count} file{'s' if count != 1 else ''} in {AUDIO_DIR.as_posix()}"
        )
        if changed:
            self.channel_map_changed.emit(dict(self._channel_map))

    def _rebuild_table(self) -> None:
        self._updating_table = True
        files = self._files
        self.table.setRowCount(len(files))
        for row, f in enumerate(files):
            rel = self._relpath(f)
            name_item = QTableWidgetItem(f.name)
            name_item.setData(Qt.ItemDataRole.UserRole, str(f))
            name_item.setToolTip(rel)
            self.table.setItem(row, 0, name_item)

            combo = QComboBox()
            combo.addItems(self._channels)
            current = self._channel_map.get(rel, "")
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.currentTextChanged.connect(
                lambda text, rel=rel: self._on_channel_picked(rel, text)
            )
            self.table.setCellWidget(row, 1, combo)
        self._updating_table = False

    def _on_channel_picked(self, rel: str, channel: str) -> None:
        if self._updating_table:
            return
        self._channel_map[rel] = channel
        self.channel_map_changed.emit(dict(self._channel_map))

    def _import_files(self) -> None:
        if not (self.project_root / "tortu.project").is_file():
            QMessageBox.warning(self, "Import Audio", "Open a project first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Audio Files",
            "",
            "Audio files (*.ogg *.midi *.mid);;All files (*)",
        )
        if not paths:
            return
        dest_dir = self.project_root / AUDIO_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        for src in paths:
            src_path = Path(src)
            dest = dest_dir / src_path.name
            if dest.exists():
                reply = QMessageBox.question(
                    self,
                    "File Exists",
                    f"{src_path.name} already exists in the project. Overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    continue
            try:
                shutil.copy2(str(src_path), str(dest))
            except OSError as exc:
                errors.append(f"{src_path.name}: {exc}")
        if errors:
            QMessageBox.warning(self, "Import Audio", "Some files could not be copied:\n" + "\n".join(errors))
        self.refresh()

    def _remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            return
        names = [self.table.item(r, 0).text() for r in rows]
        reply = QMessageBox.question(
            self,
            "Remove Audio",
            f"Delete {len(names)} file(s) from the project?\n" + "\n".join(names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        errors: list[str] = []
        for r in rows:
            path = Path(self.table.item(r, 0).data(Qt.ItemDataRole.UserRole))
            try:
                path.unlink()
            except OSError as exc:
                errors.append(f"{path.name}: {exc}")
        if errors:
            QMessageBox.warning(self, "Remove Audio", "Some files could not be deleted:\n" + "\n".join(errors))
        self.refresh()


class SoundEditorWidget(QWidget):
    """Top-level sound editor: channels config + sub-tabs for creator and import.

    Channel renames/additions and per-file channel assignments only live in
    the widgets' own memory until "Save audio channels" is clicked — nothing
    here writes to tortu.project or regenerates audio_auto.py on its own,
    mirroring the explicit "Save game settings" button on the Game Settings tab.
    """

    save_requested = pyqtSignal(list, dict)  # (channels, channel_map)

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root

        channels_group = QGroupBox("Audio Channels")
        channels_layout = QVBoxLayout(channels_group)
        self.channels_panel = ChannelsPanel()
        self.channels_panel.channels_changed.connect(self._on_channels_changed)
        channels_layout.addWidget(self.channels_panel)

        self.music_creator = MusicCreatorPanel()
        self.import_audio = ImportAudioPanel(project_root, self.channels_panel.channels)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(self.music_creator, "Music Creator")
        self.sub_tabs.addTab(self.import_audio, "Import Audio")

        self.btn_save = QPushButton("Save audio channels")
        self.btn_save.setToolTip(
            "Write the channel list and per-file assignments to tortu.project "
            "and regenerate scripts/_generated/audio_auto.py"
        )
        self.btn_save.clicked.connect(self._on_save_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(channels_group)
        layout.addWidget(self.sub_tabs, stretch=1)
        layout.addWidget(self.btn_save)

    def _on_channels_changed(self, channels: list[str]) -> None:
        self.import_audio.set_channels(channels)

    def _on_save_clicked(self) -> None:
        self.save_requested.emit(self.channels_panel.channels, self.import_audio.channel_map)

    def set_project_root(self, project_root: Path) -> None:
        self.project_root = project_root
        self.import_audio.set_project_root(project_root)

    def set_channel_map(self, channel_map: dict[str, str]) -> None:
        self.import_audio.set_channel_map(channel_map)

    def refresh(self) -> None:
        self.import_audio.refresh()
