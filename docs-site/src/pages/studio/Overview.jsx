import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function StudioOverview() {
  return (
    <>

      <h1>TortoiseStudio: Overview &amp; Workflow</h1>
      <p className="subtitle">The window layout, the project lifecycle, and the handful of global shortcuts that apply
        everywhere.</p>

      <p>TortoiseStudio is the main tool for developing your game. Here you'll manage all the assets, including
        graphics, sound, and other game components, as well as the relationships between them. You can create scripts
        within TortoiseStudio, but to edit them, use your preferred text editor.
      </p>

      <h2>Launching</h2>
      <pre><code>python -m tortoisestudio [path/to/project]</code></pre>
      <p>With a path, that project loads immediately. Without one, the window opens completely empty — there's
        no recent-projects list and no splash/picker dialog. Use <strong>File → Open Project…</strong> or
        <strong>File → New Project…</strong> to get started.
      </p>

      <div className="callout">
        <strong>New Project… is minimal by design</strong>
        There's no project-setup wizard. Picking a folder immediately scaffolds a project named "My Game" at
        <code>&lt;folder&gt;/my_game/</code> with a default bouncing-rectangle <code>main.py</code> stub, and
        opens it. Rename the game and set everything else afterward on the <strong>Game Settings</strong> tab.
      </div>

      <h2>Window layout</h2>
      <p>Menu bar → a fixed workspace tab strip → a horizontal split of (project tree + asset browser) on the
        left and the active editor in the center → a read-only console log along the bottom. There's no separate
        status bar; build results, save confirmations, and errors all print to that console.</p>

      <div className="card-grid">
        <div className="card">
          <h3>Project tree (left)</h3>
          <p>Grouped by asset kind (Sprites, Objects, Scenes, ...). Double-click a file to open its editor. An
            object's row expands to show <code>↪ scripts/xyz.py</code> — double-click to open it in your
            configured external editor. "Engine assets only" / "Show file paths" / "Show names only" checkboxes
            control what's visible.</p>
        </div>
        <div className="card">
          <h3>Asset browser (below the tree)</h3>
          <p>A filterable list scoped to whatever editor is currently active — switch to the Sprite Editor and
            it lists sprites, switch to Scene Editor and it lists scenes. Double-click an entry to open it.</p>
        </div>
        <div className="card">
          <h3>Drag and drop</h3>
          <p>Drag a <code>.tortusprite</code> or <code>.tortuobject</code> straight out of the project tree onto
            a texture/prefab picker field, or onto the Scene/GUI Layer map canvas to place it directly.</p>
        </div>
        <div className="card">
          <h3>Console log (bottom)</h3>
          <p>Save confirmations, file-watcher status, validation results, and build/play errors all print here
            — there's no separate dialog for most of these.</p>
        </div>
      </div>

      <h2>Workspace tabs</h2>
      <p>Twelve fixed, always-present tabs — Game Preview, Scene Editor, Sprite Editor, Tileset Editor,
        Background Editor, Font Editor, Object Editor, Sound, Palette Editor, GUI Layer Editor, Bar Editors, Game
        Settings. Switching away from a tab with unsaved changes prompts Save / Discard / Cancel.</p>
      <table>
        <tr>
          <th>Shortcut</th>
          <th>Tab</th>
        </tr>
        <tr>
          <td>Ctrl+1</td>
          <td>Game Preview</td>
        </tr>
        <tr>
          <td>Ctrl+2</td>
          <td>Scene Editor</td>
        </tr>
        <tr>
          <td>Ctrl+3</td>
          <td>Sprite Editor</td>
        </tr>
        <tr>
          <td>Ctrl+4</td>
          <td>Tileset Editor</td>
        </tr>
        <tr>
          <td>Ctrl+5</td>
          <td>Background Editor</td>
        </tr>
        <tr>
          <td>Ctrl+6</td>
          <td>Font Editor</td>
        </tr>
        <tr>
          <td>Ctrl+7</td>
          <td>Object Editor</td>
        </tr>
        <tr>
          <td>Ctrl+8</td>
          <td>Sound</td>
        </tr>
        <tr>
          <td>Ctrl+9</td>
          <td>Palette Editor</td>
        </tr>
        <tr>
          <td>Ctrl+0</td>
          <td>GUI Layer Editor</td>
        </tr>
        <tr>
          <td><em>(none)</em></td>
          <td>Bar Editors, Game Settings — click the tab strip directly.</td>
        </tr>
      </table>

      <h2>Saving</h2>
      <div className="callout">
        <strong>There's no global save — Ctrl+S does nothing</strong>
        Every editor has its own "Save …" button in its top toolbar. If an edit goes wrong and Ctrl+Z doesn't
        cover it (see below), discard the editor's unsaved changes instead (the Save/Discard/Cancel prompt when
        switching tabs).
      </div>

      <h2>Undo/redo</h2>
      <div className="callout">
        <strong>Ctrl+Z / Ctrl+Shift+Z (Ctrl+Y), scoped to canvas gestures</strong>
        The Sprite, Tileset, Background, Sprite Font, and Scene map canvases each keep their own undo history
        (up to 50 steps) for the strokes/placements made directly on the canvas: pixel painting, tile painting,
        and — on the Scene map — placing, erasing, or dragging objects. It does <strong>not</strong> cover
        edits made through side-panel fields (renaming, resizing, palette swaps, object property edits) — those
        still only revert via Save/Discard/Cancel. The GUI Layer canvas has no undo yet. Undo/redo also needs
        the canvas itself focused (click it first) — pressing Ctrl+Z while a spinbox or another panel has focus
        won't reach it. History resets whenever the buffer's shape changes underneath it: switching frames,
        resizing, changing the palette, adding/removing a tile layer, or loading a different asset/scene.
      </div>
      <p><strong>Game Settings</strong> is its own tab (not a dialog) with Game name, Cart name, Game FPS
        (1–120), Start scene, Author, Description, and a "Test Play: Fullscreen" checkbox (testing-only, not
        saved). Its "Save game settings" button writes <code>tortu.project</code>.</p>

      <h2>Universal editing conventions</h2>
      <p>These apply across nearly every pixel-canvas editor (Sprite, Tileset, Background, Scene map, GUI Layer
        canvas, Sprite Font glyphs):</p>
      <ul>
        <li><strong>Right-click</strong> cycles the active paint tool: Pencil/Paint → Eraser/Erase →
          Eyedropper → back to Pencil/Paint. The Sprite, Tileset, Background, and Sprite Font editors insert a
          fourth <strong>Paint Bucket</strong> (flood fill) step before cycling back — Scene map and GUI Layer
          canvas stay a 3-tool cycle.</li>
        <li><strong>Mouse wheel</strong> zooms in/out, clamped to a widget-specific range.</li>
        <li>Renaming an asset from its editor's "Rename…" button also renames every same-stem sidecar file
          (preview PNGs, reference images).</li>
      </ul>

      <h2>Script hot-reload</h2>
      <p>TortoiseStudio watches the whole project tree for <code>.py</code> changes (via <code>watchdog</code>)
        the moment a project is open — including edits made in an external editor. Press <strong>F6</strong> to
        apply pending script changes without a full relaunch.</p>

      <h2>Play, Debug Play &amp; validation</h2>
      <table>
        <tr>
          <th>Shortcut / Menu</th>
          <th>Behavior</th>
        </tr>
        <tr>
          <td>F5 — Play → Play/Resume</td>
          <td>Launches the game as a real external <code>tortoiseplayer</code> subprocess (fullscreen if the Game
            Settings "Test Play: Fullscreen" box is checked).</td>
        </tr>
        <tr>
          <td>Shift+F5 — Play → Stop</td>
          <td>Kills the play subprocess.</td>
        </tr>
        <tr>
          <td>F6 — Play → Reload Scripts</td>
          <td>Hot-reload without relaunching.</td>
        </tr>
        <tr>
          <td>F7 — Play → Debug Play (colliders)</td>
          <td>Runs the game <strong>inside the Game Preview viewport itself</strong>, overlaying live collider boxes
            (teal = active, dim red = inactive), a yellow origin crosshair, and each object's name. Click the viewport
            first to give it keyboard focus — arrows, Space, Z/X/C, WASD, Shift, Enter, and Escape are all forwarded to
            the game.</td>
        </tr>
        <tr>
          <td>Build → Validate Project</td>
          <td>Checks the entry script, <code>palettes/</code> folder, and start scene all exist; prints results to the
            console (no dialog).</td>
        </tr>
      </table>

      <p>Exporting a cart and building a standalone executable are covered on the
        <Link to="/studio/build-test">Build &amp; test</Link> page — see also
        <Link to="/get-started/install-sbc">Install on an SBC</Link> for what to do with the result.
      </p>

      <PageNav />
    </>
  )
}
