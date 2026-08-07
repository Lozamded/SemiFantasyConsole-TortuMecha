import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function ScriptingReference() {
  return (
    <>

    <h1>Reference &amp; imports</h1>
    <p className="subtitle">What's importable, what's re-exported from the top-level package, and what's internal and off-limits.</p>

    <h2>Re-exported from tortoisengine</h2>
    <p><code>import tortoisengine</code> (or <code>from tortoisengine import ...</code>) gives direct access to
    the asset data model and constants — the same types TortoiseStudio itself uses:</p>
    <table>
      <tr><th>Category</th><th>Names</th></tr>
      <tr><td>Constants</td><td><code>SCREEN_WIDTH</code>, <code>SCREEN_HEIGHT</code>, <code>MAX_COLORS</code>, <code>TRANSPARENT_INDEX</code>, <code>EMPTY_TILE</code>, <code>MIN_SCENE_TILE_LAYERS</code>, <code>MAX_SCENE_TILE_LAYERS</code>, <code>MAX_SCENE_BG_LAYERS</code></td></tr>
      <tr><td>Scene</td><td><code>Scene</code>, <code>SceneObject</code>, <code>SceneTileLayer</code>, <code>SceneBgLayer</code>, <code>SceneBgParallaxBand</code>, <code>load_scene</code>, <code>save_scene</code></td></tr>
      <tr><td>Objects</td><td><code>TortoiseObject</code>, <code>ObjectAnimation</code>, <code>ObjectCollider</code>, <code>ObjectOrigin</code>, <code>load_object</code>, <code>save_object</code>, <code>MAX_OBJECT_COLLIDERS</code>, <code>MAX_OBJECT_CUSTOM_VARS</code>, <code>CUSTOM_VAR_TYPES</code>, <code>CustomVarDef</code>, <code>default_for_custom_var_type</code>, <code>parse_custom_var_text</code>, <code>format_custom_var_value</code></td></tr>
      <tr><td>Project</td><td><code>Project</code>, <code>load_project</code>, <code>save_project</code></td></tr>
      <tr><td>Settings</td><td><code>GameSettings</code>, <code>MIN_GAME_FPS</code>, <code>MAX_GAME_FPS</code></td></tr>
      <tr><td>Palette</td><td><code>load_palette</code>, <code>closest_index</code></td></tr>
      <tr><td>Background / Sprite</td><td><code>Background</code>, <code>load_background</code>, <code>save_background</code>, <code>Sprite</code>, <code>load_sprite</code>, <code>save_sprite</code></td></tr>
    </table>
    <p>The <code>save_*</code> functions exist for TortoiseStudio's own editing/export use — a gameplay script
    reads assets, it doesn't normally write them back out.</p>

    <h2>Import by full path</h2>
    <p>These are used heavily by real scripts but aren't re-exported from the top-level package — import the
    submodule directly:</p>
    <table>
      <tr><th>Module</th><th>What it's for</th></tr>
      <tr><td><code>tortoisengine.instance_api</code></td><td>The runtime query/mutation API — see <Link to="/scripting/objects">Object scripts</Link> and <Link to="/scripting/gui">GUI layer scripts</Link>.</td></tr>
      <tr><td><code>tortoisengine.scene_renderer.SceneRenderer</code></td><td>Drives scene ticking/rendering for a level driver script — see <Link to="/scripting/subsystems">Subsystems</Link> (camera).</td></tr>
      <tr><td><code>tortoisengine.tileset</code></td><td><code>load_tileset</code>, <code>Tileset</code>, and collision constants <code>COLLISION_NONE</code>, <code>COLLISION_SOLID</code>, <code>ONE_WAY_*</code>.</td></tr>
      <tr><td><code>tortoisengine.audio</code></td><td>Channel volumes and sound loading — see Subsystems.</td></tr>
      <tr><td><code>tortoisengine.dialogue</code></td><td><code>load_dialogue</code>, <code>Dialogue</code>/<code>DialogueLine</code>/<code>DialogueOption</code>/<code>Action</code> — see Subsystems.</td></tr>
      <tr><td><code>tortoisengine.localization</code></td><td><code>bind_variables</code>, <code>resolve</code> (no <code>instance_api</code> wrapper); prefer <code>instance_api</code>'s re-exports for everything else.</td></tr>
      <tr><td><code>tortoisengine.save_data</code></td><td>Slot read/write — see Subsystems.</td></tr>
      <tr><td><code>tortoisengine.bake.bake_sprite_frame</code></td><td>Pre-bake an animation frame to a surface, used by scripts that composite sprites manually.</td></tr>
      <tr><td><code>tortoisengine.palette</code></td><td><code>load_palette</code>, <code>palette_path</code>.</td></tr>
      <tr><td><code>tortoisengine.gui_layer</code></td><td>The <code>GuiObject</code>/<code>GuiTextLabel</code>/<code>GuiTiledRect</code>/<code>GuiRepeatSprite</code>/<code>GuiLayer</code> dataclasses — rarely imported directly by gameplay scripts, since runtime access goes through <code>instance_api</code>.</td></tr>
    </table>

    <h2>Generated, project-local imports</h2>
    <p>Not part of the engine package — generated per-project by TortoiseStudio into
    <code>scripts/_generated/</code> (see <Link to="/scripting/objects">Object scripts</Link>):</p>
    <pre><code>from scripts._generated import robot_auto as auto
from scripts._generated import audio_auto as auto</code></pre>

    <h2>Not public API — don't call these from a game script</h2>
    <p>These exist in the engine but are internal implementation details or TortoiseStudio-only editor
    helpers. They're listed here so they're recognizable if you spot them while reading engine source, not
    because they're meant to be used:</p>
    <ul>
      <li>Any leading-underscore name in <code>instance_api.py</code> (<code>_find</code>,
      <code>_find_gui_element</code>, <code>_active_collision_tileset</code>,
      <code>_prefab_solid_info</code>, <code>_iter_solid_rects</code>, and its module-level
      <code>_scene</code>/<code>_player_x</code>/etc. state) — always go through the public function, never
      the underlying state.</li>
      <li>Most of <code>SceneRenderer</code>'s methods besides <code>__init__</code>,
      <code>from_cart</code>, <code>clear_baked_cache</code>, <code>reset_animations</code>,
      <code>tick</code>, <code>render</code>, <code>render_overlay</code> — the rest are private
      caching/baking helpers.</li>
      <li><code>GuiLayer</code>'s editor-mutation methods (<code>add_object</code>,
      <code>add_text_label</code>, <code>resize</code>, <code>get_tile</code>/<code>set_tile</code>,
      <code>find_*_near</code>, etc.) and the equivalent <code>Scene</code> editor methods — TortoiseStudio
      only; a running game mutates GUI/scene state exclusively through <code>instance_api</code>.</li>
      <li><code>tortoisengine.script_codegen</code>'s writers — TortoiseStudio calls these on save; a game
      script never does.</li>
      <li><code>tortoisengine.instance_scripts.InstanceScript</code> / <code>load_instance_script</code> —
      the loader that runs your script; not something your script calls back into.</li>
      <li><code>tortoisengine.cart</code>, <code>export_cart</code>, <code>build_executable</code>, most of
      <code>bake</code> (besides <code>bake_sprite_frame</code>) — build/export tooling, not runtime
      scripting API.</li>
    </ul>

      <PageNav />
    </>
  )
}
