import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function ScriptingSubsystems() {
  return (
    <>

    <h1>Subsystems</h1>
    <p className="subtitle">Input, audio, dialogue, save data, checkpoints, and camera — how scripts handle each, and what the engine does (and doesn't) provide.</p>

    <h2>Input</h2>
    <p>There is no engine input wrapper. Every script reads pygame directly:</p>
    <pre><code>import pygame

keys = pygame.key.get_pressed()
if keys[pygame.K_LEFT]:
    ...</code></pre>
    <p>Common keys across the codebase: <code>K_UP/K_DOWN/K_LEFT/K_RIGHT</code> and <code>K_w/K_a/K_s/K_d</code>
    (movement), <code>K_z/K_SPACE/K_UP/K_w</code> (jump), <code>K_x/K_LSHIFT/K_c</code> (action/attack),
    <code>K_RETURN</code> (confirm/pause). <code>K_ESCAPE</code> is handled only by the host player loop, not
    scripts.</p>
    <p>Since scripts never see <code>KEYDOWN</code> events (the host loop pumps events once, not per script),
    detecting a fresh press means comparing against the previous frame's state yourself — see the menu example
    on the <Link to="/scripting/gui">GUI layer scripts</Link> page.</p>
    <div className="callout">
      <strong>No gamepad/joystick support yet</strong>
      Nothing in the codebase reads <code>pygame.joystick</code> — input is keyboard-only for now, despite the
      SBC/controller-friendly target hardware.
    </div>

    <h2>Audio: channels and volume</h2>
    <p><code>tortoisengine.audio</code> is a thin wrapper directly on <code>pygame.mixer</code>, adding named
    channels with independently persisted volumes.</p>
    <table>
      <tr><th>Function</th><th>Behavior</th></tr>
      <tr><td><code>load_sound(root, rel_path, channel)</code></td><td>Loads (and caches) a <code>pygame.mixer.Sound</code>, registered to a channel.</td></tr>
      <tr><td><code>get_channel_volume(channel)</code> / <code>set_channel_volume(channel, volume)</code></td><td>Clamped 0..1; setting it live-reapplies to every already-loaded sound on that channel.</td></tr>
      <tr><td><code>load_settings(project_root)</code> / <code>save_settings(project_root)</code></td><td>Persists channel volumes to <code>audio_settings.json</code> at the project root.</td></tr>
    </table>
    <div className="callout">
      <strong>Music volume is on you</strong>
      There's no engine method for <code>pygame.mixer.music</code> — no channel controls background music.
      After loading/starting a track (and whenever a volume slider changes), call
      <code>pygame.mixer.music.set_volume(...)</code> yourself.
    </div>
    <p>Channel names come from the generated <code>scripts/_generated/audio_auto.py</code> sidecar (see
    <Link to="/scripting/objects">Object scripts</Link>): <code>CHANNEL_MUSIC</code>,
    <code>CHANNEL_GAME_SFX</code>, <code>CHANNEL_UI_SFX</code>, and an <code>AUDIO_CHANNELS</code> dict mapping
    each sound's project-relative path to its assigned channel. A typical project wraps this in its own small
    convention module (hello_tortu's <code>audio_settings.py</code>):</p>
    <pre><code>from scripts._generated import audio_auto as auto
from tortoisengine import audio

def set_sfx_volume(value):
    audio.set_channel_volume(auto.CHANNEL_GAME_SFX, value)
    audio.set_channel_volume(auto.CHANNEL_UI_SFX, value)

def apply_music_volume():
    import pygame
    pygame.mixer.music.set_volume(MUSIC_BASE_LEVEL * music_volume())</code></pre>

    <h2>Dialogue</h2>
    <p><code>tortoisengine.dialogue</code> is a pure data model — <code>load_dialogue(path) -&gt; Dialogue</code>
    reads a <code>dialogues/*.json</code> file into <code>Dialogue</code> (a list of <code>DialogueLine</code>:
    <code>speaker, text, icon, id, options, action</code>), where each <code>DialogueOption</code> can carry its
    own <code>next_dialogue</code> and <code>action</code>. It does not display anything — that's a GUI layer
    script's job (typically the project's <code>dialoguebox.py</code>), driven by the request/consume pair from
    <Link to="/scripting/objects">Object scripts</Link>:</p>
    <pre><code># from any object script, e.g. an NPC on the action button:
instance_api.request_dialogue("dialogues/robot_intro.json")

# in the dialogue box's own GUI layer script, every frame it isn't already showing one:
path = instance_api.take_dialogue_request()
if path:
    dialogue = dialogue_module.load_dialogue(ROOT / path)
    instance_api.set_dialogue_active(True)</code></pre>
    <p>Dialogue <code>Action</code> envelopes (<code>type</code> + <code>content</code>) are interpreted by the
    dialogue box script itself, not the engine — the conventions used are <code>set_var</code>,
    <code>do_action</code>, <code>jumpdialog</code>, <code>finishdialog</code>, and
    <code>var_compare_text</code>. A project typically pairs its dialogue files with a small "vars" module
    (plain module-level attributes/functions) that dialogue actions read and call via
    <code>getattr</code>/<code>setattr</code>, exposed to <code>[var&lt;[name]&gt;]</code> placeholders in
    dialogue text through <code>tortoisengine.localization.bind_variables(resolver)</code>.</p>

    <h2>Localization</h2>
    <p>Prefer the re-exports on <code>instance_api</code> over importing <code>tortoisengine.localization</code>
    directly:</p>
    <table>
      <tr><th>Function</th><th>Behavior</th></tr>
      <tr><td><code>instance_api.available_languages()</code></td><td><code>-&gt; list[str]</code></td></tr>
      <tr><td><code>instance_api.get_language()</code> / <code>set_language(code)</code></td><td>Read/switch the active language.</td></tr>
      <tr><td><code>instance_api.translate(key)</code></td><td>Look up a <code>languages/strings.csv</code> key directly, for script-built strings.</td></tr>
    </table>
    <p><code>localization.bind_variables(resolver)</code> and <code>localization.resolve(text)</code> have no
    <code>instance_api</code> wrapper and must be imported from <code>tortoisengine.localization</code> directly
    — mainly relevant to a dialogue box script binding <code>[var&lt;[name]&gt;]</code> placeholders.</p>

    <h2>Save data</h2>
    <p><code>tortoisengine.save_data</code> is a generic, 1-indexed slot store — <code>slot&lt;N&gt;.json</code>
    files with a caller-defined JSON payload:</p>
    <table>
      <tr><th>Function</th><th>Behavior</th></tr>
      <tr><td><code>read_slot(saves_dir, index)</code></td><td><code>-&gt; dict | None</code></td></tr>
      <tr><td><code>read_slots(saves_dir, count)</code></td><td><code>-&gt; list[dict | None]</code></td></tr>
      <tr><td><code>write_slot(saves_dir, index, data)</code></td><td>Writes <code>data</code> (a dict) to the slot.</td></tr>
    </table>
    <p>Projects wrap this with their own fixed slot count and payload schema (hello_tortu's
    <code>save_system.py</code>: 3 slots, a small <code>gamedata</code> shape). Save/load menu screens are GUI
    layer scripts that list <code>read_slots()</code> and, on a transition, publish
    <code>instance_api.request_scene_transition(...)</code> for the level driver to pick up.</p>

    <h2>Checkpoints</h2>
    <p>Entirely userland — there's no engine checkpoint module. The convention (hello_tortu's
    <code>game_state.py</code>) is a plain module holding the current checkpoint plus player stats:</p>
    <pre><code># game_state.py
checkpoint = None  # (x, y) | None

def set_checkpoint(x, y):
    global checkpoint
    checkpoint = (x, y)

def clear_checkpoint():
    global checkpoint
    checkpoint = None</code></pre>
    <p><code>clear_checkpoint()</code> is called whenever a genuinely different scene loads (not a respawn in
    the same scene). A checkpoint-flag object script calls <code>set_checkpoint</code> when the player's
    hitbox (<code>instance_api.player_hitbox()</code>) overlaps it; the player controller's own
    <code>init()</code> checks <code>game_state.checkpoint</code> to decide whether to spawn there instead of
    at the scene's authored player-start position.</p>

    <h2>Camera</h2>
    <p>No engine camera object exists either. The renderer only accepts an explicit
    <code>camera_x</code>/<code>camera_y</code> pair on every call — tracking and smoothing is entirely your
    script's job:</p>
    <pre><code># camera_follow.py
def init(scene_width, scene_height):
    ...

def update(dt, target_x, target_y):
    ...   # smoothed follow, clamped to scene bounds

def get():
    return (camera_x, camera_y)</code></pre>
    <p>A <code>Scene</code> can declare <code>camera_script</code> and <code>camera_target</code> fields so the
    level driver auto-wires this without hardcoding it — see <code>tortoisengine/scene.py</code>. The scene
    renderer's own camera-facing signature:</p>
    <pre><code>SceneRenderer.render(scene, *, camera_x=0, camera_y=0,
                     view_width=SCREEN_WIDTH, view_height=SCREEN_HEIGHT, z_max=None)

SceneRenderer.render_overlay(scene, *, camera_x=0, camera_y=0,
                             view_width=SCREEN_WIDTH, view_height=SCREEN_HEIGHT, z_min)</code></pre>
    <p><code>render_overlay</code> renders transparently above a given z-layer — typically used to composite a
    camera-locked player/GUI overlay on top of <code>render(..., z_max=z_min-1)</code>.</p>

      <PageNav />
    </>
  )
}
