"""Runtime string localization.

A project may ship any number of CSVs under `translations/` (e.g. `GUI.csv`,
`DialogsLvl1.csv`), each with a header row of language codes (e.g.
`key,en,es`) and one data row per translatable key. All CSVs in the folder
are merged into a single key table, so keys can be split across files
however makes sense (by screen, by level, ...) without callers needing to
know which file a key lives in.

Any GuiTextLabel's `text` field, a dialogue line's `text`, or any string a
script builds — may embed a placeholder shaped `[<[key]>]`; `resolve()`
substitutes it against the currently active language. A missing CSV, key,
or language cell just falls back to leaving the raw key visible, so a bad
reference never crashes the game.

A CSV cell that needs a literal comma in it (a real comma is a column
delimiter to `csv.reader`, so an unquoted one would split the row) can use
`[symbol<[comma]>]` instead — `resolve()` expands it back to "," after key
substitution, so translators can write plain unquoted cells instead of
juggling CSV quoting rules.

A cell can also embed live game state via `[var<[name]>]`. `name` is looked
up through whatever resolver a script registered with `bind_variables()`
(e.g. dialoguebox.py points it at scripts/dialogue_vars.py's attributes) —
a plain attribute is stringified as-is, while a zero-argument function is
called for its return value, so a variable's *display* text can depend on
another variable (e.g. mapping a raw "jump"/"nothing" flag to its own
`[<[key]>]` for translation) without the caller needing to know that.
`resolve()` loops key/var/symbol substitution to a fixed point so a variable
that expands to a `[<[key]>]` placeholder still gets translated.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Callable

_PLACEHOLDER_RE = re.compile(r"\[<\[([^\[\]]+)\]>\]")
_VAR_RE = re.compile(r"\[var<\[([^\[\]]+)\]>\]")
_SYMBOL_RE = re.compile(r"\[symbol<\[([^\[\]]+)\]>\]")
_SYMBOLS = {"comma": ","}

# Renderer-owned lookup for `[var<[name]>]` (see bind_variables), left unset
# in contexts with no dialogue vars module (e.g. plain GUI-only screens).
_variable_resolver: Callable[[str], object] | None = None


def bind_variables(resolver: Callable[[str], object] | None) -> None:
    """Register the callable `[var<[name]>]` looks `name` up through."""
    global _variable_resolver
    _variable_resolver = resolver


def _resolve_var(name: str) -> str:
    if _variable_resolver is None:
        return f"[var<[{name}]>]"
    value = _variable_resolver(name)
    if callable(value):
        value = value()
    if value is None:
        return f"[var<[{name}]>]"
    return str(value)

_table: dict[str, dict[str, str]] = {}
_languages: list[str] = []
_current: str = "en"
_loaded_root: Path | None = None


def load(project_root: Path) -> None:
    """(Re)load every translations/*.csv for project_root. No-op if already loaded for this root."""
    global _table, _languages, _loaded_root, _current
    if _loaded_root == project_root:
        return
    _loaded_root = project_root
    _table = {}
    _languages = []
    translations_dir = project_root / "translations"
    if not translations_dir.is_dir():
        return
    for csv_path in sorted(translations_dir.glob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        if not rows:
            continue
        file_languages = [code.strip() for code in rows[0][1:] if code.strip()]
        for lang in file_languages:
            if lang not in _languages:
                _languages.append(lang)
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue
            key = row[0].strip()
            _table[key] = {
                lang: (row[i + 1].strip() if i + 1 < len(row) else "")
                for i, lang in enumerate(file_languages)
            }
    if _current not in _languages and _languages:
        _current = _languages[0]


def available_languages() -> list[str]:
    return list(_languages)


def set_language(code: str) -> None:
    global _current
    if code in _languages:
        _current = code


def get_language() -> str:
    return _current


def translate(key: str) -> str:
    entry = _table.get(key)
    if entry is None:
        return key
    return entry.get(_current, key)


def resolve(text: str) -> str:
    """Substitute every `[<[key]>]`, `[var<[name]>]`, and `[symbol<[name]>]`
    placeholder in text.

    Runs to a fixed point (bounded) since a placeholder can expand into
    another one — a `[var<[...]>]` lookup commonly returns a `[<[key]>]` for
    translation. Plain text with no placeholders passes through untouched.
    """
    for _ in range(5):
        next_text = text
        if "[<[" in next_text:
            next_text = _PLACEHOLDER_RE.sub(lambda m: translate(m.group(1)), next_text)
        if "[var<[" in next_text:
            next_text = _VAR_RE.sub(lambda m: _resolve_var(m.group(1)), next_text)
        if "[symbol<[" in next_text:
            next_text = _SYMBOL_RE.sub(lambda m: _SYMBOLS.get(m.group(1), m.group(0)), next_text)
        if next_text == text:
            return next_text
        text = next_text
    return text
