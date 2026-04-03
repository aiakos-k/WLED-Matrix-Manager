# Home Assistant Add-on Dokumentation

## Inhaltsverzeichnis

1. [Installation](#installation)
2. [Konfiguration](#konfiguration)
3. [API Dokumentation](#api-dokumentation)
4. [WebSocket Protocol](#websocket-protocol)
5. [Entwicklung](#entwicklung)
6. [Fehlerbehebung](#fehlerbehebung)

## Installation

### Via Home Assistant

1. Gehe zu **Settings → Add-ons → Add-on Store**
2. Klicke auf die drei Punkte und wähle **Repositories**
3. Füge die Repository-URL hinzu
4. Das Add-on sollte jetzt in der Liste erscheinen
5. Klicke darauf und wähle **Install**
6. Nach Installation klicke **Start**

### Lokal aus Quelle

```bash
# Repository klonen
git clone <repository-url>
cd ha-addons-example

# In Home Assistant DevContainer
ha addons rebuild --force local_example
ha addons start local_example
```

## Konfiguration

### config.yaml

```yaml
name: Example add-on
slug: example
description: Modernes Home Assistant Add-on
version: "1.2.0"
arch:
  - aarch64
  - amd64

# Ingress UI Settings
ingress: true
ingress_port: 3000
ingress_entry_point: /dashboard
panel_icon: mdi:application
panel_title: Example Dashboard

# Exposed Ports (optional)
ports:
  8000/tcp: 8000

# Optionen für Users
options:
  log_level: info

schema:
  log_level: "list(debug|info|warning|error)?"
```

### Environment Variable

Das Add-on setzt automatisch:
- `SUPERVISOR_TOKEN` - Authentifizierung zu Home Assistant
- `HOST` - Bind Address (0.0.0.0)
- `PORT` - Bind Port (8000)

## API Dokumentation

### Health Check

```http
GET /health HTTP/1.1
```

**Response:**
```json
{
  "status": "healthy",
  "ha_connected": true
}
```

### Get Status

```http
GET /api/status HTTP/1.1
```

**Response:**
```json
{
  "status": "running",
  "version": "1.2.0",
  "message": "Home Assistant Add-on is running"
}
```

### Get Entities

```http
GET /api/entities HTTP/1.1
```

**Response:**
```json
[
  {
    "entity_id": "light.living_room",
    "state": "on",
    "attributes": {
      "brightness": 255,
      "color_temp": 366
    }
  }
]
```

### Call Service

```http
POST /api/service/light/turn_on HTTP/1.1
Content-Type: application/json

{
  "entity_id": "light.living_room",
  "brightness": 200
}
```

**Response:**
```json
{
  "success": true,
  "domain": "light",
  "service": "turn_on",
  "data": {
    "entity_id": "light.living_room",
    "brightness": 200
  }
}
```

## WebSocket Protocol

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message);
};
```

### Message Format

#### Request - Get Entities

```json
{
  "action": "get_entities"
}
```

#### Response

```json
{
  "success": true,
  "entities": [
    {
      "entity_id": "light.living_room",
      "state": "on",
      "attributes": {}
    }
  ]
}
```

#### Request - Call Service

```json
{
  "action": "call_service",
  "domain": "light",
  "service": "turn_off",
  "data": {
    "entity_id": "light.living_room"
  }
}
```

#### Response

```json
{
  "success": true
}
```

### Real-time Updates

Das Add-on sendet automatisch Updates wenn sich Entities ändern:

```json
{
  "type": "entity_update",
  "entity": {
    "entity_id": "sensor.temperature",
    "state": "22.5",
    "attributes": {
      "unit_of_measurement": "°C"
    }
  }
}
```

## Entwicklung

### Setup Development Environment

```bash
# Mit VS Code DevContainer
1. Öffne Workspace in VS Code
2. Remote Containers Extension installieren
3. "Dev Container: Reopen in Container" ausführen
```

### Backend Entwicklung

```bash
# Dependencies installieren
pip install -r example/backend/requirements.txt

# Development Server starten
cd example/backend
python main.py

# Mit reload (Auto-restart bei Änderungen)
python -m uvicorn main:app --reload
```

### Frontend Entwicklung

```bash
# Dependencies installieren
cd example/frontend
npm install

# Development Server starten
npm run dev

# Build
npm run build

# Type-Check
npx tsc --noEmit
```

### Testing

```bash
# Backend Tests (TODO)
pytest

# Frontend Tests (TODO)
npm test
```

## Fehlerbehebung

### Add-on startet nicht

1. **Logs prüfen:**
   ```bash
   docker logs addon_local_example
   ```

2. **Häufige Fehler:**
   - Python dependencies fehlen
   - Frontend nicht gebaut
   - Port schon in Verwendung

### WebSocket Verbindung fehlgeschlagen

1. **DevTools öffnen** (F12)
2. **Network → WS** Tab prüfen
3. **Console** auf Fehler prüfen
4. **Backend läuft?** - http://localhost:8000/health

### Frontend zeigt nicht an

1. **Frontend ist gebaut?** - `npm run build`
2. **Index.html existiert?** - `frontend/dist/index.html`
3. **Statische Dateien werden zurückgegeben?** - Dev Tools prüfen

### To Home Assistant Connectivity

1. **SUPERVISOR_TOKEN ist gesetzt?**
   ```bash
   echo $SUPERVISOR_TOKEN
   ```

2. **WebSocket URL erreichbar?**
   ```bash
   curl -i ws://supervisor/core/websocket
   ```

3. **In Docker? (nicht im DevContainer)**
   - Use `supervisor` hostname
   - NOT localhost!

## Performance Optimization

### Backend
- Verwende `async/await` konsequent
- Connection Pooling für Database
- Caching von oft abgerufenen Daten

### Frontend
- Code Splitting mit dinamischen Imports
- Image Optimierung
- Lazy Loading von Komponenten

## Security Best Practices

1. **Input Validation** - Nutze Pydantic Models
2. **HTTPS nur in Production** - Reverse Proxy
3. **CORS konfigurieren** - Nur vertraute Origins
4. **Rate Limiting** - Protege API vor Abuse
5. **Logging** - Sensitive Data nicht loggen

## Weitere Ressourcen

- [Home Assistant Developers](https://developers.home-assistant.io/docs/add-ons/)
- [WebSocket API Docs](https://developers.home-assistant.io/docs/api/websocket/)
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [React Hooks](https://react.dev/reference/react)
