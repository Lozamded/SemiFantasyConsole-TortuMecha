"""Run a .tortucart / project folder: python -m tortuplayer <path>"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Force nearest-neighbour pixel scaling on all SDL2 backends (including ARM GLES).
# Must be set before any pygame.init() call.
os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "0")

from tortuengine.cart import load_cart_manifest, load_game_module, resolve_cart_root
from tortuengine.project import load_project
from tortuplayer.player import WindowPlayer
from tortuplayer.scene_player import CartScenePlayer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Tortu cart on PC or device.")
    parser.add_argument(
        "path",
        type=Path,
        help="Path to project folder, .tortucart folder, or tortu.project file",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=3,
        help="Window scale factor (default: 3)",
    )
    args = parser.parse_args(argv)

    path = args.path.resolve()
    cart_root = resolve_cart_root(path)
    if cart_root is not None:
        try:
            manifest = load_cart_manifest(cart_root)
        except (OSError, ValueError, KeyError) as exc:
            print(f"error: invalid cart: {exc}", file=sys.stderr)
            return 1
        title = str(manifest.game.get("game_name", cart_root.name))
        fps = int(manifest.game.get("fps", 60))
        if manifest.start_scene:
            player = CartScenePlayer(
                cart_root,
                manifest,
                scale=args.scale,
                title=title,
                fps=fps,
            )
            try:
                player.run()
            except Exception as exc:
                print(f"runtime error: {exc}", file=sys.stderr)
                return 1
            return 0
        print("error: cart has no start_scene configured", file=sys.stderr)
        return 1

    project = None
    if path.is_file() and path.name == "tortu.project":
        project_root = path.parent
        project = load_project(path)
        entry = project.entry
    elif path.is_dir():
        project_root = path
        project_file = path / "tortu.project"
        if project_file.is_file():
            project = load_project(project_file)
            entry = project.entry
        else:
            entry = "main.py"
    else:
        print(f"error: not a project or cart folder: {path}", file=sys.stderr)
        return 1

    try:
        game = load_game_module(project_root, entry)
    except (FileNotFoundError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    title = project.game.game_name if project else project_root.name
    fps = project.game.fps if project else 60
    player = WindowPlayer(scale=args.scale, title=title, fps=fps)
    player.engine.load_game(game)

    try:
        player.run()
    except Exception as exc:
        print(f"runtime error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
