#!/usr/bin/env python3
"""
FastAPI server for Home Assistant Add-on
Provides REST API and WebSocket connection to Home Assistant
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from app.ha_client import HAClient
from app.router import router
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Home Assistant client
ha_client = HAClient()


# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Home Assistant Add-on")
    await ha_client.connect()

    yield

    # Shutdown
    logger.info("Shutting down Home Assistant Add-on")
    await ha_client.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Home Assistant Add-on",
    description="Example add-on with FastAPI backend and React frontend",
    version="1.2.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "ha_connected": ha_client.connected}


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time Home Assistant updates"""
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            logger.debug(f"Received: {data}")

            # Forward to Home Assistant or process locally
            result = await ha_client.handle_message(data)

            # Send response back
            await websocket.send_json(result)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason=str(e))


# Serve static files (React frontend)
# Must be last - catches all unmatched routes and serves index.html as fallback
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dist), html=True),
        name="static",
    )

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENV") == "development",
        log_level="info",
    )
