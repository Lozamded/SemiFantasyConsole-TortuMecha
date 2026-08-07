import PageNav from '../../components/PageNav.jsx'

export default function FormatsSpriteTileset() {
  return (
    <>

    <h1>Sprites &amp; Tilesets</h1>
    <p className="subtitle">The two raw pixel-data formats — both store palette-index pixels directly in the JSON, no external images.</p>

    <p>Both formats store pixels as flat, row-major <code>list[int]</code> arrays of palette indices (0–85) —
    not references to PNGs. TortoiseStudio does export preview PNGs alongside them, but those are sidecar
    files the runtime loader never reads.</p>

    <h2>Sprites (.tortusprite)</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>blocks_w</code> / <code>blocks_h</code></td><td>int</td><td>required</td><td>Size in 4px blocks (<code>SPRITE_BLOCK</code>) — pixel size is always <code>blocks_w*4</code> × <code>blocks_h*4</code>. Must be <code>&gt;= 1</code> each.</td></tr>
      <tr><td><code>palette</code></td><td>str</td><td>required</td><td></td></tr>
      <tr><td><code>fps</code></td><td>int</td><td><code>8</code></td><td>Animation playback rate.</td></tr>
      <tr><td><code>frames</code></td><td>list[list[int]]</td><td>required</td><td>One flat pixel-index array per frame, each exactly <code>pixel_width * pixel_height</code> long.</td></tr>
    </table>
    <p>Loading accepts a legacy single-frame <code>"pixels"</code> key (wrapped as one frame) in place of
    <code>"frames"</code>; if neither is present, loading raises. Every frame's length is validated against
    <code>pixel_width * pixel_height</code> — a mismatch raises <code>ValueError</code>. Saving always writes
    the modern <code>"frames"</code> key.</p>
    <pre><code>&#123;
  "blocks_w": 5, "blocks_h": 5, "palette": "default", "fps": 8,
  "frames": [
    [85, 85, 85, ...],   // frame 0, 400 ints (20x20px)
    [85, 85, 2, ...]     // frame 1
  ]
&#125;</code></pre>

    <h2>Tilesets (.tortutileset)</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>palette</code></td><td>str</td><td>required</td><td></td></tr>
      <tr><td><code>tile_size</code></td><td>int</td><td><code>8</code> (<code>TILE_BLOCK</code>)</td><td>Pixel width/height of each square tile.</td></tr>
      <tr><td><code>tiles</code></td><td>list[list[int]]</td><td><code>[]</code></td><td>One flat pixel-index array per tile, each <code>tile_size**2</code> long.</td></tr>
      <tr><td><code>collisions</code></td><td>list[str]</td><td>parallel to <code>tiles</code></td><td>Per-tile collision type — see below.</td></tr>
      <tr><td><code>one_ways</code></td><td>list[str]</td><td>parallel to <code>tiles</code></td><td>Per-tile one-way-platform direction — see below.</td></tr>
      <tr><td><code>collision_shapes</code></td><td>list[list[int]]</td><td>parallel to <code>tiles</code></td><td>Per-tile 0/1 pixel mask, only meaningful for <code>polygon</code> collision.</td></tr>
    </table>
    <p><code>collisions</code>/<code>one_ways</code>/<code>collision_shapes</code> are kept the same length as
    <code>tiles</code> automatically (padded with defaults, or truncated) — every tile index always has
    matching metadata entries.</p>

    <h3>Collision types</h3>
    <table>
      <tr><th>Value</th><th>Meaning</th></tr>
      <tr><td><code>"none"</code></td><td>Not solid. Effective mask is always blank, regardless of any stored <code>collision_shapes</code> entry.</td></tr>
      <tr><td><code>"solid"</code></td><td>Fully solid. Effective mask is always full, regardless of any stored <code>collision_shapes</code> entry.</td></tr>
      <tr><td><code>"polygon"</code></td><td>Solid only where the tile's own <code>collision_shapes</code> mask has a 1 — the only type where that stored array is actually read.</td></tr>
    </table>
    <div className="callout">
      <strong>collision_shapes is dead data for none/solid tiles</strong>
      <code>get_collision_shape()</code> always resolves through the tile's collision <em>type</em> first —
      the raw stored mask is only ever used when the type is <code>"polygon"</code>. A tile can carry a
      leftover polygon mask from editing history while being marked <code>"solid"</code>; it simply won't
      matter at runtime.
    </div>

    <h3>One-way platforms</h3>
    <table>
      <tr><th>Value</th></tr>
      <tr><td><code>"none"</code></td></tr>
      <tr><td><code>"up"</code></td></tr>
      <tr><td><code>"down"</code></td></tr>
      <tr><td><code>"left"</code></td></tr>
      <tr><td><code>"right"</code></td></tr>
    </table>
    <p>Collision type and one-way direction are independent, parallel per-tile fields — a tile can be both
    <code>"solid"</code> and have a one-way direction set at the same time; the value names the direction a
    moving body can pass through <em>from</em> (a typical jump-through platform is one-way <code>"up"</code>).</p>

    <h3>Runtime queries</h3>
    <p><code>get_collision(index)</code> and <code>get_collision_shape(index)</code> both return safe defaults
    (<code>"none"</code> / a blank mask) for an out-of-range index instead of raising — useful since scene
    tile arrays can reference <code>-1</code> (empty) freely. The mutators
    (<code>set_collision</code>/<code>set_one_way</code>/<code>set_collision_shape</code>) do raise
    <code>IndexError</code> for an out-of-range tile index, and <code>ValueError</code> for an unrecognized
    enum string.</p>

    <h3>Legacy sheet format</h3>
    <p>If a tileset file has no <code>"tiles"</code> key, the loader instead expects <code>tiles_w</code>,
    <code>tiles_h</code>, and a flat <code>"pixels"</code> array representing one big tile-sheet image, sliced
    into individual tiles. This legacy path has no way to specify per-tile collision metadata — it's all
    defaulted to <code>"none"</code> after slicing. Saving always writes the modern per-tile shape.</p>

    <h3>Real example</h3>
    <pre><code>&#123;
  "tile_size": 16, "palette": "default",
  "tiles": [ [ ...256 ints... ], ... ],       // 30 tiles
  "collisions": ["solid", "polygon", "none", ...],
  "one_ways": ["none", "none", "up", ...],
  "collision_shapes": [ [ ...256 ints of 0/1... ], ... ]
&#125;</code></pre>

      <PageNav />
    </>
  )
}
