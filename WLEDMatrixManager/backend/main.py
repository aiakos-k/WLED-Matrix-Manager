#!/usr/bin/env python3
"""
WLED Matrix Manager — FastAPI backend for Home Assistant Add-on.
Scene creation, WLED device control, WebSocket live preview.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from app.database import init_db
from app.ha_client import get_ha_client
from app.ha_entity_sync import get_entity_sync
from app.router import router
from app.scene_playback import get_all_playback_status
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ha_client = get_ha_client()
entity_sync = get_entity_sync()

# WebSocket clients for live preview broadcast
ws_clients: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting WLED Matrix Manager")
    await init_db()
    await ha_client.connect()

    # Register all scenes as HA entities
    await entity_sync.start()
    try:
        await entity_sync.sync_all_scenes()
    except Exception as e:
        logger.warning(f"Entity sync on startup: {e}")

    yield
    logger.info("Shutting down WLED Matrix Manager")
    await entity_sync.stop()
    await ha_client.disconnect()


app = FastAPI(
    title="WLED Matrix Manager",
    description="Create and play pixel-art scenes on WLED LED matrices",
    version="0.9.0",
    lifespan=lifespan,
)


class PathNormalizationMiddleware:
    """Collapse double slashes injected by the HA ingress proxy.

    Works for both HTTP and WebSocket scope types.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope["path"]
            while "//" in path:
                path = path.replace("//", "/")
            scope["path"] = path
        await self.app(scope, receive, send)


app.add_middleware(PathNormalizationMiddleware)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "ha_connected": ha_client.connected}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for live preview and HA integration."""
    await websocket.accept()
    ws_clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(ws_clients)} total)")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            action = msg.get("action")

            if action == "preview_frame":
                # Broadcast frame preview to all connected clients
                for client in ws_clients.copy():
                    if client != websocket:
                        try:
                            await client.send_json(
                                {"type": "preview_frame", "data": msg.get("data")}
                            )
                        except Exception:
                            ws_clients.discard(client)
                await websocket.send_json({"type": "ack", "action": "preview_frame"})

            elif action == "playback_status":
                status = get_all_playback_status()
                await websocket.send_json({"type": "playback_status", "data": status})

            else:
                result = await ha_client.handle_message(data)
                await websocket.send_json(result)

    except WebSocketDisconnect:
        ws_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(ws_clients)} total)")
    except Exception as e:
        ws_clients.discard(websocket)
        logger.error(f"WebSocket error: {e}")


# Serve frontend static files (must be last — catches all unmatched routes)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port, log_level="info")
