import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function ScriptingHowItFitsTogether() {
  return (
    <>

    <h1>How It Fits Together</h1>
    <p className="subtitle">TortoiseStudio, the code it generates, and the scripts you write never talk to each other directly in memory — they all agree through the same files on disk. Here's the full loop.</p>

    <p>You've now seen <Link to="/studio/overview">TortoiseStudio</Link>, the editor, and
    <Link to="/formats/overview">File Formats</Link>, the JSON it saves. This page is the missing piece:
    how a value you type into an Object Editor field ends up as something a Python script can actually read
    at runtime — and why there's a code-generation step in between that you're not supposed to touch.</p>

    <h2>Four things, one source of truth</h2>
    <div className="card-grid">
      <div className="card">
        <h3>TortoiseStudio</h3>
        <p>The editor. You author scenes, objects, GUI layers, audio channels — everything covered in the
        TortoiseStudio section.</p>
      </div>
      <div className="card">
        <h3>The asset files</h3>
        <p>What TortoiseStudio actually saves — <code>.tortuobject</code>, <code>.tortuscene</code>, etc. The
        single source of truth. See File Formats.</p>
      </div>
      <div className="card">
        <h3>scripts/_generated/*_auto.py</h3>
        <p>Regenerated automatically from the asset files on every TortoiseStudio save. Never hand-edit these
        — the next save overwrites them.</p>
      </div>
      <div className="card">
        <h3>Your scripts</h3>
        <p><code>main.py</code>, object scripts, GUI layer scripts — the only pieces of this whole loop you
        actually hand-write.</p>
      </div>
    </div>

    <h2>The loop, step by step</h2>
    <ol className="steps">
      <li>
        <h3>You author in TortoiseStudio</h3>
        <p>Say you add a <code>patrol</code> custom variable to a robot prefab in the Object Editor, and give
        it a default value of <code>false</code>.</p>
      </li>
      <li>
        <h3>TortoiseStudio saves the asset file</h3>
        <p>That declaration is written into <code>assets/objects/robot.tortuobject</code> as a
        <code>custom_vars</code> entry — <code>&#123;"name": "patrol", "type": "bool", "default": false&#125;</code>.
        This is the format documented on <Link to="/formats/object">Objects</Link>.</p>
      </li>
      <li>
        <h3>TortoiseStudio regenerates the _auto.py sidecar — same save, no extra step</h3>
        <p><code>tortoisengine/script_codegen.py</code> reads that same file and (re)writes
        <code>scripts/_generated/robot_auto.py</code> with constants like
        <code>CUSTOMVAR_PATROL = "patrol"</code> and <code>CUSTOMVAR_PATROL_DEFAULT = False</code> — a typo-safe
        handle onto the exact string key you'd otherwise have to spell out by hand.</p>
      </li>
      <li>
        <h3>Your script imports the generated constant</h3>
        <pre><code>from tortoisengine import instance_api
from scripts._generated import robot_auto as auto

def update(dt):
    patrol = instance_api.custom_var(SELF_ID, auto.CUSTOMVAR_PATROL, auto.CUSTOMVAR_PATROL_DEFAULT)
    if patrol:
        ...</code></pre>
        <p>Nothing here is hand-typed as a bare string — if you rename the custom var in TortoiseStudio, the
        next save regenerates <code>auto.CUSTOMVAR_PATROL</code> to match, and your script fails loudly at
        import time instead of silently reading the wrong key.</p>
      </li>
      <li>
        <h3>instance_api resolves it against the live scene</h3>
        <p>At runtime, <code>instance_api.custom_var()</code> looks up this specific placed instance's
        override (set per-instance back in the <Link to="/studio/object-scene">Scene Editor</Link>) and
        falls back to the prefab's own default — the same default your script imported from the generated
        module. See <Link to="/scripting/objects">Object scripts</Link> for the full <code>instance_api</code> reference.</p>
      </li>
    </ol>

    <img className="shot" src="/assets/screenshots/demo-04-object-editor.png" alt="Object Editor showing the Custom Variables section on the right, with a Variable combo, Name field, Type dropdown, Array checkbox, and Default value field." />
    <p className="shot-caption">This Custom Variables panel is where step 1 happens — the field a scripter never has to hand-type a key for.</p>

    <div className="callout">
      <strong>Never hand-edit scripts/_generated/*_auto.py</strong>
      Every file in that folder is overwritten the next time TortoiseStudio saves the project it belongs to.
      If you need a constant that isn't generated, define it in your own script file instead — don't add to
      the generated one.
    </div>

    <h2>The same pattern shows up everywhere</h2>
    <p>Custom variables are one instance of a rule that runs through the whole engine: whenever a script needs
    to reference something you set up visually, there's a generated constant for it instead of a hand-typed
    string or number.</p>
    <table>
      <tr><th>You set this up in...</th><th>Saved as...</th><th>Generated as...</th><th>Your script uses...</th></tr>
      <tr><td>Object Editor — animations</td><td><code>.tortuobject</code></td><td><code>ANIM_&lt;NAME&gt;</code>, <code>DEFAULT_ANIMATION</code></td><td><code>instance_api.set_animation(SELF_ID, auto.ANIM_WALK)</code></td></tr>
      <tr><td>Object Editor — colliders</td><td><code>.tortuobject</code></td><td><code>COLLIDER_&lt;NAME&gt;</code></td><td>Passed into collider-lookup helpers instead of a bare string.</td></tr>
      <tr><td>Scene Editor — object ID field</td><td><code>.tortuscene</code></td><td><code>OBJ_&lt;ID&gt;</code> in the scene's own <code>_auto.py</code></td><td>Cross-referencing a specific placed instance from another script.</td></tr>
      <tr><td>Scene Editor — Links field</td><td><code>.tortuscene</code></td><td><code>LINKS_&lt;ID&gt;</code></td><td>Same idea, for the linked-instance list injected as your script's <code>LINKS</code> global.</td></tr>
      <tr><td>Sound Editor — audio channels</td><td><code>tortu.project</code></td><td>Fixed path <code>scripts/_generated/audio_auto.py</code>: <code>CHANNEL_&lt;NAME&gt;</code>, <code>AUDIO_CHANNELS</code></td><td><code>audio.set_channel_volume(auto.CHANNEL_GAME_SFX, value)</code></td></tr>
    </table>
    <p>Full field-by-field detail on each generated module is on the <Link to="/scripting/objects">Object scripts</Link>
    page.</p>

    <h2>Where SELF_ID and LINKS actually come from</h2>
    <p>One more thing this loop explains: <code>SELF_ID</code> and <code>LINKS</code>, the two globals every
    object/GUI-layer script gets without an import (see <Link to="/scripting/objects">Object scripts</Link>), aren't
    magic either. <code>SELF_ID</code> is literally the <code>id</code> field you typed into that instance's
    card in the Scene Editor; <code>LINKS</code> is that card's Links field, or another card's header dragged
    onto it. TortoiseStudio writes both into the <code>.tortuscene</code> file
    (<Link to="/formats/scene">Scenes</Link>), and <code>tortoisengine/instance_scripts.py</code> reads them
    straight back out at load time to inject into your script's module namespace — no generated file involved
    for these two, since they're per-instance rather than per-prefab.</p>

    <h2>Where to go from here</h2>
    <p>The rest of this section is the API reference for the "your scripts" box above — what hooks exist,
    what <code>instance_api</code> can do, and how each subsystem (dialogue, save data, audio, camera) fits
    into scripts you write by hand.</p>

      <PageNav />
    </>
  )
}
