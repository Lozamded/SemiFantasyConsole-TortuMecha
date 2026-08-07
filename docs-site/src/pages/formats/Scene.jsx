import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function FormatsScene() {
  return (
    <>

    <h1>Scenes (.tortuscene)</h1>
    <p className="subtitle">The tile-map + object-placement + layer-stack format that ties every other asset together.</p>

    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>palette</code></td><td>str</td><td>required</td><td>Palette stem, e.g. <code>"default"</code>. Governs how this scene's own <strong>tile layers</strong> render — not placed sprites, backgrounds, or GUI layers, each of which always uses its own declared <code>palette</code> regardless of the scene's. See <Link to="/studio/palette">TortoiseStudio: Palette</Link>.</td></tr>
      <tr><td><code>width</code> / <code>height</code></td><td>int</td><td>required</td><td>Pixels.</td></tr>
      <tr><td><code>tile_layers</code></td><td>list</td><td><code>[]</code></td><td>1–4 layers (<code>MIN_SCENE_TILE_LAYERS</code>/<code>MAX_SCENE_TILE_LAYERS</code>), enforced on save.</td></tr>
      <tr><td><code>bg_layers</code></td><td>list</td><td><code>[]</code></td><td>0–4 layers (<code>MAX_SCENE_BG_LAYERS</code>).</td></tr>
      <tr><td><code>gui_layers</code></td><td>list</td><td><code>[]</code></td><td>0–4 slots (<code>MAX_SCENE_GUI_LAYERS</code>).</td></tr>
      <tr><td><code>objects</code></td><td>list</td><td><code>[]</code></td><td>Max <strong>256</strong> (<code>MAX_SCENE_OBJECTS</code>) — <code>add_object()</code> raises past that.</td></tr>
      <tr><td><code>collision_tile_layer</code></td><td>int</td><td><code>0</code></td><td>Index into <code>tile_layers</code> used for physics/collision queries (<code>instance_api.tile_solid_at</code>).</td></tr>
      <tr><td><code>script</code></td><td>str</td><td><code>""</code></td><td>The scene's own top-level script (a level driver — see the Scripting API's Object scripts page). Omitted from JSON when blank.</td></tr>
      <tr><td><code>camera_script</code> / <code>camera_target</code></td><td>str</td><td><code>""</code></td><td>Auto-wires a camera-follow script and the prefab it should track — see <Link to="/scripting/subsystems">Subsystems</Link>. Omitted when blank.</td></tr>
    </table>

    <h2>Tile layers</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>auto (<code>tile_layer_0</code>, ...)</td><td></td></tr>
      <tr><td><code>tiles</code></td><td>list[int]</td><td><code>[]</code></td><td>Flat, row-major, one tile index per cell; <code>-1</code> means empty (<code>EMPTY_TILE</code>).</td></tr>
      <tr><td><code>visible</code></td><td>bool</td><td><code>true</code></td><td>Only written to JSON when <code>false</code>.</td></tr>
      <tr><td><code>tileset</code></td><td>str</td><td><code>""</code></td><td>Path to a <code>.tortutileset</code>. Omitted when blank.</td></tr>
    </table>
    <div className="callout">
      <strong>Each tile layer can have a different grid resolution</strong>
      A layer's grid size comes from <em>its own tileset's</em> <code>tile_size</code> (falling back to 8px if
      the tileset is blank/unresolved) — two tile layers in the same <code>width</code>×<code>height</code>
      scene can have different column/row counts if they reference tilesets with different tile sizes. If a
      hand-edited scene's <code>tiles</code> array doesn't match its layer's expected grid size, it gets
      silently nearest-neighbor resampled to fit rather than rejected.
    </div>

    <h2>Background layers</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>auto</td><td></td></tr>
      <tr><td><code>background</code></td><td>str</td><td><code>""</code></td><td>Path to a <code>.tortubackground</code>. Omitted when blank.</td></tr>
      <tr><td><code>visible</code></td><td>bool</td><td><code>true</code></td><td></td></tr>
      <tr><td><code>parallax_x</code> / <code>parallax_y</code></td><td>float</td><td><code>0.5</code> / <code>0.0</code></td><td>Scroll speed relative to the camera; ignored horizontally when <code>band_parallax</code> is on (see below) — <code>parallax_y</code> always applies globally regardless.</td></tr>
      <tr><td><code>fixed</code></td><td>bool</td><td><code>false</code></td><td>Pins the layer regardless of camera position.</td></tr>
      <tr><td><code>repeat_x</code> / <code>repeat_y</code></td><td>bool</td><td><code>false</code></td><td>Wrap-sample instead of clipping past the background's edges.</td></tr>
      <tr><td><code>band_parallax</code></td><td>bool</td><td><code>false</code></td><td>Switch to per-row parallax bands (see below).</td></tr>
      <tr><td><code>parallax_bands</code></td><td>list</td><td><code>[]</code></td><td>Max <strong>8</strong> (<code>MAX_PARALLAX_BANDS</code>).</td></tr>
    </table>
    <p><code>fixed</code>/<code>repeat_x</code>/<code>repeat_y</code>/<code>band_parallax</code>/
    <code>parallax_bands</code>/<code>background</code> are only written to JSON when truthy.</p>

    <h3>Band parallax</h3>
    <p>Splits the background into horizontal strips, each with its own scroll behavior — used for layered
    depth (near ground scrolls fast, distant sky scrolls slow or stays fixed) within a single background
    image:</p>
    <table>
      <tr><th>Field</th><th>Type</th><th>Notes</th></tr>
      <tr><td><code>y0</code> / <code>y1</code></td><td>int</td><td>Screen-row range this band covers (inclusive).</td></tr>
      <tr><td><code>parallax_x</code></td><td>float</td><td>Default <code>0.5</code>.</td></tr>
      <tr><td><code>fixed</code> / <code>repeat_x</code> / <code>repeat_y</code></td><td>bool</td><td>Default <code>false</code> each.</td></tr>
    </table>
    <p>Bands are matched first-band-wins by row (the first band in the list where <code>y0 &lt;= y &lt;= y1</code>);
    overlapping ranges are tolerated, not an error. Real example (a 5-band parallax stack from a platformer level):</p>
    <pre><code>&#123;"name": "scene_bg_0", "parallax_x": 0.45, "band_parallax": true,
 "parallax_bands": [
   &#123;"y0": 0,   "y1": 19,  "parallax_x": 0.0,  "fixed": true&#125;,
   &#123;"y0": 20,  "y1": 46,  "parallax_x": 0.45, "repeat_x": true&#125;,
   &#123;"y0": 47,  "y1": 72,  "parallax_x": 0.52, "repeat_x": true&#125;,
   &#123;"y0": 73,  "y1": 126, "parallax_x": 0.64, "repeat_x": true&#125;,
   &#123;"y0": 127, "y1": 197, "parallax_x": 0.85, "repeat_x": true&#125;
 ], "background": "assets/backgrounds/bg1.tortubackground"&#125;</code></pre>

    <h2>GUI layer scene slots</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>auto</td><td></td></tr>
      <tr><td><code>gui_layer</code></td><td>str</td><td><code>""</code></td><td>Path to a <code>.tortuguilayer</code>.</td></tr>
      <tr><td><code>z_index</code></td><td>int</td><td><code>0</code></td><td></td></tr>
      <tr><td><code>visible</code></td><td>bool</td><td><code>true</code></td><td>This is the scene-wide toggle <code>instance_api.set_gui_layer_visible()</code> drives.</td></tr>
      <tr><td><code>editor_visible</code></td><td>bool</td><td><code>true</code></td><td>TortoiseStudio's "Visible in editor" preview toggle. Only written to JSON when <code>false</code>.</td></tr>
    </table>
    <div className="callout">
      <strong>editor_visible never affects the exported game</strong>
      <code>SceneGuiLayer.editor_visible</code> is saved so it survives closing and reopening the scene in
      TortoiseStudio, but it's a Studio-only preview convenience — <code>scene_renderer.py</code> and the
      export pipeline never read it, so it has no effect on the exported/played game. Use <code>visible</code>
      (or <code>instance_api.set_gui_layer_visible()</code>) to actually hide a GUI layer in-game.
    </div>

    <h2>Placed objects</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>prefab</code></td><td>str</td><td>required</td><td>Path to a <code>.tortuobject</code>. Written as JSON key <code>"object"</code>.</td></tr>
      <tr><td><code>x</code> / <code>y</code></td><td>int</td><td>required</td><td></td></tr>
      <tr><td><code>animation</code></td><td>str</td><td><code>""</code></td><td>Overrides the prefab's default animation.</td></tr>
      <tr><td><code>z_index</code></td><td>int</td><td><code>0</code></td><td></td></tr>
      <tr><td><code>id</code></td><td>str</td><td><code>""</code></td><td>Scene-unique instance id — this is what <code>SELF_ID</code> is set to for its script, and what other instances address it by.</td></tr>
      <tr><td><code>links</code></td><td>list[str]</td><td><code>[]</code></td><td>Other instance ids this one references — becomes its script's <code>LINKS</code>.</td></tr>
      <tr><td><code>visible</code> / <code>enabled</code></td><td>bool</td><td><code>true</code></td><td>Only written when <code>false</code>.</td></tr>
      <tr><td><code>scale</code></td><td>float</td><td><code>1.0</code></td><td></td></tr>
      <tr><td><code>flip_x</code></td><td>bool</td><td><code>false</code></td><td></td></tr>
      <tr><td><code>custom_var_overrides</code></td><td>dict</td><td><code>&#123;&#125;</code></td><td>Per-instance overrides of the prefab's declared custom vars — read via <code>instance_api.custom_var()</code>.</td></tr>
    </table>

    <p>A real object placement with a link and a custom-var override:</p>
    <pre><code>&#123;"object": "assets/objects/robot.tortuobject", "x": 119, "y": 127, "id": "robot1",
 "links": ["diag_robo1"],
 "custom_var_overrides": &#123;"dialogue": "dialogues/robot1_lvl1.json"&#125;&#125;</code></pre>

    <h2>Field emission is conditional</h2>
    <p>Almost every field above is only written to JSON when it differs from its default — a freshly saved
    scene is much sparser than the full field list suggests. A minimal real scene:</p>
    <pre><code>&#123;
  "palette": "default", "width": 264, "height": 198,
  "collision_tile_layer": 0,
  "script": "scripts/title.py",
  "bg_layers": [&#123;"name": "scene_bg_0", "visible": true, "parallax_x": 0.5, "parallax_y": 0.0,
                 "background": "assets/backgrounds/TitleScreen.tortubackground"&#125;],
  "tile_layers": [&#123;"name": "tile_layer_0", "visible": true, "tiles": [ ... ]&#125;],
  "objects": [],
  "gui_layers": [&#123;"name": "gui_layer_0", "gui_layer": "assets/gui/title_hud.tortuguilayer"&#125;]
&#125;</code></pre>

    <h2>Legacy keys still accepted on load</h2>
    <p>Hand-edited or older files may use these — all still load correctly:</p>
    <table>
      <tr><th>Legacy key</th><th>Modern equivalent</th></tr>
      <tr><td><code>layers</code></td><td><code>tile_layers</code></td></tr>
      <tr><td><code>collision_layer</code></td><td><code>collision_tile_layer</code></td></tr>
      <tr><td><code>width_tiles</code> / <code>height_tiles</code> + <code>tile_size</code></td><td>an alternate way to specify scene <code>width</code>/<code>height</code> in pixels</td></tr>
      <tr><td>top-level <code>tileset</code></td><td>legacy default applied to any tile layer missing its own <code>tileset</code></td></tr>
      <tr><td><code>prefab</code> (on an object)</td><td>alias for <code>object</code></td></tr>
      <tr><td><code>repeat</code> (on a bg layer)</td><td>sets both <code>repeat_x</code> and <code>repeat_y</code></td></tr>
    </table>

      <PageNav />
    </>
  )
}
