import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function FormatsDialogue() {
  return (
    <>

    <h1>Dialogues (dialogues/*.json)</h1>
    <p className="subtitle">Branching, localized conversations — a pure data model with a generic action system. tortoisengine.dialogue only loads and saves it; a project's own GUI layer script (typically dialoguebox.py) decides how to display it and what each action actually does.</p>

    <p>A dialogue is a flat, ordered list of lines. A line always shows its <code>speaker</code>/<code>text</code>;
    it may also carry an <code>action</code> (runs when the line is dismissed) and/or <code>options</code>
    (turns it into a decision point instead of auto-advancing). See
    <Link to="/scripting/subsystems">Subsystems</Link> for how a script requests and steps through a dialogue
    at runtime.</p>

    <h2>DialogueLine</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>speaker</code></td><td>str</td><td><code>""</code></td><td></td></tr>
      <tr><td><code>text</code></td><td>str</td><td><code>""</code></td><td>A literal string, or a <code>[&lt;[key]&gt;]</code> placeholder into <code>translations/*.csv</code> — see below.</td></tr>
      <tr><td><code>icon</code></td><td>str</td><td><code>""</code></td><td>Optional sprite path; not interpreted by the engine, purely for the display script to use.</td></tr>
      <tr><td><code>id</code></td><td>str</td><td><code>""</code></td><td>Lets a <code>jumpdialog</code> action target this line. May be declared anywhere in the file, including after the line that jumps to it.</td></tr>
      <tr><td><code>options</code></td><td>list[DialogueOption]</td><td><code>[]</code></td><td>Non-empty turns this line into a decision point.</td></tr>
      <tr><td><code>action</code></td><td>Action | None</td><td><code>None</code></td><td>See Actions below. Runs when the line is dismissed (a plain line) or, for a decision line, after whichever option was picked.</td></tr>
    </table>

    <h2>DialogueOption</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Default</th><th>Notes</th></tr>
      <tr><td><code>text</code></td><td>str</td><td><code>""</code></td><td>Same <code>[&lt;[key]&gt;]</code>-or-literal convention as a line's <code>text</code>.</td></tr>
      <tr><td><code>action</code></td><td>Action | None</td><td><code>None</code></td><td>Runs when this option is picked, before the decision line's own <code>action</code>. Use <code>changedialog</code> here to jump to another dialogue file on selection.</td></tr>
    </table>

    <div className="callout">
      <strong>No separate "next dialogue" field</strong>
      An option only carries <code>action</code> — jumping to another dialogue file is just a
      <code>changedialog</code> action like any other, not a distinct field. This keeps every way a dialogue can
      redirect flow (<code>jumpdialog</code>, <code>changedialog</code>, <code>finishdialog</code>) going through
      the same <code>Action</code> envelope instead of a parallel mechanism.
    </div>

    <h2>Actions</h2>
    <p>An <code>Action</code> is a <code>type</code> + free-form <code>content</code> dict. On disk it's an
    envelope on the line or option itself:</p>
    <pre><code>&#123;
  "action": true,
  "type": "&lt;type&gt;",
  "action_content": &#123; ... &#125;
&#125;</code></pre>
    <p>An absent or <code>false</code> <code>"action"</code> key means no action (loads as <code>None</code>);
    <code>action_content</code> is then omitted too. <code>type</code>/<code>content</code> are conventions —
    <code>tortoisengine.dialogue</code> just carries them through unchanged; the display script decides what each
    one does. <code>var_set</code> and <code>do_action</code> are pure side effects; the rest redirect control
    flow (skip the default next-line advance):</p>
    <table>
      <tr><th>Type</th><th><code>action_content</code></th><th>Typical effect</th></tr>
      <tr><td><code>var_set</code></td><td><code>&#123;"var": "&lt;name&gt;", "value": &lt;literal&gt;&#125;</code></td><td>Assigns <code>value</code> to <code>&lt;name&gt;</code> on the dialogue's paired vars module.</td></tr>
      <tr><td><code>do_action</code></td><td><code>&#123;"function": "&lt;name&gt;", "value": [&lt;arg&gt;, ...]&#125;</code></td><td>Calls <code>&lt;name&gt;</code> on the vars module with positional args; each arg is <code>&#123;"type": "literal", "value": &lt;v&gt;&#125;</code> (default) or <code>&#123;"type": "var", "value": "&lt;name&gt;"&#125;</code> (read from the vars module at call time).</td></tr>
      <tr><td><code>jumpdialog</code></td><td><code>&#123;"id": "&lt;line id&gt;"&#125;</code></td><td>Jumps to the line with that <code>id</code> within the <em>same</em> file.</td></tr>
      <tr><td><code>changedialog</code></td><td><code>&#123;"path": "dialogues/foo.json"&#125;</code></td><td><code>jumpdialog</code>'s cross-file sibling: ends this file's line sequence and starts <code>path</code> from its first line.</td></tr>
      <tr><td><code>finishdialog</code></td><td><code>&#123;&#125;</code></td><td>Ends the dialogue immediately.</td></tr>
      <tr><td><code>var_compare_text</code></td><td><code>&#123;"var": "&lt;name&gt;", "values": &#123;&lt;value&gt;: &lt;action&gt;, ...&#125;&#125;</code></td><td>Reads <code>&lt;name&gt;</code> from the vars module and runs the nested action envelope keyed by its current value. No match runs nothing.</td></tr>
      <tr><td><code>var_compare_number</code></td><td><code>&#123;"var": "&lt;name&gt;", "cases": [&#123;"op": "&lt;op&gt;", "threshold": &lt;number&gt;, "action": &lt;action&gt;&#125;, ...], "default": &lt;action&gt;&#125;</code></td><td>Reads <code>&lt;name&gt;</code>, coerces it to a number, and walks <code>cases</code> in order — the first whose <code>op</code> (<code>&lt;</code>, <code>&lt;=</code>, <code>==</code>, <code>!=</code>, <code>&gt;=</code>, <code>&gt;</code>) holds against <code>threshold</code> runs its nested action. No match falls through to <code>default</code>.</td></tr>
    </table>

    <div className="callout">
      <strong>A "vars module" is a plain per-project script, not an engine concept</strong>
      <code>tortoisengine.dialogue</code> and <code>tortoisengine.localization</code> never import a specific vars
      module — a display script like <code>dialoguebox.py</code> reads/writes it via
      <code>getattr</code>/<code>setattr</code> on whatever module it imports (by convention, <code>dialogues/
      foo.json</code> paired with <code>scripts/foo_vars.py</code>). A variable exposed to a
      <code>[var&lt;[name]&gt;]</code> text placeholder (see below) is usually a zero-arg function so it reads
      live state — reading it for an action comparison must call it the same way, or the comparison silently
      sees the function object itself instead of its value.
    </div>

    <p>A nested action inside <code>var_compare_text</code>/<code>var_compare_number</code> is the same
    envelope shape, not the <code>Action</code> dataclass directly — e.g. a "do nothing" case is
    <code>&#123;"action": false&#125;</code>.</p>

    <h2>Text and translation keys</h2>
    <p>A line's or option's <code>text</code> is either a literal string, or a single
    <code>[&lt;[key]&gt;]</code> placeholder resolved through <code>translations/*.csv</code> (see
    <Link to="/scripting/subsystems">Subsystems → Localization</Link> for the runtime API). Each CSV has a
    header row of language codes and one data row per key; every CSV in the folder merges into one lookup
    table, so a key can live in whichever file makes sense — callers never need to know which one. A cell can
    also embed <code>[var&lt;[name]&gt;]</code> (live state from the bound vars module) or
    <code>[symbol&lt;[comma]&gt;]</code> (a literal comma, since a real one would split the CSV column).</p>

    <div className="callout">
      <strong>TortoiseStudio auto-files new translation keys per dialogue</strong>
      The Dialogues tab's line editor splits <code>text</code> into a small translation-key field, a language
      picker, and a content box bound to that (key, language) cell — editing the content box writes straight
      into the CSV. An existing key always keeps living wherever it already is (including a hand-managed file
      like <code>GUI.csv</code>); a brand-new key is filed under <code>translations/&lt;dialogue file stem&gt;.csv</code>
      with no prompt, spilling into <code>_part2.csv</code>, <code>_part3.csv</code>, etc. once one file passes
      200 keys — so a translator working through one CSV sees one scene's lines together.
    </div>

    <h2>Example</h2>
    <pre><code>&#123;
  "lines": [
    &#123; "speaker": "Robot3", "text": "[&lt;[r3_l2_d3]&gt;]",
      "action": true, "type": "var_compare_number",
      "action_content": &#123;
        "var": "gears",
        "cases": [
          &#123;"op": "&gt;", "threshold": 24, "action":
            &#123;"action": true, "type": "jumpdialog", "action_content": &#123;"id": "morethan24"&#125;&#125;&#125;,
          &#123;"op": "&lt;", "threshold": 24, "action":
            &#123;"action": true, "type": "jumpdialog", "action_content": &#123;"id": "lessthan24"&#125;&#125;&#125;
        ],
        "default": &#123;"action": false&#125;
      &#125;
    &#125;,
    &#123; "speaker": "Robot3", "id": "morethan24", "text": "[&lt;[r3_l2_d3_gt24]&gt;]" &#125;,
    &#123; "speaker": "Robot3", "id": "lessthan24", "text": "[&lt;[r3_l2_d3_lt24]&gt;]" &#125;
  ]
&#125;</code></pre>
    <p>A decision line with two options, one of which jumps to another file on selection:</p>
    <pre><code>&#123; "speaker": "mechaturtle", "text": "[&lt;[mt_d1]&gt;]",
  "options": [
    &#123; "text": "[&lt;[mt_d1_o1]&gt;]", "action": true, "type": "changedialog",
      "action_content": &#123;"path": "dialogues/robot1_lvl1_2.json"&#125; &#125;,
    &#123; "text": "[&lt;[mt_d1_o2]&gt;]" &#125;
  ]
&#125;</code></pre>

      <PageNav />
    </>
  )
}
