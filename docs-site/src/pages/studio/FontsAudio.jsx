import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function StudioFontsAudio() {
  return (
    <>

    <h1>Font &amp; Audio Editors</h1>
    <p className="subtitle">Text rendering and the project's audio channel setup.</p>

    <h2>Font Editor</h2>
    <p>One widget, two tabs — <strong>Text fonts</strong> (TTF-baked) and <strong>Sprite fonts</strong>
    (hand-painted). See <Link to="/formats/fonts">Fonts</Link> for the on-disk difference between the two.</p>

    <h3>Text fonts tab</h3>
    <p><strong>New Text Font…</strong>: Name, "Browse TTF…" (required — <code>.ttf</code>/<code>.otf</code>),
    Size (px), Line height, Charset (Latin-1 / ASCII / Custom), Bake palette. The chosen TTF is copied into the
    project's <code>assets/fonts/</code> folder.</p>
    <p>The editor shows the installed TTF path (read-only, "Change TTF…" to swap it), Size, Line height,
    Charset preset (+ a Custom-chars text box when Charset = Custom), Bake palette, and a "Rebuild glyphs"
    button — though glyphs also re-bake automatically whenever size/charset/palette changes.</p>
    <p>Preview: a scaled 264×198 "console screen" mockup with a cyan frame marking the real game viewport
    bounds, live preview text, and a palette swatch row to pick the preview's ink color (cosmetic only — real
    glyphs are baked bitmaps, this doesn't change them).</p>

    <h3>Sprite fonts tab</h3>
    <p><strong>New Sprite Font…</strong>: Name, Glyph blocks wide/tall (block-quantized like sprites — a live
    pixel-size readout), Palette. New fonts start pre-populated with the base charset (A–Z, a–z, 0–9, space,
    common HUD punctuation).</p>
    <p>A left-side tab switches between the same console-preview mockup and an "Import image" tab (paste a
    glyph sheet, pick a cell, "Load to Glyph" for one character or "Import All Glyphs" to bulk-import
    left-to-right/top-to-bottom). The glyph itself is hand-painted on a small pixel canvas with the usual
    Pencil/Eraser/Eyedropper set.</p>
    <p>Sidebar: Name, Glyph blocks W/H (resize prompts confirmation), Line height, Default advance, "Add
    character" (type one character, e.g. <code>ñ</code>) / "Remove character" (base charset characters can't
    be removed), Palette, Preview text/zoom, and a "Find character" filter over the full glyph list — each
    glyph shown as a thumbnail icon you click to load into the canvas.</p>

    <h2>Sound Editor</h2>
    <div className="callout">
      <strong>There's no .tortusound asset</strong>
      This editor doesn't create per-sound asset files — it manages the project's audio <em>channels</em>
      (persisted straight into <code>tortu.project</code>'s <code>audio_channels</code>/
      <code>audio_channel_map</code>, see <Link to="/formats/overview">Project &amp; palette</Link>) and lets
      you import raw <code>.ogg</code>/<code>.midi</code> files into <code>assets/audio/</code>.
    </div>
    <p>An <strong>Audio Channels</strong> list (max 12) with +/− to add/remove channels and double-click to
    rename — this is what populates the generated <code>CHANNEL_*</code> constants scripts import (see
    <Link to="/scripting/subsystems">Subsystems</Link>).</p>
    <p>Below that, two tabs:</p>
    <ul>
      <li><strong>Music Creator</strong> — not implemented yet ("Coming soon" placeholder for a future
      step-sequencer/tracker).</li>
      <li><strong>Import Audio</strong> — a table of every audio file already in <code>assets/audio/</code>
      with a per-file Channel assignment combo. "Import audio file…" copies new files in; "Remove selected"
      deletes them from disk (with a confirmation).</li>
    </ul>
    <p>"Save audio channels" writes the channel list and file→channel assignments to
    <code>tortu.project</code> and regenerates <code>scripts/_generated/audio_auto.py</code> — nothing on this
    tab auto-saves.</p>

      <PageNav />
    </>
  )
}
