import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function StudioPalette() {
  return (
    <>

    <h1>Palette Editor</h1>
    <p className="subtitle">Colors come before art: every sprite, tileset, background, GUI layer, and font picks a palette when it's created, so it's worth understanding how palettes work before you start drawing.</p>

    <p>The Tortoise-Mecha console only supports 86 simultaneous colors; however, several different 86-color palettes can be defined in JSON files. These can be assigned to different assets in the game, but only assets that share the same color palette can coexist in a single scene.
</p>

    <h2>Editing a palette</h2>
    <p>No "New Palette" dialog — the toolbar's "New…" button just prompts for a name (plain text input) and
    seeds a fresh 86-color default palette.</p>
    <p>The grid shows all 86 slots as colored squares with their index in the corner; index 85 (transparent)
    renders as a checkerboard and can't be selected or edited. Click a slot to select it, then either:</p>
    <ul>
      <li><strong>Edit Selected Slot</strong> — a hex field (<code>#rrggbb</code>) or R/G/B spinboxes, "Apply
      color to slot" to commit.</li>
      <li><strong>Import Colors from Image</strong> — "Browse Image…" extracts up to 48 unique colors from a
      picture, sorted by how often they appear; click one to load it into the RGB editor, double-click to load
      <em>and</em> immediately apply, or select a swatch then hit "Set to selected palette slot".</li>
    </ul>
    <p>A Palette combo switches which <code>.pal</code> file you're editing; a status label shows "Saved." or
    "Unsaved changes".</p>

    <h2>A project can have many palettes — every asset picks one independently</h2>
    <p>There's nothing unusual about a project with several <code>.pal</code> files. Every "New Sprite…", "New
    Tileset…", "New Background…", "New GUI Layer…", and "New Font…" dialog has its own Palette combo, and each
    asset remembers its own choice from then on. Nothing links these choices together automatically — that's
    the point of the rest of this page.</p>

    <h2>How a scene's palette actually works</h2>
    <p>A <code>.tortuscene</code> file has exactly one <code>palette</code> field (see
    <Link to="/formats/scene">File Formats: Scenes</Link>). What that field actually controls is narrower
    — and more useful — than "everything in the scene must match it":</p>

    <div className="card-grid">
      <div className="card">
        <h3>Tile layers: yes, the scene's palette wins</h3>
        <p>A tile's pixels are stored as palette <em>indices</em>, not colors. At render time (and at cart
        export time), those indices are looked up in the <strong>scene's</strong> palette — not the tileset's
        own declared <code>palette</code> field, which is only used for the tileset's own editor preview.</p>
      </div>
      <div className="card">
        <h3>Sprites, backgrounds, GUI layers, fonts: no, they use their own</h3>
        <p>Every other asset type always renders through its own <code>palette</code> field, both live and in
        an exported cart — completely independent of whatever scene it ends up placed in. An object's sprite
        authored under one palette renders correctly in a scene using a different one; nothing needs to match.</p>
      </div>
    </div>

    <div className="callout">
      <strong>This is a feature, not a gotcha</strong>
      Because tile color comes from the scene rather than the tileset, the exact same tileset — one set of
      pixel-index tile art — can be reused across multiple scenes that each apply a different palette, for
      free color variants (a "night" level reusing "day" tile shapes with a different palette, for example).
      The cart exporter even keys its baked tile output as <code>tileset_path@palette_name</code> specifically
      to support the same tileset being baked once per palette it's actually used with.
    </div>

    <p>Nothing in TortoiseStudio validates or warns about any of this — no picker filters assets by palette
    compatibility, and there's no "these don't match" message anywhere. If a tileset's art was designed
    assuming its own palette's specific colors, placing it into a scene with a very different palette will
    still render (each index just resolves to whatever color sits at that slot in the scene's palette) — it
    just may not look like what you painted. Keeping a tileset visually consistent with the scenes it's used
    in is a choice you make, not a rule the editor enforces.</p>

      <PageNav />
    </>
  )
}
