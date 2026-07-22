"""Runtime string localization.

A project may ship a single `languages/strings.csv` with a header row of
language codes (e.g. `key,en,es`) and one data row per translatable key.
Any GuiTextLabel's `text` field — or any string a script builds — may embed
a placeholder shaped `[<[key]>]`; `resolve()` substitutes it against the
currently active language. A missing CSV, key, or language cell just falls
back to leaving the raw key visible, so a bad reference never crashes the
game.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"\[<\[([^\[\]]+)\]>\]")

_table: dict[str, dict[str, str]] = {}
_languages: list[str] = []
_current: str = "en"
_loaded_root: Path | None = None


def load(project_root: Path) -> None:
    """(Re)load languages/strings.csv for project_root. No-op if already loaded for this root."""
    global _table, _languages, _loaded_root, _current
    if _loaded_root == project_root:
        return
    _loaded_root = project_root
    _table = {}
    _languages = []
    csv_path = project_root / "languages" / "strings.csv"
    if not csv_path.is_file():
        return
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return
    _languages = [code.strip() for code in rows[0][1:] if code.strip()]
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        key = row[0].strip()
        _table[key] = {
            lang: (row[i + 1].strip() if i + 1 < len(row) else "")
            for i, lang in enumerate(_languages)
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
    """Substitute every `[<[key]>]` placeholder in text; plain text passes through untouched."""
    if "[<[" not in text:
        return text
    return _PLACEHOLDER_RE.sub(lambda m: translate(m.group(1)), text)
