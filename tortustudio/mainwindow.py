"""Main TortuStudio window layout."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
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
from tortuengine.export_cart import export_cart
from tortuengine.game_settings import MAX_GAME_FPS, MIN_GAME_FPS, slugify_cart_name
from tortuengine.background import save_background
from tortuengine.object import save_object
from tortuengine.project import Project, create_project, load_project, save_project
from tortuengine.scene import save_scene
from tortuengine.sprite import save_sprite
from tortuengine.tileset import save_tileset
from tortustudio.asset_drag import DraggableProjectTree
from tortustudio.background_editor import BackgroundEditorWidget
from tortustudio.font_editor import FontEditorWidget
from tortustudio.new_background_dialog import NewBackgroundDialog
from tortustudio.new_object_dialog import NewObjectDialog
from tortustudio.new_scene_dialog import NewSceneDialog
from tortustudio.new_sprite_dialog import NewSpriteDialog
from tortustudio.new_tileset_dialog import NewTilesetDialog
from tortustudio.object_editor import ObjectEditorWidget
from tortustudio.scene_assets import is_engine_asset, list_scene_paths
from tortustudio.scene_editor import SceneEditorWidget
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
    SCENE_EDITOR = 1
    SPRITE_EDITOR = 2
    TILESET_EDITOR = 3
    BACKGROUND_EDITOR = 4
    FONT_EDITOR = 5
    OBJECT_EDITOR = 6

    def __init__(self, project: Project | None = None) -> None:
        super().__init__()
        self.project = project
        self._game_module = None
        self._observer: Observer | None = None
        self._pending_reload = False
        self._switching_tabs = False
        self._active_sprite_path: Path | None = None
        self._active_tileset_path: Path | None = None
        self._active_scene_path: Path | None = None
        self._active_background_path: Path | None = None
        self._active_object_path: Path | None = None
        self._active_font_path: Path | None = None

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

        scene_tab_action = QAction("&Scene Editor", self)
        scene_tab_action.setShortcut("Ctrl+2")
        scene_tab_action.triggered.connect(self._activate_scene_editor_tab)
        tabs_menu.addAction(scene_tab_action)

        sprite_tab_action = QAction("&Sprite Editor", self)
        sprite_tab_action.setShortcut("Ctrl+3")
        sprite_tab_action.triggered.connect(self._activate_sprite_editor_tab)
        tabs_menu.addAction(sprite_tab_action)

        tileset_tab_action = QAction("&Tileset Editor", self)
        tileset_tab_action.setShortcut("Ctrl+4")
        tileset_tab_action.triggered.connect(self._activate_tileset_editor_tab)
        tabs_menu.addAction(tileset_tab_action)

        background_tab_action = QAction("&Background Editor", self)
        background_tab_action.setShortcut("Ctrl+5")
        background_tab_action.triggered.connect(self._activate_background_editor_tab)
        tabs_menu.addAction(background_tab_action)

        font_tab_action = QAction("&Font Editor", self)
        font_tab_action.setShortcut("Ctrl+6")
        font_tab_action.triggered.connect(self._activate_font_editor_tab)
        tabs_menu.addAction(font_tab_action)

        object_tab_action = QAction("&Object Editor", self)
        object_tab_action.setShortcut("Ctrl+7")
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

        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(4)

        self.tree_engine_only = QCheckBox("Engine assets only")
        self.tree_engine_only.setChecked(True)
        self.tree_engine_only.setToolTip(
            "Hide sidecar PNGs and other files; show .tortusprite, .tortuscene, .pal, etc."
        )
        self.tree_engine_only.toggled.connect(self._populate_tree)
        tree_layout.addWidget(self.tree_engine_only)

        self.project_tree = DraggableProjectTree(drag_suffixes=(".tortusprite",))
        self.project_tree.setHeaderLabel("Project")
        self.project_tree.setMinimumWidth(180)
        self.project_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        tree_layout.addWidget(self.project_tree, stretch=1)

        splitter.addWidget(tree_panel)

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
        self.scene_editor = SceneEditorWidget(Path("."))
        self.scene_editor.saved.connect(self._on_scene_saved)
        self.scene_editor.new_scene_requested.connect(self._action_new_scene)
        self.scene_editor.open_scene_requested.connect(self._action_open_scene)
        self.background_editor = BackgroundEditorWidget(Path("."))
        self.background_editor.saved.connect(self._on_background_saved)
        self.background_editor.new_background_requested.connect(self._action_new_background)
        self.background_editor.open_background_requested.connect(self._action_open_background)
        self.font_editor = FontEditorWidget(Path("."))
        self.font_editor.saved.connect(self._on_font_saved)
        self.font_editor.new_font_requested.connect(self._action_new_text_font)
        self.font_editor.open_font_requested.connect(self._action_open_text_font)
        self.font_editor.new_sprite_font_requested.connect(self._action_new_sprite_font)
        self.font_editor.open_sprite_font_requested.connect(self._action_open_sprite_font)
        self.object_editor = ObjectEditorWidget(Path("."))
        self.object_editor.saved.connect(self._on_object_saved)
        self.object_editor.new_object_requested.connect(self._action_new_object)
        self.object_editor.open_object_requested.connect(self._action_open_object)

        self.center_stack.addWidget(self.viewport)
        self.center_stack.addWidget(self.scene_editor)
        self.center_stack.addWidget(self.sprite_editor)
        self.center_stack.addWidget(self.tileset_editor)
        self.center_stack.addWidget(self.background_editor)
        self.center_stack.addWidget(self.font_editor)
        self.center_stack.addWidget(self.object_editor)
        splitter.addWidget(self.center_stack)

        inspector = QWidget()
        inspector_layout = QFormLayout(inspector)
        inspector_layout.addRow(QLabel("<b>Game Settings</b>"))

        self.field_game_name = QLineEdit()
        self.field_game_name.setPlaceholderText("My Game")
        inspector_layout.addRow("Game name:", self.field_game_name)

        self.field_cart_name = QLineEdit()
        self.field_cart_name.setPlaceholderText("my_game")
        inspector_layout.addRow("Cart name:", self.field_cart_name)

        self.field_game_fps = QSpinBox()
        self.field_game_fps.setRange(MIN_GAME_FPS, MAX_GAME_FPS)
        self.field_game_fps.setValue(60)
        inspector_layout.addRow("Game FPS:", self.field_game_fps)

        self.field_start_scene = QComboBox()
        self.field_start_scene.setEditable(True)
        self.field_start_scene.lineEdit().setPlaceholderText("scenes/level_01.tortuscene")
        self.field_start_scene.setToolTip(
            "Scene loaded in Game Preview when you press Play (F5). Save game settings to keep."
        )
        inspector_layout.addRow("Start scene:", self.field_start_scene)

        self.field_author = QLineEdit()
        inspector_layout.addRow("Author:", self.field_author)

        self.field_description = QLineEdit()
        inspector_layout.addRow("Description:", self.field_description)

        self.btn_save_game_settings = QPushButton("Save game settings")
        self.btn_save_game_settings.clicked.connect(self._save_game_settings)
        inspector_layout.addRow(self.btn_save_game_settings)

        inspector_layout.addRow(QLabel("<b>Open Asset</b>"))
        self.field_name = QLineEdit()
        self.field_name.setReadOnly(True)
        self.field_name.setPlaceholderText("No asset open")
        inspector_layout.addRow("File:", self.field_name)

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
        self.scene_editor.project_root = project.root
        self.background_editor.project_root = project.root
        self.font_editor.set_project_root(project.root)
        self.object_editor.project_root = project.root
        self._active_sprite_path = None
        self._active_tileset_path = None
        self._active_scene_path = None
        self._active_background_path = None
        self._active_object_path = None
        self._active_font_path = None
        self.workspace_tabs.reset()
        self.setWindowTitle(f"TortuStudio — {project.name}")
        self._load_game_settings_form()
        self._populate_start_scene_combo()
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

        project_file = self.project.root / "tortu.project"
        if project_file.is_file() and self._tree_include_file(project_file):
            QTreeWidgetItem(root_item, [project_file.relative_to(self.project.root).as_posix()])

        for label, path in (
            ("Palettes", self.project.palettes_dir()),
            ("Tiles", self.project.tiles_dir()),
            ("Backgrounds", self.project.backgrounds_dir()),
            ("Scenes", self.project.scenes_dir()),
            ("Objects", self.project.objects_dir()),
            ("Fonts", self.project.fonts_dir()),
            ("Sprites", self.project.sprites_dir()),
            ("Assets", self.project.assets_dir()),
            ("Scripts", self.project.scripts_dir()),
        ):
            folder = QTreeWidgetItem([label])
            root_item.addChild(folder)
            if path.is_dir():
                for child in sorted(path.rglob("*")):
                    if child.is_file() and self._tree_include_file(child):
                        rel = child.relative_to(self.project.root)
                        QTreeWidgetItem(folder, [str(rel)])

        root_item.setExpanded(True)

    def _tree_include_file(self, path: Path) -> bool:
        if self.tree_engine_only.isChecked():
            return is_engine_asset(path)
        return True

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

    def _populate_start_scene_combo(self) -> None:
        if not self.project:
            return
        current = self.field_start_scene.currentText().strip()
        self.field_start_scene.blockSignals(True)
        self.field_start_scene.clear()
        self.field_start_scene.addItem("")
        for rel in list_scene_paths(self.project.root):
            self.field_start_scene.addItem(rel)
        if current:
            index = self.field_start_scene.findText(current)
            if index >= 0:
                self.field_start_scene.setCurrentIndex(index)
            else:
                self.field_start_scene.setEditText(current)
        elif self.project.game.start_scene:
            index = self.field_start_scene.findText(self.project.game.start_scene)
            if index >= 0:
                self.field_start_scene.setCurrentIndex(index)
            else:
                self.field_start_scene.setEditText(self.project.game.start_scene)
        self.field_start_scene.blockSignals(False)

    def _start_scene_rel_path(self) -> str:
        return self.field_start_scene.currentText().strip().replace("\\", "/")

    def _action_play(self) -> None:
        self._activate_preview_tab()
        if not self.project:
            QMessageBox.information(self, "Play", "Open a project first.")
            return

        start_rel = self._start_scene_rel_path() or self.project.game.start_scene.strip()
        scene_path = (self.project.root / start_rel).resolve() if start_rel else None

        if scene_path and scene_path.is_file():
            self.viewport.set_scene_preview(self.project.root, scene_path)
            self.viewport.set_fps(self.project.game.fps)
            if not self.viewport.playing:
                self.viewport.start_playback()
            self.log(f"Playing scene {start_rel}")
            return

        if self._pending_reload:
            self._pending_reload = False
            self._reload_scripts()

        if start_rel:
            self.log(f"Start scene not found: {start_rel}")
            QMessageBox.warning(
                self,
                "Play",
                f"Start scene not found:\n{start_rel}\n\nPick a scene in Game Settings and save.",
            )
            return

        self.viewport.set_game(self._game_module)
        self.viewport.set_fps(self.project.game.fps)
        if not self.viewport.playing:
            self.viewport.start_playback()
        self.log("Play (entry script)")

    def _action_stop(self) -> None:
        self.viewport.stop_playback()
        self.log("Stop")

    def _action_export_cart(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Export Cart", "Open a project first.")
            return
        try:
            self.project.game.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Export Cart", str(exc))
            return
        if not self.project.game.start_scene.strip():
            QMessageBox.warning(
                self,
                "Export Cart",
                "Set a start scene in Game Settings before exporting.",
            )
            return

        default_name = f"{self.project.game.cart_name}.tortucart"
        dest = QFileDialog.getExistingDirectory(self, "Export .tortucart To…")
        if not dest:
            return
        cart_path = Path(dest) / default_name
        if cart_path.exists():
            reply = QMessageBox.question(
                self,
                "Export Cart",
                f"Overwrite existing cart?\n{cart_path}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            export_cart(self.project, cart_path)
        except Exception as exc:
            QMessageBox.warning(self, "Export Cart", str(exc))
            return

        self.log(f"Exported cart to {cart_path}")
        QMessageBox.information(
            self,
            "Export Cart",
            f"Cart exported to:\n{cart_path}\n\n"
            f"Run: python -m tortuplayer {cart_path}",
        )

    def _load_game_settings_form(self) -> None:
        if not self.project:
            return
        game = self.project.game
        self.field_game_name.setText(game.game_name)
        self.field_cart_name.setText(game.cart_name)
        self.field_game_fps.setValue(game.fps)
        if game.start_scene:
            index = self.field_start_scene.findText(game.start_scene)
            if index >= 0:
                self.field_start_scene.setCurrentIndex(index)
            else:
                self.field_start_scene.setEditText(game.start_scene)
        else:
            self.field_start_scene.setCurrentIndex(0)
        self.field_author.setText(game.author)
        self.field_description.setText(game.description)
        self.viewport.set_fps(game.fps)

    def _save_game_settings(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Game Settings", "Open a project first.")
            return
        cart_name = self.field_cart_name.text().strip() or slugify_cart_name(
            self.field_game_name.text()
        )
        self.project.game.game_name = self.field_game_name.text().strip() or "Untitled Game"
        self.project.game.cart_name = cart_name
        self.project.game.fps = self.field_game_fps.value()
        self.project.game.start_scene = self._start_scene_rel_path()
        self.field_start_scene.setEditText(self.project.game.start_scene)
        self.project.game.author = self.field_author.text().strip()
        self.project.game.description = self.field_description.text().strip()
        try:
            self.project.game.validate()
        except ValueError as exc:
            QMessageBox.warning(self, "Game Settings", str(exc))
            return
        save_project(self.project)
        self.viewport.set_fps(self.project.game.fps)
        self.log("Saved game settings.")

    def _action_validate_project(self) -> None:
        if not self.project:
            self.log("Validate: no project open.")
            return
        issues = []
        if not self.project.entry_path().is_file():
            issues.append(f"Missing entry script: {self.project.entry}")
        if not self.project.palettes_dir().is_dir():
            issues.append("Missing palettes/ folder")
        start_scene = self.project.start_scene_path()
        if start_scene is not None and not start_scene.is_file():
            issues.append(f"Missing start scene: {self.project.game.start_scene}")
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

    def _activate_scene_editor_tab(self) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_scene_editor()
        self._switching_tabs = False
        self._show_scene_editor()

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
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_background_editor()
        self._switching_tabs = False
        self._show_background_editor()
    
    def _activate_object_editor_tab(self) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_object_editor()
        self._switching_tabs = False
        self._show_object_editor()

    def _activate_font_editor_tab(self) -> None:
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

    def _open_scene(self, path: Path) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_scene_editor()
        self._switching_tabs = False
        self._show_scene(path)

    def _open_background(self, path: Path) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_background_editor()
        self._switching_tabs = False
        self._show_background(path)

    def _open_object(self, path: Path) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_object_editor()
        self._switching_tabs = False
        self._show_object(path)

    def _open_text_font(self, path: Path) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_font_editor()
        self._switching_tabs = False
        self._show_text_font(path)

    def _open_sprite_font(self, path: Path) -> None:
        if not self._confirm_discard_editor_changes():
            return
        self._switching_tabs = True
        self.workspace_tabs.select_font_editor()
        self._switching_tabs = False
        self._show_sprite_font(path)

    def _show_preview(self) -> None:
        self.viewport.stop_playback()
        self.center_stack.setCurrentIndex(self.VIEWPORT)
        self.field_name.clear()

    def _show_scene_editor(self) -> None:
        self.center_stack.setCurrentIndex(self.SCENE_EDITOR)
        if self._active_scene_path:
            self.field_name.setText(self._active_scene_path.name)
        else:
            self.field_name.setPlaceholderText("No scene open — use New / Open Scene above")

    def _show_scene(self, path: Path) -> None:
        self.scene_editor.open_scene(path)
        self._active_scene_path = path.resolve()
        self.center_stack.setCurrentIndex(self.SCENE_EDITOR)
        self.field_name.setText(path.name)

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

    def _show_background_editor(self) -> None:
        self.center_stack.setCurrentIndex(self.BACKGROUND_EDITOR)
        if self._active_background_path:
            self.field_name.setText(self._active_background_path.name)
        else:
            self.field_name.setPlaceholderText(
                "No background open — use New / Open Background above"
            )

    def _show_background(self, path: Path) -> None:
        self.background_editor.open_background(path)
        self._active_background_path = path.resolve()
        self.center_stack.setCurrentIndex(self.BACKGROUND_EDITOR)
        self.field_name.setText(path.name)

    def _show_object_editor(self) -> None:
        self.center_stack.setCurrentIndex(self.OBJECT_EDITOR)
        if self._active_object_path:
            self.field_name.setText(self._active_object_path.name)
        else:
            self.field_name.setPlaceholderText(
                "No object open — use New / Open Object above"
            )

    def _show_object(self, path: Path) -> None:
        self.object_editor.open_object(path)
        self._active_object_path = path.resolve()
        self.center_stack.setCurrentIndex(self.OBJECT_EDITOR)
        self.field_name.setText(path.name)

    def _show_font_editor(self) -> None:
        self.center_stack.setCurrentIndex(self.FONT_EDITOR)
        if self._active_font_path:
            self.field_name.setText(self._active_font_path.name)
        else:
            self.field_name.setPlaceholderText(
                "No font open — use New / Open in the Font Editor"
            )

    def _show_text_font(self, path: Path) -> None:
        self.font_editor.open_text_font(path)
        self._active_font_path = path.resolve()
        self.center_stack.setCurrentIndex(self.FONT_EDITOR)
        self.field_name.setText(path.name)

    def _show_sprite_font(self, path: Path) -> None:
        self.font_editor.open_sprite_font(path)
        self._active_font_path = path.resolve()
        self.center_stack.setCurrentIndex(self.FONT_EDITOR)
        self.field_name.setText(path.name)

    def _show_active_font(self, path: Path) -> None:
        if path.suffix == ".tortuspritefont":
            self._show_sprite_font(path)
        else:
            self._show_text_font(path)

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

        if ref.kind == TabKind.SCENE_EDITOR:
            if not self._confirm_discard_editor_changes():
                self._switching_tabs = True
                self._restore_editor_tab()
                self._switching_tabs = False
                return
            if self._active_scene_path and self._active_scene_path.is_file():
                self._show_scene(self._active_scene_path)
            else:
                self._show_scene_editor()
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
            return

        if ref.kind == TabKind.BACKGROUND_EDITOR:
            if not self._confirm_discard_editor_changes():
                self._switching_tabs = True
                self._restore_editor_tab()
                self._switching_tabs = False
                return
            if self._active_background_path and self._active_background_path.is_file():
                self._show_background(self._active_background_path)
            else:
                self._show_background_editor()
            return

        if ref.kind == TabKind.FONT_EDITOR:
            if not self._confirm_discard_editor_changes():
                self._switching_tabs = True
                self._restore_editor_tab()
                self._switching_tabs = False
                return
            if self._active_font_path and self._active_font_path.is_file():
                self._show_active_font(self._active_font_path)
            else:
                self._show_font_editor()
            return

        if ref.kind == TabKind.OBJECT_EDITOR:
            if not self._confirm_discard_editor_changes():
                self._switching_tabs = True
                self._restore_editor_tab()
                self._switching_tabs = False
                return
            if self._active_object_path and self._active_object_path.is_file():
                self._show_object(self._active_object_path)
            else:
                self._show_object_editor()

    def _restore_editor_tab(self) -> None:
        index = self.center_stack.currentIndex()
        if index == self.SCENE_EDITOR:
            self.workspace_tabs.select_scene_editor()
        elif index == self.SPRITE_EDITOR:
            self.workspace_tabs.select_sprite_editor()
        elif index == self.TILESET_EDITOR:
            self.workspace_tabs.select_tileset_editor()
        elif index == self.BACKGROUND_EDITOR:
            self.workspace_tabs.select_background_editor()
        elif index == self.FONT_EDITOR:
            self.workspace_tabs.select_font_editor()
        elif index == self.OBJECT_EDITOR:
            self.workspace_tabs.select_object_editor()
        else:
            self.workspace_tabs.select_preview()

    def _confirm_discard_editor_changes(self) -> bool:
        index = self.center_stack.currentIndex()
        if index == self.SCENE_EDITOR and self.scene_editor.has_unsaved_changes():
            return self._confirm_discard_unsaved("scene", self.scene_editor.save)
        if index == self.SPRITE_EDITOR and self.sprite_editor.has_unsaved_changes():
            return self._confirm_discard_unsaved("sprite", self.sprite_editor.save)
        if index == self.TILESET_EDITOR and self.tileset_editor.has_unsaved_changes():
            return self._confirm_discard_unsaved("tileset", self.tileset_editor.save)
        if index == self.BACKGROUND_EDITOR and self.background_editor.has_unsaved_changes():
            return self._confirm_discard_unsaved("background", self.background_editor.save)
        if index == self.FONT_EDITOR and self.font_editor.has_unsaved_changes():
            return self._confirm_discard_unsaved("font", self.font_editor.save)
        if index == self.OBJECT_EDITOR and self.object_editor.has_unsaved_changes():
            return self._confirm_discard_unsaved("object", self.object_editor.save)
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
        if path.suffix == ".tortuscene":
            self._open_scene(path)
        elif path.suffix == ".tortusprite":
            self._open_sprite(path)
        elif path.suffix == ".tortutileset":
            self._open_tileset(path)
        elif path.suffix == ".tortubackground":
            self._open_background(path)
        elif path.suffix == ".tortuobject":
            self._open_object(path)
        elif path.suffix == ".tortufont":
            self._open_text_font(path)
        elif path.suffix == ".tortuspritefont":
            self._open_sprite_font(path)
        elif path.suffix == ".pal":
            self.log(f"Edit palette in external editor: {path}")
            cmd = self.project.editor_command.format(file=path, line=1)
            subprocess.Popen(cmd, shell=True)

    def _on_sprite_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_tree()
        if self.viewport.scene_preview_active:
            self.viewport.invalidate_baked_assets()

    def _on_tileset_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_tree()
        if self.viewport.scene_preview_active:
            self.viewport.invalidate_baked_assets()

    def _on_scene_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_start_scene_combo()
        self._populate_tree()
        if self.viewport.scene_preview_active and self.project:
            self.viewport.reload_scene_preview(self.project.root)

    def _on_background_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_tree()
        if self.viewport.scene_preview_active:
            self.viewport.invalidate_baked_assets()

    def _on_font_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_tree()

    def _on_object_saved(self, path: Path) -> None:
        self.log(f"Saved {path.relative_to(self.project.root)}")
        self._populate_tree()
        if self.viewport.scene_preview_active:
            self.viewport.invalidate_baked_assets()

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

    def _action_new_scene(self) -> None:
        if not self.project:
            QMessageBox.information(self, "New Scene", "Open a project first.")
            return

        dialog = NewSceneDialog(self.project.root, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        name = dialog.scene_name or "scene"
        scene_path = self.project.scenes_dir() / f"{name}.tortuscene"
        if scene_path.exists():
            QMessageBox.warning(self, "New Scene", f"{scene_path.name} already exists.")
            return

        if not self._confirm_discard_editor_changes():
            return

        self.scene_editor.new_scene(scene_path, dialog.palette_name)
        if not self.scene_editor.scene:
            return
        save_scene(
            self.scene_editor.scene,
            scene_path,
            project_root=self.project.root,
        )
        self.scene_editor._dirty = False
        self._populate_tree()
        self._open_scene(scene_path)
        self.log(f"Created {scene_path.relative_to(self.project.root)}")

    def _action_open_scene(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Open Scene", "Open a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Scene",
            str(self.project.scenes_dir()),
            "Tortu Scenes (*.tortuscene)",
        )
        if path:
            self._open_scene(Path(path))

    def _action_new_background(self) -> None:
        if not self.project:
            QMessageBox.information(self, "New Background", "Open a project first.")
            return

        dialog = NewBackgroundDialog(self.project.root, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        name = dialog.background_name or "background"
        background_path = self.project.backgrounds_dir() / f"{name}.tortubackground"
        if background_path.exists():
            QMessageBox.warning(
                self, "New Background", f"{background_path.name} already exists."
            )
            return

        if not self._confirm_discard_editor_changes():
            return

        self.background_editor.new_background(
            background_path,
            dialog.palette_name,
            dialog.image_path,
        )
        if not self.background_editor.background:
            return
        save_background(self.background_editor.background, background_path)
        self.background_editor._dirty = False
        self._populate_tree()
        self._open_background(background_path)
        self.log(f"Created {background_path.relative_to(self.project.root)}")

    def _action_open_background(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Open Background", "Open a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Background",
            str(self.project.backgrounds_dir()),
            "Tortu Backgrounds (*.tortubackground)",
        )
        if path:
            self._open_background(Path(path))

    def _action_new_text_font(self) -> None:
        if not self.project:
            QMessageBox.information(self, "New Text Font", "Open a project first.")
            return
        if not self._confirm_discard_editor_changes():
            return
        self.font_editor.new_text_font()
        text_editor = self.font_editor.text_editor
        if not text_editor.tortu_font or not text_editor.file_path:
            return
        text_editor.save()
        self._populate_tree()
        self._open_text_font(text_editor.file_path)
        self.log(f"Created {text_editor.file_path.relative_to(self.project.root)}")

    def _action_open_text_font(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Open Text Font", "Open a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Text Font",
            str(self.project.fonts_dir()),
            "Tortu Text Fonts (*.tortufont)",
        )
        if path:
            self._open_text_font(Path(path))

    def _action_new_sprite_font(self) -> None:
        if not self.project:
            QMessageBox.information(self, "New Sprite Font", "Open a project first.")
            return
        if not self._confirm_discard_editor_changes():
            return
        self.font_editor.new_sprite_font()
        sprite_editor = self.font_editor.sprite_editor
        if not sprite_editor.sprite_font or not sprite_editor.file_path:
            return
        sprite_editor.save()
        self._populate_tree()
        self._open_sprite_font(sprite_editor.file_path)
        self.log(f"Created {sprite_editor.file_path.relative_to(self.project.root)}")

    def _action_open_sprite_font(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Open Sprite Font", "Open a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Sprite Font",
            str(self.project.fonts_dir()),
            "Tortu Sprite Fonts (*.tortuspritefont)",
        )
        if path:
            self._open_sprite_font(Path(path))

    def _action_new_object(self) -> None:
        if not self.project:
            QMessageBox.information(self, "New Object", "Open a project first.")
            return

        dialog = NewObjectDialog(self.project.root, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        if not dialog.sprite_path:
            QMessageBox.warning(
                self,
                "New Object",
                "Create a sprite asset before making an object.",
            )
            return

        name = dialog.object_name or "object"
        object_path = self.project.objects_dir() / f"{name}.tortuobject"
        if object_path.exists():
            QMessageBox.warning(self, "New Object", f"{object_path.name} already exists.")
            return

        if not self._confirm_discard_editor_changes():
            return

        self.object_editor.new_object(
            object_path, dialog.sprite_path, name, dialog.animation_name
        )
        if not self.object_editor.tortu_object:
            return
        save_object(self.object_editor.tortu_object, object_path)
        self.object_editor._dirty = False
        self._populate_tree()
        self._open_object(object_path)
        self.log(f"Created {object_path.relative_to(self.project.root)}")

    def _action_open_object(self) -> None:
        if not self.project:
            QMessageBox.information(self, "Open Object", "Open a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Object",
            str(self.project.objects_dir()),
            "Tortu Objects (*.tortuobject)",
        )
        if path:
            self._open_object(Path(path))

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
