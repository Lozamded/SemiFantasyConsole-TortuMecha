"""Main TortuStudio window layout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from tortuengine.cart import load_game_module, reload_game_module
from tortuengine.project import Project, create_project, load_project
from tortuengine.sprite import save_sprite
from tortuengine.tileset import save_tileset
from tortustudio.new_sprite_dialog import NewSpriteDialog
from tortustudio.new_tileset_dialog import NewTilesetDialog
from tortustudio.sprite_editor import SpriteEditorWidget
from tortustudio.tileset_editor import TilesetEditorWidget
from tortustudio.viewport import ViewportWidget
from tortustudio.workspace_tabs import TabKind, TabRef, WorkspaceTabs


class _ScriptReloadHandler(FileSystemEventHandler):
    def __init__(self, studio: "MainWindow") -> None:
        self._studio = studio

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix == ".py":
            self._studio.schedule_script_reload()


class MainWindow(QMainWindow):
    VIEWPORT = 0
    SPRITE_EDITOR = 1
    TILESET_EDITOR = 2

    def __init__(self, project: Project | None = None) -> None:
        super().__init__()
        self.project = project
        self._game_module = None
        self._observer: Observer | None = None
        self._pending_reload = False
        self._switching_tabs = False
        self._active_sprite_path: Path | None = None
        self._active_tileset_path: Path | None = None

        self.setWindowTitle("TortuStudio")
        self.resize(1280, 720)

        self._build_menu()
        self._build_ui()

        if project:
            self.open_project(project)

    def _build_menu(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("&File")
        open_action = QAction("&Open Project…", self)
        open_action.triggered.connect(self._action_open_project)
        file_menu.addAction(open_action)

        new_action = QAction("&New Project…", self)
        new_action.triggered.connect(self._action_new_project)
        file_menu.addAction(new_action)

        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        tabs_menu = menu.addMenu("&Tabs")
        preview_tab_action = QAction("&Game Preview", self)
        preview_tab_action.setShortcut("Ctrl+1")
        preview_tab_action.triggered.connect(self._activate_preview_tab)
        tabs_menu.addAction(preview_tab_action)

        sprite_tab_action = QAction("&Sprite Editor", self)
        sprite_tab_action.setShortcut("Ctrl+2")
        sprite_tab_action.triggered.connect(self._activate_sprite_editor_tab)
        tabs_menu.addAction(sprite_tab_action)

        tileset_tab_action = QAction("&Tileset Editor", self)
        tileset_tab_action.setShortcut("Ctrl+3")
        tileset_tab_action.triggered.connect(self._activate_tileset_editor_tab)
        tabs_menu.addAction(tileset_tab_action)

        background_tab_action = QAction("&background Editor", self)
        background_tab_action.setShortcut("Ctrl+3")
        background_tab_action.triggered.connect(self._activate_background_editor_tab)
        tabs_menu.addAction(background_tab_action)

        font_tab_action = QAction("&Font Editor", self)
        font_tab_action.setShortcut("Ctrl+4")
        font_tab_action.triggered.connect(self._activate_font_editor_tab)
        tabs_menu.addAction(font_tab_action)

        object_tab_action = QAction("&Object Editor", self)
        object_tab_action.setShortcut("Ctrl+5")
        object_tab_action.triggered.connect(self._activate_object_editor_tab)
        tabs_menu.addAction(object_tab_action)

        build_menu = menu.addMenu("&Build")
        export_action = QAction("Export .tortucart…", self)
        export_action.triggered.connect(self._action_export_cart)
        build_menu.addAction(export_action)

        validate_action = QAction("&Validate Project", self)
        validate_action.triggered.connect(self._action_validate_project)
        build_menu.addAction(validate_action)

        play_menu = menu.addMenu("&Play")
        play_action = QAction("&Play / Resume", self)
        play_action.setShortcut("F5")
        play_action.triggered.connect(self._action_play)
        play_menu.addAction(play_action)

        stop_action = QAction("&Stop", self)
        stop_action.setShortcut("Shift+F5")
        stop_action.triggered.connect(self._action_stop)
        play_menu.addAction(stop_action)

        reload_action = QAction("Reload Scripts", self)
        reload_action.setShortcut("F6")
        reload_action.triggered.connect(self._reload_scripts)
        play_menu.addAction(reload_action)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        self.workspace_tabs = WorkspaceTabs()
        self.workspace_tabs.tab_selected.connect(self._on_workspace_tab_selected)
        root.addWidget(self.workspace_tabs)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabel("Project")
        self.project_tree.setMinimumWidth(180)
        self.project_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        splitter.addWidget(self.project_tree)

        self.center_stack = QStackedWidget()
        self.viewport = ViewportWidget()
        self.sprite_editor = SpriteEditorWidget(Path("."))
        self.sprite_editor.saved.connect(self._on_sprite_saved)
        self.sprite_editor.new_sprite_requested.connect(self._action_new_sprite)
        self.sprite_editor.open_sprite_requested.connect(self._action_open_sprite)
        self.tileset_editor = TilesetEditorWidget(Path("."))
        self.tileset_editor.saved.connect(self._on_tileset_saved)
        self.tileset_editor.new_tileset_requested.connect(self._action_new_tileset)
        self.tileset_editor.open_tileset_requested.connect(self._action_open_tileset)
        self.center_stack.addWidget(self.viewport)
        self.center_stack.addWidget(self.sprite_editor)
        self.center_stack.addWidget(self.tileset_editor)
        splitter.addWidget(self.center_stack)

        inspector = QWidget()
        inspector_layout = QFormLayout(inspector)
        inspector_layout.addRow(QLabel("<b>Inspector</b>"))
        self.field_name = QLineEdit()
        self.field_name.setReadOnly(True)
        self.field_name.setPlaceholderText("Select a sprite or actor")
        inspector_layout.addRow("Name:", self.field_name)

        self.field_script = QLineEdit()
        self.field_script.setReadOnly(True)
        self.field_script.setPlaceholderText("scripts/example.py")
        inspector_layout.addRow("Script:", self.field_script)

        self.btn_open_editor = QPushButton("Open main.py in Editor")
        self.btn_open_editor.clicked.connect(self._open_entry_in_editor)
        inspector_layout.addRow(self.btn_open_editor)
        inspector.setMinimumWidth(220)
        splitter.addWidget(inspector)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        root.addWidget(splitter, stretch=1)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(500)
        self.console.setPlaceholderText("Build log and play errors…")
        root.addWidget(self.console, stretch=0)

    def log(self, message: str) -> None:
        self.console.appendPlainText(message)

    def schedule_script_reload(self) -> None:
        self._pending_reload = True

    def open_project(self, project: Project) -> None:
        self.project = project
        self.sprite_editor.project_root = project.root
        self.tileset_editor.project_root = project.root
        self._active_sprite_path = None
        self._active_tileset_path = None
        self.workspace_tabs.reset()
        self.setWindowTitle(f"TortuStudio — {project.name}")
        self._populate_tree()
        self._start_watcher()
        self._load_cart(silent=False)
        self._switching_tabs = True
        self.workspace_tabs.select_preview()
        self._switching_tabs = False
        self._show_preview()

    def _populate_tree(self) -> None:
        self.project_tree.clear()
        if not self.project:
            return

        root_item = QTreeWidgetItem([self.project.name])
        self.project_tree.addTopLevelItem(root_item)

        for label, path in (
            ("Palettes", self.project.palettes_dir()),
            ("Tiles", self.project.tiles_dir()),
            ("Scenes", self.project.scenes_dir()),
            ("Objects", self.project.objects_dir()),
            ("Sprites", self.project.sprites_dir()),
            ("Assets", self.project.assets_dir()),
            ("Scripts", self.project.scripts_dir()),
        ):
            folder = QTreeWidgetItem([label])
            root_item.addChild(folder)
            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_file() and child.suffix != ".ref.png":
                        rel = child.relative_to(self.project.root)
                        QTreeWidgetItem(folder, [str(rel)])

        root_item.setExpanded(True)

    def _start_watcher(self) -> None:
        self._stop_watcher()
        if not self.project:
            return

        handler = _ScriptReloadHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.project.root), recursive=True)
        self._observer.start()
        self.log(f"Watching {self.project.root} for script changes.")

    def _stop_watcher(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=1)
            self._observer = None

    def _load_cart(self, silent: bool) -> None:
        if not self.project:
            return

        try:
            self._game_module = load_game_module(self.project.root, self.project.entry)
            self.viewport.set_game(self._game_module)
            if not silent:
                self.log(f"Loaded {self.project.entry}")
        except (FileNotFoundError, ImportError) as exc:
            self.viewport.set_game(None)
            self.log(f"Load error: {exc}")

    def _reload_scripts(self) -> None:
        if not self.project or self._game_module is None:
            self._load_cart(silent=False)
            return

        try:
            self._game_module = reload_game_module(self._game_module)
            self.viewport.set_game(self._game_module)
            self.log("Scripts reloaded.")
        except Exception as exc:
            self.log(f"Reload error: {exc}")

    def _action_play(self) -> None:
        self._activate_preview_tab()
        if self._pending_reload:
            self._pending_reload = False
            self._reload_scripts()
        if not self.viewport.playing:
            self.viewport.start_playback()
            self.log("Play")
        else:
            self.log("Already playing")

    def _action_stop(self) -> None:
        self.viewport.stop_playback()
        self.log("Stop")

    def _action_export_cart(self) -> None:
        self.log("Export .tortucart — coming soon.")

    def _action_validate_project(self) -> None:
        if not self.project:
            self.log("Validate: no project open.")
            return
        issues = []
        if not self.project.entry_path().is_file():
            issues.append(f"Missing entry script: {self.project.entry}")
        if not self.project.palettes_dir().is_dir():
            issues.append("Missing palettes/ folder")
        if issues:
            for issue in issues:
                self.log(f"Validate: {issue}")
        else:
            self.log("Validate: project structure looks OK.")

    def _activate_preview_tab(self) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_preview()
        self._switching_tabs = False
        self._show_preview()

    def _activate_sprite_editor_tab(self) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_sprite_editor()
        self._switching_tabs = False
        self._show_sprite_editor()

    def _activate_tileset_editor_tab(self) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_tileset_editor()
        self._switching_tabs = False
        self._show_tileset_editor()

    def _activate_background_editor_tab(self) -> None:
        return
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_background_editor()
        self._switching_tabs = False
        self._show_background_editor()
    
    def _activate_object_editor_tab(self) -> None:
        return
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_object_editor()
        self._switching_tabs = False
        self._show_object_editor()

    def _activate_font_editor_tab(self) -> None:
        return
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_font_editor()
        self._switching_tabs = False
        self._show_font_editor()

    def _open_sprite(self, path: Path) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_sprite_editor()
        self._switching_tabs = False
        self._show_sprite(path)

    def _open_tileset(self, path: Path) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_tileset_editor()
        self._switching_tabs = False
        self._show_tileset(path)

    def _show_preview(self) -> None:
        self.viewport.stop_playback()
        self.center_stack.setCurrentIndex(self.VIEWPORT)
        self.field_name.clear()

    def _show_sprite_editor(self) -> None:
        self.center_stack.setCurrentIndex(self.SPRITE_EDITOR)
        if self._active_sprite_path:
            self.field_name.setText(self._active_sprite_path.name)
        else:
            self.field_name.setPlaceholderText("No sprite open — use New / Open Sprite above")

    def _show_sprite(self, path: Path) -> None:
        self.sprite_editor.open_sprite(path)
        self._active_sprite_path = path.resolve()
        self.center_stack.setCurrentIndex(self.SPRITE_EDITOR)
        self.field_name.setText(path.name)

    def _show_tileset_editor(self) -> None:
        self.center_stack.setCurrentIndex(self.TILESET_EDITOR)
        if self._active_tileset_path:
            self.field_name.setText(self._active_tileset_path.name)
        else:
            self.field_name.setPlaceholderText("No tileset open — use New / Open Tileset above")

    def _show_tileset(self, path: Path) -> None:
        self.tileset_editor.open_tileset(path)
        self._active_tileset_path = path.resolve()
        self.center_stack.setCurrentIndex(self.TILESET_EDITOR)
        self.field_name.setText(path.name)

    def _on_workspace_tab_selected(self, ref: TabRef) -> None:
        if self._switching_tabs:
            return
        if ref.kind == TabKind.PREVIEW:
            if not self._confirm_discard_editor_changes():
                self._switching_tabs = True
                self._restore_editor_tab()
                self._switching_tabs = False
                return
            self._show_preview()
            return

        if ref.kind == TabKind.SPRITE_EDITOR:
            if not self._confirm_discard_editor_changes():
                self._switching_tabs = True
                self.workspace_tabs.select_preview()
                self._switching_tabs = False
                return
            if self._active_sprite_path and self._active_sprite_path.is_file():
                self._show_sprite(self._active_sprite_path)
            else:
                self._show_sprite_editor()
            return

        if ref.kind == TabKind.TILESET_EDITOR:
            if not self._confirm_discard_editor_changes():
                self._switching_tabs = True
                self._restore_editor_tab()
                self._switching_tabs = False
                return
            if self._active_tileset_path and self._active_tileset_path.is_file():
                self._show_tileset(self._active_tileset_path)
            else:
                self._show_tileset_editor()

    def _restore_editor_tab(self) -> None:
        index = self.center_stack.currentIndex()
        if index == self.SPRITE_EDITOR:
            self.workspace_tabs.select_sprite_editor()
        elif index == self.TILESET_EDITOR:
            self.workspace_tabs.select_tileset_editor()
        else:
            self.workspace_tabs.select_preview()

    def _confirm_discard_editor_changes(self) -> bool:
        index = self.center_stack.currentIndex()
        if index == self.SPRITE_EDITOR and self.sprite_editor.has_unsaved_changes():
            return self._confirm_discard_unsaved("sprite", self.sprite_editor.save)
        if index == self.TILESET_EDITOR and self.tileset_editor.has_unsaved_changes():
            return self._confirm_discard_unsaved("tileset", self.tileset_editor.save)
        return True

    def _confirm_discard_unsaved(self, label: str, save_fn) -> bool:
        reply = QMessageBox.question(
            self,
            f"Unsaved {label.title()}",
            f"Save changes to the {label} before leaving?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            save_fn()
        elif reply == QMessageBox.StandardButton.Cancel:
            return False
        return True

    def _confirm_discard_sprite_changes(self) -> bool:
        return self._confirm_discard_editor_changes()

    def _on_tree_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        if not self.project:
            return
        rel = item.text(0)
        path = self.project.root / rel
        if path.suffix == ".tortusprite":
            self._open_sprite(path)
        elif path.suffix == ".tortutileset":
            self._open_tileset(path)
        elif path.suffix == ".pal":
            self.log(f"Edit palette in external editor: {path}")
            cmd = self.project.editor_command.format(file=path, line=1)
            subprocess.Popen(cmd, shell=True)

    def _on_sprite_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_tree()

    def _on_tileset_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_tree()

    def _action_open_project(self) -> None:
        if not self._confirm_discard_editor_changes():
            return
        path = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if not path:
            return
        try:
            project = load_project(Path(path))
        except FileNotFoundError:
            QMessageBox.warning(self, "Open Project", "No tortu.project found in that folder.")
            return
        self.open_project(project)

    def _action_new_project(self) -> None:
        if not self._confirm_discard_editor_changes():
            return
        path = QFileDialog.getExistingDirectory(self, "Create Project In…")
        if not path:
            return
        name = "My Game"
        root = Path(path) / "my_game"
        project = create_project(root, name=name)
        self._write_default_main(project)
        self.open_project(project)
        self.log(f"Created project at {project.root}")

    def _action_new_sprite(self) -> None:
        if not self.project:
            QMessageBox.information(self, "New Sprite", "Open a project first.")
            return

        dialog = NewSpriteDialog(self.project.root, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        name = dialog.sprite_name or "sprite"
        sprite_path = self.project.sprites_dir() / f"{name}.tortusprite"
        if sprite_path.exists():
            QMessageBox.warning(self, "New Sprite", f"{sprite_path.name} already exists.")
            return

        if not self._confirm_discard_editor_changes():
            return

        self.sprite_editor.new_sprite(
            sprite_path,
            dialog.blocks_w.value(),
            dialog.blocks_h.value(),
            dialog.palette_name,
        )
        save_sprite(self.sprite_editor.sprite, sprite_path)  # type: ignore[arg-type]
        self.sprite_editor._dirty = False
        self._populate_tree()
        self._open_sprite(sprite_path)
        self.log(f"Created {sprite_path.relative_to(self.project.root)}")

    def _action_open_sprite(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Open Sprite", "Open a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Sprite",
            str(self.project.sprites_dir()),
            "Tortu Sprites (*.tortusprite)",
        )
        if path:
            self._open_sprite(Path(path))

    def _action_new_tileset(self) -> None:
        if not self.project:
            QMessageBox.information(self, "New Tileset", "Open a project first.")
            return

        dialog = NewTilesetDialog(self.project.root, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        name = dialog.tileset_name or "tileset"
        tileset_path = self.project.tiles_dir() / f"{name}.tortutileset"
        if tileset_path.exists():
            QMessageBox.warning(self, "New Tileset", f"{tileset_path.name} already exists.")
            return

        if not self._confirm_discard_editor_changes():
            return

        self.tileset_editor.new_tileset(
            tileset_path,
            dialog.palette_name,
            tile_size=dialog.tile_size.value(),
        )
        save_tileset(self.tileset_editor.tileset, tileset_path)  # type: ignore[arg-type]
        self.tileset_editor._dirty = False
        self._populate_tree()
        self._open_tileset(tileset_path)
        self.log(f"Created {tileset_path.relative_to(self.project.root)}")

    def _action_open_tileset(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Open Tileset", "Open a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Tileset",
            str(self.project.tiles_dir()),
            "Tortu Tilesets (*.tortutileset)",
        )
        if path:
            self._open_tileset(Path(path))

    def _open_entry_in_editor(self) -> None:
        if not self.project:
            return
        entry = self.project.entry_path()
        if not entry.is_file():
            QMessageBox.information(self, "Open Editor", f"{entry} does not exist yet.")
            return
        cmd = self.project.editor_command.format(file=entry, line=1)
        self.log(f"Launching: {cmd}")
        try:
            subprocess.Popen(cmd, shell=True)
        except OSError as exc:
            self.log(f"Editor launch failed: {exc}")

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._confirm_discard_editor_changes():
            event.ignore()
            return
        self._stop_watcher()
        self.viewport.stop_playback()
        super().closeEvent(event)

    def _write_default_main(self, project: Project) -> None:
        main_py = project.root / project.entry
        if main_py.exists():
            return
        main_py.write_text(
            '''"""Cart entry — edit in your favorite editor (Cursor, VSCode, nano)."""

_t = 0.0


def init(engine):
    pass


def update(dt):
    global _t
    _t += dt


def draw(engine):
    engine.clear((12, 18, 32))
    x = int(120 + 80 * __import__("math").sin(_t * 2))
    engine.rect((80, 200, 120), (x, 80, 24, 24))
    engine.text("TortuStudio", 72, 16, (240, 240, 255), 16)
''',
            encoding="utf-8",
        )


def run_studio(project_path: Path | None = None) -> int:
    app = QApplication(sys.argv)
    project = load_project(project_path) if project_path else None
    window = MainWindow(project)
    window.show()
    return app.exec()
