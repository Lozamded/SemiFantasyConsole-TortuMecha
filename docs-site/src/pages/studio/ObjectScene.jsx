import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function StudioObjectScene() {
  return (
    <>

    <h1>Object &amp; Scene Editors</h1>
    <p className="subtitle">Build a prefab in the Object Editor, then place it in the Scene Editor.</p>

    <h2>Object Editor</h2>
    <p><strong>New Object…</strong>: Name, First animation name (default "idle"), Sprite (from existing
    sprites — the combo is disabled with a hint if none exist yet, so make a sprite first).</p>

    <h3>Origin &amp; colliders — edited visually, on the canvas</h3>
    <p>The preview canvas isn't read-only — origin and colliders are dragged directly on the sprite:</p>
    <ul>
      <li><strong>Origin</strong>: drag the yellow crosshair. Numeric X/Y spinboxes exist too, for precision.</li>
      <li><strong>Colliders</strong>: click a collider's border to select it (highlights yellow). A move-handle
      appears at its center (drag to reposition) and four triangular resize handles appear on its edges (drag
      to resize, clamped to the sprite bounds). Unselected colliders show teal (active) or dim red (inactive)
      outlines — a "Show all colliders" checkbox can hide the ones you aren't editing.</li>
    </ul>
    <p>Mouse wheel zooms the preview 1×–16×.</p>

    <h3>Animations, colliders &amp; custom vars — list management</h3>
    <table>
      <tr><th>Section</th><th>Controls</th><th>Limit</th></tr>
      <tr><td>Animations</td><td>Active-animation combo, Name field, Sprite field (a drop target — drag a <code>.tortusprite</code> from the tree), Default-animation combo, Add/Remove</td><td>1–16</td></tr>
      <tr><td>Colliders</td><td>Collider combo, Name, "Active by default" checkbox, "Full sprite" checkbox (disables the X/Y/W/H spinboxes — collider always tracks whatever sprite is showing), X/Y/Width/Height spinboxes, Add/Remove</td><td>1–8</td></tr>
      <tr><td>Custom Variables</td><td>Variable combo, Name, Type combo (float/int/string/bool), "Array" checkbox, Default value field (comma-separated for arrays), Add/Remove</td><td>up to 16</td></tr>
      <tr><td>Spawnable objects</td><td>Combo + Add/Remove, plus a drop list that accepts <code>.tortuobject</code> files dragged from the tree</td><td>—</td></tr>
    </table>
    <div className="callout">
      <strong>Custom variables become per-instance overrides in the Scene Editor</strong>
      Declaring a custom var here (say, <code>patrol: bool</code>) adds a matching field to every scene
      placement of this prefab — each placed instance can override it independently. See
      <Link to="/scripting/objects">Object scripts</Link> for how <code>instance_api.custom_var()</code> reads
      it at runtime.
    </div>

    <h3>Script</h3>
    <p>Shows a single "Create Script" button if none is assigned yet (creates a stub and opens it
    immediately); once assigned, shows the path plus "Browse…" (assign an existing file) and "Open script"
    (launches it in your configured external editor — see <code>editor_command</code> in
    <Link to="/formats/overview">tortu.project</Link>).</p>

    <h2>Scene Editor</h2>
    <p><strong>New Scene…</strong>: Name, Palette.</p>

    <h3>Draw mode vs. Edit mode</h3>
    <p>Two toggle buttons switch the canvas's whole interaction model: <strong>Draw</strong> paints new
    content (tiles or objects, depending on the active bottom tab); <strong>Edit</strong> lets you click-select
    and drag already-placed <em>objects</em> around (tiles aren't draggable — repaint them instead).</p>

    <h3>What Paint places depends on the bottom tab</h3>
    <p>A tab strip below the canvas has two tabs — <strong>Tileset</strong> (pick a tile from the strip) and
    <strong>Objects</strong> (pick a prefab from the strip) — whichever is active determines what Paint/Erase
    do in Draw mode: paint tile indices into the active tile layer, or drop/remove object instances.</p>
    <p>Objects can also be placed by <strong>dragging a <code>.tortuobject</code> file straight from the
    project tree onto the map canvas</strong> — drops it at the cursor position, no tab-switching needed.</p>
    <div className="callout">
      <strong>Ctrl+Z undoes map canvas edits</strong>
      Tile strokes and object placement/erase/drag are all undoable (Ctrl+Z) and redoable (Ctrl+Shift+Z) with
      the map canvas focused — see <Link to="/studio/overview">Studio Overview</Link> for the exact scope and
      what resets the history (switching tile layers doesn't, but adding/removing one does).
    </div>

    <h3>Objects in Scene panel</h3>
    <p>One collapsible card per placed instance: ID (optional, for scripting — see
    <code>SELF_ID</code>/<code>LINKS</code> on the <Link to="/scripting/objects">Object scripts</Link> page),
    Links (comma-separated — or drag another card's header onto this field to link them), X/Y/Z-index, Scale,
    Animation override, Visible/Enabled checkboxes, and (if the prefab declares any) a nested Custom Variables
    section with one field per declared var. "Click origin of object to move" switches the canvas's
    click-to-select hit test from bounding-box to nearest-origin — useful when colliders overlap.</p>

    <h3>Side panel sections (collapsible)</h3>
    <table>
      <tr><th>Section</th><th>Default</th><th>Contents</th></tr>
      <tr><td>Scripts</td><td>—</td><td>The scene's own top-level script (level driver) — Create/Assign/Open.</td></tr>
      <tr><td>Backgrounds</td><td>collapsed</td><td>Per-layer: asset combo, visibility, Parallax X/Y, Fixed, Repeat X/Y, and a "Band parallax" toggle that reveals per-band Y-range/parallax/fixed/repeat controls with "Show band guides on map" for a visual overlay. Add/Remove layer (max 4).</td></tr>
      <tr><td>GUI Layers</td><td>collapsed</td><td>Per-slot: GUI layer asset combo, Z-index, editor/play visibility. Add/Remove slot (max 4).</td></tr>
      <tr><td>Tile layers</td><td>expanded</td><td>Per-layer: Tileset combo, visibility, and the scene-wide Collision layer combo (which layer physics uses). Add/Remove layer (1–4).</td></tr>
      <tr><td>Camera</td><td>expanded</td><td>Target object combo (drop an object card here to set the follow target), Camera script (Create/Assign), Camera X/Y sliders for scrubbing the preview position while editing, visibility toggles.</td></tr>
      <tr><td>Map</td><td>collapsed</td><td>Width/Height, Resize/Reset to screen, Zoom, Tile grid toggle.</td></tr>
    </table>

      <PageNav />
    </>
  )
}
