# AI Agent Instructions

This repository contains the **WLED Matrix Manager**, a Home Assistant add-on with a
FastAPI backend and a React (Vite + antd) frontend.

## Repository layout

| Path | Purpose |
|---|---|
| `wled_matrix_manager/config.yaml` | Add-on manifest (slug `wled_matrix_manager`, version, options) |
| `wled_matrix_manager/Dockerfile` | Multi-stage image build (Node frontend stage → Python runtime, `ARG BUILD_FROM`) |
| `wled_matrix_manager/rootfs/` | Files copied into the add-on image (`/etc/s6-overlay/s6-rc.d/...`) |
| `wled_matrix_manager/backend/main.py` | FastAPI entry point, static file serving, WebSocket endpoint |
| `wled_matrix_manager/backend/app/` | Backend modules (`ha_client`, `ha_entity_sync`, `router`, `database`, …) |
| `wled_matrix_manager/backend/requirements.txt` | Pinned Python dependencies (production) |
| `wled_matrix_manager/backend/requirements-dev.txt` | Dev tooling (Ruff) |
| `wled_matrix_manager/frontend/src/` | React sources |
| `.github/workflows/builder.yaml` | CI: builds and publishes the add-on image |
| `AGENTS.md`, `QUICKSTART.md` | These instructions and the setup guide |

## Development environment

The repository has **no own dev container** – development happens inside the central
`ha-development` platform (see `QUICKSTART.md`). It provides:

- Python **3.12** – the same version as the add-on image
  (`ghcr.io/home-assistant/*-base:3.23` → Alpine → Python 3.12). Do not change the
  Python version in `.python-version` without also updating the add-on base image.
- Node **22** for the frontend build.
- `uv` for the Python virtual environment, like Home Assistant Core does.
- The Home Assistant Supervisor and Home Assistant Core, so the add-on can be installed
  and tested locally.

Supervisor patches are applied centrally by the platform
(`bash scripts/ha-stack.sh patch`), not by this repository.

## Commands

Backend (run inside `wled_matrix_manager/backend`, with `venv` activated):

```bash
venv/bin/python -m uvicorn main:app --reload --port 8000   # dev server
venv/bin/python -m ruff check .                             # lint
```

Frontend (run inside `wled_matrix_manager/frontend`):

```bash
npm ci           # install exactly the committed lock file
npm run dev         # dev server on http://localhost:3000
npm run build       # type check (tsc) + production build
npm run type-check  # tsc --noEmit
npm run lint        # biome check
npm run lint:fix    # biome check --write
```

Add-on (centrally, via `ha-development`):

```bash
bash scripts/ha-stack.sh apps rebuild local_wled_matrix_manager
bash scripts/ha-stack.sh apps start local_wled_matrix_manager
bash scripts/ha-stack.sh logs local_wled_matrix_manager
```

## Releases

A release touches **exactly two files** in this repository:

1. `wled_matrix_manager/config.yaml` → set `version:` to the new version
2. `wled_matrix_manager/CHANGELOG.md` → insert a new `## X.Y.Z` section **at the top**

Both files always belong into the same commit. `wled_matrix_manager/frontend/package.json`
has its own, separate version which is deliberately **not** touched for add-on releases.

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
   (`bash scripts/ha-stack.sh apps rebuild local_wled_matrix_manager`) and check the logs.

## Gotchas

- The add-on image is built from `ghcr.io/home-assistant/{arch}-base:3.23` (see
  `ARG BUILD_FROM`). Python dependencies must therefore be installable on
  **Alpine / Python 3.12** – wheels for other platforms are not enough.
- `config.yaml` deliberately has **no** `image:` field: the Supervisor builds the add-on
  locally from the Dockerfile. The CI publishes the images via `IMAGE_PATTERN` in
  `.github/workflows/builder.yaml`.
- The legacy `home-assistant/builder` action is deprecated; the workflow uses the
  composable actions (`actions/build-image`, `actions/publish-multi-arch-manifest`).
  If you pin the legacy action instead, the image tag has to match the action ref
  (only published up to `2026.03.2`).
- The add-on runs under **S6 overlay v3** (`/etc/s6-overlay/s6-rc.d`), not under the
  legacy `/etc/services.d` layout.
- The backend virtual environment lives inside the workspace
  (`wled_matrix_manager/backend/venv`). On the host the interpreter symlink may be
  dangling – recreate it with `python3 -m venv venv`.
