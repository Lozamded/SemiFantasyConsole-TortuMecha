"""Build standalone executables from a .tortucart using PyInstaller.

Native builds run PyInstaller in the current Python environment.
Cross-arch builds run PyInstaller inside a Podman container.
The resulting binary is placed in cart_root/bin/<cart_name>_<arch>.
When frozen, the binary locates the cart via sys.executable/../..
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

_PKG_ROOT = Path(__file__).parent.parent

ARCH_NATIVE = "native"
ARCH_ARM64  = "arm64"
ARCH_ARMHF  = "armhf"
ARCH_X86_64 = "x86_64"

_PODMAN_PLATFORMS: dict[str, str] = {
    ARCH_ARM64: "linux/arm64",
    ARCH_ARMHF: "linux/arm/v7",
    ARCH_X86_64: "linux/amd64",
}

_LAUNCHER = """\
import sys
from pathlib import Path
if getattr(sys, "frozen", False):
    _cart = Path(sys.executable).parent.parent
else:
    _cart = Path(__file__).parent.parent
sys.argv = [sys.argv[0], str(_cart)]
from tortuplayer.__main__ import main
raise SystemExit(main())
"""

_PYINSTALLER_FLAGS = [
    "--onefile",
    "--console",
    "--collect-all", "tortuengine",
    "--collect-all", "tortuplayer",
    "--hidden-import", "pygame",
    "--hidden-import", "numpy",
    "--noconfirm",
]


def current_arch() -> str:
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return ARCH_X86_64
    if m in ("aarch64", "arm64"):
        return ARCH_ARM64
    if m.startswith("arm"):
        return ARCH_ARMHF
    return m


def podman_available() -> bool:
    return shutil.which("podman") is not None


def podman_networking_available() -> bool:
    """Check if podman's rootless network backend (pasta or slirp4netns) is present."""
    return shutil.which("pasta") is not None or shutil.which("slirp4netns") is not None


def qemu_arm_available() -> bool:
    """Check if binfmt_misc handlers for ARM are registered (needed for cross-arch containers)."""
    binfmt = Path("/proc/sys/fs/binfmt_misc")
    return any(
        (binfmt / name).exists()
        for name in ("qemu-aarch64", "qemu-arm", "qemu-armeb")
    )


def build_executable(
    cart_root: Path,
    arch: str = ARCH_NATIVE,
    *,
    log: Callable[[str], None] = print,
) -> Path:
    """Build a standalone executable and place it in cart_root/bin/.

    Returns the path to the built executable.
    Raises RuntimeError on build failure.
    """
    cart_root = cart_root.resolve()
    raw = cart_root.name
    if raw.endswith(".tortucart"):
        raw = raw[: -len(".tortucart")]
    cart_name = raw.replace(" ", "_") or "game"

    resolved_arch = current_arch() if arch == ARCH_NATIVE else arch
    exe_name = f"{cart_name}_{resolved_arch}"

    bin_dir = cart_root / "bin"
    bin_dir.mkdir(exist_ok=True)

    if resolved_arch == current_arch():
        return _build_native(exe_name, bin_dir, log=log)

    if resolved_arch in _PODMAN_PLATFORMS:
        if not podman_available():
            raise RuntimeError("podman not found — install Podman for cross-compilation")
        return _build_podman(resolved_arch, exe_name, bin_dir, log=log)

    raise ValueError(f"Unknown arch: {resolved_arch!r}")


def _stream(proc: subprocess.Popen, log: Callable[[str], None]) -> int:
    assert proc.stdout is not None
    for line in proc.stdout:
        log(line.rstrip())
    proc.wait()
    return proc.returncode


def _build_native(
    exe_name: str, bin_dir: Path, *, log: Callable[[str], None]
) -> Path:
    log(f"[build] native — {exe_name}")
    with tempfile.TemporaryDirectory(prefix="tortu_build_") as tmp:
        tmp_path = Path(tmp)
        launcher = tmp_path / "_launcher.py"
        launcher.write_text(_LAUNCHER, encoding="utf-8")

        cmd = [
            sys.executable, "-m", "PyInstaller",
            *_PYINSTALLER_FLAGS,
            "--name", exe_name,
            "--distpath", str(tmp_path / "dist"),
            "--workpath", str(tmp_path / "work"),
            "--specpath", str(tmp_path),
            str(launcher),
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        rc = _stream(proc, log)
        if rc != 0:
            raise RuntimeError(f"PyInstaller exited with code {rc}")

        built = tmp_path / "dist" / exe_name
        if not built.is_file():
            raise FileNotFoundError(f"Expected binary not found: {built}")

        dest = bin_dir / exe_name
        shutil.copy2(built, dest)
        dest.chmod(0o755)

    log(f"[build] done → {dest}")
    return dest


def _build_podman(
    arch: str, exe_name: str, bin_dir: Path, *, log: Callable[[str], None]
) -> Path:
    platform_flag = _PODMAN_PLATFORMS[arch]
    log(f"[build] podman {platform_flag} — {exe_name}")

    if not podman_networking_available():
        raise RuntimeError(
            "Podman rootless network backend not found.\n"
            "Install pasta:  sudo apt install passt\n"
            "Then retry the build."
        )

    if arch in (ARCH_ARM64, ARCH_ARMHF) and not qemu_arm_available():
        raise RuntimeError(
            "ARM binfmt handlers not registered — podman cannot emulate ARM.\n"
            "Install qemu:   sudo apt install qemu-user-static\n"
            "Then run:       sudo systemctl restart systemd-binfmt\n"
            "Then retry the build."
        )

    with tempfile.TemporaryDirectory(prefix="tortu_podman_") as tmp:
        tmp_path = Path(tmp)

        src = tmp_path / "src"
        src.mkdir()
        shutil.copytree(_PKG_ROOT / "tortuengine", src / "tortuengine")
        shutil.copytree(_PKG_ROOT / "tortuplayer", src / "tortuplayer")
        # Write a minimal pyproject.toml — no PyQt6/tortustudio inside the container
        (src / "pyproject.toml").write_text(
            '[build-system]\n'
            'requires = ["setuptools>=61"]\n'
            'build-backend = "setuptools.build_meta"\n'
            '\n'
            '[project]\n'
            'name = "semi-fantasy-console"\n'
            'version = "0.1.0"\n'
            'requires-python = ">=3.11"\n'
            'dependencies = ["pygame>=2.6.0", "numpy>=1.24.0"]\n'
            '\n'
            '[tool.setuptools.packages.find]\n'
            'where = ["."]\n'
            'include = ["tortuengine*", "tortuplayer*"]\n',
            encoding="utf-8",
        )

        (tmp_path / "_launcher.py").write_text(_LAUNCHER, encoding="utf-8")
        (tmp_path / "dist").mkdir()

        flags = " ".join(_PYINSTALLER_FLAGS)
        script = (
            "set -e && "
            "apt-get update -qq && apt-get install -y -q binutils gcc g++ zlib1g-dev libsdl2-dev libfreetype6-dev pkg-config && "
            "pip install --quiet pyinstaller pygame numpy && "
            "pip install --quiet -e /build/src && "
            f"pyinstaller {flags} "
            f"--name {exe_name} "
            "--distpath /build/dist --workpath /build/work "
            "--specpath /build "
            "/build/_launcher.py"
        )
        cmd = [
            "podman", "run", "--rm",
            "--platform", platform_flag,
            "-v", f"{tmp_path}:/build",
            "python:3.11-slim",
            "bash", "-c", script,
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        rc = _stream(proc, log)
        if rc != 0:
            raise RuntimeError(f"Podman build failed (exit {rc})")

        built = tmp_path / "dist" / exe_name
        if not built.is_file():
            raise FileNotFoundError(f"Expected binary not found: {built}")

        dest = bin_dir / exe_name
        shutil.copy2(built, dest)
        dest.chmod(0o755)

    log(f"[build] done → {dest}")
    return dest
