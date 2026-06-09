"""Launch TortuStudio: python -m tortustudio [project folder]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tortustudio.mainwindow import run_studio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TortuStudio — Semi-Fantasy Console editor")
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        help="Optional path to project folder or tortu.project",
    )
    args = parser.parse_args(argv)

    project_path = args.project.resolve() if args.project else None
    return run_studio(project_path)


if __name__ == "__main__":
    raise SystemExit(main())
