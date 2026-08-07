import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function FormatsGui() {
  return (
    <>

    <h1>GUI Layers &amp; Elements</h1>
    <p className="subtitle">.tortuguilayer canvases, plus the two reusable-look assets they can place: .tortuprogressbar and .tortupipbar.</p>

    <p>This page is the raw file schema. For how a script drives these elements at runtime (via
    <code>instance_api</code>), see the <Link to="/scripting/gui">GUI layer scripts</Link> page.</p>

    <h2>GUI layers (.tortuguilayer)</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>width</code> / <code>height</code></td><td>int</td><td>required</td><td></td></tr>
      <tr><td><code>palette</code></td><td>str</td><td><code>"default"</code></td><td></td></tr>
      <tr><td><code>tileset</code></td><td>str</td><td><code>""</code></td><td>At most one tile layer per GUI layer. Omitted from JSON when blank.</td></tr>
      <tr><td><code>tiles</code></td><td>list[int]</td><td><code>[]</code></td><td>Flat, row-major, <code>-1</code> = empty. Grid resolution comes from the referenced tileset's <code>tile_size</code> (8px default). <strong>Only present in the JSON at all if <code>tileset</code> is non-blank</strong> — no tileset means no <code>tiles</code> key, not an empty array.</td></tr>
      <tr><td><code>tile_layer_visible</code></td><td>bool</td><td><code>true</code></td><td></td></tr>
      <tr><td><code>objects</code></td><td>list</td><td><code>[]</code></td><td>Max 64 (<code>MAX_GUI_OBJECTS</code>) — enforced by the editor's <code>add_object()</code>, not by the loader.</td></tr>
      <tr><td><code>text_labels</code></td><td>list</td><td><code>[]</code></td><td>Max 32 (<code>MAX_GUI_TEXT_LABELS</code>), same caveat.</td></tr>
      <tr><td><code>tiled_rects</code></td><td>list</td><td><code>[]</code></td><td>Max 16 (<code>MAX_GUI_TILED_RECTS</code>), same caveat.</td></tr>
      <tr><td><code>repeat_sprites</code></td><td>list</td><td><code>[]</code></td><td>Max 16 (<code>MAX_GUI_REPEAT_SPRITES</code>), same caveat.</td></tr>
      <tr><td><code>script</code></td><td>str</td><td><code>""</code></td><td>See <Link to="/scripting/gui">GUI layer scripts</Link>. Omitted when blank.</td></tr>
    </table>
    <div className="callout">
      <strong>scroll_x / scroll_y are runtime-only</strong>
      These exist on the in-memory <code>GuiLayer</code> object (driven by
      <code>instance_api.set_gui_layer_scroll()</code>) but are never read from or written to the
      <code>.tortuguilayer</code> file — a fresh load always starts at <code>(0, 0)</code>.
    </div>

    <h3>Placed elements</h3>
    <table>
      <tr><th>Element</th><th>Fields</th></tr>
      <tr>
        <td><code>GuiObject</code></td>
        <td><code>prefab</code> (str, JSON key <code>"object"</code>), <code>x</code>/<code>y</code> (int), <code>animation</code> (str, <code>""</code>), <code>scale</code> (float, <code>1.0</code>), <code>visible</code>/<code>enabled</code> (bool, <code>true</code>), <code>id</code> (str, <code>""</code> — optional; set it to address the element at runtime).</td>
      </tr>
      <tr>
        <td><code>GuiTextLabel</code></td>
        <td><code>text</code> (str), <code>x</code>/<code>y</code> (int), <code>id</code> (str, <code>""</code>), <code>font</code> (str, <code>""</code> — path to a <code>.tortufont</code>/<code>.tortuspritefont</code>), <code>color_index</code> (int, <code>-1</code> = font's baked color; no-op for sprite-font labels), <code>scale</code> (float, <code>1.0</code>), <code>align</code> (<code>"left"</code>/<code>"center"</code>/<code>"right"</code>), <code>wrap_width</code> (int, <code>0</code> = no wrap), <code>justify</code> (<code>"left"</code>/<code>"center"</code>/<code>"right"</code>/<code>"justify"</code>, only meaningful when <code>wrap_width &gt; 0</code>), <code>wrap_height</code> (int, <code>0</code> = no limit), <code>min_scale</code> (float, <code>1.0</code>), <code>visible</code>/<code>enabled</code> (bool).</td>
      </tr>
      <tr>
        <td><code>GuiTiledRect</code></td>
        <td><code>id</code>, <code>prefab</code> (path to a <code>.tortuprogressbar</code>), <code>x</code>/<code>y</code>/<code>width</code>/<code>height</code> (int), <code>number</code>/<code>max_number</code> (float, <code>1.0</code> each), <code>visible</code>/<code>enabled</code>.</td>
      </tr>
      <tr>
        <td><code>GuiRepeatSprite</code></td>
        <td><code>id</code>, <code>prefab</code> (path to a <code>.tortupipbar</code>), <code>x</code>/<code>y</code> (int), <code>number</code>/<code>max_number</code> (int, <code>0</code> each), <code>visible</code>/<code>enabled</code>.</td>
      </tr>
    </table>
    <p>Legacy key aliases still accepted on load: <code>GuiObject.prefab</code> also reads <code>"object"</code>;
    <code>GuiTiledRect.prefab</code> also reads <code>"texture"</code>, its <code>number</code> also reads
    <code>"value"</code>; <code>GuiRepeatSprite.prefab</code> also reads <code>"object"</code>, its
    <code>number</code> also reads <code>"count"</code>.</p>

    <h3>Real example</h3>
    <pre><code>&#123;
  "width": 264, "height": 198, "palette": "default",
  "tileset": "assets/tiles/terrain.tortutileset",
  "tiles": [ ...tile indices... ],
  "objects": [
    &#123;"object": "assets/objects/cursor.tortuobject", "x": 10, "y": 20, "id": "cursor"&#125;
  ],
  "text_labels": [
    &#123;"text": "LIVES", "x": 8, "y": 4, "id": "lives_label",
     "font": "assets/fonts/VCR.tortufont"&#125;
  ],
  "tiled_rects": [
    &#123;"id": "energy_bar", "prefab": "assets/gui_elements/health_bar.tortuprogressbar",
     "x": 8, "y": 16, "width": 40, "height": 8, "number": 100, "max_number": 100&#125;
  ]
&#125;</code></pre>

    <h2>Progress bars (.tortuprogressbar)</h2>
    <p>A reusable "look" for a <code>GuiTiledRect</code> placement — the fill texture and direction, shared
    across every placement that references it.</p>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>file stem if absent</td><td></td></tr>
      <tr><td><code>texture</code></td><td>str</td><td><code>""</code></td><td>A <code>.tortusprite</code> path, tiled to fill the bar (not stretched — keeps pixel art crisp at any bar size).</td></tr>
      <tr><td><code>fill_direction</code></td><td>str</td><td><code>"left_to_right"</code></td><td>One of <code>left_to_right</code>, <code>right_to_left</code>, <code>top_to_bottom</code>, <code>bottom_to_top</code>. An unrecognized value is silently reset to the default, not an error.</td></tr>
      <tr><td><code>width</code> / <code>height</code></td><td>int</td><td><code>40</code> / <code>8</code></td><td></td></tr>
      <tr><td><code>ranges</code></td><td>list</td><td><code>[]</code></td><td>Max 8 (<code>MAX_PROGRESS_BAR_RANGES</code>) — <strong>enforced</strong>, raises past that. Swaps the fill texture based on the current value.</td></tr>
    </table>
    <p>Each range: <code>min_number</code>/<code>max_number</code> (float), <code>texture</code> (str,
    <code>""</code>). Matched first-range-wins by the bar's current <code>number</code> — same pattern as a
    scene's parallax bands.</p>
    <pre><code>&#123;"name": "health_bar", "texture": "assets/sprites/bar_fill.tortusprite",
 "fill_direction": "left_to_right", "width": 40, "height": 8&#125;</code></pre>

    <h2>Pip bars (.tortupipbar)</h2>
    <p>A reusable "look" for a <code>GuiRepeatSprite</code> placement — life pips, hearts, ammo counters drawn
    as a row/column of repeated icons.</p>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>file stem if absent</td><td></td></tr>
      <tr><td><code>full_sprite</code></td><td>str</td><td><code>""</code></td><td><code>.tortusprite</code> path drawn for filled slots.</td></tr>
      <tr><td><code>empty_sprite</code></td><td>str</td><td><code>""</code></td><td><code>.tortusprite</code> path for empty slots — blank means empty slots are simply skipped, not drawn.</td></tr>
      <tr><td><code>direction</code></td><td>str</td><td><code>"horizontal"</code></td><td><code>"horizontal"</code> or <code>"vertical"</code>. Invalid value silently resets to horizontal.</td></tr>
      <tr><td><code>spacing</code></td><td>int</td><td><code>0</code></td><td>Pixel gap between pips.</td></tr>
      <tr><td><code>scale</code></td><td>float</td><td><code>1.0</code></td><td></td></tr>
      <tr><td><code>ranges</code></td><td>list</td><td><code>[]</code></td><td>Max 8 (<code>MAX_PIP_BAR_RANGES</code>), enforced. Swaps <code>full_sprite</code> based on the current count.</td></tr>
    </table>
    <p>Each range: <code>min_number</code>/<code>max_number</code> (int), <code>full_sprite</code> (str,
    <code>""</code>). Real example — a life-pip bar that swaps to a red icon at low health:</p>
    <pre><code>&#123;"name": "pip_bar", "full_sprite": "assets/sprites/icon_shell_green.tortusprite",
 "empty_sprite": "", "direction": "horizontal", "spacing": 0, "scale": 1.0,
 "ranges": [
   &#123;"min_number": 0, "max_number": 1, "full_sprite": "assets/sprites/icon_shell_red.tortusprite"&#125;,
   &#123;"min_number": 2, "max_number": 5, "full_sprite": "assets/sprites/icon_shell_green.tortusprite"&#125;
 ]&#125;</code></pre>

      <PageNav />
    </>
  )
}
