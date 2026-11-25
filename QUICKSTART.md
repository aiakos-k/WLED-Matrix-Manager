# Quickstart Guide — WLED Matrix Manager

## Prerequisites

- Docker (als Host-Runtime)
- Git
- VS Code (optional — die Toolchain steckt im zentralen DevContainer)

---

## Setup (zentrale Plattform `ha-development`)

Dieses Repository wird **innerhalb** der zentralen Plattform `ha-development`
entwickelt. Es gibt **kein eigenes DevContainer** in diesem Repo mehr: VS Code
würde sonst für den Ordner einen zweiten Container starten und mit dem zentralen
Container um Ports kollidieren.

```bash
# 1. Zentrale Plattform holen
git clone <url> ~/ha-development
cd ~/ha-development

# 2. Add-on-Repository klonen (landet automatisch unter projects/)
bash scripts/bootstrap.sh --clone

# 3. In VS Code öffnen
code ~/ha-development
```

Der zentrale DevContainer bringt mit: Python/uv, Node 20 (+ Node 22 für
KI-Agenten), Ruff, Biome, ESPHome, PlatformIO, Pi, Claude Code und Copilot CLI.

---

## Start Home Assistant

Supervisor und Home Assistant Core laufen zentral (Variante B, Supervisor gegen
den Docker-Daemon des Hosts):

```bash
cd ~/ha-development
bash scripts/ha-stack.sh up      # Supervisor + Core starten
bash scripts/ha-stack.sh url     # URL der HA-Oberfläche
```

Home Assistant ist danach unter der von `ha-stack.sh url` gemeldeten Adresse
erreichbar (Standard: **http://localhost**).

---

## Supervisor-Patches

Die Systemprüfungen des Supervisors (systemd, os-agent, Journal, Docker-Logging)
sind auf einem normalen Linux-Host nicht erfüllbar. Die zentrale Plattform
patcht den Supervisor deshalb automatisch und startet ihn neu:

```bash
cd ~/ha-development
bash scripts/ha-stack.sh patch    # Patches anwenden, Supervisor neu starten
```

Die Patches sind idempotent und werden bei jedem `ha-stack.sh up` erneut
angewendet und verifiziert.

---

## Install the Add-on

```bash
bash scripts/ha-stack.sh apps install local_wled_matrix_manager
bash scripts/ha-stack.sh apps start   local_wled_matrix_manager
```

Der Supervisor baut das Image lokal aus dem Dockerfile (kein Registry nötig).
Das Add-on erscheint in der Seitenleiste als **WLED Matrix Manager** (Ingress).

---

## Useful Commands

```bash
# Alles zentral (Prefix: bash scripts/ha-stack.sh)
bash scripts/ha-stack.sh apps rebuild local_wled_matrix_manager   # neu bauen
bash scripts/ha-stack.sh apps start   local_wled_matrix_manager   # starten
bash scripts/ha-stack.sh logs         local_wled_matrix_manager   # Logs
bash scripts/ha-stack.sh status                                   # Übersicht
```

---

## Lokal ohne Container

```bash
# Backend (Terminal 1)
cd wled_matrix_manager/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# Frontend (Terminal 2)
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

> Supervisor, Home Assistant Core, DevContainer und Toolchain liegen in der
> zentralen Plattform `ha-development` (Verzeichnis `projects/WLED-Matrix-Manager`).

---

## Troubleshooting

### Add-on install fails with `docker_gateway_unprotected`

```bash
cd ~/ha-development
bash scripts/ha-stack.sh patch    # Patches anwenden, Supervisor neu starten
```

### Onboarding: "Failed to save: Unknown error"

Same cause — `bash scripts/ha-stack.sh patch` ausführen.

### Add-on panel missing from sidebar

```bash
cd ~/ha-development
bash scripts/ha-stack.sh apps rebuild local_wled_matrix_manager
bash scripts/ha-stack.sh apps start   local_wled_matrix_manager
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
