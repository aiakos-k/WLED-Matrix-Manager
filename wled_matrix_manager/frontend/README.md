# WLED Matrix Manager — Frontend

React TypeScript frontend for the WLED Matrix Manager.

## Development

```bash
npm ci
npm run dev
```

The frontend runs on http://localhost:3000 (development) or is served as static files by FastAPI in production builds.

## Build

```bash
npm run build
```

The build output in `dist/` is served by the backend as static files.

**Important:** `base: './'` in `vite.config.ts` ensures relative asset paths that work via Home Assistant Ingress.

## Technologies

- **React 19** + **TypeScript 7**
- **Vite 8** — Build tool
- **Ant Design** — UI components
- **React Router** — SPA navigation

## License

EUPL-1.2 — See [LICENSE](../../LICENSE)
