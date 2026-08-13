#!/usr/bin/env python3
"""Physical cartridge reader.

Deployed at ~/console/sdcart_reader.py on the SBC alongside launcher.py.

Two ways to get a cartridge readable here, both of which end up as a
normal block device that this script mounts and scans for a .tortucart
bundle:

1. USB storage (recommended). A USB microSD adapter, or just a plain USB
   flash drive -- no microSD needed at all. Plug into any USB port -- the
   kernel's generic usb-storage driver handles either one with zero setup
   and the drive shows up as /dev/sdaN. No overlay, no wiring, no
   kernel-support gamble.
2. SPI microSD breakout (IC303K-style: 3V3, GND, CS, MOSI, MISO, CLK)
   wired to the SPI bus, with a board-specific device-tree overlay (see
   hardware/overlays/) binding the kernel's mmc_spi driver so the card
   shows up as /dev/mmcblk1. This only works if mmc_spi is actually
   present in your kernel build -- check with `modinfo mmc_spi` *before*
   wiring anything, since several current Armbian kernels ship without
   it (no module, not built in), in which case the overlay loads fine
   but no driver ever claims the device. Cheap SPI readers also rarely
   wire a card-detect line, so mmc_spi only probes the card at module
   load / boot -- reload it to notice a swapped card:
       sudo rmmod mmc_spi && sudo modprobe mmc_spi

Run as root (mounting requires it):
    sudo python3 sdcart_reader.py            # single check
    sudo python3 sdcart_reader.py --watch     # poll until a cart is found

Settings (mount point, poll interval, and an optional explicit device
override) live in sdcart_config.json next to this script -- see
DEFAULT_CONFIG below for the defaults used when that file is absent.
Note this only covers things Linux can change at runtime: which SPI pins
the reader uses is baked into the device-tree overlay and needs a rebuild
of that overlay to change, not a config edit here.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tortoisengine.cart import resolve_cart_root  # noqa: E402

CONFIG_PATH = ROOT / "sdcart_config.json"

DEFAULT_CONFIG = {
    "mount_point": "/mnt/tortucart",
    "poll_interval": 2.0,
    # Explicit partition path (e.g. "/dev/mmcblk1p1") to use instead of
    # auto-detection -- useful with multiple readers or unusual setups.
    "device": None,
}


def load_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.is_file():
        try:
            config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"warning: ignoring invalid {CONFIG_PATH.name}: {exc}")
    return config


def _lsblk() -> list[dict]:
    out = subprocess.run(
        ["lsblk", "-J", "-o", "NAME,PATH,TYPE,FSTYPE,MOUNTPOINT,PKNAME"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)["blockdevices"]


def _flatten(devices: list[dict]) -> list[dict]:
    flat = []
    for dev in devices:
        flat.append(dev)
        flat.extend(_flatten(dev.get("children", [])))
    return flat


def _root_disk() -> str | None:
    """Block device backing '/', so we never touch the SBC's own boot media."""
    try:
        src = subprocess.run(
            ["findmnt", "/", "-no", "SOURCE"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for dev in _flatten(_lsblk()):
        if dev["path"] == src:
            return dev.get("pkname") or dev["name"]
    return None


# mmcblk1p1 (SPI/mmc_spi reader) or sda1 (USB reader via usb-storage).
_CARD_PARTITION_RE = re.compile(r"^(mmcblk\d+p\d+|sd[a-z]+\d+)$")


def find_sdcard_partition(config: dict | None = None) -> dict | None:
    """The configured device override, or else the first mountable partition
    on an SD/USB card reader that isn't the SBC's own root disk."""
    config = config or load_config()
    devices = _flatten(_lsblk())

    if config.get("device"):
        for dev in devices:
            if dev["path"] == config["device"]:
                return dev
        return None

    root_disk = _root_disk()
    for dev in devices:
        if dev["type"] != "part":
            continue
        if not _CARD_PARTITION_RE.match(dev["name"]):
            continue
        if root_disk and dev.get("pkname") == root_disk:
            continue
        if not dev.get("fstype"):
            continue
        return dev
    return None


def ensure_mounted(dev: dict, config: dict | None = None) -> Path:
    """Mount *dev* if needed and return its mount point."""
    if dev.get("mountpoint"):
        return Path(dev["mountpoint"])

    config = config or load_config()
    mount_point = Path(config["mount_point"])
    mount_point.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["mount", "-o", "ro", dev["path"], str(mount_point)],
        check=True,
    )
    return mount_point


def check_once(config: dict | None = None) -> Path | None:
    """Detect, mount, and search for a cart. Returns the cart root if found."""
    config = config or load_config()

    dev = find_sdcard_partition(config)
    if dev is None:
        print("no microSD card detected on the SPI reader")
        return None

    print(f"found card partition {dev['path']} (fstype={dev['fstype']})")
    mount_point = ensure_mounted(dev, config)
    print(f"mounted at {mount_point}")

    cart_root = resolve_cart_root(mount_point)
    if cart_root is None:
        print(f"no .tortucart bundle found under {mount_point}")
        return None

    print(f"cartridge found: {cart_root}")
    return cart_root


def main() -> None:
    config = load_config()
    poll_interval = float(config["poll_interval"])

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watch", action="store_true",
        help="keep polling every %.0fs until a cartridge is found" % poll_interval,
    )
    args = parser.parse_args()

    if not args.watch:
        cart_root = check_once(config)
        sys.exit(0 if cart_root else 1)

    print("watching for a cartridge... (Ctrl-C to stop)")
    try:
        while True:
            if check_once(config) is not None:
                break
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
