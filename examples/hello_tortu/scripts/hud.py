"""Script for GUI layer hud — drives the energy pips and lives counter from player state.

power_bar (bar1) isn't wired up yet — reserved for a future shoot/attack meter.
"""

from tortuengine import instance_api

GUI_LAYER_PATH = "assets/gui/hud.tortuguilayer"
ENERGY_PIPS_ID = "pips1"
LIVES_LABEL_ID = "lives_label"


def init(engine):
    pass


def update(dt):
    energy = instance_api.player_energy()
    if energy is not None:
        current, maximum = energy
        instance_api.set_gui_repeat_sprite_number(GUI_LAYER_PATH, ENERGY_PIPS_ID, current, maximum)

    lives = instance_api.player_lives()
    if lives is not None:
        current, _maximum = lives
        instance_api.set_gui_text_label_text(GUI_LAYER_PATH, LIVES_LABEL_ID, f"x{current}")


def draw(engine):
    pass
