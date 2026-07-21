"""Script for GUI layer gameover_hud — shows the final gear count."""

from tortuengine import instance_api
from scripts import game_state

GUI_LAYER_PATH = "assets/gui/gameover_hud.tortuguilayer"
GEARS_LABEL_ID = "gears_label"


def init(engine):
    pass


def update(dt):
    instance_api.set_gui_text_label_text(
        GUI_LAYER_PATH, GEARS_LABEL_ID, f"GEARS: x{game_state.gears}"
    )


def draw(engine):
    pass
