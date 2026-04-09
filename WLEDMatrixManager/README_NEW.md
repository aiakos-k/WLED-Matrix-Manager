# WLED Matrix Manager — Architecture Reference

> This document describes the internal architecture.
> For user documentation see [DOCS.md](./DOCS.md).

## Architecture

```
Home Assistant Core
    │ WebSocket API (ws://supervisor/core/websocket)
    ▼
FastAPI Backend (:8000)
├── REST API (/api/...)         Scenes, Devices, Playback
├── WebSocket (/ws)             Live Preview & Status Updates
├── HA Client                   Bidirectional HA Communication
├── Entity Sync                 Scenes ↔ HA Switch Entities
├── Device Controller           WLED JSON API + UDP DNRGB
├── Scene Playback              Frame Sequencing, Upscaling
├── Image Converter             Image → Pixel Data (Pillow)
├── Binary Format               .ledm Import/Export
└── SQLite (async SQLAlchemy)   Persistence (/data/wled_matrix.db)
    │
    ▼
React Frontend (Ingress UI)
├── Scene Editor                Pixel-Art Editor, Multi-Frame
├── Device Management           WLED Device CRUD + Health
├── Playback Control            Start/Stop, Status Display
└── Ant Design UI               Responsive Layout
```

## Directory Structure

```
WLEDMatrixManager/
├── backend/
│   ├── main.py                 FastAPI App, Lifespan, WebSocket
│   ├── requirements.txt
│   └── app/
│       ├── router.py           All API Endpoints
│       ├── models.py           SQLAlchemy + Pydantic Models
│       ├── database.py         Async SQLite Session
│       ├── device_controller.py  WLED JSON/UDP Communication
│       ├── scene_playback.py   Playback Engine with Upscaling
│       ├── ha_client.py        HA WebSocket Client
│       ├── ha_entity_sync.py   Scene ↔ HA Entity Registration
│       ├── image_converter.py  Image Upload → Pixel Data
│       └── binary_format.py    .ledm Serialization
├── frontend/
│   ├── src/
│   │   ├── App.tsx             Routing, Layout
│   │   ├── pages/              Home, Devices, Scenes, SceneEditor
│   │   ├── api/client.ts       API + WebSocket Client
│   │   ├── hooks/              useWebSocket
│   │   └── utils/              binaryFormat, wledParser
│   ├── vite.config.ts          base: './' for Ingress
│   └── package.json
├── rootfs/                     s6-overlay Service
├── Dockerfile                  Multi-Stage Build (Node → Python)
├── config.yaml                 Add-on Configuration
└── DOCS.md                     User Documentation
```

## License

EUPL-1.2 — See [LICENSE](../LICENSE)
