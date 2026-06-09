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
from tortustudio.new_sprite_dialog import NewSpriteDialog
from tortustudio.sprite_editor import SpriteEditorWidget
from tortustudio.viewport import ViewportWidget


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

    def __init__(self, project: Project | None = None) -> None:
        super().__init__()
        self.project = project
        self._game_module = None
        self._observer: Observer | None = None
        self._pending_reload = False

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

        sprite_menu = menu.addMenu("&Sprite")
        new_sprite_action = QAction("&New Sprite…", self)
        new_sprite_action.triggered.connect(self._action_new_sprite)
        sprite_menu.addAction(new_sprite_action)

        view_menu = menu.addMenu("&View")
        preview_action = QAction("&Game Preview", self)
        preview_action.setShortcut("Ctrl+1")
        preview_action.triggered.connect(self._show_viewport)
        view_menu.addAction(preview_action)

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
        self.center_stack.addWidget(self.viewport)
        self.center_stack.addWidget(self.sprite_editor)
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
        self.setWindowTitle(f"TortuStudio — {project.name}")
        self._populate_tree()
        self._start_watcher()
        self._load_cart(silent=False)
        self._show_viewport()

    def _populate_tree(self) -> None:
        self.project_tree.clear()
        if not self.project:
            return

        root_item = QTreeWidgetItem([self.project.name])
        self.project_tree.addTopLevelItem(root_item)

        for label, path in (
            ("Palettes", self.project.palettes_dir()),
            ("Scenes", self.project.scenes_dir()),
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
        self._show_viewport()
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

    def _show_viewport(self) -> None:
        if not self._confirm_discard_sprite_changes():
            return
        self.center_stack.setCurrentIndex(self.VIEWPORT)

    def _show_sprite_editor(self, path: Path | None = None) -> None:
        if path:
            if not self._confirm_discard_sprite_changes():
                return
            self.sprite_editor.open_sprite(path)
            self.field_name.setText(path.name)
        self.center_stack.setCurrentIndex(self.SPRITE_EDITOR)

    def _confirm_discard_sprite_changes(self) -> bool:
        if (
            self.center_stack.currentIndex() == self.SPRITE_EDITOR
            and self.sprite_editor.has_unsaved_changes()
        ):
            reply = QMessageBox.question(
                self,
                "Unsaved Sprite",
                "Save changes to the sprite before leaving?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self.sprite_editor.save()
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
        return True

    def _on_tree_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        if not self.project:
            return
        rel = item.text(0)
        path = self.project.root / rel
        if path.suffix == ".tortusprite":
            self._show_sprite_editor(path)
        elif path.suffix == ".pal":
            self.log(f"Edit palette in external editor: {path}")
            cmd = self.project.editor_command.format(file=path, line=1)
            subprocess.Popen(cmd, shell=True)

    def _on_sprite_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_tree()

    def _action_open_project(self) -> None:
        if not self._confirm_discard_sprite_changes():
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
        if not self._confirm_discard_sprite_changes():
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

        if not self._confirm_discard_sprite_changes():
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
        self._show_sprite_editor(sprite_path)
        self.log(f"Created {sprite_path.relative_to(self.project.root)}")

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
        if not self._confirm_discard_sprite_changes():
            event.ignore()
            return
        self._stop_watcher()
        self.viewport.stop_playback()
        super().closeEvent(event)


def run_studio(project_path: Path | None = None) -> int:
    app = QApplication(sys.argv)
    project = load_project(project_path) if project_path else None
    window = MainWindow(project)
    window.show()
    return app.exec()
