# WLED Matrix Manager — Architektur-Referenz

> Dieses Dokument beschreibt die interne Architektur.
> Für die Benutzerdokumentation siehe [DOCS.md](./DOCS.md).

## Architektur

```
Home Assistant Core
    │ WebSocket API (ws://supervisor/core/websocket)
    ▼
FastAPI Backend (:8000)
├── REST API (/api/...)         Szenen, Geräte, Playback
├── WebSocket (/ws)             Live-Preview & Status-Updates
├── HA Client                   Bidirektionale HA-Kommunikation
├── Entity Sync                 Szenen ↔ HA Switch-Entities
├── Device Controller           WLED JSON API + UDP DNRGB
├── Scene Playback              Frame-Sequencing, Upscaling
├── Image Converter             Bild → Pixel-Daten (Pillow)
├── Binary Format               .ledm Import/Export
└── SQLite (async SQLAlchemy)   Persistenz (/data/wled_matrix.db)
    │
    ▼
React Frontend (Ingress UI)
├── Scene Editor                Pixel-Art Editor, Multi-Frame
├── Device Management           WLED-Geräte CRUD + Health
├── Playback Control            Start/Stop, Status-Anzeige
└── Ant Design UI               Responsive Layout
```

## Verzeichnisstruktur

```
WLEDMatrixManager/
├── backend/
│   ├── main.py                 FastAPI App, Lifespan, WebSocket
│   ├── requirements.txt
│   └── app/
│       ├── router.py           Alle API-Endpoints
│       ├── models.py           SQLAlchemy + Pydantic Models
│       ├── database.py         Async SQLite Session
│       ├── device_controller.py  WLED JSON/UDP Kommunikation
│       ├── scene_playback.py   Playback-Engine mit Upscaling
│       ├── ha_client.py        HA WebSocket Client
│       ├── ha_entity_sync.py   Scene ↔ HA Entity Registration
│       ├── image_converter.py  Bild-Upload → Pixel-Daten
│       └── binary_format.py    .ledm Serialisierung
├── frontend/
│   ├── src/
│   │   ├── App.tsx             Routing, Layout
│   │   ├── pages/              Home, Devices, Scenes, SceneEditor
│   │   ├── api/client.ts       API + WebSocket Client
│   │   ├── hooks/              useWebSocket
│   │   └── utils/              binaryFormat, wledParser
│   ├── vite.config.ts          base: './' für Ingress
│   └── package.json
├── custom_components/
│   └── wled_matrix_manager/    HA Custom Integration (Switch)
├── rootfs/                     s6-overlay Service
├── Dockerfile                  Multi-Stage Build (Node → Python)
├── config.yaml                 Add-on Konfiguration
└── DOCS.md                     Benutzerdokumentation
```

## Lizenz

EUPL-1.2 — Siehe [LICENSE](../LICENSE)
