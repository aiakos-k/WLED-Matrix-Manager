# WLED Matrix Manager — Frontend

React TypeScript Frontend für den WLED Matrix Manager.

## Entwicklung

```bash
npm install
npm run dev
```

Frontend läuft auf http://localhost:3000 (Development) bzw. wird im Produktions-Build über FastAPI ausgeliefert.

## Build

```bash
npm run build
```

Die Build-Ausgabe in `dist/` wird vom Backend als Static Files serviert.

**Wichtig:** `base: './'` in `vite.config.ts` sorgt für relative Asset-Pfade, die über Home Assistant Ingress funktionieren.

## Technologien

- **React 18** + **TypeScript**
- **Vite** — Build-Tool
- **Ant Design** — UI-Komponenten
- **React Router** — SPA-Navigation

## Lizenz

EUPL-1.2 — Siehe [LICENSE](../../LICENSE)
