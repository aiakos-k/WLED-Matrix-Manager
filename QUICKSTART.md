# Quickstart Guide — WLED Matrix Manager

## Prerequisites

- VS Code with **Dev Containers** extension
- Docker Desktop
- Git

---

## Setup (DevContainer)

```bash
# 1. Clone the repository
git clone https://github.com/aiakos-k/WLED-Matrix-Manager.git
cd WLED-Matrix-Manager

# 2. Open in VS Code
code .
```

Then: **Command Palette** (`Ctrl+Shift+P`) → `Dev Containers: Reopen in Container`

The container builds automatically and `devcontainer_bootstrap` runs on first start:
- Installs backend + frontend dependencies
- Installs Claude Code CLI
- Starts Home Assistant Supervisor
- Watches for Supervisor restarts and re-applies patches automatically

---

## Start Home Assistant

After the container is ready, start the Supervisor if it is not already running:

```bash
ha supervisor start
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

```bash
# Start backend (Terminal 1)
cd wled_matrix_manager/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# Start frontend (Terminal 2)
cd wled_matrix_manager/frontend
npm install
npm run dev
```

Frontend: http://localhost:3000
Backend: http://localhost:8000/docs

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
| `devcontainer_bootstrap` | Post-start setup + Supervisor monitor |
| `patch_supervisor.sh` | Supervisor patch for DevContainer |

---

## Troubleshooting

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

## Resources

- [Home Assistant Add-on Docs](https://developers.home-assistant.io/docs/add-ons/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/tutorial/)
- [React Documentation](https://react.dev/learn)
- [HA WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)
