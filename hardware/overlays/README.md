# SPI microSD reader overlays

> **Check this before wiring anything.** These overlays only get you a
> working card if your kernel actually ships the `mmc_spi` driver. Run
> `modinfo mmc_spi` on the board first — if it errors with "not found",
> your kernel doesn't have it (several current Armbian kernels don't,
> confirmed on a `6.18.35-current-sunxi64` Orange Pi Zero 2W build: the
> overlay loaded fine, the SPI bus registered the child device, and
> still nothing ever bound because the driver plain isn't there). In
> that case skip SPI entirely and use **USB storage** instead — a USB
> microSD adapter, or just a plain USB flash drive (no microSD needed at
> all). Both use the generic `usb-storage` driver, which is in every
> Armbian kernel, no overlay or device-tree work required.
> `sdcart_reader.py` picks up SPI or USB storage automatically, no config
> changes needed either way.

Two overlays bind the kernel's `mmc_spi` driver to an SPI bus, so an
IC303K-style microSD reader wired to that bus's pins on the GPIO header
shows up as a normal block device (e.g. `/dev/mmcblk1`) once a card is
inserted. This is a prerequisite for `sdcart_reader.py` — nothing in this
repo bit-bangs the SD/SPI protocol itself. Pick the one matching your
board's SoC.

| Board | SoC | File | Bus |
|-------|-----|------|-----|
| Orange Pi Zero | Allwinner H2+/H3 | `sun8i-h3-spi-mmc.dts` | spi0 |
| Orange Pi Zero 2W | Allwinner H616/H618 | `sun50i-h616-spi-mmc.dts` | spi1 |

Both boards happen to expose their SPI bus at the same physical header
pins (1, 19, 20, 21, 23, 24, 25) — only the GPIO port letters and bus
number differ, since the SoC changed between the two boards.

## Wiring

**Orange Pi Zero (26-pin header):**

| Reader pin | Header pin | Signal      |
|------------|-----------|-------------|
| VCC (3V3)  | 1         | 3.3V        |
| GND        | 20 or 25  | GND         |
| MOSI       | 19        | PC0 / SPI0_MOSI |
| MISO       | 21        | PC1 / SPI0_MISO |
| CLK        | 23        | PC2 / SPI0_SCLK |
| CS         | 24        | PC3 / SPI0_CS0  |

**Orange Pi Zero 2W (40-pin header):**

| Reader pin | Header pin | Signal      |
|------------|-----------|-------------|
| VCC (3V3)  | 1         | 3.3V        |
| GND        | 20 or 25  | GND         |
| MOSI       | 19        | PH7 / SPI1_MOSI |
| MISO       | 21        | PH8 / SPI1_MISO |
| CLK        | 23        | PH6 / SPI1_CLK  |
| CS         | 24        | PH5 / SPI1_CS0  |

Do not use 5V (pins 2/4) for the reader's VCC — these boards are 3.3V-only.

## Build

Needs `device-tree-compiler` (`dtc`) on the SBC or a cross-compile host.
Substitute the `.dts`/`.dtbo` name for your board throughout this doc.
Run these as **two separate commands**, not pasted onto one line — a
merged line runs everything as arguments to `apt install`, which then
fails on `dtc`'s `-@` flag:

```bash
sudo apt install device-tree-compiler
```

```bash
dtc -@ -I dts -O dtb -o sun50i-h616-spi-mmc.dtbo sun50i-h616-spi-mmc.dts
```

Run `dtc` from inside `hardware/overlays/` (or wherever you copied the
`.dts` file to) — it needs the file in the current directory, or an
explicit path to it.

Both overlays declare `#address-cells = <1>; #size-cells = <0>;` on the
child node explicitly, so a clean `dtc` run should produce no warnings.
If you do see `Warning (reg_format)` / `#address-cells == 2, #size-cells
== 1` warnings, that means `dtc` is checking the overlay standalone
without seeing the target node's real cell sizes (only present in the
board's actual base `.dtb`, not this file) — harmless for the `.dtbo`
it still produces, since `reg = <0>` compiles to exactly the bytes
written regardless of the warning; it's resolved correctly once the
overlay is merged onto the real tree at boot.

## Install

Armbian (kernel 6.1+, supports user overlays):

```bash
sudo mkdir -p /boot/overlay-user
sudo cp sun50i-h616-spi-mmc.dtbo /boot/overlay-user/
```

Before editing `/boot/armbianEnv.txt`, check whether it already has a
`user_overlays` line:

```bash
grep user_overlays /boot/armbianEnv.txt
```

`user_overlays` is a **space-separated list**, not a single value. If a
line already exists (e.g. `user_overlays=some-other-overlay`), **append**
to it rather than replacing it — overwriting it disables whatever that
other overlay was doing, which may be unrelated to this SD reader (WiFi,
USB, audio, board-specific fixups, etc.):

```
user_overlays=some-other-overlay sun50i-h616-spi-mmc
```

If you're not sure what an existing overlay does before deciding whether
to keep it, check for a filename hint and dump its strings:

```bash
find /boot/dtb* -iname "<name>*.dtbo" 2>/dev/null
strings /boot/overlay-user/<name>.dtbo 2>/dev/null | head -20
```

If there was no `user_overlays` line at all, add one:

```
user_overlays=sun50i-h616-spi-mmc
```

On older Armbian without `user_overlays` support, drop the `.dtbo` into
the board family's overlay directory instead (e.g.
`/boot/dtb/allwinner/overlay/`) and reference it by the suffix after the
`overlay_prefix` set in `armbianEnv.txt` via the standard `overlays=`
line (also space-separated — same append-don't-replace caution applies),
e.g.:

```
overlays=spi-mmc
```

Check `overlay_prefix=` in your `armbianEnv.txt` first — for H616/H618
boards including the Zero 2W it's commonly `sun50i-h616`, but confirm it
matches the actual prefix on your image before relying on it, since
Armbian's family grouping can vary by release.

Reboot after either change, then re-check anything the pre-existing
overlay was responsible for (WiFi, USB, etc.) still works alongside the
SD reader.

## Verify

```bash
dmesg | grep -i mmc_spi
lsblk
```

If `/dev/mmcblkN` doesn't appear after reboot but `dmesg` shows the SPI
device registered, load the driver manually:

```bash
sudo modprobe mmc_spi
```

If that fails with `FATAL: Module mmc_spi not found in directory
/lib/modules/<version>`, the driver isn't shipped with this kernel at
all — not as a loadable module, not built in (confirm with
`ls /sys/bus/spi/devices/spi*.0/driver`, which won't exist either). The
overlay and wiring can be perfectly correct and this will still never
work; getting `mmc_spi` back means rebuilding the kernel with it
enabled. Easier fix: use a USB microSD reader instead (see the note at
the top of this file) — no kernel changes needed.

Note: this reader has no card-detect line, so `mmc_spi` only probes the
card at driver load / boot — swapping cards while running requires
`sudo rmmod mmc_spi && sudo modprobe mmc_spi` before `sdcart_reader.py`
will see the new card.

## Conflicts

Don't also enable Armbian's built-in `spi-spidev` overlay on the same
bus/chip-select your board's overlay uses — both claim it and only one
device can be bound at a time.
