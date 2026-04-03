"""Home Assistant WebSocket Client"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class HAClient:
    """Client for connecting to Home Assistant WebSocket API"""

    def __init__(self):
        self.url = "ws://supervisor/core/websocket"
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.connected = False
        self.auth_token = None
        self._message_id = 0

    async def connect(self) -> bool:
        """Connect to Home Assistant"""
        try:
            logger.info("Connecting to Home Assistant...")
            self.session = aiohttp.ClientSession()

            # Get authentication token from supervisor
            self.auth_token = await self._get_auth_token()

            # Connect to WebSocket
            self.ws = await self.session.ws_connect(self.url)
            self.connected = True
            logger.info("Connected to Home Assistant")

            # Start listening for messages
            asyncio.create_task(self._listen())

            return True
        except Exception as e:
            logger.error(f"Failed to connect to Home Assistant: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from Home Assistant"""
        try:
            if self.ws:
                await self.ws.close()
            if self.session:
                await self.session.close()
            self.connected = False
            logger.info("Disconnected from Home Assistant")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def _get_auth_token(self) -> str:
        """Get authentication token from Home Assistant supervisor"""
        try:
            # In a supervisor environment, the token is available via environment
            import os

            token = os.getenv("SUPERVISOR_TOKEN", "")
            if not token:
                logger.warning("No SUPERVISOR_TOKEN found")
            return token
        except Exception as e:
            logger.error(f"Failed to get auth token: {e}")
            return ""

    async def _listen(self):
        """Listen for messages from Home Assistant"""
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        logger.debug(f"Received from HA: {data}")
                        await self._handle_message(data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {msg.data}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")
            self.connected = False

    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming message from Home Assistant"""
        msg_type = data.get("type")

        if msg_type == "auth_required":
            await self._authenticate()
        elif msg_type == "auth_ok":
            logger.info("Authentication with Home Assistant successful")
        elif msg_type == "auth_invalid":
            logger.error("Authentication with Home Assistant failed")
            self.connected = False

    async def _authenticate(self):
        """Authenticate with Home Assistant"""
        auth_message = {"type": "auth", "access_token": self.auth_token}
        await self.ws.send_json(auth_message)

    async def handle_message(self, message: str) -> Dict[str, Any]:
        """Handle message from WebSocket client"""
        try:
            data = json.loads(message)
            action = data.get("action")

            if action == "get_entities":
                return await self._get_entities()
            elif action == "call_service":
                return await self._call_service(data)
            else:
                return {"error": "Unknown action"}
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return {"error": str(e)}

    async def _get_entities(self) -> Dict[str, Any]:
        """Get list of entities from Home Assistant"""
        # This would send a get_states request to Home Assistant
        return {"success": True, "entities": []}

    async def _call_service(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Home Assistant service"""
        domain = data.get("domain")
        service = data.get("service")

        if not domain or not service:
            return {"error": "Missing domain or service"}

        # Send service call to Home Assistant
        message = {
            "id": self._get_next_message_id(),
            "type": "call_service",
            "domain": domain,
            "service": service,
            "service_data": data.get("data", {}),
        }

        try:
            await self.ws.send_json(message)
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to call service: {e}")
            return {"error": str(e)}

    def _get_next_message_id(self) -> int:
        """Get next message ID"""
        self._message_id += 1
        return self._message_id
