# WLED Matrix Manager — Documentation

## Table of Contents

1. [Installation](#installation)
2. [First Steps](#first-steps)
3. [Managing Devices](#managing-devices)
4. [Creating & Playing Scenes](#creating--playing-scenes)
5. [Home Assistant Integration](#home-assistant-integration)
6. [API Reference](#api-reference)
7. [WebSocket](#websocket)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)

---

## Installation

### Via Home Assistant Add-on Store

1. Go to **Settings → Add-ons → Add-on Store**
2. Click ⋮ → **Repositories** and add the repository URL
3. Install **WLED Matrix Manager** from the list
4. Start the add-on — it appears in the **sidebar**

### Prerequisites

- Home Assistant 2023.8+
- At least one WLED device on the network
- WLED devices must be reachable via HTTP and/or UDP

---

## First Steps

1. **Start the add-on** and open it from the sidebar
2. **Add a WLED device** (manually via IP or Auto-Discovery from HA)
3. **Create a new scene** with matrix dimensions (e.g., 16×16)
4. **Draw pixels** in the Scene Editor
5. **Play** on the WLED device

---

## Managing Devices

### Adding a Device

On the Devices page you can register WLED devices:

- **Name** — Display name
- **IP Address** — Network address of the WLED device
- **Matrix Size** — Width × Height (e.g., 16×16)
- **Communication Protocol** — `udp_dnrgb` (default, for animations) or `json_api`
- **Segment ID** — WLED segment (default: 0)
- **Scale Mode** — Scaling for different resolutions (`stretch`, `tile`, `center`, `none`)

### Auto-Discovery

Via `/api/ha/discover`, WLED devices can be automatically discovered from Home Assistant. Prerequisite: The WLED integration is configured in HA.

### Health Check

Via `/api/devices/{id}/health`, the add-on checks whether the WLED device is reachable at the stored IP (GET on `/json/info`).

---

## Creating & Playing Scenes

### Creating a Scene

A scene consists of:

- **Name & Description**
- **Matrix Dimensions** (Width × Height)
- **Frames** — Each frame contains:
  - **Pixel Data** — JSON object with `"x,y": [R, G, B]` entries
  - **Duration** — Display duration in milliseconds
  - **Brightness** — 0–255
  - **Background Color** — RGB values for unset pixels
- **Loop Mode** — `once`, `loop`, or `bounce`

### Playing a Scene

Scenes can be played on assigned devices via the UI or API (`POST /api/scenes/{id}/play`).

**Playback behavior:**
- With **UDP DNRGB**: Before the first frame, a solid-black effect is sent to WLED to prevent the start flash (300ms wait)
- With **JSON API**: Frames are sent as `/json/state` commands with `seg.i`
- **Upscaling**: Scene resolution is automatically scaled to the device resolution
- **Device exclusivity**: Only one scene can run per device at a time

### Import/Export

- **Export**: `GET /api/scenes/{id}/export` — Binary file (`.ledm` format)
- **Import**: `POST /api/scenes/import` — Upload `.ledm` file
- **Image Import**: `POST /api/image/convert` — Convert image to pixel data

---

## Home Assistant Integration

### Scenes as HA Entities

Each scene is registered as a **Switch entity** in Home Assistant:
- `switch.wled_matrix_<scene_name>` — On/Off toggles playback
- Entity attributes show frame count, matrix dimensions, loop mode, etc.

### Automations

Scenes can be used in HA automations:

```yaml
automation:
  - trigger:
      - platform: time
        at: "20:00"
    action:
      - service: switch.turn_on
        entity_id: switch.wled_matrix_evening_mood
```

---

## API Reference

Base URL: relative to the Ingress path or `http://<host>:8000`

### Status & Health

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (`ha_connected` status) |
| `/api/status` | GET | Add-on version & status |
| `/api/stats` | GET | Statistics (scenes, devices, active playbacks) |

### Devices

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/devices` | GET | List all active devices |
| `/api/devices` | POST | Create a new device |
| `/api/devices/{id}` | PUT | Update a device |
| `/api/devices/{id}` | DELETE | Deactivate a device (soft-delete) |
| `/api/devices/{id}/health` | GET | WLED health check |
| `/api/devices/test-frame` | POST | Send a single frame directly to devices |
| `/api/ha/discover` | GET | Discover WLED devices from HA |
| `/api/ha/debug` | GET | HA connection diagnostics |

### Scenes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scenes` | GET | All active scenes (incl. frames & devices) |
| `/api/scenes` | POST | Create a new scene |
| `/api/scenes/{id}` | GET | Read a single scene |
| `/api/scenes/{id}` | PUT | Update a scene |
| `/api/scenes/{id}` | DELETE | Deactivate a scene (soft-delete) |

### Playback

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scenes/{id}/play` | POST | Play a scene |
| `/api/scenes/{id}/stop` | POST | Stop playback |
| `/api/playback/status` | GET | Status of all running playbacks |

### Import/Export

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/scenes/{id}/export` | GET | Export scene as `.ledm` binary file |
| `/api/scenes/import` | POST | Import `.ledm` file |
| `/api/image/convert` | POST | Convert image to pixel data |

---

## WebSocket

Endpoint: `/ws`

### Client Messages

**Send preview frame** (forwarded to all other clients):
```json
{"action": "preview_frame", "data": { ... }}
```

**Query playback status:**
```json
{"action": "playback_status"}
```

**HA Actions** (to the HA WebSocket client):
```json
{"action": "get_entities"}
{"action": "call_service", "domain": "light", "service": "turn_on", "data": {"entity_id": "light.wled"}}
```

### Server Messages

```json
{"type": "preview_frame", "data": { ... }}
{"type": "playback_status", "data": { ... }}
{"type": "ack", "action": "preview_frame"}
```

---

## Configuration

### Add-on Options (config.yaml)

| Option | Description | Default |
|--------|-------------|---------|
| `log_level` | Log level: `debug`, `info`, `warning`, `error` | `info` |

### Required Permissions

- **homeassistant_api** — WebSocket communication with HA Core
- **hassio_api (admin)** — Supervisor access
- **Network (Port 8000)** — Frontend & API
- **share:rw, addon_config:rw** — Data persistence

### WLED Device Settings

Relevant WLED settings under Settings → Sync:

| Setting | Description |
|---------|-------------|
| Force Max Brightness | Forces brightness 255 in realtime mode |
| Realtime Timeout | Default timeout for realtime (recommended: 5s) |
| Use Main Segment Only | Use only the main segment for realtime |

---

## Troubleshooting

### Add-on won't start

```bash
docker logs addon_local_wled_matrix_manager
```

Common causes:
- Port 8000 already in use
- Python dependencies broken → Rebuild the add-on

### Frontend shows 404

- Check if `frontend/dist/index.html` exists (in the Docker image)
- Vite must be built with `base: './'` (see TEMPLATE_GUIDE.md)

### WLED device unreachable

1. IP address correct? → `curl http://<wled-ip>/json/info`
2. Device on the same network as HA?
3. Check firewall rules (UDP Port 21324 for DNRGB)

### Flash on playback start

Before the first UDP frame, a solid-black effect is automatically set (300ms wait). If a flash is still visible:
- Check if "Force Max Brightness" is disabled in WLED
- Increase the pre-delay time

Details: [WLED_PROTOCOLS.md](./backend/docs/WLED_PROTOCOLS.md) — Section "Realtime-Mode Lifecycle"

### Add-on not in sidebar

`ingress_panel: true` must be set. In DevContainer:
```bash
ha apps rebuild --force local_wled_matrix_manager
ha apps start local_wled_matrix_manager
```

### WebSocket connection failed

- In DevContainer: WebSocket runs on the `supervisor` hostname, not `localhost`
- Browser DevTools → Network → WS tab for errors

---

## Support

If you find this add-on useful, consider buying me a coffee:

<a href="https://www.buymeacoffee.com/aiakosmk" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me a Coffee" style="height: 60px !important;width: 217px !important;" ></a>
