import PageNav from '../../components/PageNav.jsx'

export default function CartReader() {
  return (
    <>

    <h1>Physical cart reader</h1>
    <p className="subtitle">Insert a USB drive or microSD card so <code>launcher.py</code> can boot a <code>.tortucart</code> straight off it — plain USB storage (recommended) or a card wired to the SBC's SPI pins.</p>

    <p>This is the physical-cartridge path: instead of copying a <code>.tortucart</code> folder into
    <code>~/console/cart/</code>, you insert removable storage — a USB flash drive, a USB microSD adapter, or
    a card wired to SPI — and the kernel turns it into a normal block device. <code>sdcart_reader.py</code>
    mounts it and looks for a cart on it; <code>launcher.py</code> checks that path automatically if no local
    cart is found.</p>

    <div className="callout">
      <strong>Check this before wiring anything</strong>
      The SPI route below only works if your kernel actually ships the <code>mmc_spi</code> driver. Run
      <code>modinfo mmc_spi</code> on the board first — if it errors with "not found", your kernel doesn't
      have it (confirmed missing on a <code>6.18.35-current-sunxi64</code> Orange Pi Zero 2W build: overlay
      loaded fine, SPI bus registered the child device, and nothing ever bound because the driver simply
      isn't there). If that's you, skip straight to the <a href="#usb-reader">USB storage</a> section
      below instead — no overlay, no wiring, no kernel gamble.
    </div>

    <div className="callout">
      <strong>Board-specific</strong>
      The SPI steps below cover the two Armbian boards this has been wired up for so far: the
      <strong>Orange Pi Zero</strong> (Allwinner H2+/H3) and the <strong>Orange Pi Zero 2W</strong>
      (Allwinner H616/H618) — they need different overlay files since the SoC and SPI bus differ. Raspberry
      Pi or Radxa boards follow the same general flow, but need their own overlay targeting that SoC.
    </div>

    <h2 id="usb-reader">USB storage (recommended)</h2>
    <p>Plug a generic USB microSD adapter — or just a plain USB flash drive, no microSD involved at all —
    into any USB port on the SBC. The kernel's built-in <code>usb-storage</code> driver handles either one
    identically, automatically: no overlay, no device tree, no wiring, and no dependency on whether your
    specific kernel build includes <code>mmc_spi</code>. It shows up as a normal partition (e.g.
    <code>/dev/sda1</code>) the moment it's inserted:</p>
    <pre><code>dmesg | tail
lsblk</code></pre>
    <p><code>sdcart_reader.py</code> already recognizes both SPI-attached (<code>mmcblkN</code>) and
    USB-attached (<code>sdX</code>) card/drive partitions, so no config changes are needed — just run it:</p>
    <pre><code>sudo python3 sdcart_reader.py</code></pre>
    <p>This is the simpler, more reliable path for most setups, and a plain USB flash drive is arguably
    more "cartridge-like" anyway — just drop a <code>.tortucart</code> folder on it and plug it in. The SPI
    wiring route below is only worth doing if you specifically want a microSD card built into an enclosure
    without a free USB port, or if you're targeting a board/kernel combo you've already confirmed has
    working <code>mmc_spi</code> support.</p>

    <h2>Hardware (SPI route)</h2>
    <p>A generic SPI microSD breakout board (e.g. an "IC303K"-style reader) with six pins: <code>3V3</code>,
    <code>GND</code>, <code>CS</code>, <code>MOSI</code>, <code>MISO</code>, <code>CLK</code>. There's no
    onboard controller chip — the SBC's kernel speaks the SD-over-SPI protocol directly via
    <code>mmc_spi</code>.</p>

    <table>
      <tr><th>Board</th><th>SoC</th><th>Overlay file</th><th>Bus</th></tr>
      <tr><td>Orange Pi Zero</td><td>Allwinner H2+/H3</td><td><code>sun8i-h3-spi-mmc.dts</code></td><td>spi0</td></tr>
      <tr><td>Orange Pi Zero 2W</td><td>Allwinner H616/H618</td><td><code>sun50i-h616-spi-mmc.dts</code></td><td>spi1</td></tr>
    </table>
    <p>Both boards happen to expose their SPI bus at the same physical header pins (1, 19, 20, 21, 23, 24,
    25) — only the GPIO port letters and bus number differ between them.</p>

    <h2>Wiring</h2>
    <p><strong>Orange Pi Zero</strong> (26-pin header):</p>
    <table>
      <tr><th>Reader pin</th><th>Header pin</th><th>Signal</th></tr>
      <tr><td><code>VCC</code></td><td>1</td><td>3.3V</td></tr>
      <tr><td><code>GND</code></td><td>20 or 25</td><td>GND</td></tr>
      <tr><td><code>MOSI</code></td><td>19</td><td>PC0 / SPI0_MOSI</td></tr>
      <tr><td><code>MISO</code></td><td>21</td><td>PC1 / SPI0_MISO</td></tr>
      <tr><td><code>CLK</code></td><td>23</td><td>PC2 / SPI0_SCLK</td></tr>
      <tr><td><code>CS</code></td><td>24</td><td>PC3 / SPI0_CS0</td></tr>
    </table>
    <p><strong>Orange Pi Zero 2W</strong> (40-pin header):</p>
    <table>
      <tr><th>Reader pin</th><th>Header pin</th><th>Signal</th></tr>
      <tr><td><code>VCC</code></td><td>1</td><td>3.3V</td></tr>
      <tr><td><code>GND</code></td><td>20 or 25</td><td>GND</td></tr>
      <tr><td><code>MOSI</code></td><td>19</td><td>PH7 / SPI1_MOSI</td></tr>
      <tr><td><code>MISO</code></td><td>21</td><td>PH8 / SPI1_MISO</td></tr>
      <tr><td><code>CLK</code></td><td>23</td><td>PH6 / SPI1_CLK</td></tr>
      <tr><td><code>CS</code></td><td>24</td><td>PH5 / SPI1_CS0</td></tr>
    </table>
    <p>Use the 3.3V pin only — these readers are not 5V-tolerant.</p>

    <h2>Step by step</h2>
    <ol className="steps">
      <li>
        <h3>Build and install the device-tree overlay</h3>
        <p>The overlay sources live in <code>hardware/overlays/</code> in the repo — pick the one matching
        your board from the table above. Both flip the SoC's SPI node to <code>status = "okay"</code> and
        add an <code>mmc-spi-slot</code> child device at chip-select 0, but the Zero 2W's overlay also has
        to set <code>pinctrl-names</code>/<code>pinctrl-0</code> explicitly for <code>spi1</code>, since
        unlike <code>spi0</code> that bus doesn't predefine them in the base
        <code>sun50i-h616.dtsi</code>. Compile it on the board (or a cross-compile host) with
        <code>device-tree-compiler</code>, as <strong>two separate commands</strong> — pasting them onto one
        line runs everything as arguments to <code>apt install</code>, which then fails on <code>dtc</code>'s
        <code>-@</code> flag:</p>
        <pre><code>sudo apt install device-tree-compiler</code></pre>
        <pre><code>dtc -@ -I dts -O dtb -o sun50i-h616-spi-mmc.dtbo sun50i-h616-spi-mmc.dts</code></pre>
        <p>Run <code>dtc</code> from inside <code>hardware/overlays/</code> (or wherever you copied the
        <code>.dts</code> file to) — it needs the file in the current directory, or an explicit path. Both
        overlays declare <code>#address-cells</code>/<code>#size-cells</code> on the child node explicitly,
        so a clean run should produce no warnings; if you do see <code>Warning (reg_format)</code>, that's
        <code>dtc</code> checking the overlay standalone without the target node's real cell sizes (only
        present in the board's actual base <code>.dtb</code>) — harmless, since <code>reg = &lt;0&gt;</code>
        compiles to the bytes written regardless and resolves correctly once merged onto the real tree at
        boot.</p>
        <p>Install it and point Armbian at it via <code>user_overlays</code> in
        <code>/boot/armbianEnv.txt</code> (kernel 6.1+):</p>
        <pre><code>sudo mkdir -p /boot/overlay-user
sudo cp sun50i-h616-spi-mmc.dtbo /boot/overlay-user/</code></pre>
        <p><strong>Check for an existing <code>user_overlays</code> line first</strong> — it's a
        space-separated list, and overwriting an existing value disables whatever else it was loading
        (WiFi, USB, audio, other board fixups):</p>
        <pre><code>grep user_overlays /boot/armbianEnv.txt</code></pre>
        <p>If something's already there, append rather than replace:</p>
        <pre><code># if the line already reads e.g. user_overlays=some-other-overlay:
user_overlays=some-other-overlay sun50i-h616-spi-mmc</code></pre>
        <p>If it's empty or missing, just add the line:</p>
        <pre><code>user_overlays=sun50i-h616-spi-mmc</code></pre>
        <p>On older Armbian without <code>user_overlays</code>, drop the <code>.dtbo</code> into the board
        family's overlay directory instead (e.g. <code>/boot/dtb/allwinner/overlay/</code>) and reference it
        via the standard <code>overlays=</code> line (also space-separated — same append-don't-replace
        caution) using the suffix after whatever <code>overlay_prefix</code> your <code>armbianEnv.txt</code>
        already sets — check that value first, since it can vary by Armbian release. Reboot after either
        change, then re-check anything the pre-existing overlay was responsible for still works alongside
        the SD reader. Full details, including the Orange Pi Zero (non-2W) commands, are in
        <code>hardware/overlays/README.md</code>.</p>
      </li>

      <li>
        <h3>Verify the card is detected</h3>
        <p>With a card inserted, check that <code>mmc_spi</code> bound to the device and a block device
        showed up:</p>
        <pre><code>dmesg | grep -i mmc_spi
lsblk</code></pre>
        <p>If <code>dmesg</code> shows the SPI device registered but no <code>/dev/mmcblkN</code> appears,
        load the driver manually:</p>
        <pre><code>sudo modprobe mmc_spi</code></pre>
        <p>If that fails with <code>FATAL: Module mmc_spi not found in directory /lib/modules/&lt;version&gt;</code>,
        the driver isn't shipped with this kernel at all — not as a module, not built in (confirm with
        <code>ls /sys/bus/spi/devices/spi*.0/driver</code>, which won't exist either). The wiring and overlay
        can be entirely correct and this will still never produce a block device; getting <code>mmc_spi</code>
        back means rebuilding the kernel with it enabled. Switch to the <a href="#usb-reader">USB reader</a>
        section above instead.</p>
      </li>

      <li>
        <h3>Test with <code>sdcart_reader.py</code></h3>
        <p>This script detects the card's partition (skipping the SBC's own boot/root disk), mounts it
        read-only, and searches it for a <code>.tortucart</code> bundle using the same
        <code>resolve_cart_root()</code> logic the rest of the engine uses:</p>
        <pre><code>sudo python3 sdcart_reader.py            # single check
sudo python3 sdcart_reader.py --watch     # poll until a cart is found</code></pre>
        <p>It needs root to mount the card. On success it prints the detected partition, the mount point
        (<code>/mnt/tortucart</code> by default), and the cart path found on it.</p>
        <p>Mount point, poll interval, and an optional explicit device override (e.g. <code>/dev/mmcblk1p1</code>,
        useful with multiple readers or if auto-detection ever picks the wrong partition) live in
        <code>sdcart_config.json</code> next to the script:</p>
        <pre><code>{'{'}
    "mount_point": "/mnt/tortucart",
    "poll_interval": 2.0,
    "device": null
{'}'}</code></pre>
        <p>This only covers what Linux can change at runtime — which SPI pins the reader uses is baked into
        the device-tree overlay from the previous step and needs a rebuild of that overlay to change, not a
        config edit here.</p>
      </li>

      <li>
        <h3>Let the launcher pick it up automatically</h3>
        <p><code>launcher.py</code>'s <code>_find_cart()</code> checks <code>~/console/cart/</code> first,
        then falls back to <code>_find_sd_cart()</code>, which reuses
        <code>sdcart_reader.find_sdcard_partition()</code> / <code>ensure_mounted()</code> and
        <code>resolve_cart_root()</code>. If nothing local is found but a card with a valid cart is inserted,
        the launcher's "CARTRIDGE FOUND" screen appears without any extra steps — just run
        <code>launcher.py</code> as root so it can mount the card when needed.</p>
      </li>
    </ol>

    <h2>Limitations</h2>

    <h3>No card-detect line</h3>
    <p>This pinout has no CD pin, so <code>mmc_spi</code> only probes the card at driver load / boot.
    Swapping cards while the SBC is running won't be noticed until you reload the driver:</p>
    <pre><code>sudo rmmod mmc_spi && sudo modprobe mmc_spi</code></pre>

    <h3>Don't combine with <code>spi-spidev</code></h3>
    <p>Armbian's built-in <code>spi-spidev</code> overlay claims the same bus and chip-select your board's
    overlay uses — enable only one of the two at a time.</p>

      <PageNav />
    </>
  )
}
