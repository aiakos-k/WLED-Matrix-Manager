# WLED Matrix Manager — Dokumentation

## Inhaltsverzeichnis

1. [Installation](#installation)
2. [Erste Schritte](#erste-schritte)
3. [Geräte verwalten](#geräte-verwalten)
4. [Szenen erstellen & abspielen](#szenen-erstellen--abspielen)
5. [Home Assistant Integration](#home-assistant-integration)
6. [API-Referenz](#api-referenz)
7. [WebSocket](#websocket)
8. [Konfiguration](#konfiguration)
9. [Fehlerbehebung](#fehlerbehebung)

---

## Installation

### Via Home Assistant Add-on Store

1. Gehe zu **Settings → Add-ons → Add-on Store**
2. Klicke auf ⋮ → **Repositories** und füge die Repository-URL hinzu
3. **WLED Matrix Manager** aus der Liste installieren
4. Add-on starten — es erscheint in der **Seitenleiste**

### Voraussetzungen

- Home Assistant 2023.8+
- Mindestens ein WLED-Gerät im Netzwerk
- WLED-Geräte müssen per HTTP und/oder UDP erreichbar sein

---

## Erste Schritte

1. **Add-on starten** und in der Seitenleiste öffnen
2. **WLED-Gerät hinzufügen** (manuell per IP oder Auto-Discovery aus HA)
3. **Neue Szene erstellen** mit Matrix-Dimensionen (z.B. 16×16)
4. **Pixel zeichnen** im Scene Editor
5. **Abspielen** auf dem WLED-Gerät

---

## Geräte verwalten

### Gerät hinzufügen

Über die Geräte-Seite kannst du WLED-Geräte registrieren:

- **Name** — Anzeigename
- **IP-Adresse** — Netzwerkadresse des WLED-Geräts
- **Matrix-Größe** — Breite × Höhe (z.B. 16×16)
- **Kommunikationsprotokoll** — `udp_dnrgb` (Standard, für Animationen) oder `json_api`
- **Segment-ID** — WLED-Segment (Standard: 0)
- **Scale Mode** — Skalierung bei unterschiedlicher Auflösung (`stretch`, `tile`, `center`, `none`)

### Auto-Discovery

Unter `/api/ha/discover` können WLED-Geräte automatisch aus Home Assistant erkannt werden. Voraussetzung: Die WLED-Integration ist in HA konfiguriert.

### Health-Check

Per `/api/devices/{id}/health` wird geprüft, ob das WLED-Gerät unter der gespeicherten IP erreichbar ist (GET auf `/json/info`).

---

## Szenen erstellen & abspielen

### Szene erstellen

Eine Szene besteht aus:

- **Name & Beschreibung**
- **Matrix-Dimensionen** (Breite × Höhe)
- **Frames** — Jeder Frame enthält:
  - **Pixel-Daten** — JSON-Objekt mit `"x,y": [R, G, B]` Einträgen
  - **Dauer** — Anzeigedauer in Millisekunden
  - **Helligkeit** — 0–255
  - **Hintergrundfarbe** — RGB-Werte für unbesetzte Pixel
- **Loop-Modus** — `once`, `loop` oder `bounce`

### Szene abspielen

Szenen können über die UI oder per API (`POST /api/scenes/{id}/play`) auf zugewiesene Geräte abgespielt werden.

**Playback-Verhalten:**
- Bei **UDP DNRGB**: Vor dem ersten Frame wird ein Solid-Black-Effekt an WLED gesendet, um Start-Flash zu vermeiden (300ms Wartezeit)
- Bei **JSON API**: Frames werden als `/json/state`-Commands mit `seg.i` gesendet
- **Upscaling**: Szenen-Auflösung wird automatisch auf die Geräte-Auflösung skaliert
- **Device-Exklusivität**: Pro Gerät kann nur eine Szene gleichzeitig laufen

### Import/Export

- **Export**: `GET /api/scenes/{id}/export` — Binärdatei (`.ledm`-Format)
- **Import**: `POST /api/scenes/import` — `.ledm`-Datei hochladen
- **Bild-Import**: `POST /api/image/convert` — Bild in Pixel-Daten umwandeln

---

## Home Assistant Integration

### Szenen als HA Entities

Jede Szene wird als **Switch-Entity** in Home Assistant registriert:
- `switch.wled_matrix_<scene_name>` — Ein/Aus schaltet Playback
- Entity-Attribute zeigen Frame-Anzahl, Matrix-Dimensionen, Loop-Modus etc.

### Automatisierungen

Szenen können in HA-Automatisierungen genutzt werden:

```yaml
automation:
  - trigger:
      - platform: time
        at: "20:00"
    action:
      - service: switch.turn_on
        entity_id: switch.wled_matrix_abendstimmung
```

---

## API-Referenz

Basis-URL: relativ zum Ingress-Pfad oder `http://<host>:8000`

### Status & Health

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/health` | GET | Health-Check (`ha_connected`-Status) |
| `/api/status` | GET | Add-on Version & Status |
| `/api/stats` | GET | Statistiken (Szenen, Geräte, aktive Playbacks) |

### Geräte

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/devices` | GET | Alle aktiven Geräte auflisten |
| `/api/devices` | POST | Neues Gerät anlegen |
| `/api/devices/{id}` | PUT | Gerät aktualisieren |
| `/api/devices/{id}` | DELETE | Gerät deaktivieren (soft-delete) |
| `/api/devices/{id}/health` | GET | WLED Health-Check |
| `/api/devices/test-frame` | POST | Einzelnen Frame direkt an Geräte senden |
| `/api/ha/discover` | GET | WLED-Geräte aus HA entdecken |
| `/api/ha/debug` | GET | HA-Verbindungsdiagnose |

### Szenen

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/scenes` | GET | Alle aktiven Szenen (inkl. Frames & Devices) |
| `/api/scenes` | POST | Neue Szene erstellen |
| `/api/scenes/{id}` | GET | Einzelne Szene lesen |
| `/api/scenes/{id}` | PUT | Szene aktualisieren |
| `/api/scenes/{id}` | DELETE | Szene deaktivieren (soft-delete) |

### Playback

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/scenes/{id}/play` | POST | Szene abspielen |
| `/api/scenes/{id}/stop` | POST | Playback stoppen |
| `/api/playback/status` | GET | Status aller laufenden Playbacks |

### Import/Export

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/scenes/{id}/export` | GET | Szene als `.ledm` Binärdatei |
| `/api/scenes/import` | POST | `.ledm`-Datei importieren |
| `/api/image/convert` | POST | Bild in Pixel-Daten konvertieren |

---

## WebSocket

Endpoint: `/ws`

### Nachrichten vom Client

**Preview-Frame senden** (wird an alle anderen Clients weitergeleitet):
```json
{"action": "preview_frame", "data": { ... }}
```

**Playback-Status abfragen:**
```json
{"action": "playback_status"}
```

**HA-Aktionen** (an den HA WebSocket Client):
```json
{"action": "get_entities"}
{"action": "call_service", "domain": "light", "service": "turn_on", "data": {"entity_id": "light.wled"}}
```

### Nachrichten vom Server

```json
{"type": "preview_frame", "data": { ... }}
{"type": "playback_status", "data": { ... }}
{"type": "ack", "action": "preview_frame"}
```

---

## Konfiguration

### Add-on Optionen (config.yaml)

| Option | Beschreibung | Standard |
|--------|-------------|----------|
| `log_level` | Log-Level: `debug`, `info`, `warning`, `error` | `info` |

### Benötigte Berechtigungen

- **homeassistant_api** — WebSocket-Kommunikation mit HA Core
- **hassio_api (admin)** — Supervisor-Zugriff
- **Netzwerk (Port 8000)** — Frontend & API
- **share:rw, addon_config:rw** — Datenpersistenz

### WLED-Gerät Einstellungen

Relevante WLED-Settings unter Settings → Sync:

| Setting | Bedeutung |
|---------|----------|
| Force Max Brightness | Erzwingt Brightness 255 im Realtime-Mode |
| Realtime Timeout | Standard-Timeout für Realtime (empfohlen: 5s) |
| Use Main Segment Only | Nur Hauptsegment für Realtime nutzen |

---

## Fehlerbehebung

### Add-on startet nicht

```bash
docker logs addon_local_wled_matrix_manager
```

Häufige Ursachen:
- Port 8000 bereits belegt
- Python-Dependencies fehlerhaft → Add-on neu bauen

### Frontend zeigt 404

- Prüfe ob `frontend/dist/index.html` existiert (im Docker-Image)
- Vite muss mit `base: './'` gebaut werden (siehe TEMPLATE_GUIDE.md)

### WLED-Gerät nicht erreichbar

1. IP-Adresse korrekt? → `curl http://<wled-ip>/json/info`
2. Gerät im gleichen Netzwerk wie HA?
3. Firewall-Regeln prüfen (UDP Port 21324 für DNRGB)

### Flash beim Playback-Start

Vor dem ersten UDP-Frame wird automatisch ein Solid-Black-Effekt gesetzt (300ms Wartezeit). Falls dennoch ein Flash sichtbar ist:
- Prüfe ob „Force Max Brightness" in WLED deaktiviert ist
- Erhöhe die Pre-Delay-Zeit

Details: [WLED_PROTOCOLS.md](./backend/docs/WLED_PROTOCOLS.md) — Abschnitt „Realtime-Mode Lifecycle"

### Add-on nicht in Seitenleiste

`ingress_panel: true` muss gesetzt sein. Im DevContainer:
```bash
./dev.sh start:addon
```

### WebSocket-Verbindung fehlgeschlagen

- Im DevContainer: WebSocket läuft auf `supervisor` Hostname, nicht `localhost`
- Browser DevTools → Network → WS Tab auf Fehler prüfen
