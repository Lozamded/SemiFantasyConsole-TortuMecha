Semi-Fantasy Console "TortuMecha"

Project to make a semi fantasy console using PyGame. The target is mini-pc ARM boards like Raspberry / Orange / Radxa Pi Zero, expected 1 GB of RAM (maybe RISC-V in the future).

```bash
python -m tortuplayer examples/hello_tortu --fullscreen
```

## Run TortuStudio

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m tortustudio examples/hello_tortu/
```


## Build Executables (cross-compilation via Podman)

TortuStudio can build standalone executables for ARM64 and ARMhf targets from
an x86-64 host using Podman containers. Three things must be in place first.

### 1. Install Podman

```bash
sudo apt install podman
```

### 2. Install the rootless network backend

Podman 5.x requires `pasta` to configure networking inside rootless containers:

```bash
sudo apt install passt
```

### 3. Install ARM emulation support

To run ARM containers on an x86-64 host the kernel needs QEMU binfmt handlers:

```bash
sudo apt install qemu-user-static
sudo systemctl restart systemd-binfmt
```

### Verify

```bash
podman run --rm --platform linux/arm64 python:3.11-slim python -c \
  "import platform; print(platform.machine())"
# expected output: aarch64
```

Once the output is `aarch64`, the ARM64 and ARMhf checkboxes in the
**Build > Build Executable** dialog will work correctly.