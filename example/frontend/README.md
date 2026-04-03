# Home Assistant Add-on Frontend

React TypeScript Frontend für das Home Assistant Add-on.

## Features

- 🎨 Modernes UI mit React
- 🔌 WebSocket Echtzeit-Updates
- 📱 Responsive Design
- ⚡ Vite für schnelle Entwicklung
- 🎯 TypeScript für Type-Safety
- 🧠 Zustand State Management

## Entwicklung

```bash
npm install
npm run dev
```

Frontend läuft auf: http://localhost:3000

## Build

```bash
npm run build
```

Die Build-Ausgabe wird in `dist/` erstellt.

## Environment Variables

- `NODE_ENV`: 'development' oder 'production'

Bei production werden API-Calls automatically zum Backend proxied.
