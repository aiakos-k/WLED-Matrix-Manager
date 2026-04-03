# Template Guide: FastAPI + React Add-on für Home Assistant

Dieses Dokument beschreibt alle Entscheidungen und Konfigurationen, die notwendig waren,
damit dieses Template (FastAPI Backend + Vite/React Frontend) als Home Assistant Add-on
korrekt über Ingress funktioniert.

---

## 1. Wie Home Assistant Ingress funktioniert

Home Assistant betreibt einen Reverse-Proxy (im Supervisor). Wenn ein Add-on `ingress: true`
hat, wird es unter folgendem Pfad erreichbar:

```
/api/hassio_ingress/<session_token>/
```

Der Token ist dynamisch und ändert sich bei jedem Add-on-Restart. Der Supervisor leitet
Requests an den `ingress_port` des Add-on-Containers weiter und **entfernt dabei den
Ingress-Prefix** — das Add-on sieht also nur `/`, `/api/...`, `/assets/...` etc.

**Kernproblem**: Das Frontend wird in einem `<iframe>` geladen. Die URL in der Adressleiste
ist `http://ha:8123/api/hassio_ingress/<token>/`. Wenn das Frontend absolute Pfade
verwendet (`/assets/...`), sucht der Browser unter `http://ha:8123/assets/...` —
das gibt 404, weil der Ingress-Prefix fehlt.

---

## 2. Die Lösung: Relative Pfade

### 2.1 Vite Config (`frontend/vite.config.ts`)

```ts
export default defineConfig({
  base: './',   // ← Entscheidend! Erzeugt relative Asset-Pfade
  // ...
})
```

**Ohne `base: './'`** generiert Vite:
```html
<script src="/assets/index-abc123.js"></script>
```
→ Browser lädt `http://ha:8123/assets/index-abc123.js` → **404**

**Mit `base: './'`** generiert Vite:
```html
<script src="./assets/index-abc123.js"></script>
```
→ Browser löst relativ zur aktuellen URL auf → `http://ha:8123/api/hassio_ingress/<token>/assets/index-abc123.js` → **funktioniert**

### 2.2 API Client (`frontend/src/api/client.ts`)

```ts
// Produktion: relative Pfade (kein führender /)
export const API_BASE_URL = isProd ? "api" : "http://localhost:8000/api";

// WebSocket: basierend auf aktuellem Pfad
export const WS_URL = isProd
  ? `wss://${window.location.host}${window.location.pathname.replace(/\/$/, '')}/ws`
  : "ws://localhost:8000/ws";
```

- `"api"` statt `"/api"` — damit der Request relativ zum Ingress-Pfad geht
- `window.location.pathname` enthält den Ingress-Prefix, der für WebSocket benötigt wird

---

## 3. Backend-Konfiguration (`backend/main.py`)

```python
# API-Routen werden ZUERST registriert
app.include_router(router)  # /api/...

@app.get("/health")
async def health_check(): ...

@app.websocket("/ws")
async def websocket_endpoint(websocket): ...

# Static Files werden ZULETZT gemountet (Catch-All)
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
```

**Wichtig:**
- `StaticFiles` mit `html=True` liefert `index.html` für alle unbekannten Routen aus
  (SPA-Fallback)
- Der Mount auf `/` muss **nach** allen API-Routen kommen, sonst fängt er alles ab
- **Kein separater `/dashboard`-Pfad** nötig — das Frontend wird direkt am Root serviert

---

## 4. Add-on Config (`config.yaml`)

```yaml
ingress: true
ingress_port: 8000          # Port auf dem uvicorn lauscht
ingress_entry_point: /       # Root-Pfad, nicht /dashboard
panel_icon: mdi:application
panel_title: Example Dashboard
```

- `ingress_port` muss mit dem uvicorn-Port übereinstimmen (8000)
- `ingress_entry_point: /` — der Supervisor lädt diese URL beim Öffnen des Panels
- `init: false` — wir verwenden s6-overlay für den Prozess-Start

---

## 5. Dockerfile (Multi-Stage Build)

```dockerfile
# Stage 1: Frontend bauen
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --omit=dev
COPY frontend/ ./
RUN npm run build              # erzeugt dist/ mit relativen Pfaden

# Stage 2: Finales Image
FROM $BUILD_FROM
# Python + Dependencies installieren
COPY backend/ /app/backend/
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
```

- Frontend wird im Build-Stage kompiliert, nur `dist/` wird ins finale Image kopiert
- `$BUILD_FROM` ist das HA Base Image (wird von `build.yaml` gesetzt)

---

## 6. Service-Start (`rootfs/etc/services.d/example/run`)

```bash
#!/usr/bin/with-contenv bashio
cd /app/backend
exec python3 main.py
```

- `bashio` stellt Umgebungsvariablen bereit (`SUPERVISOR_TOKEN`, etc.)
- `exec` ersetzt den Shell-Prozess → s6-overlay kann den Prozess überwachen

---

## 7. DevContainer-spezifische Workarounds

Im DevContainer fehlen systemd, dbus und os-agent. Das verursacht zwei Probleme:

### 7.1 Firewall-Check schlägt fehl

Der Supervisor versucht iptables-Regeln über systemd zu setzen → `docker_gateway_unprotected`.

**Patch** (in `devcontainer_bootstrap`): Die Methode `apply_gateway_firewall_rules` wird
durch einen No-Op ersetzt.

### 7.2 Diagnostics/Analytics-Speichern schlägt fehl

Beim Onboarding ruft HA `set_diagnostics()` über D-Bus auf → OS-Agent nicht vorhanden → Fehler.

**Patch**: Der `set_diagnostics()`-Aufruf wird in `try/except` gewrappt.

### 7.3 Automatisches Re-Patching

Der Supervisor-Container wird bei Updates neugebaut → Patches gehen verloren.
`devcontainer_bootstrap` überwacht `docker events` und patcht automatisch nach jedem
Supervisor-Neustart.

---

## 8. Ingress Panel aktivieren

Damit das Add-on in der HA-Seitenleiste erscheint, muss `ingress_panel: true` gesetzt werden:

```bash
# Wird automatisch von dev.sh start:addon ausgeführt
curl -X POST \
  -H "Authorization: Bearer $SUPERVISOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ingress_panel": true}' \
  http://supervisor/addons/local_example/options
```

---

## 9. Zusammenfassung: Was muss stimmen

| Komponente | Einstellung | Warum |
|---|---|---|
| `vite.config.ts` | `base: './'` | Relative Asset-Pfade für Ingress-iframe |
| `client.ts` | `API_BASE_URL = "api"` (ohne `/`) | Relative API-Requests |
| `client.ts` | `window.location.pathname` für WS | WebSocket braucht vollen Ingress-Pfad |
| `main.py` | `app.mount("/", StaticFiles(...))` | Frontend am Root servieren |
| `main.py` | Static mount **nach** API-Routen | Sonst fängt Catch-All die API ab |
| `config.yaml` | `ingress_port: 8000` | Muss zum uvicorn-Port passen |
| `config.yaml` | `ingress_entry_point: /` | Supervisor lädt Root-URL |
| `Dockerfile` | Multi-Stage: `npm run build` | Frontend wird mit `base: './'` gebaut |
| `devcontainer_bootstrap` | Firewall + Diagnostics Patches | DevContainer hat kein systemd/dbus |

---

## 10. Häufige Fehler

**404 Not Found im Dashboard:**
→ Prüfe `base: './'` in `vite.config.ts` und rebuild das Frontend

**Add-on nicht in Seitenleiste:**
→ `ingress_panel: true` über Supervisor-API setzen (siehe Abschnitt 8)

**"Unhealthy: docker_gateway_unprotected":**
→ Firewall-Patch im Supervisor fehlt (nur DevContainer-Problem)

**"Failed to save" beim Onboarding:**
→ Diagnostics-Patch im Supervisor fehlt (nur DevContainer-Problem)

**Assets laden nicht (net::ERR_ABORTED 404):**
→ `base` in vite.config.ts ist nicht `'./'`, oder Frontend wurde nicht neu gebaut

**API-Requests gehen an falschen Host:**
→ `API_BASE_URL` darf in Produktion keinen führenden `/` haben → `"api"` statt `"/api"`
