import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function StudioBuildTest() {
  return (
    <>

    <h1>Build &amp; Test</h1>
    <p className="subtitle">From in-editor playtesting to a standalone executable ready for an SBC.</p>

    <h2>Playtesting without leaving the editor</h2>
    <p>Covered in full on <Link to="/studio/overview">Overview &amp; workflow</Link> — the short version:
    <strong>F5</strong> launches the real game as an external process, <strong>F7</strong> runs it inside the
    Game Preview viewport with a collider/origin debug overlay, and <strong>F6</strong> hot-reloads script
    changes into whichever is currently running.</p>

    <h2>Export .tortucart</h2>
    <p><strong>Build → Export .tortucart…</strong>. Requires a valid start scene (set on the Game Settings
    tab). Pick a destination folder; it writes <code>&lt;cart_name&gt;.tortucart</code> there (prompting to
    overwrite if it already exists), then shows the destination path and the exact
    <code>python -m tortoiseplayer &lt;path&gt;</code> command to run it.</p>
    <p>This is the packaged, played-from-source form — scenes, baked sprite/tileset/background PNGs, and a
    <code>cart.json</code> manifest, runnable directly with <code>tortoiseplayer</code> wherever Python +
    dependencies are already installed.</p>

    <h2>Build Executable…</h2>
    <p><strong>Build → Build Executable…</strong> first asks for the folder containing an already-exported
    <code>.tortucart</code> (export one first if you haven't). It then opens the Build Executable dialog:</p>

    <div className="card-grid">
      <div className="card">
        <h3>Current platform</h3>
        <p>Always available, always checked — builds natively for whatever machine TortoiseStudio itself is
        running on.</p>
      </div>
      <div className="card">
        <h3>ARM64 (via Podman)</h3>
        <p>For Raspberry Pi 4/5, Orange Pi, Radxa 64-bit images. Cross-compiles in a Podman+QEMU container.
        Disabled with a tooltip if the host machine already <em>is</em> ARM64, or if a prerequisite is
        missing.</p>
      </div>
      <div className="card">
        <h3>ARMhf / ARM32 (via Podman)</h3>
        <p>For older/32-bit ARM boards. Same cross-compile mechanism as ARM64.</p>
      </div>
    </div>

    <p>If a cross-compile checkbox is disabled, orange hint text spells out exactly what's missing — matching
    the one-time host setup already documented on <Link to="/get-started/install-sbc">Install on an SBC</Link>:</p>
    <pre><code>Podman not found — sudo apt install podman
Network backend missing — sudo apt install passt
ARM emulation missing — sudo apt install qemu-user-static && sudo systemctl restart systemd-binfmt</code></pre>

    <p>Click <strong>Build</strong> to start; a live log streams into the dialog as each selected architecture
    builds in turn. The button re-enables when done, and <strong>Close</strong> becomes <strong>Done</strong>
    if every build succeeded (it stays "Close" if any failed — check the log for which one and why).</p>

    <p>Each build lands in the cart bundle itself:</p>
    <pre><code>&lt;cart_name&gt;.tortucart/bin/&lt;cart_name&gt;_&lt;arch&gt;</code></pre>

      <PageNav />
    </>
  )
}
