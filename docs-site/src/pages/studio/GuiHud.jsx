import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function StudioGuiHud() {
  return (
    <>

    <h1>GUI/HUD Editors</h1>
    <p className="subtitle">The GUI Layer Editor, plus the two reusable-look editors it draws from: Progress Bar and Pip Bar.</p>

    <h2>GUI Layer Editor</h2>
    <p><strong>New GUI Layer…</strong>: Name, Width/Height (default 264×198), Palette.</p>
    <p>Same Draw/Edit mode split as the Scene Editor, but with <strong>five</strong> paintable targets instead
    of two — a row of checkable buttons: <strong>Tiles / Objects / Text / Tiled Rect / Repeat Sprite</strong>.
    The bottom tab strip changes to match whichever target is active (a tile strip, an object-prefab strip, a
    <code>.tortuprogressbar</code> strip, or a <code>.tortupipbar</code> strip). Eyedropper only works for the
    Tiles target. Text labels aren't click-painted — they're added via the "Add label" button in the Text
    Labels panel instead.</p>

    <h3>Side panel sections (collapsible)</h3>
    <table>
      <tr><th>Section</th><th>Contents</th></tr>
      <tr><td>Size</td><td>Width/Height, Resize/Reset to screen, Zoom, Tile grid toggle.</td></tr>
      <tr><td>Script</td><td>The layer's own script — Create/Assign/Open. See <Link to="/scripting/gui">GUI layer scripts</Link> for what <code>SELF_ID</code> means here (the layer's own asset path, not a scene instance id).</td></tr>
      <tr><td>Tile Layer</td><td>Tileset combo, visibility.</td></tr>
      <tr><td>Objects</td><td>Search filter + one card per placed <code>GuiObject</code>: ID, X, Y, Scale, Animation, Visible/Enabled.</td></tr>
      <tr><td>Text Labels</td><td>New-label Text field + Font combo + "Add label", then one card per label — see fields below.</td></tr>
      <tr><td>Tiled Rects</td><td>"Add tiled rect" (after picking a texture in the Tiled Rects strip below), one card per placement.</td></tr>
      <tr><td>Repeat Sprites</td><td>One card per placement — placed by click-painting on the canvas, no explicit "Add" button.</td></tr>
    </table>

    <h3>Text label fields</h3>
    <p>Text, Font combo, ID (optional — for <code>instance_api.set_gui_text_label_text</code> etc.), X/Y,
    Color combo (overrides the font's baked ink color; disabled for sprite fonts — see the callout below),
    Scale, Align (Left/Center/Right), "Limit text to a box width" + Wrap width + Justify (Left/Center/Right/
    Justify), "Limit text to a box height" + Height + Min-scale (auto-shrinks to fit when both width and
    height limits are set), Visible/Enabled.</p>
    <div className="callout">
      <strong>Color override only works on .tortufont labels</strong>
      A sprite-font glyph is a pre-colored bitmap, so the Color combo has nothing to override — it's disabled
      whenever the label's Font is a <code>.tortuspritefont</code>. Use a <code>.tortufont</code> label if you
      need runtime color changes (e.g. highlighting a selected menu item).
    </div>

    <h3>Tiled rect / repeat sprite fields</h3>
    <p><strong>Tiled Rect</strong>: Prefab (<code>.tortuprogressbar</code>) combo, X, Y, Width, Height, Number,
    Max number, Visible/Enabled. <strong>Repeat Sprite</strong>: Prefab (<code>.tortupipbar</code>) combo, X,
    Y, Number, Max number, Visible/Enabled.</p>

    <h2>Progress Bar Editor</h2>
    <p><strong>New Progress Bar…</strong>: Name, Texture (an existing sprite — creation is blocked with a
    warning if no sprites exist yet).</p>
    <p>Fields: Display name, Texture (drag-drop enabled), Fill direction (Left To Right / Right To Left / Top
    To Bottom / Bottom To Top), default Width/Height. A live tiled-texture preview shows the bar at its current
    size (not stretched — the texture tiles to stay pixel-crisp at any size).</p>
    <p><strong>Texture Ranges</strong> (max 8): swap the texture based on the bar's current value — e.g. a red
    fill under 20% health. Each range: Number from/to, Texture. First matching range wins.</p>

    <h2>Pip Bar Editor</h2>
    <p><strong>New Pip Bar…</strong>: Name, Full sprite (creation blocked if no sprites exist).</p>
    <p>Fields: Display name, Full sprite (drag-drop), Empty sprite (drag-drop, optional — "(none)" skips
    drawing empty slots entirely rather than leaving a gap), Direction (Horizontal/Vertical), Spacing (px
    between pips), Scale. A preview shows an illustrative row of 3 slots at the current settings.</p>
    <p><strong>Texture Ranges</strong> (max 8): swaps the <em>full</em> sprite over an integer count range —
    e.g. a cracked heart icon once lives drop to 1. Same first-match-wins rule as Progress Bar ranges.</p>

      <PageNav />
    </>
  )
}
