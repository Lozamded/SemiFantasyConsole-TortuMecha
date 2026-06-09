"""Load game scripts from a project directory or .tortucart folder."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_game_module(project_root: Path, entry: str = "main.py"):
    """Import the cart entry script from *project_root*."""
    entry_path = project_root / entry
    if not entry_path.is_file():
        raise FileNotFoundError(f"Cart entry not found: {entry_path}")

    project_root = project_root.resolve()
    root_str = str(project_root)

    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    module_name = f"tortu_cart_{abs(hash(root_str))}"
    spec = importlib.util.spec_from_file_location(module_name, entry_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load cart entry: {entry_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def reload_game_module(module):
    """Reload a previously loaded cart module (after external edits)."""
    import importlib

    return importlib.reload(module)
