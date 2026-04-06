# WLED Matrix Manager — Home Assistant Add-on

Erstelle und verwalte Pixel-Art-Szenen für WLED LED-Matrizen direkt aus Home Assistant heraus.

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Faiakos-k%2FWLEDMatrixManager)

## Was ist WLED Matrix Manager?

WLED Matrix Manager ist ein Home Assistant Add-on, mit dem du:

- **Pixel-Art-Szenen** erstellen und auf WLED LED-Matrizen abspielen kannst
- **Geräte verwalten** — WLED-Geräte hinzufügen, konfigurieren und den Health-Status prüfen
- **Animationen abspielen** — Frame-basierte Szenen mit einstellbarer Geschwindigkeit, Helligkeit und Loop-Modi
- **Live-Vorschau** per WebSocket direkt im Browser sehen kannst
- **Home Assistant Integration** — Szenen werden als HA-Entities registriert und sind per Automatisierung steuerbar
- **Import/Export** — Szenen als Binärdatei oder Bild importieren/exportieren

## Architektur

```
Home Assistant Core
    │ WebSocket API
    ▼
FastAPI Backend (:8000)
├── REST API (/api/...)      — Szenen, Geräte, Playback
├── WebSocket (/ws)          — Live-Preview & Status
├── WLED-Kommunikation       — JSON API + UDP DNRGB
└── SQLite Datenbank         — Szenen & Geräte-Speicher
    │
    ▼
React Frontend (Ingress UI)
├── Scene Editor             — Pixel-Art Editor mit Frame-Support
├── Device Management        — WLED-Geräte verwalten
└── Playback Control         — Szenen starten/stoppen
```

### Kommunikationsprotokolle

| Protokoll | Einsatz | Max LEDs |
|-----------|---------|----------|
| **JSON API** (`/json/state`) | Einzelframes, Konfiguration | unbegrenzt |
| **UDP DNRGB** (Port 21324) | Echtzeit-Streaming, Animationen | 489/Paket (chunked) |

Details: [WLED_PROTOCOLS.md](./WLEDMatrixManager/backend/docs/WLED_PROTOCOLS.md)

## Installation

### Via Home Assistant Add-on Store

1. **Settings → Add-ons → Add-on Store** → ⋮ → **Repositories**
2. Repository-URL hinzufügen
3. **WLED Matrix Manager** installieren und starten
4. Das Add-on erscheint in der **Seitenleiste**

### Entwickler-Setup

Siehe [QUICKSTART.md](./QUICKSTART.md) für das DevContainer-Setup.

## Konfiguration

| Option | Beschreibung | Standard |
|--------|-------------|----------|
| `log_level` | Log-Level (`debug`, `info`, `warning`, `error`) | `info` |

Das Add-on benötigt:
- **Homeassistant API** — für WebSocket-Kommunikation mit HA Core
- **Hassio API (admin)** — für Supervisor-Zugriff
- **Netzwerkzugriff** — UDP/HTTP-Kommunikation mit WLED-Geräten

## API-Übersicht

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/status` | GET | Add-on Status |
| `/api/devices` | GET/POST | Geräte auflisten/anlegen |
| `/api/devices/{id}` | PUT/DELETE | Gerät bearbeiten/löschen |
| `/api/devices/{id}/health` | GET | WLED-Gerät Health-Check |
| `/api/ha/discover` | GET | WLED-Geräte aus HA entdecken |
| `/api/scenes` | GET/POST | Szenen auflisten/anlegen |
| `/api/scenes/{id}` | GET/PUT/DELETE | Szene lesen/bearbeiten/löschen |
| `/api/scenes/{id}/play` | POST | Szene abspielen |
| `/api/scenes/{id}/stop` | POST | Playback stoppen |
| `/api/scenes/{id}/export` | GET | Szene als Binärdatei exportieren |
| `/api/scenes/import` | POST | Szene importieren |
| `/api/devices/test-frame` | POST | Einzelnen Frame an Geräte senden |
| `/health` | GET | Health-Check |
| `/ws` | WebSocket | Live-Preview & Playback-Status |

Swagger-Docs: `http://<host>:8000/docs`

## Technologien

### Backend
- **Python 3.11+** / **FastAPI** / **Uvicorn**
- **SQLAlchemy** (async) + **SQLite**
- **aiohttp** — WLED HTTP & HA WebSocket
- **Pydantic** — Datenvalidierung
- **Pillow / NumPy** — Bildverarbeitung

### Frontend
- **React 18** / **TypeScript** / **Vite**
- **Ant Design** — UI-Komponenten
- **React Router** — SPA-Navigation

### Infrastruktur
- **Docker** Multi-Stage Build
- **s6-overlay** — Prozess-Management
- **Home Assistant Ingress** — nahtlose UI-Integration

## Dokumentation

- [QUICKSTART.md](./QUICKSTART.md) — DevContainer-Setup & erste Schritte
- [TEMPLATE_GUIDE.md](./TEMPLATE_GUIDE.md) — Ingress-Routing & Build-Architektur
- [WLED_PROTOCOLS.md](./WLEDMatrixManager/backend/docs/WLED_PROTOCOLS.md) — WLED-Protokollreferenz (JSON API, UDP DNRGB, Realtime-Mode)
- [DOCS.md](./WLEDMatrixManager/DOCS.md) — Detaillierte Add-on Dokumentation

## Lizenz

Dieses Projekt ist unter der **European Union Public Licence v. 1.2 (EUPL-1.2)** lizenziert.

Siehe [LICENSE](./LICENSE) für den vollständigen Lizenztext.

EUPL-1.2 ist kompatibel mit GPL v2/v3, AGPL v3, LGPL v2.1/v3, MPL v2 und weiteren
(siehe Anhang der Lizenz).

---

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
