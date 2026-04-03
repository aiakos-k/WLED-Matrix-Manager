# Home Assistant Add-on - Modern Architecture

Eine moderne, professionelle Home Assistant Add-on Architektur mit **FastAPI Backend**, **React Frontend** und **WebSocket Integration**.

## 🏗️ Architektur

```
┌─────────────────────────────────────────────────────────┐
│                Home Assistant Core                      │
├─────────────────────────────────────────────────────────┤
│  WebSocket API    (supervisor/core/websocket)           │
└───────────────────────┬─────────────────────────────────┘
                        │ WebSocket
                        ▼
        ┌───────────────────────────────┐
        │  FastAPI Backend              │
        │  ┌─────────────────────────┐  │
        │  │ REST API (/api/...)     │  │
        │  │ WebSocket (/ws)         │  │
        │  │ Static Files (/static)  │  │
        │  └─────────────────────────┘  │ :8000
        │  │                             │
        │  │ HA WebSocket Client         │
        │  │ - Service Calls             │
        │  │ - State Management          │
        │  │ - Entity Updates            │
        │  └─────────────────────────┘  │
        └───────────────────────────────┘
                    │         │
              REST  │         │ WebSocket
                    ▼         ▼
        ┌─────────────────────────────┐
        │  React Frontend Dashboard   │
        │  ┌─────────────────────────┐│
        │  │ Real-time UI Updates    ││
        │  │ Entity Controls         ││
        │  │ Settings & Config       ││
        │  └─────────────────────────┘│  :3000
        │  ┌─────────────────────────┐│
        │  │ Zustand State Mgmt      ││
        │  │ TypeScript Support      ││
        │  │ Responsive Design       ││
        │  └─────────────────────────┘│
        └─────────────────────────────┘
```

## 🚀 Features

### Backend (FastAPI)
- ✅ **FastAPI** - Modernes, schnelles Python Web Framework
- ✅ **WebSocket Client** - Bidirektionale Kommunikation mit Home Assistant
- ✅ **REST API** - RESTful endpoints für Frontend-Kommunikation
- ✅ **Type Hints** - Pydantic Models für API Validation
- ✅ **Async/Await** - Vollständig asynchrone Architektur
- ✅ **Health Check** - Eingebaute Health-Check Endpoints
- ✅ **Logging** - Strukturiertes Logging

### Frontend (React)
- ✅ **React 18** - Neueste React Version
- ✅ **TypeScript** - Type-Safe Entwicklung
- ✅ **Vite** - Ultra-schneller Build Tool
- ✅ **Zustand** - Leichtgewichtiges State Management
- ✅ **WebSocket Client** - Echtzeit-Updates
- ✅ **Responsive Design** - Mobile-first Approach
- ✅ **CSS-in-CSS** - Modernes Styling

### Add-on Integration
- ✅ **Ingress UI** - Nativ in Home Assistant integriert
- ✅ **Multi-Arch** - aarch64 und amd64 Support
- ✅ **Docker Multi-Stage Build** - Optimierte Image Größe
- ✅ **Environment Variables** - Konfigurierbar via Home Assistant
- ✅ **Logging Integration** - Zugriff auf Home Assistant Logs

## 📋 Voraussetzungen

- Home Assistant 2023.8+
- Docker (für lokale Entwicklung)
- Node.js 18+ (für Frontend Development)
- Python 3.11+ (für Backend Development)
- Mamba oder Conda (empfohlen)

## 🛠️ Entwicklung

### VS Code DevContainer Setup

1. **Öffne das Projekt in VS Code** mit Remote Container
2. **DevContainer startet automatisch** mit allen Tools
3. **Ports werden automatisch gemappt**:
   - Backend: http://localhost:8000
   - Frontend: http://localhost:3000
   - Home Assistant: http://localhost:7123

### Backend-Entwicklung

```bash
# In VS Code Terminal oder DevContainer

# Installiere Dependencies
pip install -r example/backend/requirements.txt

# Starte FastAPI Development Server
cd example/backend
python main.py
```

Backend läuft auf: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

### Frontend-Entwicklung

```bash
# In VS Code Terminal oder DevContainer

# Installiere Dependencies
cd example/frontend
npm install

# Starte Vite Development Server
npm run dev
```

Frontend läuft auf: `http://localhost:3000`

## 📦 Projektstruktur

```
example/
├── backend/                      # FastAPI Backend
│   ├── main.py                   # Application Entry Point
│   ├── requirements.txt           # Python Dependencies
│   └── app/
│       ├── __init__.py
│       ├── router.py             # API Routes
│       ├── models.py             # Pydantic Models
│       └── ha_client.py          # Home Assistant WebSocket Client
│
├── frontend/                     # React Frontend
│   ├── package.json              # NPM Dependencies
│   ├── tsconfig.json            # TypeScript Config
│   ├── vite.config.ts           # Vite Config
│   ├── index.html               # HTML Entry Point
│   └── src/
│       ├── main.tsx             # React Entry Point
│       ├── App.tsx              # Main Component
│       ├── api/
│       │   └── client.ts        # Home Assistant API Client
│       ├── store/
│       │   └── ha.ts            # Zustand State Store
│       ├── hooks/
│       │   └── useWebSocket.ts  # WebSocket Hook
│       └── components/
│           ├── Dashboard.tsx    # Dashboard Component
│           └── Dashboard.css    # Styles
│
├── rootfs/                      # Add-on Runtime
│   └── etc/services.d/example/
│       └── run                  # Service Start Script
│
├── Dockerfile                    # Multi-Stage Build
├── config.yaml                   # Add-on Configuration
├── build.yaml                    # Build Configuration
└── DOCS.md                      # Documentation
```

## 🐳 Docker Build

### Lokaler Build

```bash
# Build für lokale Home Assistant Instance
ha addons rebuild --force local_example

# Start Addon
ha addons start local_example

# View Logs
docker logs --follow addon_local_example
```

### Production Build

```bash
# Build für Release
docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.15 \
  --tag ghcr.io/myusername/amd64-addon-example:1.2.0 \
  ./example
```

## 🔌 API Endpoints

### REST API

```
GET  /health                    # Health Check
GET  /api/status               # Get Add-on Status
GET  /api/entities             # Get All Entities
POST /api/service/{domain}/{service}  # Call Service
```

### WebSocket

```
ws://localhost:8000/ws         # Real-time Updates
```

Beispiel-Nachricht:
```json
{
  "action": "get_entities"
}
```

## 🎯 Home Assistant Integration

### Ingress Configuration

Das Add-on wird automatisch im Add-on Dashboard verfügbar gemacht unter:
- **Titel**: Home Assistant Add-on
- **Icon**: mdi:application
- **URL**: /dashboard
- **Port**: 3000 (intern), automatisch durch Ingress gemappt

### WebSocket Verbindung zu Home Assistant

Der HAClient stellt automatisch eine Verbindung her zu:
```
ws://supervisor/core/websocket
```

Authentifizierung erfolgt via `SUPERVISOR_TOKEN` Environment Variable.

## 📚 Verwendete Technologien

### Backend
- **FastAPI** - Web Framework
- **Uvicorn** - ASGI Server
- **Pydantic** - Data Validation
- **aiohttp** - Async HTTP Client
- **WebSockets** - WebSocket Support

### Frontend
- **React 18** - UI Framework
- **TypeScript** - Type Safety
- **Vite** - Build Tool
- **Zustand** - State Management
- **Axios** - HTTP Client

### Infrastructure
- **Docker** - Containerization
- **Alpine Linux** - Base Image (3.15)
- **s6-overlay** - Init System
- **Home Assistant** - Platform

## 🔐 Security

- ✅ HTTPS in Production
- ✅ CORS Protection
- ✅ CSRF Tokens (optional)
- ✅ Input Validation (Pydantic)
- ✅ Rate Limiting ready
- ✅ Authentication via Supervisor Token

## 📖 Weitere Ressourcen

- [Home Assistant Developers](https://developers.home-assistant.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [WebSocket API Guide](https://developers.home-assistant.io/docs/api/websocket/)

## 📝 Lizenz

Apache License 2.0 - siehe LICENSE Datei

## 🤝 Beitragen

Beiträge sind willkommen! Bitte erstelle einen Pull Request mit deinen Änderungen.

---

**Entwickelt mit ❤️ für Home Assistant**
