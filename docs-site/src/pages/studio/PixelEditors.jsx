import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function StudioPixelEditors() {
  return (
    <>

    <h1>Sprite, Tileset &amp; Background Editors</h1>
    <p className="subtitle">The three raw-pixel editors — they share the same paint tools and canvas conventions.</p>

    <p>All three editors paint with the same four-tool set: <strong>Pencil</strong>, <strong>Eraser</strong>,
    <strong>Eyedropper</strong>, <strong>Paint Bucket</strong>. Right-click cycles between them in that order;
    mouse wheel zooms. A palette swatch grid below each canvas picks the pencil color, restricted to the 85
    paintable indices (index 85/transparent is never a paint color, only what the eraser produces).</p>
    <div className="callout">
      <strong>Paint Bucket is a 4-connected flood fill</strong>
      Click a pixel and every orthogonally-connected pixel sharing its exact index gets replaced with the
      current color — diagonal-only neighbors and different indices act as a wall. It fills with the palette
      swatch color like Pencil, not with transparency; use Eraser for that. Implemented once in
      <code>tortoisestudio/pixel_tools.py</code> and shared by all four pixel canvases (Sprite, Tileset,
      Background, Sprite Font glyphs) rather than reimplemented per editor.
    </div>

    <h2>Sprite Editor</h2>
    <p><strong>New Sprite…</strong>: Name, Blocks wide / Blocks tall (1–32, default 4×4 = 16×16px), Palette.
    Sizes are authored in 4px blocks, not raw pixels — the dialog shows a live "Pixel size" readout.</p>

    <h3>Frames &amp; animation</h3>
    <p>A sprite is a list of frames, each independently paintable. Frame spinbox + ◀/▶ step through frames;
    "+ Frame" / "Duplicate" / "Delete" manage the list; "Play"/"Stop" previews the animation at the sprite's
    FPS (spinbox) times a Speed multiplier (0.25×–4×).</p>

    <h3>Reference tracing</h3>
    <p>"Load Reference…" overlays an image semi-transparently (Reference opacity slider) as a tracing guide —
    optionally stripped of a flat background color first via the <strong>Color key</strong> checkbox+swatch.
    "Convert to Current Palette" quantizes the reference directly into real sprite pixels. Reference images are
    saved as <code>&lt;name&gt;.refN.png</code> sidecar files per frame — editor-only, never read by the game.</p>

    <div className="callout">
      <strong>Resizing can crop</strong>
      Changing Blocks wide/tall on an existing sprite with painted pixels outside the new bounds prompts a
      confirm-crop dialog. Changing the Palette combo on a sprite that already has pixels also prompts to
      confirm, since the same indices will render as different colors.
    </div>

    <h2>Tileset Editor</h2>
    <p><strong>New Tileset…</strong>: Name, Tile size (4–64px, default 8), Palette. The workflow is
    import-sheet → edit one tile in a buffer → commit it into a growing tile stack, repeated per tile (or
    bulk-imported all at once):</p>
    <ol className="steps">
      <li>
        <h3>Import a sheet (optional)</h3>
        <p>"Load Import Image…" loads a full tile-sheet PNG (with Color key support). Click a cell to select
        it, then either "Load to editor" (send just that cell to the edit buffer) or "Save all from image"
        (bulk-converts and appends every cell in the sheet to the stack in one pass).</p>
      </li>
      <li>
        <h3>Paint the tile</h3>
        <p>The edit buffer has two tabs: <strong>Pencil</strong> (normal pixel painting, same 4-tool set as
        the sprite editor) and <strong>Collision</strong> (see below).</p>
      </li>
      <li>
        <h3>Set collision</h3>
        <p>On the Collision tab: a <strong>Collision</strong> combo (<code>none</code> / <code>solid</code> /
        <code>polygon</code>) and a <strong>One way</strong> combo (<code>none</code>/<code>up</code>/
        <code>down</code>/<code>left</code>/<code>right</code>, rendered as a directional arrow overlay). Only
        <code>polygon</code> is hand-paintable — its canvas becomes a pixel-by-pixel mask you paint with
        "Paint collision"/"Erase collision" toggle buttons. <code>solid</code>/<code>none</code> use an
        automatic full/empty mask and aren't editable directly.</p>
      </li>
      <li>
        <h3>Commit to the stack</h3>
        <p>"Save to stack" (new tile) or "Replace in stack" (editing an existing slot) commits the buffer.
        "Clear editor" discards it. The bottom tile strip shows every committed tile as a thumbnail — checkbox
        overlays let it preview collision fill / one-way arrows directly on the thumbnails.</p>
      </li>
    </ol>
    <div className="callout">
      <strong>Changing tile size resamples every stacked tile</strong>
      Do this early — changing it later prompts to resample the whole stack, and changing the Palette prompts
      to confirm (indices stay the same, rendered colors change).
    </div>

    <h2>Background Editor</h2>
    <p><strong>New Background…</strong>: Name, "Browse…" to pick a source image (canvas size always matches
    the source — shown live as "W×H px (N.N× screen width)"), Palette, Color key. Reuses the exact same Tool
    enum/canvas as the Sprite Editor (imported directly, not reimplemented).</p>
    <p>An 8px "Segment grid" overlay (on by default) helps line up tile-scale detail; a highlighted rectangle
    driven by a <strong>Camera X</strong> slider previews where the 264×198 game view currently sits on the
    canvas — useful for checking a wide background reads correctly as the camera scrolls across it.</p>
    <p>Resize controls: Width/Height spinboxes + "Resize canvas" (confirms before resampling existing pixels)
    and "Reset to screen" (sets height back to 198px). "Export PNG…" / "Import PNG…" round-trip to an external
    image editor.</p>
    <div className="callout">
      <strong>No parallax preview here</strong>
      This editor only shows where the camera view currently sits — it doesn't simulate scrolling or bands.
      Parallax speed, fixed/repeat, and band-parallax are all configured per scene, in the Scene Editor's
      Backgrounds panel (see <Link to="/studio/object-scene">Object &amp; scene editors</Link>).
    </div>

      <PageNav />
    </>
  )
}
