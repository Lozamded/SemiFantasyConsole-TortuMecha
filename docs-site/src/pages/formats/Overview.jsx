import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function FormatsOverview() {
  return (
    <>

    <h1>File Formats: Project &amp; Palette</h1>
    <p className="subtitle">The project manifest, the shared conventions every asset format follows, and the palette file every asset references.</p>

    <p>Every TortoiseMecha asset is JSON (palettes are the one exception — see below), always UTF-8, always
    written with a trailing newline. This page covers the project root itself and the two things every other
    format leans on: color palettes, and how asset files reference each other.</p>

    <h2>Project layout</h2>
    <pre><code>my_project/
  tortu.project
  palettes/*.pal
  scenes/*.tortuscene
  assets/sprites/*.tortusprite
  assets/tiles/*.tortutileset
  assets/backgrounds/*.tortubackground
  assets/gui/*.tortuguilayer
  assets/gui_elements/*.tortuprogressbar
  assets/gui_elements/*.tortupipbar
  assets/objects/*.tortuobject
  assets/fonts/          # .tortufont (TTF-baked) and .tortuspritefont (sprite glyphs)
  assets/audio/
  scripts/
  main.py</code></pre>

    <div className="callout">
      <strong>assets/gui_elements/ isn't auto-created</strong>
      TortoiseStudio's <code>create_project()</code> scaffolds every folder above except
      <code>assets/gui_elements/</code> — if you're hand-building a project from scratch (not through the
      editor) and want progress bars or pip bars, create that folder yourself.
    </div>

    <h2>tortu.project</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td><code>"Untitled"</code></td><td>Project display name.</td></tr>
      <tr><td><code>version</code></td><td>str</td><td><code>"0.1.0"</code></td><td>Free-form.</td></tr>
      <tr><td><code>entry</code></td><td>str</td><td><code>"main.py"</code></td><td>Project-relative path to the game's entry script.</td></tr>
      <tr><td><code>editor_command</code></td><td>str</td><td><code>"xdg-open &#123;file&#125;"</code></td><td>Command TortoiseStudio runs to open a script file in an external editor; <code>&#123;file&#125;</code> is substituted.</td></tr>
      <tr><td><code>game</code></td><td>object</td><td>—</td><td>A <code>GameSettings</code> object, see below.</td></tr>
    </table>

    <h3>game settings</h3>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>game_name</code></td><td>str</td><td><code>"Untitled Game"</code></td><td>Shown in the window title bar. Legacy files may use <code>title</code> instead — still read as a fallback.</td></tr>
      <tr><td><code>cart_name</code></td><td>str</td><td><code>"untitled"</code></td><td>Must match <code>^[a-z0-9][a-z0-9_-]*$</code> — used as the exported <code>.tortucart</code> folder name.</td></tr>
      <tr><td><code>fps</code></td><td>int</td><td><code>60</code></td><td>Must be <code>1–120</code> (<code>MIN_GAME_FPS</code>/<code>MAX_GAME_FPS</code>).</td></tr>
      <tr><td><code>start_scene</code></td><td>str</td><td><code>""</code></td><td>Project-relative <code>.tortuscene</code> path; omitted from the JSON entirely when blank.</td></tr>
      <tr><td><code>author</code> / <code>description</code></td><td>str</td><td><code>""</code></td><td>Omitted when blank.</td></tr>
      <tr><td><code>audio_channels</code></td><td>list[str]</td><td><code>["music","sfx_1","sfx_2","sfx_3"]</code></td><td>Named channels — see the <Link to="/scripting/subsystems">Subsystems</Link> scripting page.</td></tr>
      <tr><td><code>audio_channel_map</code></td><td>dict[str,str]</td><td><code>&#123;&#125;</code></td><td>Project-relative audio file path → channel name.</td></tr>
    </table>

    <div className="callout">
      <strong>Saving validates, loading doesn't</strong>
      <code>save_project()</code> calls <code>GameSettings.validate()</code> first and raises on an empty
      <code>game_name</code>, a bad <code>cart_name</code>, or an out-of-range <code>fps</code> — but
      <code>load_project()</code> does not re-validate, so a hand-edited file that violates these constraints
      still loads; it'll only fail the next time it's saved (or exported).
    </div>

    <h2>Palette files (.pal)</h2>
    <p>The one non-JSON format — plain text, one entry per line:</p>
    <pre><code>&lt;index&gt; &lt;RRGGBB or 'transparent'&gt;   [# optional trailing comment]</code></pre>
    <pre><code># Tortoise palette — index 85 is always transparent
0 1a1c2e
1 ffffff
2 ff004d
...
85 transparent</code></pre>
    <p>Blank lines and lines starting with <code>#</code> are skipped. Hex may be written with or without a
    leading <code>#</code>; the token <code>transparent</code> is also accepted for any index. Every palette
    is exactly <strong>86 entries</strong> (indices 0–85, <code>MAX_COLORS</code>) — <code>load_palette()</code>
    raises if any index is missing.</p>

    <div className="callout">
      <strong>Index 85's color is cosmetic — only the index matters</strong>
      The engine's rendering checks <code>index == 85</code> and skips the pixel outright; it never reads
      whatever RGB is stored there. <code>save_palette()</code> always writes index 85 as the literal token
      <code>transparent</code> regardless of what was passed in, and <code>closest_index()</code> (nearest-color
      matching, e.g. importing a PNG) never returns index 85 — so an artist can't accidentally quantize an
      opaque pixel to "transparent" by color proximity.
    </div>

    <p>Palettes are referenced elsewhere by their bare filename stem (e.g. <code>"default"</code> →
    <code>palettes/default.pal</code>), not a path.</p>

    <h2>How asset files reference each other</h2>
    <p>Every cross-reference field across every format (a scene's <code>tileset</code>, an object's
    <code>script</code>, a GUI layer's <code>font</code>, and so on) is a <strong>project-root-relative,
    forward-slash path string</strong> — e.g. <code>"assets/sprites/hero.tortusprite"</code>. Loaders accept
    backslashes and normalize them to forward slashes; savers always write forward slashes, so files stay
    portable across editing on Windows/Linux/macOS. Nothing validates that the path actually resolves to an
    existing file, or that it stays inside the project — a broken reference simply fails wherever it's
    resolved at load/render time, not when the referencing file itself is saved.</p>

      <PageNav />
    </>
  )
}
