# Quickstart Guide — WLED Matrix Manager

Quick guide to get started with the WLED Matrix Manager setup.

## ⚡ 5-Minute Setup (DevContainer)

### Prerequisites

- VS Code with **Remote Container Extension**
- Docker Desktop
- Git

### Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd WLEDMatrixManager

# 2. Open in VS Code
code .

# 3. Start the container
# Command Palette (Ctrl+Shift+P) →
# "Dev Container: Reopen in Container"
# → Wait until the container is built (1-2 min)

# 4. Start Home Assistant (terminal inside the container)
# Option A: Use a VS Code Task (Command Palette → "Run Task: Start Home Assistant")
# Option B: Run the command in the terminal
supervisor_run

# 5. Build & start the add-on (in a new terminal)
./dev.sh start:addon
```

**Done!** 🎉

- **Home Assistant**: http://localhost:7123
- **Add-on Dashboard**: In the HA sidebar → "WLED Matrix Manager"
- Backend API (direct): http://localhost:8000
- Swagger Docs (direct): http://localhost:8000/docs

> The add-on is displayed via **Ingress** in the sidebar.
> If it doesn't appear, run `./dev.sh start:addon` again.

---

## 📱 Without DevContainer (Local)

If you don't want to use DevContainer:

```bash
# Start backend (Terminal 1)
cd WLEDMatrixManager/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# Start frontend (Terminal 2)
cd WLEDMatrixManager/frontend
npm install
npm run dev
```

Frontend: http://localhost:3000
Backend: http://localhost:8000

---

## 🤔 First Steps

### Test the Backend

Open http://localhost:8000/docs to see the **Swagger API Docs**.

Try it out:

1. `GET /health` - Health Check
2. `GET /api/status` - Get status
3. Explore more endpoints

### Explore the Frontend

Open http://localhost:3000

The React Dashboard shows:

- Connection status to the backend
- Entity list
- Buttons for testing

### Modify Code

Backend & frontend run in **watch mode**:

- Backend: Edit `WLEDMatrixManager/backend/app/*.py` → Auto reload
- Frontend: Edit `WLEDMatrixManager/frontend/src/**` → Hot Module Reload

### Connect to Home Assistant

The add-on automatically connects to Home Assistant via:

```
ws://supervisor/core/websocket
```

Code: `WLEDMatrixManager/backend/app/ha_client.py`

---

## 🛠️ Useful Development Commands

```bash
# In DevContainer or locally

# Setup (install everything)
./dev.sh setup

# Build frontend only
./dev.sh build:frontend

# Test backend only
./dev.sh start:backend

# Build Docker image
./dev.sh build:docker

# Start add-on (DevContainer)
./dev.sh start:addon

# View logs (DevContainer)
./dev.sh logs

# Clean up everything
./dev.sh clean
```

---

## 📂 Important Files

| File                                            | Purpose                     |
| ----------------------------------------------- | --------------------------- |
| `WLEDMatrixManager/backend/main.py`              | FastAPI Application Entry   |
| `WLEDMatrixManager/backend/app/ha_client.py`     | HA WebSocket Client         |
| `WLEDMatrixManager/frontend/src/App.tsx`          | React App                   |
| `WLEDMatrixManager/frontend/src/api/client.ts`   | Frontend API Client         |
| `WLEDMatrixManager/config.yaml`                   | Add-on Configuration        |
| `.devcontainer.json`                               | VS Code DevContainer Config |

---

## 🐛 Common Issues

### "DevContainer is not found"

→ Install the **Remote Container Extension** in VS Code

### Backend won't start

```bash
# Check if Python 3.11+ is installed
python3 --version

# Reinstall dependencies
pip install -r requirements.txt
```

### Frontend shows nothing / 404 Not Found

```bash
# Is the backend running?
curl http://localhost:8000/health

# Rebuild frontend (important: vite.config.ts must have base: './')
cd WLEDMatrixManager/frontend && npm run build

# Restart the add-on
./dev.sh start:addon
```

→ For details on Ingress routing see [TEMPLATE_GUIDE.md](./TEMPLATE_GUIDE.md)

### Onboarding: "Failed to save: Unknown error"

The DevContainer patches the Supervisor automatically on start. If this fails
(e.g., after a Supervisor update), apply the patch manually:

```bash
# 1. Apply the patch
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

# 2. Restart the Supervisor (do NOT use 'ha supervisor restart' — it removes the patch!)
docker restart hassio_supervisor

# 3. Wait ~20 seconds, then retry onboarding
```

> **Important:** Always use `docker restart hassio_supervisor`!
> - `ha supervisor restart` recreates the container → patches are lost
> - `pkill` causes a cascade → Docker daemon crashes

### "Port already in use"

```bash
# Port 8000 or 3000 is already in use
# Kill other processes or use different ports
lsof -i :8000  # Find process
kill -9 <PID>
```

---

## 📚 Additional Resources

- [Home Assistant Add-on Docs](https://developers.home-assistant.io/docs/add-ons/)
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [React Documentation](https://react.dev/learn)
- [WebSocket API Reference](https://developers.home-assistant.io/docs/api/websocket/)

---

## 💡 Next Steps

1. **Fork the repository** - Create your own version
2. **Customize the README** - Describe your add-on
3. **Add features** - Extend the code
4. **Test in Home Assistant** - With real smart home devices
5. **Set up GitHub Actions** - Automated builds
6. **Publish** - Share with the community 🎉

---

## 📖 Further Reading

- [TEMPLATE_GUIDE.md](./TEMPLATE_GUIDE.md) — Technical details on Ingress, routing, and DevContainer patches
- [Home Assistant Add-on Docs](https://developers.home-assistant.io/docs/add-ons/)

---

**Happy coding! 🚀**

Questions? → [Community Forum](https://community.home-assistant.io/)
