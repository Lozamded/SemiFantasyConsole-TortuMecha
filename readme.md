Semi-Fantasy Console "TortoMecha"

Project to make a semi fantasy console using PyGame. The target is mini-pc ARM boards like Raspberry / Orange / Radxa Pi Zero, expected 1 GB of RAM (maybe RISC-V in the future).

```bash
python -m tortoiseplayer examples/hello_tortu --fullscreen
```

## Run TortoiseStudio

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m tortoisestudio examples/hello_tortu/
```


## Documentation site

The docs live in `docs-site/` as a React + Vite app (not static HTML), so
viewing or editing them requires Node.js — the Python venv above doesn't
cover this part.

### 1. Install Node.js

Node 20+ is recommended (matches the Vite/React versions in
`docs-site/package.json`):

```bash
sudo apt install nodejs npm
node -v   # confirm 20+
```

### 2. Install dependencies and run it

```bash
cd docs-site
npm install
npm run dev       # http://localhost:5173, hot-reloading
```

Other useful commands (run from `docs-site/`):

```bash
npm run build     # production build -> dist/
npm run preview   # serve the production build locally
npm run verify    # server-render every page in nav.js, checks for dead
                   # links / missing screenshots / render errors
```

See `docs-site/README.md` for how the site is structured (`src/nav.js` is
the single source of truth for the sidebar, page order, and routing) and how
to add a new page, plus instructions for exporting the whole site as a PDF.

## Build Executables (cross-compilation via Podman)

TortoiseStudio can build standalone executables for ARM64 and ARMhf targets from
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