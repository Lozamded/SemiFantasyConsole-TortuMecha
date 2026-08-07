import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function FormatsBackground() {
  return (
    <>

    <h1>Backgrounds (.tortubackground)</h1>
    <p className="subtitle">A single flat pixel canvas — parallax and scroll behavior live on the scene, not here.</p>

    <div className="callout">
      <strong>This asset has no layers or parallax settings of its own</strong>
      A <code>.tortubackground</code> file is just one flat image. Parallax speed, fixed/repeat scrolling, and
      band-parallax are all configured on the <em>scene's</em> background layer that references this asset —
      see <Link to="/formats/scene">Scenes</Link>. The same background image can be reused by multiple scene
      layers with completely different scroll behavior each.
    </div>

    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>palette</code></td><td>str</td><td>required</td><td></td></tr>
      <tr><td><code>width</code> / <code>height</code></td><td>int</td><td>required, min 1×1</td><td>New backgrounds default to <code>SCREEN_WIDTH*2 × SCREEN_HEIGHT</code> (528×198) — double screen width, to give horizontal parallax room to scroll before repeating.</td></tr>
      <tr><td><code>pixels</code></td><td>list[int]</td><td><code>[]</code></td><td>Flat, row-major palette-index array, length <code>width*height</code>.</td></tr>
    </table>

    <pre><code>&#123;"palette": "default", "width": 312, "height": 198, "pixels": [ ...61776 ints... ]&#125;</code></pre>

    <p>If the <code>pixels</code> array's length doesn't match <code>width*height</code> — e.g. after a
    hand-edited resize — it's silently nearest-neighbor resampled to fit on load, not rejected.</p>

    <h2>Legacy multi-layer format</h2>
    <p>Older files may have a <code>bg_layers</code> key instead of <code>pixels</code> — a list of
    <code>&#123;visible, pixels&#125;</code> entries that predates the scene-level parallax-band redesign. On load,
    these are composited into one flat canvas: layers are walked in list order, and <strong>the first layer
    with an opaque pixel at a given position wins</strong> — later layers only fill positions still
    transparent after earlier ones. Saving always writes the modern flat <code>pixels</code> shape; a legacy
    file re-saved through TortoiseStudio loses its original layer separation permanently.</p>

    <h2>How scenes actually scroll it</h2>
    <p>Scroll/parallax/repeat behavior lives in <code>Background</code>'s drawing methods, which the scene
    renderer calls with parameters sourced from the scene's background layer fields (not stored on the
    background asset itself):</p>
    <table>
      <tr><th>Method</th><th>Used for</th></tr>
      <tr><td><code>draw_parallax(camera_x, camera_y, parallax_x, parallax_y, fixed, repeat_x, repeat_y)</code></td><td>Uniform, layer-wide parallax.</td></tr>
      <tr><td><code>draw_parallax_bands(camera_x, camera_y, parallax_y, fixed, bands)</code></td><td>Per-row band parallax, one set of scroll params per <code>SceneBgParallaxBand</code>.</td></tr>
    </table>
    <p><code>fixed=True</code> zeroes the scroll offset entirely (the layer stays pinned regardless of camera
    position); <code>repeat_x</code>/<code>repeat_y</code> wrap the sample coordinate with modulo instead of
    clipping past the image edge.</p>

      <PageNav />
    </>
  )
}
