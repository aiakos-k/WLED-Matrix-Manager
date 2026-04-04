"""
Home Assistant Supervisor API Client.
Discovers WLED devices via HA config entries / entity registry.
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

_instance: Optional["HAClient"] = None


def get_ha_client() -> "HAClient":
    """Return the singleton HAClient instance."""
    global _instance
    if _instance is None:
        _instance = HAClient()
    return _instance


class HAClient:
    """Client for Home Assistant Supervisor and WebSocket APIs"""

    def __init__(self):
        self.ws_url = "ws://supervisor/core/websocket"
        self.api_url = "http://supervisor/core/api"
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.connected = False
        self.auth_token: str = ""
        self._message_id = 0
        self._pending: Dict[int, asyncio.Future] = {}

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.auth_token}"}

    async def connect(self) -> bool:
        """Connect to Home Assistant WebSocket API"""
        try:
            self.auth_token = os.getenv("SUPERVISOR_TOKEN", "")
            if not self.auth_token:
                logger.warning("No SUPERVISOR_TOKEN found — running outside HA?")
                return False

            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(self.ws_url)
            self.connected = True
            asyncio.create_task(self._listen())
            logger.info("Connected to Home Assistant")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to HA: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        try:
            if self.ws:
                await self.ws.close()
            if self.session:
                await self.session.close()
            self.connected = False
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    async def _listen(self):
        """Listen for WS messages and dispatch to pending futures."""
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")

                    if msg_type == "auth_required":
                        await self._authenticate()
                    elif msg_type == "auth_ok":
                        logger.info("HA auth successful")
                    elif msg_type == "auth_invalid":
                        logger.error("HA auth failed")
                        self.connected = False
                    elif msg_type == "result":
                        msg_id = data.get("id")
                        if msg_id in self._pending:
                            self._pending[msg_id].set_result(data)
                            del self._pending[msg_id]
        except Exception as e:
            logger.error(f"WS listen error: {e}")
            self.connected = False

    async def _authenticate(self):
        if self.ws:
            await self.ws.send_json({"type": "auth", "access_token": self.auth_token})

    async def _send_ws(self, payload: dict) -> Optional[dict]:
        """Send a WS message and wait for result."""
        if not self.ws or not self.connected:
            return None
        self._message_id += 1
        msg_id = self._message_id
        payload["id"] = msg_id

        future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        await self.ws.send_json(payload)
        try:
            return await asyncio.wait_for(future, timeout=10)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            logger.error(f"WS request {msg_id} timed out")
            return None

    async def get_states(self) -> List[Dict]:
        """Get all entity states via REST API."""
        try:
            if not self.auth_token:
                return []
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/states",
                    headers=self._headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"Failed to get states: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Error getting states: {e}")
            return []

    async def discover_wled_devices(self) -> List[Dict]:
        """
        Discover WLED devices using HA config entries (reliable IP) +
        entity registry + states.  Falls back to state-based search.
        """
        # --- Try config-entry approach first (most reliable for IP) ---
        entries_resp = await self._send_ws({"type": "config_entries/get"})
        if entries_resp and entries_resp.get("success"):
            return await self._discover_from_config_entries(entries_resp)

        # --- Fallback: scan entity states ---
        return await self._discover_from_states()

    async def _discover_from_config_entries(self, entries_resp: dict) -> List[Dict]:
        """Use config entries + entity registry for accurate IP discovery."""
        wled_entries: Dict[str, Dict] = {}
        for entry in entries_resp.get("result", []):
            if entry.get("domain") == "wled":
                wled_entries[entry["entry_id"]] = {
                    "host": entry.get("data", {}).get("host", ""),
                    "title": entry.get("title", ""),
                }

        if not wled_entries:
            return []

        # Map config_entry_id → light entity
        entity_resp = await self._send_ws({"type": "config/entity_registry/list"})
        entry_entities: Dict[str, str] = {}  # entry_id → entity_id (light.*)
        if entity_resp and entity_resp.get("success"):
            for ent in entity_resp.get("result", []):
                ce_id = ent.get("config_entry_id")
                eid = ent.get("entity_id", "")
                if ce_id in wled_entries and eid.startswith("light."):
                    entry_entities.setdefault(ce_id, eid)

        # Fetch all states for friendly_name / on-off
        states = await self.get_states()
        state_map = {s["entity_id"]: s for s in states}

        devices: List[Dict] = []
        for entry_id, info in wled_entries.items():
            entity_id = entry_entities.get(entry_id, "")
            state = state_map.get(entity_id, {})
            attrs = state.get("attributes", {})
            devices.append(
                {
                    "entity_id": entity_id,
                    "name": attrs.get("friendly_name", info["title"]),
                    "ip_address": info["host"],
                    "state": state.get("state", "unknown"),
                    "attributes": attrs,
                }
            )

        logger.info(f"Found {len(devices)} WLED devices via config entries")
        return devices

    async def _discover_from_states(self) -> List[Dict]:
        """Fallback: discover WLED devices from entity states."""
        states = await self.get_states()
        devices: List[Dict] = []
        for entity in states:
            entity_id = entity.get("entity_id", "")
            attrs = entity.get("attributes", {})
            if entity_id.startswith("light.wled"):
                ip = attrs.get("ip_address") or attrs.get("host", "")
                devices.append(
                    {
                        "entity_id": entity_id,
                        "name": attrs.get("friendly_name", entity_id),
                        "ip_address": ip,
                        "state": entity.get("state", "unknown"),
                        "attributes": attrs,
                    }
                )
        logger.info(f"Found {len(devices)} WLED devices via states fallback")
        return devices

    async def handle_message(self, data: str) -> dict:
        """Handle incoming message from frontend WebSocket."""
        try:
            msg = json.loads(data)
            action = msg.get("action")

            if action == "discover_devices":
                devices = await self.discover_wled_devices()
                return {"type": "devices", "data": devices}
            elif action == "get_states":
                states = await self.get_states()
                return {"type": "states", "data": states}
            elif action == "call_service":
                return await self._call_service(msg)
            else:
                return {"type": "error", "message": f"Unknown action: {action}"}
        except json.JSONDecodeError:
            return {"type": "error", "message": "Invalid JSON"}
        except Exception as e:
            return {"type": "error", "message": str(e)}

    async def _call_service(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Call a Home Assistant service."""
        domain = data.get("domain")
        service = data.get("service")
        if not domain or not service:
            return {"error": "Missing domain or service"}
        resp = await self._send_ws(
            {
                "type": "call_service",
                "domain": domain,
                "service": service,
                "service_data": data.get("data", {}),
            }
        )
        if resp and resp.get("success"):
            return {"type": "result", "success": True}
        return {"type": "error", "message": "Service call failed"}
