import PageNav from '../../components/PageNav.jsx'

export default function InstallSbc() {
  return (
    <>

    <h1>Install on an SBC</h1>
    <p className="subtitle">Run a built game on a Raspberry Pi, Orange Pi, Radxa, or similar ARM board — no Python required on the device.</p>

    <p>TortoiseMecha targets low-spec ARM boards with as little as 1&nbsp;GB of RAM. The recommended way to run a
    game there is to <strong>build a standalone executable on a desktop machine</strong> and copy it to the board,
    rather than installing Python and the full toolchain on the SBC itself. The executable bundles Python, pygame,
    and numpy, so the device only needs to run one file.</p>

    <div className="callout">
      <strong>What you need before starting</strong>
      An x86-64 desktop/laptop with TortoiseStudio set up (see the readme's
      <code>Build Executables</code> section for the one-time Podman/QEMU setup), and a Raspberry Pi OS
      (or other Debian-based) image already flashed and reachable on the SBC.
    </div>

    <h2>Overview</h2>
    <p>The flow has three parts:</p>
    <ol>
      <li>Build a standalone executable for the SBC's CPU architecture, on your desktop.</li>
      <li>Copy the resulting <code>.tortucart</code> folder to the SBC.</li>
      <li>Run the binary on the SBC.</li>
    </ol>

    <h2>Step by step</h2>
    <ol className="steps">
      <li>
        <h3>Check the SBC's architecture</h3>
        <p>SSH into the board (or open a terminal on it) and run:</p>
        <pre><code>uname -m</code></pre>
        <table>
          <tr><th><code>uname -m</code> output</th><th>Build target</th></tr>
          <tr><td><code>aarch64</code></td><td><code>arm64</code> — most 64-bit Raspberry Pi OS, Orange Pi, and Radxa images</td></tr>
          <tr><td><code>armv7l</code> / <code>armv6l</code></td><td><code>armhf</code> — 32-bit Raspberry Pi OS, older boards (e.g. Pi Zero, Pi 1/2)</td></tr>
        </table>
      </li>

      <li>
        <h3>Build the executable in TortoiseStudio</h3>
        <p>On your desktop machine, open the project in TortoiseStudio, then go to
        <strong>Build &gt; Build Executable</strong> and check the box matching the architecture from step 1
        (<strong>ARM64</strong> or <strong>ARMhf</strong>). This cross-compiles inside a Podman container using
        QEMU emulation — it can take a few minutes the first time while dependencies install in the container.</p>
        <p>The finished binary is written into the cart bundle at:</p>
        <pre><code>&lt;project&gt;/builds/&lt;cart_name&gt;.tortucart/bin/&lt;cart_name&gt;_&lt;arch&gt;</code></pre>
        <p>For example: <code>hello_tortu.tortucart/bin/hello_tortu_arm64</code>.</p>
      </li>

      <li>
        <h3>Copy the cart bundle to the SBC</h3>
        <p>Copy the whole <code>&lt;cart_name&gt;.tortucart</code> folder — not just the binary — since the
        executable loads its scenes and assets as relative files next to it. Over the network:</p>
        <pre><code>scp -r hello_tortu.tortucart pi@&lt;sbc-ip&gt;:/home/pi/games/</code></pre>
        <p>A USB drive or SD card works just as well if the board isn't networked yet.</p>
      </li>

      <li>
        <h3>Make the binary executable and run it</h3>
        <p>On the SBC:</p>
        <pre><code>cd ~/games/hello_tortu.tortucart/bin
chmod +x hello_tortu_arm64
./hello_tortu_arm64</code></pre>
        <p>The game launches fullscreen by default, auto-fitting the largest integer pixel scale that fits the
        board's display so pixels stay crisp.</p>
      </li>
    </ol>

    <h2>Troubleshooting</h2>

    <h3>The binary won't launch, or exits immediately</h3>
    <p>Run it from a terminal (not a file manager double-click) to see the error output. A missing shared
    library on a minimal/Lite image is the most common cause — install the SDL2 runtime libraries:</p>
    <pre><code>sudo apt install libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0</code></pre>

    <h3>"Permission denied" when running the binary</h3>
    <p>The executable bit doesn't survive some transfer methods (e.g. certain USB filesystems). Re-run
    <code>chmod +x</code> on the SBC after copying.</p>

    <h3>No display / running headless (no desktop session)</h3>
    <p>pygame needs a video backend. On a Raspberry Pi OS Lite image without a desktop session, set the SDL
    driver to use the kernel mode-setting backend before launching:</p>
    <pre><code>SDL_VIDEODRIVER=kmsdrm ./hello_tortu_arm64</code></pre>

    <h3>Wrong architecture ("cannot execute binary file")</h3>
    <p>The build doesn't match the board — recheck <code>uname -m</code> and rebuild with the matching
    checkbox in <strong>Build &gt; Build Executable</strong>.</p>

      <PageNav />
    </>
  )
}
