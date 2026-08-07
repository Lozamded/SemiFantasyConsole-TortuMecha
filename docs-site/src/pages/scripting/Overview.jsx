import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function ScriptingOverview() {
  return (
    <>

    <h1>Scripting API: Overview</h1>
    <p className="subtitle">How a game's code is structured, and the drawing/timing API every script has access to through the engine object.</p>

    <p>A TortoiseMecha game is plain Python — <strong>no subclassing, no engine base classes</strong>. Every
    script (the cart's <code>main.py</code>, an object's script, a GUI layer's script) is just a module with a
    few optional functions that the engine calls by name.</p>

    <div className="callout">
      <strong>Three kinds of script, one convention</strong>
      <code>main.py</code>, object scripts, and GUI layer scripts all follow the same
      <code>init</code> / <code>update</code> / <code>draw</code> shape. This page covers <code>main.py</code>
      and the engine itself; object and GUI layer scripts have their own pages since they run under a
      different loader with extra rules (see the sidebar).
    </div>

    <h2>The main.py hooks</h2>
    <p>All three are optional — the engine checks with <code>hasattr</code> before calling any of them.</p>

    <pre><code>def init(engine):
    ...              # called once, when the game/cart loads

def update(dt):
    ...              # called every frame; dt is seconds since the last frame

def draw(engine):
    ...              # called every frame, after update()</code></pre>

    <p>Unlike object/GUI scripts (see the next pages), <code>main.py</code>'s <code>draw</code> is fully
    functional — it's how a cart actually puts pixels on screen.</p>

    <h2>The TortoiseEngine object</h2>
    <p>Every hook receives (or can reach) a single <code>TortoiseEngine</code> instance
    (<code>tortoisengine/engine.py</code>) — a 264×198 framebuffer with a small drawing API. There is no
    window here; something else (see below) displays the framebuffer each frame.</p>

    <table>
      <tr><th>Member</th><th>Signature</th><th>Behavior</th></tr>
      <tr><td><code>framebuffer</code></td><td>attribute</td><td>The <code>pygame.Surface</code> everything draws onto. Read it directly for advanced blitting.</td></tr>
      <tr><td><code>clock</code></td><td>attribute</td><td>The underlying <code>pygame.time.Clock</code>.</td></tr>
      <tr><td><code>fps</code> / <code>running</code></td><td>attributes</td><td>Mutable; <code>set_fps()</code> is the normal way to change <code>fps</code>.</td></tr>
      <tr><td><code>set_fps(fps)</code></td><td><code>(int) -&gt; None</code></td><td>Clamped to at least 1.</td></tr>
      <tr><td><code>clear(color)</code></td><td><code>((r,g,b)) -&gt; None</code></td><td>Fills the framebuffer with a flat color.</td></tr>
      <tr><td><code>pixel(x, y, color)</code></td><td><code>(int, int, (r,g,b)) -&gt; None</code></td><td>Bounds-checked single-pixel set.</td></tr>
      <tr><td><code>rect(color, rect, width=0)</code></td><td><code>((r,g,b), Rect|tuple, int) -&gt; None</code></td><td>Wraps <code>pygame.draw.rect</code>; <code>width=0</code> fills.</td></tr>
      <tr><td><code>text(text, x, y, color=(255,255,255), font_size=8)</code></td><td>see left</td><td>Draws with pygame's built-in system font — <strong>not</strong> a <code>.tortufont</code>/<code>.tortuspritefont</code> asset. Use a GUI layer text label for real pixel-font text (see the GUI layer scripts page).</td></tr>
      <tr><td><code>blit(surface, pos)</code></td><td><code>(Surface, (int,int)) -&gt; None</code></td><td>Wraps <code>framebuffer.blit</code>.</td></tr>
      <tr><td><code>tick(dt=None)</code></td><td><code>(float|None) -&gt; float</code></td><td>Advances the clock (or accepts a caller-supplied <code>dt</code>), calls <code>update(dt)</code>, returns <code>dt</code>.</td></tr>
      <tr><td><code>render_frame()</code></td><td><code>() -&gt; Surface</code></td><td>Calls <code>draw(engine)</code>, returns the framebuffer.</td></tr>
      <tr><td><code>load_game(module)</code> / <code>unload_game()</code></td><td>—</td><td>Host-loop calls; <code>unload_game()</code> also stops all <code>pygame.mixer</code> playback.</td></tr>
    </table>

    <div className="callout">
      <strong>No input, audio, or camera methods</strong>
      <code>TortoiseEngine</code> is deliberately minimal. Input is read straight from
      <code>pygame.key.get_pressed()</code>, audio goes through <code>tortoisengine.audio</code> (a thin
      wrapper directly on <code>pygame.mixer</code>), and "camera" is just an
      <code>(x, y)</code> pair your own code tracks and passes into the scene renderer. See
      <Link to="/scripting/subsystems">Subsystems</Link> for all three.
    </div>

    <h2>Two ways a game actually runs</h2>
    <p>What calls <code>init</code>/<code>update</code>/<code>draw</code>, and what happens in between, depends
    on how the game was launched:</p>

    <div className="card-grid">
      <div className="card">
        <h3>WindowPlayer — plain project</h3>
        <p><code>tortoiseplayer.player.WindowPlayer</code>. Opens an OS window and drives a bare
        <code>TortoiseEngine</code> loop. <code>main.py</code> is fully responsible for everything —
        loading scenes, rendering, input.</p>
      </div>
      <div className="card">
        <h3>CartScenePlayer — exported .tortucart</h3>
        <p><code>tortoiseplayer.scene_player.CartScenePlayer</code>. Auto-loads the manifest's start scene
        and ticks/renders it itself every frame, calling <code>main.py</code>'s hooks as an overlay on top.
        It also sets <code>engine.cart_root</code> / <code>engine.manifest</code>.</p>
      </div>
    </div>

    <p>In practice, hello_tortu's own <code>main.py</code> doesn't lean on <code>CartScenePlayer</code>'s
    built-in scene handling at all — it drives its own <code>SceneRenderer</code> directly (see
    <Link to="/scripting/objects">Object scripts</Link>) and only checks
    <code>getattr(engine, "cart_root", None)</code> to decide whether assets should be loaded from the exported
    cart or a live project folder. This is the pattern to follow for anything beyond a single static scene.</p>

      <PageNav />
    </>
  )
}
