"""Dialogue editor — edit dialogues/*.json: lines, branching options, and actions.

See ``tortoisengine.dialogue`` for the on-disk shape this mirrors (line
speaker/text/icon/id, an optional line-level action, and options that may
each carry their own action — including a ``changedialog`` action to jump to
another dialogue file).
"""

from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tortoisengine.dialogue import (
    Action,
    Dialogue,
    DialogueLine,
    DialogueOption,
    load_action,
    load_dialogue,
    save_dialogue,
)
from tortoisestudio.localization_data import (
    all_keys,
    all_languages,
    apply_key_values,
    find_key,
    list_language_csv_paths,
)
from tortoisestudio.scene_assets import list_dialogue_paths

DIALOGUES_DIR = Path("dialogues")

ACTION_TYPES = [
    "(none)", "var_set", "do_action", "jumpdialog", "changedialog", "finishdialog",
    "var_compare_text", "var_compare_number",
]
COMPARE_OPS = ["<", "<=", "==", "!=", ">=", ">"]

# A line's text is either a literal string or exactly one [<[key]>] placeholder
# referencing languages/*.csv (see tortoisengine.localization) — never a mix.
_KEY_PATTERN = re.compile(r"^\[<\[([^\[\]]+)\]>\]$")


def _parse_literal(text: str) -> object:
    """Best-effort JSON-literal inference for a plain-text field (bool/int/float/str)."""
    stripped = text.strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return text


def _literal_to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _action_to_envelope(action: Action | None) -> dict:
    if action is None:
        return {"action": False}
    return {"action": True, "type": action.type, "action_content": action.content}


def _envelope_to_action(data: object) -> Action | None:
    if not isinstance(data, dict):
        return None
    return load_action(data)


class ArgsEditor(QWidget):
    """Editable list of do_action call args: each a literal or a var lookup."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Kind", "Value"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(120)
        self.table.itemChanged.connect(lambda _item: self.changed.emit())

        btn_add = QPushButton("+ Arg")
        btn_add.clicked.connect(self._add_row)
        btn_remove = QPushButton("− Arg")
        btn_remove.clicked.connect(self._remove_selected)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(btn_row)

    def _add_row(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        combo = QComboBox()
        combo.addItems(["literal", "var"])
        combo.currentTextChanged.connect(lambda _t: self.changed.emit())
        self.table.setCellWidget(row, 0, combo)
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.changed.emit()

    def _remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        if rows:
            self.changed.emit()

    def set_args(self, args: list[dict]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for arg in args:
            row = self.table.rowCount()
            self.table.insertRow(row)
            kind = arg.get("type", "literal") if isinstance(arg, dict) else "literal"
            combo = QComboBox()
            combo.addItems(["literal", "var"])
            idx = combo.findText(kind)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.currentTextChanged.connect(lambda _t: self.changed.emit())
            self.table.setCellWidget(row, 0, combo)
            value = arg.get("value") if isinstance(arg, dict) else arg
            self.table.setItem(row, 1, QTableWidgetItem(_literal_to_text(value)))
        self.table.blockSignals(False)

    def get_args(self) -> list[dict]:
        args = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            kind = combo.currentText() if combo else "literal"
            item = self.table.item(row, 1)
            text = item.text() if item else ""
            value = text if kind == "var" else _parse_literal(text)
            args.append({"type": kind, "value": value})
        return args


class ActionEditorWidget(QWidget):
    """Editable action envelope: a type picker plus type-specific fields.

    Handles every documented action type (see tortoisengine.dialogue's module
    docstring). An action type outside that set round-trips unchanged so a
    hand-authored file never loses data just from being opened here.
    """

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._other_type: str | None = None
        self._other_content: dict = {}
        self._case_rows: list[dict] = []  # nested var_compare_text case envelopes
        self._dialogue_choices: list[str] = []

        self.combo_type = QComboBox()
        self.combo_type.addItems(ACTION_TYPES)
        self.combo_type.currentTextChanged.connect(self._on_type_changed)

        self.stack = QStackedWidget()
        self._page_none = QLabel("No action.")
        self._page_none.setStyleSheet("color: #888;")
        self.stack.addWidget(self._page_none)

        page_var_set = QWidget()
        form_var_set = QFormLayout(page_var_set)
        self.field_var = QLineEdit()
        self.field_var.textChanged.connect(lambda _t: self.changed.emit())
        form_var_set.addRow("Variable:", self.field_var)
        self.field_value = QLineEdit()
        self.field_value.setPlaceholderText("text, true/false, or a number")
        self.field_value.textChanged.connect(lambda _t: self.changed.emit())
        form_var_set.addRow("Value:", self.field_value)
        self.stack.addWidget(page_var_set)

        page_do_action = QWidget()
        form_do_action = QFormLayout(page_do_action)
        self.field_function = QLineEdit()
        self.field_function.textChanged.connect(lambda _t: self.changed.emit())
        form_do_action.addRow("Function:", self.field_function)
        self.args_editor = ArgsEditor()
        self.args_editor.changed.connect(self.changed.emit)
        form_do_action.addRow("Args:", self.args_editor)
        self.stack.addWidget(page_do_action)

        page_jumpdialog = QWidget()
        form_jump = QFormLayout(page_jumpdialog)
        self.field_jump_id = QLineEdit()
        self.field_jump_id.setPlaceholderText("target line id in this dialogue")
        self.field_jump_id.textChanged.connect(lambda _t: self.changed.emit())
        form_jump.addRow("Line id:", self.field_jump_id)
        self.stack.addWidget(page_jumpdialog)

        page_changedialog = QWidget()
        form_changedialog = QFormLayout(page_changedialog)
        self.field_change_dialog_path = QComboBox()
        self.field_change_dialog_path.setEditable(True)
        self.field_change_dialog_path.currentTextChanged.connect(lambda _t: self.changed.emit())
        form_changedialog.addRow("Dialogue file:", self.field_change_dialog_path)
        self.stack.addWidget(page_changedialog)

        page_finish = QWidget()
        finish_layout = QVBoxLayout(page_finish)
        finish_label = QLabel("Ends the dialogue immediately.")
        finish_label.setStyleSheet("color: #888;")
        finish_layout.addWidget(finish_label)
        self.stack.addWidget(page_finish)

        page_compare = QWidget()
        compare_layout = QVBoxLayout(page_compare)
        compare_form = QFormLayout()
        self.field_compare_var = QLineEdit()
        self.field_compare_var.textChanged.connect(lambda _t: self.changed.emit())
        compare_form.addRow("Variable:", self.field_compare_var)
        compare_layout.addLayout(compare_form)
        self.cases_table = QTableWidget(0, 2)
        self.cases_table.setHorizontalHeaderLabels(["Case value", "Action"])
        self.cases_table.verticalHeader().setVisible(False)
        self.cases_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.cases_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.cases_table.itemChanged.connect(self._on_case_item_changed)
        self.cases_table.itemDoubleClicked.connect(self._on_case_double_clicked)
        compare_layout.addWidget(self.cases_table)
        case_btn_row = QHBoxLayout()
        btn_add_case = QPushButton("+ Case")
        btn_add_case.clicked.connect(self._add_case)
        btn_remove_case = QPushButton("− Case")
        btn_remove_case.clicked.connect(self._remove_selected_case)
        btn_edit_case = QPushButton("Edit case action…")
        btn_edit_case.clicked.connect(self._edit_selected_case_action)
        case_btn_row.addWidget(btn_add_case)
        case_btn_row.addWidget(btn_remove_case)
        case_btn_row.addWidget(btn_edit_case)
        case_btn_row.addStretch()
        compare_layout.addLayout(case_btn_row)
        self.stack.addWidget(page_compare)

        page_compare_number = QWidget()
        compare_number_layout = QVBoxLayout(page_compare_number)
        compare_number_form = QFormLayout()
        self.field_compare_number_var = QLineEdit()
        self.field_compare_number_var.textChanged.connect(lambda _t: self.changed.emit())
        compare_number_form.addRow("Variable:", self.field_compare_number_var)
        compare_number_layout.addLayout(compare_number_form)
        self.number_cases_table = QTableWidget(0, 3)
        self.number_cases_table.setHorizontalHeaderLabels(["Op", "Threshold", "Action"])
        self.number_cases_table.verticalHeader().setVisible(False)
        self.number_cases_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.number_cases_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.number_cases_table.itemChanged.connect(self._on_number_case_item_changed)
        self.number_cases_table.itemDoubleClicked.connect(self._on_number_case_double_clicked)
        compare_number_layout.addWidget(QLabel("Evaluated top to bottom — first matching case wins."))
        compare_number_layout.addWidget(self.number_cases_table)
        number_case_btn_row = QHBoxLayout()
        btn_add_number_case = QPushButton("+ Case")
        btn_add_number_case.clicked.connect(self._add_number_case)
        btn_remove_number_case = QPushButton("− Case")
        btn_remove_number_case.clicked.connect(self._remove_selected_number_case)
        btn_move_number_case_up = QPushButton("Move ↑")
        btn_move_number_case_up.clicked.connect(lambda: self._move_number_case(-1))
        btn_move_number_case_down = QPushButton("Move ↓")
        btn_move_number_case_down.clicked.connect(lambda: self._move_number_case(1))
        btn_edit_number_case = QPushButton("Edit case action…")
        btn_edit_number_case.clicked.connect(self._edit_selected_number_case_action)
        number_case_btn_row.addWidget(btn_add_number_case)
        number_case_btn_row.addWidget(btn_remove_number_case)
        number_case_btn_row.addWidget(btn_move_number_case_up)
        number_case_btn_row.addWidget(btn_move_number_case_down)
        number_case_btn_row.addWidget(btn_edit_number_case)
        number_case_btn_row.addStretch()
        compare_number_layout.addLayout(number_case_btn_row)

        self._default_envelope: dict = {"action": False}
        default_group = QGroupBox("Default (no case matches)")
        default_layout = QHBoxLayout(default_group)
        self.default_summary_label = QLabel(self._case_summary(self._default_envelope))
        btn_edit_default = QPushButton("Edit default action…")
        btn_edit_default.clicked.connect(self._edit_default_action)
        default_layout.addWidget(self.default_summary_label, stretch=1)
        default_layout.addWidget(btn_edit_default)
        compare_number_layout.addWidget(default_group)
        self.stack.addWidget(page_compare_number)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Action type:"))
        type_row.addWidget(self.combo_type, stretch=1)
        layout.addLayout(type_row)
        layout.addWidget(self.stack)

    def set_dialogue_choices(self, paths: list[str]) -> None:
        self._dialogue_choices = paths
        current = self.field_change_dialog_path.currentText()
        self.field_change_dialog_path.blockSignals(True)
        self.field_change_dialog_path.clear()
        self.field_change_dialog_path.addItems(paths)
        idx = self.field_change_dialog_path.findText(current)
        if idx >= 0:
            self.field_change_dialog_path.setCurrentIndex(idx)
        else:
            self.field_change_dialog_path.setEditText(current)
        self.field_change_dialog_path.blockSignals(False)

    def _on_type_changed(self, text: str) -> None:
        idx = ACTION_TYPES.index(text) if text in ACTION_TYPES else 0
        self.stack.setCurrentIndex(idx)
        self.changed.emit()

    def _case_summary(self, envelope: dict) -> str:
        action = _envelope_to_action(envelope)
        if action is None:
            return "(no action)"
        return f"{action.type}: {action.content}"

    def _add_case(self) -> None:
        row = self.cases_table.rowCount()
        self.cases_table.insertRow(row)
        self.cases_table.setItem(row, 0, QTableWidgetItem("value"))
        action_item = QTableWidgetItem(self._case_summary({"action": False}))
        action_item.setFlags(action_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        action_item.setData(Qt.ItemDataRole.UserRole, {"action": False})
        self.cases_table.setItem(row, 1, action_item)
        self.changed.emit()

    def _remove_selected_case(self) -> None:
        rows = sorted({idx.row() for idx in self.cases_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.cases_table.removeRow(row)
        if rows:
            self.changed.emit()

    def _on_case_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self.changed.emit()

    def _on_case_double_clicked(self, item: QTableWidgetItem) -> None:
        if item.column() == 1:
            self._edit_selected_case_action()

    def _edit_selected_case_action(self) -> None:
        row = self.cases_table.currentRow()
        if row < 0:
            return
        action_item = self.cases_table.item(row, 1)
        envelope = action_item.data(Qt.ItemDataRole.UserRole) or {"action": False}
        current = _envelope_to_action(envelope)
        dialog = ActionDialog(current, title="Edit Case Action", parent=self, dialogue_choices=self._dialogue_choices)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_action = dialog.result_action()
            new_envelope = _action_to_envelope(new_action)
            action_item.setData(Qt.ItemDataRole.UserRole, new_envelope)
            action_item.setText(self._case_summary(new_envelope))
            self.changed.emit()

    def _add_number_case(self) -> None:
        row = self.number_cases_table.rowCount()
        self.number_cases_table.insertRow(row)
        combo = QComboBox()
        combo.addItems(COMPARE_OPS)
        combo.currentTextChanged.connect(lambda _t: self.changed.emit())
        self.number_cases_table.setCellWidget(row, 0, combo)
        self.number_cases_table.setItem(row, 1, QTableWidgetItem("0"))
        action_item = QTableWidgetItem(self._case_summary({"action": False}))
        action_item.setFlags(action_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        action_item.setData(Qt.ItemDataRole.UserRole, {"action": False})
        self.number_cases_table.setItem(row, 2, action_item)
        self.changed.emit()

    def _remove_selected_number_case(self) -> None:
        rows = sorted({idx.row() for idx in self.number_cases_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.number_cases_table.removeRow(row)
        if rows:
            self.changed.emit()

    def _move_number_case(self, delta: int) -> None:
        row = self.number_cases_table.currentRow()
        target = row + delta
        if row < 0 or not (0 <= target < self.number_cases_table.rowCount()):
            return
        op_combo = self.number_cases_table.cellWidget(row, 0)
        threshold_item = self.number_cases_table.takeItem(row, 1)
        action_item = self.number_cases_table.takeItem(row, 2)
        op_text = op_combo.currentText() if op_combo else COMPARE_OPS[0]

        self.number_cases_table.removeRow(row)
        self.number_cases_table.insertRow(target)
        new_combo = QComboBox()
        new_combo.addItems(COMPARE_OPS)
        idx = new_combo.findText(op_text)
        new_combo.setCurrentIndex(idx if idx >= 0 else 0)
        new_combo.currentTextChanged.connect(lambda _t: self.changed.emit())
        self.number_cases_table.setCellWidget(target, 0, new_combo)
        self.number_cases_table.setItem(target, 1, threshold_item)
        self.number_cases_table.setItem(target, 2, action_item)
        self.number_cases_table.setCurrentCell(target, 1)
        self.changed.emit()

    def _on_number_case_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 1:
            self.changed.emit()

    def _on_number_case_double_clicked(self, item: QTableWidgetItem) -> None:
        if item.column() == 2:
            self._edit_selected_number_case_action()

    def _edit_selected_number_case_action(self) -> None:
        row = self.number_cases_table.currentRow()
        if row < 0:
            return
        action_item = self.number_cases_table.item(row, 2)
        envelope = action_item.data(Qt.ItemDataRole.UserRole) or {"action": False}
        current = _envelope_to_action(envelope)
        dialog = ActionDialog(current, title="Edit Case Action", parent=self, dialogue_choices=self._dialogue_choices)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_action = dialog.result_action()
            new_envelope = _action_to_envelope(new_action)
            action_item.setData(Qt.ItemDataRole.UserRole, new_envelope)
            action_item.setText(self._case_summary(new_envelope))
            self.changed.emit()

    def _edit_default_action(self) -> None:
        current = _envelope_to_action(self._default_envelope)
        dialog = ActionDialog(current, title="Edit Default Action", parent=self, dialogue_choices=self._dialogue_choices)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._default_envelope = _action_to_envelope(dialog.result_action())
            self.default_summary_label.setText(self._case_summary(self._default_envelope))
            self.changed.emit()

    def set_action(self, action: Action | None) -> None:
        self.blockSignals(True)
        self._other_type = None
        self._other_content = {}
        self.field_var.clear()
        self.field_value.clear()
        self.field_function.clear()
        self.args_editor.set_args([])
        self.field_jump_id.clear()
        self.field_change_dialog_path.setCurrentText("")
        self.field_compare_var.clear()
        self.cases_table.setRowCount(0)
        self.field_compare_number_var.clear()
        self.number_cases_table.setRowCount(0)
        self._default_envelope = {"action": False}
        self.default_summary_label.setText(self._case_summary(self._default_envelope))

        if action is None:
            self.combo_type.setCurrentText("(none)")
        elif action.type == "var_set":
            self.combo_type.setCurrentText("var_set")
            self.field_var.setText(str(action.content.get("var", "")))
            self.field_value.setText(_literal_to_text(action.content.get("value", "")))
        elif action.type == "do_action":
            self.combo_type.setCurrentText("do_action")
            self.field_function.setText(str(action.content.get("function", "")))
            self.args_editor.set_args(list(action.content.get("value", []) or []))
        elif action.type == "jumpdialog":
            self.combo_type.setCurrentText("jumpdialog")
            self.field_jump_id.setText(str(action.content.get("id", "")))
        elif action.type == "changedialog":
            self.combo_type.setCurrentText("changedialog")
            self.field_change_dialog_path.setCurrentText(str(action.content.get("path", "")))
        elif action.type == "finishdialog":
            self.combo_type.setCurrentText("finishdialog")
        elif action.type == "var_compare_text":
            self.combo_type.setCurrentText("var_compare_text")
            self.field_compare_var.setText(str(action.content.get("var", "")))
            values = action.content.get("values", {}) or {}
            for case_value, envelope in values.items():
                row = self.cases_table.rowCount()
                self.cases_table.insertRow(row)
                self.cases_table.setItem(row, 0, QTableWidgetItem(str(case_value)))
                action_item = QTableWidgetItem(self._case_summary(envelope))
                action_item.setFlags(action_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                action_item.setData(Qt.ItemDataRole.UserRole, envelope)
                self.cases_table.setItem(row, 1, action_item)
        elif action.type == "var_compare_number":
            self.combo_type.setCurrentText("var_compare_number")
            self.field_compare_number_var.setText(str(action.content.get("var", "")))
            for case in action.content.get("cases", []) or []:
                row = self.number_cases_table.rowCount()
                self.number_cases_table.insertRow(row)
                combo = QComboBox()
                combo.addItems(COMPARE_OPS)
                op = case.get("op", COMPARE_OPS[0])
                idx = combo.findText(op)
                combo.setCurrentIndex(idx if idx >= 0 else 0)
                combo.currentTextChanged.connect(lambda _t: self.changed.emit())
                self.number_cases_table.setCellWidget(row, 0, combo)
                self.number_cases_table.setItem(row, 1, QTableWidgetItem(_literal_to_text(case.get("threshold", 0))))
                envelope = case.get("action", {"action": False})
                action_item = QTableWidgetItem(self._case_summary(envelope))
                action_item.setFlags(action_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                action_item.setData(Qt.ItemDataRole.UserRole, envelope)
                self.number_cases_table.setItem(row, 2, action_item)
            self._default_envelope = action.content.get("default") or {"action": False}
            self.default_summary_label.setText(self._case_summary(self._default_envelope))
        else:
            self._other_type = action.type
            self._other_content = action.content
            if self.combo_type.findText(action.type) < 0:
                self.combo_type.addItem(action.type)
            self.combo_type.setCurrentText(action.type)
            idx = self.stack.count() - 1
            warn = QLabel(f"Unsupported action type '{action.type}' — kept as-is.")
            warn.setStyleSheet("color: #e8590c;")
            self.stack.addWidget(warn)
            self.stack.setCurrentIndex(self.stack.count() - 1)
        self.blockSignals(False)

    def get_action(self) -> Action | None:
        t = self.combo_type.currentText()
        if t == "(none)":
            return None
        if t == "var_set":
            return Action("var_set", {
                "var": self.field_var.text().strip(),
                "value": _parse_literal(self.field_value.text()),
            })
        if t == "do_action":
            return Action("do_action", {
                "function": self.field_function.text().strip(),
                "value": self.args_editor.get_args(),
            })
        if t == "jumpdialog":
            return Action("jumpdialog", {"id": self.field_jump_id.text().strip()})
        if t == "changedialog":
            return Action("changedialog", {"path": self.field_change_dialog_path.currentText().strip()})
        if t == "finishdialog":
            return Action("finishdialog", {})
        if t == "var_compare_text":
            values = {}
            for row in range(self.cases_table.rowCount()):
                key_item = self.cases_table.item(row, 0)
                action_item = self.cases_table.item(row, 1)
                key = key_item.text().strip() if key_item else ""
                if not key:
                    continue
                values[key] = action_item.data(Qt.ItemDataRole.UserRole) if action_item else {"action": False}
            return Action("var_compare_text", {
                "var": self.field_compare_var.text().strip(),
                "values": values,
            })
        if t == "var_compare_number":
            cases = []
            for row in range(self.number_cases_table.rowCount()):
                combo = self.number_cases_table.cellWidget(row, 0)
                threshold_item = self.number_cases_table.item(row, 1)
                action_item = self.number_cases_table.item(row, 2)
                cases.append({
                    "op": combo.currentText() if combo else COMPARE_OPS[0],
                    "threshold": _parse_literal(threshold_item.text() if threshold_item else "0"),
                    "action": action_item.data(Qt.ItemDataRole.UserRole) if action_item else {"action": False},
                })
            content = {
                "var": self.field_compare_number_var.text().strip(),
                "cases": cases,
                "default": self._default_envelope,
            }
            return Action("var_compare_number", content)
        return Action(t, self._other_content)


class ActionDialog(QDialog):
    """Modal wrapper around ActionEditorWidget, used for nested (case) actions."""

    def __init__(
        self,
        action: Action | None,
        title: str = "Edit Action",
        parent: QWidget | None = None,
        dialogue_choices: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.editor = ActionEditorWidget()
        self.editor.set_dialogue_choices(dialogue_choices or [])
        self.editor.set_action(action)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.editor)
        layout.addWidget(buttons)
        self.resize(420, 360)

    def result_action(self) -> Action | None:
        return self.editor.get_action()


class OptionsEditor(QWidget):
    """Editable list of a line's branching options (text and action — use a
    ``changedialog`` action to jump to another dialogue file when picked)."""

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dialogue_choices: list[str] = []

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Option text", "Action"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(lambda _item: self.changed.emit())
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)

        btn_add = QPushButton("+ Option")
        btn_add.clicked.connect(self._add_option)
        btn_remove = QPushButton("− Option")
        btn_remove.clicked.connect(self._remove_selected)
        btn_edit_action = QPushButton("Edit action…")
        btn_edit_action.clicked.connect(self._edit_selected_action)

        btn_row = QHBoxLayout()
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addWidget(btn_edit_action)
        btn_row.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(btn_row)

    def set_dialogue_choices(self, paths: list[str]) -> None:
        self._dialogue_choices = paths

    def _action_item(self, action: Action | None) -> QTableWidgetItem:
        summary = "(no action)" if action is None else f"{action.type}"
        item = QTableWidgetItem(summary)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setData(Qt.ItemDataRole.UserRole, action)
        return item

    def _add_option(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem("Option text"))
        self.table.setItem(row, 1, self._action_item(None))
        self.changed.emit()

    def _remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        if rows:
            self.changed.emit()

    def _on_item_double_clicked(self, item: QTableWidgetItem) -> None:
        if item.column() == 1:
            self._edit_selected_action()

    def _edit_selected_action(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        action_item = self.table.item(row, 1)
        current = action_item.data(Qt.ItemDataRole.UserRole) if action_item else None
        dialog = ActionDialog(current, title="Edit Option Action", parent=self, dialogue_choices=self._dialogue_choices)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_action = dialog.result_action()
            self.table.setItem(row, 1, self._action_item(new_action))
            self.changed.emit()

    def set_options(self, options: list[DialogueOption]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for option in options:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(option.text))
            self.table.setItem(row, 1, self._action_item(option.action))
        self.table.blockSignals(False)

    def get_options(self) -> list[DialogueOption]:
        options = []
        for row in range(self.table.rowCount()):
            text_item = self.table.item(row, 0)
            action_item = self.table.item(row, 1)
            options.append(DialogueOption(
                text=text_item.text() if text_item else "",
                action=action_item.data(Qt.ItemDataRole.UserRole) if action_item else None,
            ))
        return options


class DialogueLinePanel(QWidget):
    """Editor for a single DialogueLine: speaker/text/icon/id, action, options.

    A line's text is either a literal string or a [<[key]>] placeholder into
    languages/*.csv. The Text group exposes that as a small "Translation key"
    field plus a language picker and a big content box that reads/writes the
    selected (key, language) cell directly — editing the key switches which
    CSV row the content box is bound to; clearing it falls back to literal
    text, editing the content box directly.
    """

    changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False
        self.project_root = Path(".")
        self._current_key_path: Path | None = None
        self._key_target_cache: dict[str, Path] = {}
        self._last_applied_key = ""
        self._active_language = ""
        self._content_dirty = False

        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(500)
        self._flush_timer.timeout.connect(self.flush_pending_content)

        form = QFormLayout()
        self.field_speaker = QLineEdit()
        self.field_speaker.textChanged.connect(self._emit_changed)
        form.addRow("Speaker:", self.field_speaker)

        self.field_icon = QLineEdit()
        self.field_icon.setPlaceholderText("optional sprite path, e.g. assets/sprites/robot1_icon.tortusprite")
        self.field_icon.textChanged.connect(self._emit_changed)
        form.addRow("Icon:", self.field_icon)

        self.field_id = QLineEdit()
        self.field_id.setPlaceholderText("optional — lets jumpdialog target this line")
        self.field_id.textChanged.connect(self._emit_changed)
        form.addRow("Line id:", self.field_id)

        text_group = QGroupBox("Text")
        text_layout = QVBoxLayout(text_group)
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Translation key:"))
        self.field_text_key = QComboBox()
        self.field_text_key.setEditable(True)
        self.field_text_key.setMaximumWidth(220)
        self.field_text_key.lineEdit().setPlaceholderText("empty = literal text")
        # Resolve on commit (Enter/blur/pick), not on every keystroke — an
        # unrecognized key triggers a blocking "which CSV file?" prompt, which
        # must not interrupt the user mid-type.
        self.field_text_key.lineEdit().editingFinished.connect(self._commit_key_field)
        self.field_text_key.textActivated.connect(lambda _t: self._commit_key_field())
        key_row.addWidget(self.field_text_key)
        key_row.addStretch()
        key_row.addWidget(QLabel("Language:"))
        self.language_selector = QComboBox()
        self.language_selector.currentTextChanged.connect(self._on_language_changed)
        key_row.addWidget(self.language_selector)
        text_layout.addLayout(key_row)

        self.field_text_content = QPlainTextEdit()
        self.field_text_content.setMinimumHeight(90)
        self.field_text_content.setPlaceholderText(
            "Content — with a key set, this edits that key's CSV cell for the "
            "selected language; with no key, it's the line's literal text."
        )
        self.field_text_content.textChanged.connect(self._on_content_changed)
        text_layout.addWidget(self.field_text_content)

        action_group = QGroupBox("Line Action")
        action_layout = QVBoxLayout(action_group)
        self.action_editor = ActionEditorWidget()
        self.action_editor.changed.connect(self._emit_changed)
        action_layout.addWidget(self.action_editor)

        options_group = QGroupBox("Options (branching)")
        options_layout = QVBoxLayout(options_group)
        self.options_editor = OptionsEditor()
        self.options_editor.changed.connect(self._emit_changed)
        options_layout.addWidget(self.options_editor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(form)
        layout.addWidget(text_group)
        layout.addWidget(action_group)
        layout.addWidget(options_group, stretch=1)

    def set_project_root(self, project_root: Path) -> None:
        self.project_root = project_root
        self._key_target_cache = {}
        self.refresh_known_keys()

    def refresh_known_keys(self) -> None:
        current = self.field_text_key.currentText()
        self.field_text_key.blockSignals(True)
        self.field_text_key.clear()
        self.field_text_key.addItems(all_keys(self.project_root))
        self.field_text_key.setCurrentText(current)
        self.field_text_key.blockSignals(False)

    def set_dialogue_choices(self, paths: list[str]) -> None:
        self.action_editor.set_dialogue_choices(paths)
        self.options_editor.set_dialogue_choices(paths)

    def _emit_changed(self) -> None:
        if not self._loading:
            self.changed.emit()

    # -- translation key / language / content -------------------------------

    def _resolve_target_path(self, key: str) -> Path | None:
        if key in self._key_target_cache:
            return self._key_target_cache[key]
        loc = find_key(self.project_root, key)
        if loc is not None:
            self._key_target_cache[key] = loc.path
            return loc.path
        choices = [
            p.relative_to(self.project_root).as_posix()
            for p in list_language_csv_paths(self.project_root)
        ]
        choices.append("<new file…>")
        choice, ok = QInputDialog.getItem(
            self,
            "New Translation Key",
            f"Key '{key}' isn't in any languages/*.csv yet. Create it in:",
            choices,
            0,
            False,
        )
        if not ok:
            return None
        if choice == "<new file…>":
            name, ok2 = QInputDialog.getText(self, "New Language CSV", "File name (without .csv):")
            if not ok2 or not name.strip():
                return None
            path = self.project_root / "languages" / f"{name.strip()}.csv"
        else:
            path = self.project_root / choice
        self._key_target_cache[key] = path
        return path

    def _apply_key(self, key: str) -> None:
        # Any pending edit belongs to whichever (key, language) was active
        # before this call — must flush before _current_key_path etc. move on.
        self.flush_pending_content()
        if not key:
            self._current_key_path = None
            self._active_language = ""
            self.language_selector.setEnabled(False)
            self._loading = True
            self.language_selector.clear()
            self._loading = False
            return
        path = self._resolve_target_path(key)
        self._current_key_path = path
        loc = find_key(self.project_root, key)
        languages = loc.languages if loc else (all_languages(self.project_root) or ["en"])
        self._populate_language_selector(languages)
        self.language_selector.setEnabled(path is not None)
        self._refresh_content_for_current_language()

    def _populate_language_selector(self, languages: list[str]) -> None:
        self._loading = True
        current = self.language_selector.currentText()
        self.language_selector.clear()
        self.language_selector.addItems(languages)
        idx = self.language_selector.findText(current)
        self.language_selector.setCurrentIndex(idx if idx >= 0 else 0)
        self._loading = False

    def _refresh_content_for_current_language(self) -> None:
        key = self.field_text_key.currentText().strip()
        lang = self.language_selector.currentText()
        value = ""
        if key and lang:
            loc = find_key(self.project_root, key)
            if loc is not None:
                value = loc.values.get(lang, "")
        self._loading = True
        self.field_text_content.setPlainText(value)
        self._loading = False
        self._active_language = lang
        self._content_dirty = False

    def _commit_key_field(self) -> None:
        if self._loading:
            return
        key = self.field_text_key.currentText().strip()
        if key == self._last_applied_key:
            return
        self.flush_pending_content()  # commit the outgoing key's edit first
        self._last_applied_key = key
        self._apply_key(key)
        self._emit_changed()

    def _on_language_changed(self, _text: str) -> None:
        if self._loading:
            return
        self.flush_pending_content()  # commit the outgoing language's edit first
        self._refresh_content_for_current_language()

    def _on_content_changed(self) -> None:
        if self._loading:
            return
        key = self.field_text_key.currentText().strip()
        if key:
            self._content_dirty = True
            self._flush_timer.start()
        else:
            self._emit_changed()

    def flush_pending_content(self) -> None:
        self._flush_timer.stop()
        if not self._content_dirty:
            return
        key = self._last_applied_key
        lang = self._active_language
        if not key or not lang or self._current_key_path is None:
            self._content_dirty = False
            return
        value = self.field_text_content.toPlainText()
        apply_key_values(self._current_key_path, {(key, lang): value})
        self._content_dirty = False

    # -- line load / save -----------------------------------------------------

    def set_line(self, line: DialogueLine) -> None:
        self.flush_pending_content()
        self._loading = True
        self.field_speaker.setText(line.speaker)
        self.field_icon.setText(line.icon)
        self.field_id.setText(line.id)
        match = _KEY_PATTERN.match(line.text.strip())
        key = match.group(1) if match else ""
        self.field_text_key.setCurrentText(key)
        self._last_applied_key = key
        if not key:
            self.field_text_content.setPlainText(line.text)
            self.language_selector.setEnabled(False)
        self.action_editor.set_action(line.action)
        self.options_editor.set_options(line.options)
        self._loading = False
        if key:
            self._apply_key(key)

    def get_line(self) -> DialogueLine:
        key = self.field_text_key.currentText().strip()
        text = f"[<[{key}]>]" if key else self.field_text_content.toPlainText()
        return DialogueLine(
            speaker=self.field_speaker.text(),
            text=text,
            icon=self.field_icon.text().strip(),
            id=self.field_id.text().strip(),
            options=self.options_editor.get_options(),
            action=self.action_editor.get_action(),
        )

    def set_enabled_state(self, enabled: bool) -> None:
        self.setEnabled(enabled)


def _line_summary(line: DialogueLine, index: int) -> str:
    speaker = line.speaker or "(no speaker)"
    text = (line.text[:40] + "…") if len(line.text) > 40 else line.text
    tag = f" [{line.id}]" if line.id else ""
    branch = f"  ⤷ {len(line.options)} option(s)" if line.options else ""
    return f"{index + 1}. {speaker}{tag}: {text}{branch}"


class DialogueEditorWidget(QWidget):
    """File list of dialogues/*.json on the left, a line-by-line editor on the right."""

    saved = pyqtSignal(Path)

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self._dialogue: Dialogue | None = None
        self._current_path: Path | None = None
        self._current_line_index: int | None = None
        self._dirty = False
        self._loading = False

        self.file_list = QListWidget()
        self.file_list.setMaximumWidth(220)
        self.file_list.currentItemChanged.connect(self._on_file_selected)

        self.btn_new_file = QPushButton("New Dialogue…")
        self.btn_new_file.clicked.connect(self._new_file)
        self.btn_delete_file = QPushButton("Delete Dialogue")
        self.btn_delete_file.clicked.connect(self._delete_file)

        file_btn_row = QHBoxLayout()
        file_btn_row.addWidget(self.btn_new_file)
        file_btn_row.addWidget(self.btn_delete_file)

        file_col = QVBoxLayout()
        file_col.addWidget(QLabel("dialogues/*.json"))
        file_col.addWidget(self.file_list, stretch=1)
        file_col.addLayout(file_btn_row)

        self.lines_list = QListWidget()
        self.lines_list.setMaximumHeight(160)
        self.lines_list.currentRowChanged.connect(self._on_line_selected)

        self.btn_add_line = QPushButton("+ Line")
        self.btn_add_line.clicked.connect(self._add_line)
        self.btn_remove_line = QPushButton("− Line")
        self.btn_remove_line.clicked.connect(self._remove_line)
        self.btn_move_up = QPushButton("Move ↑")
        self.btn_move_up.clicked.connect(lambda: self._move_line(-1))
        self.btn_move_down = QPushButton("Move ↓")
        self.btn_move_down.clicked.connect(lambda: self._move_line(1))

        lines_btn_row = QHBoxLayout()
        lines_btn_row.addWidget(self.btn_add_line)
        lines_btn_row.addWidget(self.btn_remove_line)
        lines_btn_row.addWidget(self.btn_move_up)
        lines_btn_row.addWidget(self.btn_move_down)
        lines_btn_row.addStretch()

        self.line_panel = DialogueLinePanel()
        self.line_panel.changed.connect(self._on_line_panel_changed)

        self.line_panel_scroll = QScrollArea()
        self.line_panel_scroll.setWidgetResizable(True)
        self.line_panel_scroll.setWidget(self.line_panel)

        self.btn_save = QPushButton("Save Dialogue")
        self.btn_save.clicked.connect(self.save)

        self.status_label = QLabel("No project open")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")

        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("Lines:"))
        right_col.addWidget(self.lines_list)
        right_col.addLayout(lines_btn_row)
        right_col.addWidget(self.line_panel_scroll, stretch=1)
        right_col.addWidget(self.btn_save)
        right_col.addWidget(self.status_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(file_col)
        layout.addLayout(right_col, stretch=1)

        self._set_dialogue_enabled(False)

    # -- project / file list -------------------------------------------------

    def set_project_root(self, project_root: Path) -> None:
        self.project_root = project_root
        self._current_path = None
        self._dialogue = None
        self._dirty = False
        self.line_panel.set_project_root(project_root)
        self.refresh()

    def flush_pending_translation_edits(self) -> None:
        """Commit any in-flight [<[key]>] content edit to its CSV immediately.

        Call before navigating away from this tab entirely — line/file
        switches inside this widget already flush at their own choke points,
        but leaving via the main workspace tab bar bypasses those.
        """
        self.line_panel.flush_pending_content()

    def refresh(self) -> None:
        dialogues_dir = self.project_root / DIALOGUES_DIR
        files = sorted(dialogues_dir.glob("*.json")) if dialogues_dir.is_dir() else []

        previous = self._current_path
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for f in files:
            item = QListWidgetItem(f.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            item.setToolTip(f.relative_to(self.project_root).as_posix())
            self.file_list.addItem(item)
        self.file_list.blockSignals(False)

        choices = list_dialogue_paths(self.project_root)
        self.line_panel.set_dialogue_choices(choices)
        self.line_panel.refresh_known_keys()

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
            self._dialogue = None
            self.lines_list.clear()
            self._set_dialogue_enabled(False)
            if self.file_list.count():
                self.file_list.setCurrentRow(0)

        count = len(files)
        self.status_label.setText(
            f"{count} file{'s' if count != 1 else ''} in {DIALOGUES_DIR.as_posix()}"
        )

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def _set_dialogue_enabled(self, enabled: bool) -> None:
        for w in (self.lines_list, self.btn_add_line, self.btn_remove_line,
                  self.btn_move_up, self.btn_move_down, self.line_panel, self.btn_save):
            w.setEnabled(enabled)

    # -- loading / selecting a file -------------------------------------------

    def _on_file_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is previous:
            return
        self.line_panel.flush_pending_content()
        if self._dirty and previous is not None:
            reply = QMessageBox.question(
                self,
                "Unsaved Dialogue",
                "Save changes to the current dialogue before switching?",
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
            self._dialogue = None
            self.lines_list.clear()
            self._set_dialogue_enabled(False)
            return
        path = Path(current.data(Qt.ItemDataRole.UserRole))
        self._load_dialogue(path)

    def _load_dialogue(self, path: Path) -> None:
        self._dialogue = load_dialogue(path)
        self._current_path = path
        self._current_line_index = None
        self._rebuild_lines_list()
        self._dirty = False
        self._set_dialogue_enabled(True)
        if self._dialogue.lines:
            self.lines_list.setCurrentRow(0)
        else:
            self.line_panel.set_line(DialogueLine())

    def _rebuild_lines_list(self) -> None:
        self._loading = True
        self.lines_list.blockSignals(True)
        current_row = self.lines_list.currentRow()
        self.lines_list.clear()
        for i, line in enumerate(self._dialogue.lines):
            self.lines_list.addItem(_line_summary(line, i))
        self.lines_list.blockSignals(False)
        self._loading = False
        if 0 <= current_row < self.lines_list.count():
            self.lines_list.setCurrentRow(current_row)

    # -- line selection / editing --------------------------------------------

    def _on_line_selected(self, row: int) -> None:
        if self._loading or self._dialogue is None:
            return
        self._current_line_index = row if 0 <= row < len(self._dialogue.lines) else None
        if self._current_line_index is None:
            return
        self.line_panel.set_line(self._dialogue.lines[self._current_line_index])

    def _on_line_panel_changed(self) -> None:
        if self._dialogue is None or self._current_line_index is None:
            return
        self._dialogue.lines[self._current_line_index] = self.line_panel.get_line()
        self._dirty = True
        self._loading = True
        self.lines_list.item(self._current_line_index).setText(
            _line_summary(self._dialogue.lines[self._current_line_index], self._current_line_index)
        )
        self._loading = False

    def _add_line(self) -> None:
        if self._dialogue is None:
            return
        insert_at = self._current_line_index + 1 if self._current_line_index is not None else len(self._dialogue.lines)
        self._dialogue.lines.insert(insert_at, DialogueLine(speaker="", text=""))
        self._dirty = True
        self._rebuild_lines_list()
        self.lines_list.setCurrentRow(insert_at)

    def _remove_line(self) -> None:
        if self._dialogue is None or self._current_line_index is None:
            return
        row = self._current_line_index
        del self._dialogue.lines[row]
        self._dirty = True
        self._current_line_index = None
        self._rebuild_lines_list()
        if self._dialogue.lines:
            self.lines_list.setCurrentRow(min(row, len(self._dialogue.lines) - 1))
        else:
            self.line_panel.set_line(DialogueLine())

    def _move_line(self, delta: int) -> None:
        if self._dialogue is None or self._current_line_index is None:
            return
        row = self._current_line_index
        target = row + delta
        if not (0 <= target < len(self._dialogue.lines)):
            return
        self._dialogue.lines[row], self._dialogue.lines[target] = (
            self._dialogue.lines[target], self._dialogue.lines[row]
        )
        self._dirty = True
        self._rebuild_lines_list()
        self.lines_list.setCurrentRow(target)

    # -- file management --------------------------------------------------

    def _new_file(self) -> None:
        if not (self.project_root / "tortu.project").is_file():
            QMessageBox.warning(self, "New Dialogue", "Open a project first.")
            return
        name, ok = QInputDialog.getText(self, "New Dialogue", "File name (without .json):")
        name = name.strip()
        if not ok or not name:
            return
        dialogues_dir = self.project_root / DIALOGUES_DIR
        dialogues_dir.mkdir(parents=True, exist_ok=True)
        dest = dialogues_dir / f"{name}.json"
        if dest.exists():
            QMessageBox.warning(self, "New Dialogue", f"{dest.name} already exists.")
            return
        save_dialogue(Dialogue(lines=[]), dest)
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
            "Delete Dialogue",
            f"Delete {path.name} from the project? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Delete Dialogue", f"Could not delete {path.name}: {exc}")
            return
        self._current_path = None
        self._dialogue = None
        self._dirty = False
        self.refresh()

    # -- save ---------------------------------------------------------------

    def save(self) -> None:
        if self._current_path is None or self._dialogue is None:
            return
        self.line_panel.flush_pending_content()
        if self._current_line_index is not None:
            self._dialogue.lines[self._current_line_index] = self.line_panel.get_line()
        save_dialogue(self._dialogue, self._current_path)
        self._dirty = False
        self.saved.emit(self._current_path)
        self.status_label.setText(f"Saved {self._current_path.relative_to(self.project_root).as_posix()}")
