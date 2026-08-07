import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function FormatsObject() {
  return (
    <>

    <h1>Objects (.tortuobject)</h1>
    <p className="subtitle">The prefab format: animations, collision boxes, and custom variables for anything placed in a scene.</p>

    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>required</td><td></td></tr>
      <tr><td><code>animations</code></td><td>list</td><td>required, non-empty</td><td><code>save_object()</code> raises if empty. Soft limit 16 (<code>MAX_OBJECT_ANIMATIONS</code>) — <strong>not enforced</strong> by load/save.</td></tr>
      <tr><td><code>default_animation</code></td><td>str</td><td><code>""</code></td><td>Falls back to the first animation's name if it doesn't match any declared one.</td></tr>
      <tr><td><code>script</code></td><td>str</td><td><code>""</code></td><td>See the <Link to="/scripting/objects">Object scripts</Link> page.</td></tr>
      <tr><td><code>solid</code></td><td>bool</td><td><code>false</code></td><td>Default collision-solidity for every placed instance; overridable per-instance via <code>instance_api.set_object_solid()</code>.</td></tr>
      <tr><td><code>origin</code></td><td>object</td><td><code>&#123;x:0,y:0&#125;</code></td><td>Placement anchor in sprite pixel space. Omitted from JSON when <code>(0,0)</code>.</td></tr>
      <tr><td><code>colliders</code></td><td>list</td><td><code>[&#123;name:"main"&#125;]</code></td><td>Always at least one after loading — see below. Soft limit 8 (<code>MAX_OBJECT_COLLIDERS</code>), not enforced.</td></tr>
      <tr><td><code>spawnable_objects</code></td><td>list[str]</td><td><code>[]</code></td><td>Other <code>.tortuobject</code> paths this prefab may spawn at runtime (e.g. a bullet) but that are never placed directly in a scene — listed so the cart exporter doesn't miss their assets.</td></tr>
      <tr><td><code>custom_vars</code></td><td>list</td><td><code>[]</code></td><td>Soft limit 16 (<code>MAX_OBJECT_CUSTOM_VARS</code>), not enforced.</td></tr>
    </table>

    <p><code>default_sprite</code> is a computed property, not a stored field — it resolves through
    <code>default_animation</code> first, falling back to the first animation's sprite.</p>

    <h2>Animations</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>required, no default</td></tr>
      <tr><td><code>sprite</code></td><td>str</td><td>required, no default — path to a <code>.tortusprite</code></td></tr>
    </table>

    <h2>Colliders</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>required</td><td></td></tr>
      <tr><td><code>x</code> / <code>y</code></td><td>int</td><td><code>0</code></td><td>Offset in sprite pixel space.</td></tr>
      <tr><td><code>w</code> / <code>h</code></td><td>int</td><td><code>0</code></td><td>See below.</td></tr>
      <tr><td><code>active</code></td><td>bool</td><td><code>true</code></td><td>Default state at spawn.</td></tr>
    </table>
    <div className="callout">
      <strong>w/h of 0 means "track the sprite's current size"</strong>
      <code>ObjectCollider.resolved(sprite_w, sprite_h)</code> substitutes the current animation frame's pixel
      dimensions whenever the stored <code>w</code>/<code>h</code> is <code>&lt;= 0</code>. A collider with
      <code>w:0, h:0</code> isn't a zero-size box — it dynamically tracks whatever sprite is currently showing.
      Set an explicit positive <code>w</code>/<code>h</code> for a fixed-size hitbox independent of the art.
    </div>

    <h2>Custom variables</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>name</code></td><td>str</td><td>required</td><td>Looked up at runtime via <code>instance_api.custom_var(instance_id, name, default)</code>.</td></tr>
      <tr><td><code>type</code></td><td>str</td><td><code>"float"</code></td><td>One of <code>float</code>, <code>int</code>, <code>string</code>, <code>bool</code> (<code>CUSTOM_VAR_TYPES</code>).</td></tr>
      <tr><td><code>is_array</code></td><td>bool</td><td><code>false</code></td><td></td></tr>
      <tr><td><code>default</code></td><td>varies</td><td><code>0.0</code></td><td>Coerced to the declared type on load via <code>.coerce()</code>.</td></tr>
    </table>
    <p>A per-instance override for a custom var lives on the <em>scene</em> object placement, not here — see
    <code>custom_var_overrides</code> on <Link to="/formats/scene">Scenes</Link>.</p>

    <h2>Legacy compat on load</h2>
    <ul>
      <li>If <code>animations</code> is empty/missing, a legacy top-level <code>sprite</code> key is wrapped
      into a single <code>"idle"</code> animation. If neither exists, loading raises <code>ValueError</code>.</li>
      <li>A legacy <code>hitbox: &#123;x, y, w, h&#125;</code> dict (instead of a <code>colliders</code> list) is
      converted into a single collider named <code>"main"</code>.</li>
      <li>If <code>colliders</code> ends up empty either way, a default <code>[ObjectCollider("main")]</code>
      is injected — <strong>a loaded object prefab always has at least one collider.</strong></li>
    </ul>

    <h2>Real example</h2>
    <p>From <code>examples/hello_tortu/assets/objects/mechaturtle.tortuobject</code> — multiple animations,
    two named colliders, a spawnable prefab, and a float custom var:</p>
    <pre><code>&#123;
  "name": "mechaturtle",
  "animations": [
    &#123;"name": "idle", "sprite": "assets/sprites/mechaturtle_idle.tortusprite"&#125;,
    &#123;"name": "walk", "sprite": "assets/sprites/mechaturtle_walk.tortusprite"&#125;,
    &#123;"name": "jump", "sprite": "assets/sprites/mechaturtle_jump.tortusprite"&#125;
  ],
  "default_animation": "idle",
  "script": "scripts/mechaturtle_player.py",
  "solid": true,
  "colliders": [
    &#123;"name": "body", "x": 4, "y": 8, "w": 8, "h": 12&#125;,
    &#123;"name": "head", "x": 4, "y": 0, "w": 8, "h": 8&#125;
  ],
  "spawnable_objects": ["assets/objects/bullet.tortuobject"],
  "custom_vars": [
    &#123;"name": "move_speed", "type": "float", "default": 40.0&#125;
  ]
&#125;</code></pre>

      <PageNav />
    </>
  )
}
