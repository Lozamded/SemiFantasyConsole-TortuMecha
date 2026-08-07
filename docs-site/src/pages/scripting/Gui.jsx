import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function ScriptingGui() {
  return (
    <>

    <h1>GUI layer scripts</h1>
    <p className="subtitle">HUDs, menus, and dialogue boxes are .tortuguilayer assets with their own script — same hooks, different SELF_ID.</p>

    <p>A <code>.tortuguilayer</code> asset has a <code>script</code> field, run under the exact same isolated
    module-per-instance loader as object scripts (see
    <Link to="/scripting/objects">Object scripts</Link>): <code>init(engine)</code> /
    <code>update(dt)</code> / <code>draw(engine)</code>, with <code>draw</code> equally unused — the renderer
    draws every GUI element from its own state, never by calling the script.</p>

    <div className="callout">
      <strong>SELF_ID here is the layer's asset path, not a scene id</strong>
      For an object script, <code>SELF_ID</code> is a placed instance's scene id. For a GUI layer script,
      <code>SELF_ID</code> is the GUI layer's own asset path (e.g.
      <code>"assets/gui/hud.tortuguilayer"</code>) — because a GUI layer isn't "placed" with an id the way a
      scene object is. <code>LINKS</code> is always empty for GUI layer scripts.
    </div>

    <h2>The elements a GUI layer script drives</h2>
    <p>A <code>.tortuguilayer</code> canvas holds up to four kinds of placed element (defined in
    <code>tortoisengine/gui_layer.py</code>). Scripts never mutate a loaded <code>GuiLayer</code> object
    directly — the renderer owns loading/caching it — they go through the <code>set_gui_*</code> /
    <code>gui_*</code> functions in <code>instance_api</code>, addressing an element by the layer's asset path
    plus its <code>id</code>.</p>

    <table>
      <tr><th>Element</th><th>What it is</th><th>instance_api functions</th></tr>
      <tr>
        <td><code>GuiTextLabel</code></td>
        <td>A text string with position, alignment, optional word-wrap, and an ink color override.</td>
        <td><code>set_gui_text_label_text</code> / <code>gui_text_label_text</code><br />
            <code>set_gui_text_label_color</code> / <code>gui_text_label_color</code> (-1 = font's baked color; no-op on sprite-font labels)<br />
            <code>set_gui_text_label_scale</code> / <code>gui_text_label_scale</code><br />
            <code>set_gui_text_label_visible</code> / <code>gui_text_label_visible</code><br />
            <code>gui_text_label_position</code> (read-only — e.g. to place a cursor next to it)</td>
      </tr>
      <tr>
        <td><code>GuiTiledRect</code></td>
        <td>A progress-bar-style rect (backed by a reusable <code>.tortuprogressbar</code> texture) that fills to <code>number / max_number</code> — e.g. a health bar tracking current/max HP directly.</td>
        <td><code>set_gui_tiled_rect_number(path, id, number, max_number=None)</code><br />
            <code>gui_tiled_rect_number(path, id) -&gt; (number, max_number) | None</code></td>
      </tr>
      <tr>
        <td><code>GuiRepeatSprite</code></td>
        <td>A prefab drawn <code>number</code> times out of <code>max_number</code> slots (backed by a reusable <code>.tortupipbar</code>) — life pips, hearts, ammo counters.</td>
        <td><code>set_gui_repeat_sprite_number(path, id, number, max_number=None)</code><br />
            <code>gui_repeat_sprite_number(path, id) -&gt; (number, max_number) | None</code></td>
      </tr>
      <tr>
        <td><code>GuiObject</code></td>
        <td>A placed <code>.tortuobject</code> prefab instance inside the layer — e.g. a menu selection cursor icon.</td>
        <td><code>set_gui_object_position(path, id, x, y)</code> / <code>gui_object_position</code><br />
            <code>set_gui_object_visible(path, id, visible)</code> / <code>gui_object_visible</code></td>
      </tr>
    </table>

    <p>Two layer-wide (not per-element) controls round it out:</p>
    <table>
      <tr><th>Function</th><th>Behavior</th></tr>
      <tr><td><code>set_gui_layer_scroll(path, x, y=0)</code> / <code>gui_layer_scroll(path)</code></td><td>Pans the whole canvas — used to slide between two panels laid out side by side on one wide layer (e.g. a pause menu with a settings page next to the main page). Not persisted; resets to (0, 0) on reload.</td></tr>
      <tr><td><code>set_gui_layer_visible(path, visible)</code> / <code>is_gui_layer_visible(path)</code></td><td>Shows/hides an entire GUI layer <em>scene slot</em> by asset path — different from hiding one element.</td></tr>
    </table>

    <h2>A HUD script</h2>
    <p>The simplest pattern: read published player state each frame and push it into GUI elements.</p>
    <pre><code>from tortoisengine import instance_api

GUI_LAYER_PATH = "assets/gui/hud.tortuguilayer"

def update(dt):
    energy = instance_api.player_energy()
    if energy is not None:
        current, maximum = energy
        instance_api.set_gui_tiled_rect_number(GUI_LAYER_PATH, "energy_bar", current, maximum)

    lives = instance_api.player_lives()
    if lives is not None:
        current, maximum = lives
        instance_api.set_gui_repeat_sprite_number(GUI_LAYER_PATH, "lives_pips", current, maximum)

def draw(engine):
    pass</code></pre>

    <h2>Menus: the hand-rolled edge-detection idiom</h2>
    <p>There's no built-in "menu cursor" helper — every menu script (pause menu, title screen, save/load
    slot pickers) repeats the same idiom: track the previous frame's key state to detect a fresh press, move a
    highlighted item, and reposition a cursor object relative to the highlighted label's own position.</p>

    <pre><code>import pygame
from tortoisengine import instance_api

GUI_LAYER_PATH = "assets/gui/pause_menu.tortuguilayer"
HIGHLIGHT_COLOR = 4
NORMAL_COLOR = -1

_option_index = 0
_options = ["resume", "options", "quit"]
_prev_down = False
_prev_up = False

def update(dt):
    global _option_index, _prev_down, _prev_up
    keys = pygame.key.get_pressed()

    down_pressed = keys[pygame.K_DOWN] and not _prev_down
    up_pressed = keys[pygame.K_UP] and not _prev_up
    _prev_down, _prev_up = keys[pygame.K_DOWN], keys[pygame.K_UP]

    if down_pressed:
        _option_index = (_option_index + 1) % len(_options)
    elif up_pressed:
        _option_index = (_option_index - 1) % len(_options)

    for i, name in enumerate(_options):
        color = HIGHLIGHT_COLOR if i == _option_index else NORMAL_COLOR
        instance_api.set_gui_text_label_color(GUI_LAYER_PATH, name, color)

    pos = instance_api.gui_text_label_position(GUI_LAYER_PATH, _options[_option_index])
    if pos is not None:
        x, y = pos
        instance_api.set_gui_object_position(GUI_LAYER_PATH, "cursor", x - 12, y)</code></pre>

    <p>Note that scripts never see raw <code>pygame.KEYDOWN</code> events — event pumping happens once in the
    host loop (<code>WindowPlayer</code>/<code>CartScenePlayer</code>), not per script — so this
    read-and-compare-to-last-frame pattern is how every menu, dialogue box, and pause screen debounces input.
    See <Link to="/scripting/subsystems">Subsystems</Link> for the exact key constants used across the
    codebase.</p>

      <PageNav />
    </>
  )
}
