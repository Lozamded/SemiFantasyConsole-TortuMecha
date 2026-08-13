"""Shared read/write helpers for translations/*.csv, used by both the
Translations and Dialogues editor tabs.

Mirrors the load shape in tortoisengine/localization.py (header row of
language codes, one data row per key) but is editor-facing: it can locate a
single key's row across every CSV in the folder and write a cell back
in-place, rather than merging everything into one runtime lookup table.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

TRANSLATIONS_DIR = Path("translations")

# Row cap for an auto-managed per-dialogue CSV (see dialogue_translation_target)
# before a new key spills into the next "<stem>_partN.csv".
DIALOGUE_CSV_MAX_ROWS = 200


@dataclass
class KeyLocation:
    path: Path
    languages: list[str] = field(default_factory=list)
    values: dict[str, str] = field(default_factory=dict)  # lang -> value, this file only


def list_translation_csv_paths(project_root: Path) -> list[Path]:
    translations_dir = project_root / TRANSLATIONS_DIR
    if not translations_dir.is_dir():
        return []
    return sorted(translations_dir.glob("*.csv"))


def _read_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def find_key(project_root: Path, key: str) -> KeyLocation | None:
    """Return the first CSV whose key column has a row matching `key`."""
    for path in list_translation_csv_paths(project_root):
        rows = _read_rows(path)
        if not rows:
            continue
        languages = [code.strip() for code in rows[0][1:]]
        for row in rows[1:]:
            if row and row[0].strip() == key:
                values = {
                    lang: (row[i + 1].strip() if i + 1 < len(row) else "")
                    for i, lang in enumerate(languages)
                }
                return KeyLocation(path=path, languages=languages, values=values)
    return None


def all_languages(project_root: Path) -> list[str]:
    """Every language code seen across every CSV header, first-seen order."""
    seen: list[str] = []
    for path in list_translation_csv_paths(project_root):
        rows = _read_rows(path)
        if not rows:
            continue
        for code in rows[0][1:]:
            code = code.strip()
            if code and code not in seen:
                seen.append(code)
    return seen


def all_keys(project_root: Path) -> list[str]:
    """Every translation key across every CSV, sorted for a picker/autocomplete."""
    keys: set[str] = set()
    for path in list_translation_csv_paths(project_root):
        rows = _read_rows(path)
        for row in rows[1:]:
            if row and row[0].strip():
                keys.add(row[0].strip())
    return sorted(keys)


def dialogue_translation_target(project_root: Path, dialogue_stem: str) -> Path:
    """Where a brand-new key authored from dialogue `dialogue_stem` (a
    dialogues/*.json file's stem, e.g. "robot1_lvl1") should be written.

    Keys stay grouped by the dialogue file they came from — translations/
    <stem>.csv — so a translator sees one scene's lines together, instead of
    a meaningless numbered bucket. Once that file reaches
    DIALOGUE_CSV_MAX_ROWS keys, new ones spill into <stem>_part2.csv, then
    _part3.csv, and so on, so a single busy dialogue's CSV doesn't grow
    without bound. Called only when the key doesn't already exist anywhere
    (see find_key) — an existing key always keeps living wherever it is.
    """
    part = 1
    while True:
        name = f"{dialogue_stem}.csv" if part == 1 else f"{dialogue_stem}_part{part}.csv"
        path = project_root / TRANSLATIONS_DIR / name
        if not path.is_file():
            return path
        if len(_read_rows(path)) - 1 < DIALOGUE_CSV_MAX_ROWS:
            return path
        part += 1


def apply_key_values(csv_path: Path, edits: dict[tuple[str, str], str]) -> None:
    """Write `edits` ({(key, lang): value}) into csv_path, creating the CSV,
    the key's row, and/or the lang's column as needed."""
    if csv_path.is_file():
        rows = _read_rows(csv_path)
    else:
        rows = []
    if not rows:
        rows = [["key"]]
    header = rows[0]

    for lang in {lang for _key, lang in edits}:
        if lang not in header:
            header.append(lang)
            for row in rows[1:]:
                row.append("")

    by_key = {row[0].strip(): row for row in rows[1:] if row and row[0].strip()}
    for (key, lang), value in edits.items():
        lang_idx = header.index(lang)
        row = by_key.get(key)
        if row is None:
            row = [key] + [""] * (len(header) - 1)
            rows.append(row)
            by_key[key] = row
        while len(row) <= lang_idx:
            row.append("")
        row[lang_idx] = value

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
