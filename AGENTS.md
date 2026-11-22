# AI Agent Instructions

This repository contains the **WLED Matrix Manager**, a Home Assistant add-on with a
FastAPI backend and a React (Vite + antd) frontend.

## Repository layout

| Path | Purpose |
|---|---|
| `wled_matrix_manager/config.yaml` | Add-on manifest (slug `wled_matrix_manager`, version, options) |
| `wled_matrix_manager/build.yaml` | Build metadata (base images per architecture) |
| `wled_matrix_manager/Dockerfile` | Multi-stage image build (Node frontend stage → Python runtime) |
| `wled_matrix_manager/rootfs/` | Files copied into the add-on image (`/etc/services.d/...`) |
| `wled_matrix_manager/backend/main.py` | FastAPI entry point, static file serving, WebSocket endpoint |
| `wled_matrix_manager/backend/app/` | Backend modules (`ha_client`, `ha_entity_sync`, `router`, `database`, …) |
| `wled_matrix_manager/backend/requirements.txt` | Pinned Python dependencies (production **and** dev container) |
| `wled_matrix_manager/frontend/src/` | React sources |
| `devcontainer_bootstrap` | Dev container setup: dependencies, pi/Claude CLI, Supervisor patches |
| `.devcontainer.json` | Dev container definition (Python 3.12, Node 22) |

## Development environment

The dev container is the supported way to work on this repository
(*Dev Containers: Reopen in Container*). It provides:

- Python **3.12** – the same version as the add-on image
  (`ghcr.io/home-assistant/*-base:3.20` → Alpine 3.20 → Python 3.12). Do not change the
  Python version in `.devcontainer.json` without also updating the add-on base image.
- Node **22** for the frontend build (Node 20 is EOL).
- `uv` for the Python virtual environment, like Home Assistant Core does.
- The Home Assistant Supervisor (patched via `patch_supervisor.sh`) so the add-on can be
  installed and tested locally.

`devcontainer_bootstrap` is idempotent: it recreates the virtual environment when the
Python version changed and reinstalls dependencies only when `requirements.txt` or
`package-lock.json` changed (tracked via stamp files).

## Commands

Backend (run inside `wled_matrix_manager/backend`, with `venv` activated):

```bash
venv/bin/python -m uvicorn main:app --reload --port 8000   # dev server
venv/bin/python -m ruff check .                             # lint
```

Frontend (run inside `wled_matrix_manager/frontend`):

```bash
npm run dev         # dev server on http://localhost:3000
npm run build       # type check (tsc) + production build
npm run type-check  # tsc --noEmit
npm run lint        # biome check
npm run lint:fix    # biome check --write
```

Add-on:

```bash
ha apps rebuild --force local_wled_matrix_manager
ha apps start local_wled_matrix_manager
docker logs --follow addon_local_wled_matrix_manager
```

## Conventions

- **Python**: `ruff` with the configuration in `wled_matrix_manager/backend/pyproject.toml`
  (line length 100, double quotes, isort ordering, flake8-bandit rules). Format with
  `ruff format`. Never disable a lint rule inline without a comment explaining why.
- **TypeScript/React**: `biome` for linting and formatting (`biome.json`), `tsc` for type
  checking. The biome configuration targets the schema of the installed biome version –
  after a biome upgrade run `npx biome migrate --write`.
- **Frontend formatting**: the repository uses Prettier via the VS Code extension for
  TypeScript. `biome format` can disagree with Prettier; do not reformat the whole
  frontend unless explicitly asked.
- **Dependencies**: `requirements.txt` is pinned exactly (`==`) and the frontend uses a
  committed `package-lock.json`. Never bump a dependency without updating the lock file.
- Prefer the smallest possible change. Do not mix unrelated refactors into a dependency
  update – this is explicitly required by the Home Assistant review guidelines.

## Pull requests

- Use the PR template in `.github/PULL_REQUEST_TEMPLATE.md` if present and keep every
  section and unchecked checkbox.
- Do not amend, squash or rebase commits that are already pushed to an open PR branch.
- A dependency bump PR must contain **only** the changes required for that bump.
- Mark breaking changes explicitly (Home Assistant requires a `## Breaking change`
  section with the type `breaking change`).
- Describe the effect of the change in the PR body, and mention the verification you ran
  (build, lint, tests).

## Before opening a pull request

1. `npm run build` in `wled_matrix_manager/frontend` (includes `tsc`)
2. `ruff check .` in `wled_matrix_manager/backend`
3. For dependency changes: build the add-on image
   (`ha apps rebuild --force local_wled_matrix_manager`) and check the logs.

## Gotchas

- The backend virtual environment lives inside the workspace
  (`wled_matrix_manager/backend/venv`). It only works **inside** the dev container –
  on the host the interpreter symlink is dangling. The bootstrap recreates it
  automatically.
- The add-on image is built from `ghcr.io/home-assistant/{arch}-base:3.20`. Python
  dependencies must therefore be installable on **Alpine 3.20 / Python 3.12** – wheels
  for other platforms are not enough.
- The legacy `home-assistant/builder` action is deprecated and only published up to
  `2026.03.2`. The builder image tag has to match the action ref, otherwise the image
  cannot be pulled.
- The Supervisor in the dev container needs the patches from `patch_supervisor.sh`;
  without them the add-on install fails with `docker_gateway_unprotected`.
