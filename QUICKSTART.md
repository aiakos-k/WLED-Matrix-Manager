# Quickstart Guide — WLED Matrix Manager

## Prerequisites

- VS Code with **Dev Containers** extension
- Docker
- Git

### Install Docker

| OS | What to do |
|---|---|
| **Linux** | Install the [Docker Engine](https://docs.docker.com/engine/install/) for your distribution and follow the post-installation steps so you can use Docker without `root`. |
| **macOS** | Install [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/). |
| **Windows** | Everything runs inside **WSL2**. Install WSL2 with the default Ubuntu distribution (`wsl --install`), check that it shows version 2 (`wsl -l -v`) and enable systemd in `/etc/wsl.conf`: `[boot]` / `systemd=true`. Restart with `wsl --shutdown`. Then install the Docker Engine inside WSL as described above. |

> **Windows:** Do all Git and code work inside WSL2, not in the Windows file system –
> code on the Windows side runs into permission problems.

> **USB/Bluetooth:** The container cannot access hardware like USB sticks or a Bluetooth
> adapter directly. On Linux you can pass them through to the container. On Windows use
> [usbipd-win](https://learn.microsoft.com/windows/wsl/connect-usb) to attach the device
> to WSL. On macOS the container has no direct access to USB devices.

### Networking under WSL2

If `http://localhost:7123` does not open from Windows, find the address of WSL with
`ip addr show eth0` and use the inet address without the part after the slash, e.g.
`172.20.37.6/20` → `http://172.20.37.6:7123`.

By default WSL uses NAT networking, which keeps Home Assistant from discovering devices
in your network. **Mirrored mode** networking gives WSL the same network interfaces as
Windows (including multicast), so discovery with mDNS works.

---

## Setup (DevContainer)

```bash
# 1. Clone the repository
git clone https://github.com/aiakos-k/WLED-Matrix-Manager.git
cd WLED-Matrix-Manager

# 2. Open in VS Code
code .
```

Then: **Command Palette** (`Ctrl+Shift+P`) → `Dev Containers: Reopen in Container**

The container builds automatically and `devcontainer_bootstrap` runs on first start:
- Installs [uv](https://docs.astral.sh/uv/) and creates the backend virtual environment
  (Python **3.12** – the same version as the add-on image)
- Installs backend + frontend dependencies
- Installs the Claude Code CLI and the `pi` coding agent
- Starts Home Assistant Supervisor
- Watches for Supervisor restarts and re-applies patches automatically

The bootstrap is idempotent: it only reinstalls dependencies when
`requirements.txt` or `package-lock.json` changed and recreates the virtual environment
when the Python version no longer matches.

### Useful tasks and debugging

Open the Command Palette → **Tasks: Run Task** for the common workflows:

| Task | What it does |
|---|---|
| Start Home Assistant | Starts the Supervisor (Home Assistant on `http://localhost:7123`) |
| Rebuild and Start Addon | Rebuilds the add-on image and starts it |
| Install Dependencies | Runs `devcontainer_bootstrap` |
| Run Backend (dev) | FastAPI on `http://localhost:8000/docs` |
| Run Frontend (dev) | Vite dev server on `http://localhost:3000` |
| Lint Backend (ruff) / Lint Frontend (biome) | Runs the linters |
| Type-check Frontend (tsc) | Runs `tsc --noEmit` |
| Build Add-on Image (docker) | Builds the image locally without the Supervisor |

Press **F5** to start the backend or the frontend in the debugger
(`.vscode/launch.json`).

---

## Start Home Assistant

After the container is ready, start the Supervisor if it is not already running:

```bash
supervisor_run
```

Home Assistant is available at **http://localhost:7123**

---

## Patch the Supervisor

The DevContainer lacks systemd/dbus, so the Supervisor starts in an unhealthy state
(`docker_gateway_unprotected`). The patch script fixes this:

```bash
chmod +x ./patch_supervisor.sh && ./patch_supervisor.sh
```

Expected output:
```
[patch_supervisor] Patching diagnostics (dbus/agent error)...
  -> PATCHED
[patch_supervisor] Scanning all supervisor files for DOCKER_GATEWAY_UNPROTECTED...
  -> PATCHED: supervisor/host/firewall.py
[patch_supervisor] Restarting Supervisor...
[patch_supervisor] Done!
```

The script is idempotent — run it again any time after a Supervisor update or restart.
`devcontainer_bootstrap` watches for Supervisor restarts and re-patches automatically in the background.

> **Note:** Use `docker restart hassio_supervisor` to restart the Supervisor manually.
> `ha supervisor restart` recreates the container and loses the patches.

---

## Install the Add-on

1. Go to **Settings → Add-ons → Add-on Store** in Home Assistant
2. Find **WLED Matrix Manager** under Local add-ons
3. Click **Install**

The Supervisor builds the image locally from the Dockerfile (no registry needed).
The add-on appears in the sidebar as **WLED Matrix Manager** via Ingress.

---

## Useful Commands

```bash
# Rebuild and restart the add-on after code changes
ha apps rebuild --force local_wled_matrix_manager
ha apps start local_wled_matrix_manager

# View add-on logs
docker logs --follow addon_local_wled_matrix_manager

# Re-patch Supervisor after a restart
./patch_supervisor.sh
```

---

## Without DevContainer (Local)

Use this if you do not want to use Docker or Visual Studio Code. You need **Python 3.12**
(the version the add-on image uses – see `.python-version`) and **Node 22**.

```bash
# Python 3.12 via uv (recommended, same as Home Assistant Core uses)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv python install            # reads .python-version

# Start backend (Terminal 1)
cd wled_matrix_manager/backend
uv venv venv
uv pip install -r requirements.txt
venv/bin/python main.py

# Start frontend (Terminal 2)
cd wled_matrix_manager/frontend
npm ci
npm run dev
```

Frontend: http://localhost:3000
Backend: http://localhost:8000/docs

> Without the Supervisor you do not get the Home Assistant API access – the backend
> then runs without HA connection (`ha_connected: false`). Use the dev container if you
> want to test the integration with a real Home Assistant.

---

## Important Files

| File | Purpose |
|---|---|
| `wled_matrix_manager/config.yaml` | Add-on manifest (name, slug, options) |
| `wled_matrix_manager/Dockerfile` | Multi-stage build (React + FastAPI) |
| `wled_matrix_manager/backend/main.py` | FastAPI application entry point |
| `wled_matrix_manager/backend/app/ha_client.py` | Home Assistant WebSocket client |
| `wled_matrix_manager/frontend/src/App.tsx` | React app root |
| `wled_matrix_manager/frontend/src/api/client.ts` | Frontend API client (Ingress-aware) |
| `.devcontainer.json` | VS Code DevContainer config |
| `.python-version` | Python version used by the dev container and `uv` |
| `devcontainer_bootstrap` | Post-start setup + Supervisor monitor |
| `patch_supervisor.sh` | Supervisor patch for DevContainer |
| `AGENTS.md` | Instructions for AI coding agents |

---

## Troubleshooting

### The dev container does not build

- Make sure your fork/branch is up to date.
- Clean the Docker build cache: `docker buildx prune`.
- Open the container in recovery mode (*Open configuration in recovery devcontainer*),
  run `git pull` in its terminal, then select **Dev Containers: Rebuild Container**.

### `uv` reports that no download was found for the required Python version

Your `uv` is too old. Update it and run the bootstrap again:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
bash devcontainer_bootstrap
```

### The backend venv does not work

The virtual environment lives inside the workspace and only works inside the dev
container. The bootstrap recreates it automatically when the Python version changed. To
force a rebuild:

```bash
rm -rf wled_matrix_manager/backend/venv
bash devcontainer_bootstrap
```

### Add-on install fails with `docker_gateway_unprotected`

Run `./patch_supervisor.sh` and try again.

### Onboarding: "Failed to save: Unknown error"

Same cause — run `./patch_supervisor.sh`.

### Add-on panel missing from sidebar

```bash
ha apps rebuild --force local_wled_matrix_manager
ha apps start local_wled_matrix_manager
```

### Port already in use

```bash
lsof -i :8000   # find process
kill -9 <PID>
```

---

## AI tools in the repository

If you use an AI coding tool, it does not have to guess how this add-on works. The
repository has an [`AGENTS.md`](AGENTS.md) file with instructions for agents: repository
layout, commands, conventions and the pitfalls of the add-on build.

---

## Resources

- [Home Assistant Add-on Docs](https://developers.home-assistant.io/docs/add-ons/)
- [Home Assistant Development Environment](https://www.home-assistant.io/development/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/tutorial/)
- [React Documentation](https://react.dev/learn)
- [HA WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)
