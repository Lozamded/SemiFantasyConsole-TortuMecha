from tortuengine import instance_api

# level_01.tortuscene's placed id for the robot this dialogue belongs to —
# this module is already specific to robot2's dialogue (see dialog_r2_action
# below), not a generic multi-NPC vars module.
ROBOT2_ID = "robot2"

dialog_r2_action = "nothing"
dialog_r2_selected_action_= {
    "jump":"[<[var_d2_act1]>]",
    "nothing":"[<[var_d2_act2]>]"
}
Fav_Cookie = "nothing_yet"

def action_Do_DR2Action(selected_action):
    if selected_action == "jump":
        instance_api.request_object_hop(ROBOT2_ID)
    else:
        print("do nothing")


def d2_selected_action():
    """[var<[d2_selected_action]>] in dialogues/robot2_lv1.json's last line —
    a zero-arg variable resolved by tortuengine.localization.resolve() maps
    the raw dialog_r2_action flag to its own [<[key]>], so the displayed
    word is still translated per-language."""
    return dialog_r2_selected_action_[dialog_r2_action]