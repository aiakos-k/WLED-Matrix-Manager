# 🚀 Quickstart Guide - Home Assistant Add-on

Schnelle Anleitung um mit dem modernen Add-on Setup zu starten.

## ⚡ 5-Minuten Setup (DevContainer)

### Voraussetzungen

- VS Code mit **Remote Container Extension**
- Docker Desktop
- Git

### Setup

```bash
# 1. Repository klonen
git clone https://github.com/home-assistant/addons-example.git
cd ha-addons-example

# 2. In VS Code öffnen
code .

# 3. Container starten
# Command Palette (Ctrl+Shift+P) →
# "Dev Container: Reopen in Container"
# → Warten bis Container gebaut ist (1-2 Min)

# 4. Home Assistant starten (Terminal im Container)
# Option A: VS Code Task verwenden (Command Palette → "Run Task: Start Home Assistant")
# Option B: Befehl im Terminal
supervisor_run

# 5. Add-on bauen & starten (in neuem Terminal)
./dev.sh start:addon
```

**Fertig!** 🎉

- **Home Assistant**: http://localhost:7123
- **Add-on Dashboard**: In der HA-Seitenleiste → "Example Dashboard"
- Backend API (direkt): http://localhost:8000
- Swagger Docs (direkt): http://localhost:8000/docs

> Das Add-on wird über **Ingress** in der Seitenleiste angezeigt.
> Falls es nicht erscheint, `./dev.sh start:addon` nochmal ausführen.

---

## 📱 Ohne DevContainer (Lokal)

Wenn du DevContainer nicht nutzen möchtest:

```bash
# Backend starten (Terminal 1)
cd WLEDMatrixManager/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# Frontend starten (Terminal 2)
cd WLEDMatrixManager/frontend
npm install
npm run dev
```

Frontend: http://localhost:3000
Backend: http://localhost:8000

---

## 🤔 Erste Schritte

### Backend testen

Öffne http://localhost:8000/docs um die **Swagger API Docs** zu sehen.

Probiere aus:

1. `GET /health` - Health Check
2. `GET /api/status` - Status abrufen
3. Weitere Endpoints erkunden

### Frontend erkunden

Öffne http://localhost:3000

Der React Dashboard zeigt:

- Verbindungsstatus zu Backend
- Entity Liste
- Buttons zum Testen

### Code ändern

Die Backend & Frontend laufen im **Watch-Modus**:

- Backend: Bearbeite `WLEDMatrixManager/backend/app/*.py` → Automatisch Reload
- Frontend: Bearbeite `WLEDMatrixManager/frontend/src/**` → Hot Module Reload

### Mit Home Assistant verbinden

Das Add-on verbindet sich automatisch zu Home Assistant über:

```
ws://supervisor/core/websocket
```

Code: `WLEDMatrixManager/backend/app/ha_client.py`

---

## 🛠️ Nützliche Development Commands

```bash
# Im DevContainer oder lokal

# Setup (alles installieren)
./dev.sh setup

# Nur Frontend bauen
./dev.sh build:frontend

# Nur Backend testen
./dev.sh start:backend

# Docker Image bauen
./dev.sh build:docker

# Add-on starten (DevContainer)
./dev.sh start:addon

# Logs anschauen (DevContainer)
./dev.sh logs

# Alles aufräumen
./dev.sh clean
```

---

## 📂 Wichtige Dateien

| Datei                                           | Purpose                     |
| ----------------------------------------------- | --------------------------- |
| `WLEDMatrixManager/backend/main.py`              | FastAPI Application Entry   |
| `WLEDMatrixManager/backend/app/ha_client.py`     | HA WebSocket Client         |
| `WLEDMatrixManager/frontend/src/App.tsx`          | React App                   |
| `WLEDMatrixManager/frontend/src/api/client.ts`   | Frontend API Client         |
| `WLEDMatrixManager/config.yaml`                   | Add-on Konfiguration        |
| `.devcontainer.json`                               | VS Code DevContainer Config |

---

## 🐛 Häufige Fehler

### "DevContainer is not found"

→ Installiere **Remote Container Extension** in VS Code

### Backend startet nicht

```bash
# Check ob Python 3.11+ installiert ist
python3 --version

# Dependencies neu installieren
pip install -r requirements.txt
```

### Frontend zeigt nichts / 404 Not Found

```bash
# Backend läuft?
curl http://localhost:8000/health

# Frontend neu bauen (wichtig: vite.config.ts muss base: './' haben!)
cd WLEDMatrixManager/frontend && npm run build

# Add-on neu starten
./dev.sh start:addon
```

→ Details zu Ingress-Routing siehe [TEMPLATE_GUIDE.md](./TEMPLATE_GUIDE.md)

### Onboarding: "Failed to save: Unknown error"

Der DevContainer patcht den Supervisor automatisch beim Start. Falls das fehlschlägt
(z.B. nach Supervisor-Update), den Patch manuell anwenden:

```bash
# 1. Patch anwenden
docker exec hassio_supervisor python3 -c "
path = '/usr/src/supervisor/supervisor/api/supervisor.py'
with open(path, 'r') as f:
    content = f.read()
old = '        if ATTR_DIAGNOSTICS in body:\\n            self.sys_config.diagnostics = body[ATTR_DIAGNOSTICS]\\n            await self.sys_dbus.agent.set_diagnostics(body[ATTR_DIAGNOSTICS])'
new = '        if ATTR_DIAGNOSTICS in body:\\n            self.sys_config.diagnostics = body[ATTR_DIAGNOSTICS]\\n            try:\\n                await self.sys_dbus.agent.set_diagnostics(body[ATTR_DIAGNOSTICS])\\n            except Exception:\\n                pass'
if old in content:
    with open(path, 'w') as f:
        f.write(content.replace(old, new))
    print('PATCHED')
else:
    print('already patched or pattern changed')
"

# 2. Supervisor-Prozess neustarten (NICHT 'ha supervisor restart' — das löscht den Patch!)
docker exec hassio_supervisor pkill -f 'python3 -m supervisor'

# 3. 10 Sekunden warten, dann Onboarding erneut versuchen
```

> **Wichtig:** `ha supervisor restart` erstellt den Container neu und löscht alle Patches.
> Stattdessen immer `pkill` innerhalb des Containers verwenden.

### "Port already in use"

```bash
# Port 8000 oder 3000 sind schon belegt
# Andere Prozesse killen oder andere Ports verwenden
lsof -i :8000  # Find process
kill -9 <PID>
```

---

## 📚 Weitere Ressourcen

- [Home Assistant Add-on Docs](https://developers.home-assistant.io/docs/add-ons/)
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [React Documentation](https://react.dev/learn)
- [WebSocket API Reference](https://developers.home-assistant.io/docs/api/websocket/)

---

## 💡 Nächste Schritte

1. **Repository forken** - Deine eigene Version erstellen
2. **README anpassen** - Dein Add-on beschreiben
3. **Features hinzufügen** - Den Code erweitern
4. **In Home Assistant testen** - Mit echten Smart Home Devices
5. **GitHub Actions einrichten** - Automatische Builds
6. **Publishen** - In Community teilen 🎉

---

## 📖 Weiterführend

- [TEMPLATE_GUIDE.md](./TEMPLATE_GUIDE.md) — Technische Details zu Ingress, Routing und DevContainer-Patches
- [Home Assistant Add-on Docs](https://developers.home-assistant.io/docs/add-ons/)

---

**Viel Spaß bei der Entwicklung! 🚀**

Fragen? → [Community Forum](https://community.home-assistant.io/)
