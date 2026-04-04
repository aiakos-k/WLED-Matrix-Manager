"""
Home Assistant Supervisor API Client.
Discovers WLED devices via Supervisor proxy, direct Core API, or entity states.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

_instance: Optional["HAClient"] = None


def get_ha_client() -> "HAClient":
    global _instance
    if _instance is None:
        _instance = HAClient()
    return _instance


def _read_token() -> str:
    """Read Supervisor token from env or s6 files."""
    for var in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN"):
        val = os.getenv(var, "").strip()
        if val:
            logger.info(f"Token from ${var} (len={len(val)})")
            return val

    for var in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN"):
        p = Path(f"/run/s6/container_environment/{var}")
        if p.exists():
            val = p.read_text().strip()
            if val:
                logger.info(f"Token from {p} (len={len(val)})")
                return val

    logger.warning("No supervisor token found")
    return ""


class HAClient:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.connected = False
        self.authenticated = False
        self.auth_token: str = ""
        self.core_token: str = ""  # might differ from auth_token
        self._message_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._auth_event = asyncio.Event()
        self._core_api_url: str = ""  # discovered at runtime

    async def connect(self) -> bool:
        """Connect and discover the working Core API access method."""
        self.auth_token = _read_token()
        if not self.auth_token:
            return False

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Step 1: Get our addon info from Supervisor
        addon_info = await self._supervisor_get("/addons/self/info")
        if addon_info:
            data = addon_info.get("data", {})
            logger.info(
                f"Addon info: homeassistant_api={data.get('homeassistant_api')}, "
                f"hassio_api={data.get('hassio_api')}, "
                f"ingress={data.get('ingress')}, "
                f"slug={data.get('slug')}"
            )
        else:
            logger.warning("Could not get addon self info")

        # Step 2: Try to find a working Core API URL
        core_urls = [
            "http://supervisor/core/api",
            "http://supervisor/homeassistant/api",
        ]

        for url in core_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{url}/config",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        logger.info(f"Core API probe {url}/config: {resp.status}")
                        if resp.status == 200:
                            self._core_api_url = url
                            self.core_token = self.auth_token
                            break
            except Exception as e:
                logger.error(f"Core API probe {url}: {e}")

        # Step 3: If no proxy works, try getting an ingress session/token
        if not self._core_api_url:
            logger.warning(
                "Core API proxy not accessible - trying to create ingress token"
            )
            # Try getting a short-lived token from Supervisor
            token_resp = await self._supervisor_post("/auth/token", data=None)
            if token_resp:
                logger.info(f"Auth token response: {list(token_resp.keys())}")

        # Step 4: Try direct Core connection
        if not self._core_api_url:
            for host in ("homeassistant", "core", "localhost"):
                url = f"http://{host}:8123/api"
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"{url}/config",
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=3),
                        ) as resp:
                            logger.info(
                                f"Direct Core probe {url}/config: {resp.status}"
                            )
                            if resp.status == 200:
                                self._core_api_url = url
                                self.core_token = self.auth_token
                                break
                except Exception as e:
                    logger.debug(f"Direct Core {host}: {e}")

        if self._core_api_url:
            logger.info(f"Core API accessible at: {self._core_api_url}")
        else:
            logger.error("Core API NOT accessible via any method!")

        # Step 5: Try WS connection
        ws_urls = [
            "ws://supervisor/core/websocket",
            "ws://homeassistant:8123/api/websocket",
        ]
        for ws_url in ws_urls:
            try:
                self.session = aiohttp.ClientSession()
                self.ws = await self.session.ws_connect(
                    ws_url, timeout=aiohttp.ClientTimeout(total=5)
                )
                self.connected = True
                self._auth_event.clear()
                asyncio.create_task(self._listen())

                try:
                    await asyncio.wait_for(self._auth_event.wait(), timeout=10)
                except asyncio.TimeoutError:
                    pass

                if self.authenticated:
                    logger.info(f"WS authenticated via {ws_url}")
                    break
                else:
                    logger.warning(f"WS auth failed at {ws_url}")
                    await self.session.close()
                    self.connected = False
            except Exception as e:
                logger.debug(f"WS {ws_url}: {e}")
                if self.session:
                    await self.session.close()
                self.connected = False

        logger.info(
            f"Connection result: core_api={'OK' if self._core_api_url else 'FAIL'}, "
            f"ws={'OK' if self.authenticated else 'FAIL'}"
        )
        return bool(self._core_api_url) or self.authenticated

    async def disconnect(self):
        try:
            if self.ws:
                await self.ws.close()
            if self.session:
                await self.session.close()
            self.connected = False
            self.authenticated = False
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    # --- Supervisor API (always works) ---

    async def _supervisor_get(self, path: str) -> Optional[Dict]:
        """GET from Supervisor API (uses hassio_api role)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://supervisor{path}",
                    headers={"Authorization": f"Bearer {self.auth_token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"Supervisor GET {path}: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Supervisor GET {path}: {e}")
            return None

    async def _supervisor_post(self, path: str, data: Optional[Dict]) -> Optional[Dict]:
        """POST to Supervisor API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://supervisor{path}",
                    headers={
                        "Authorization": f"Bearer {self.auth_token}",
                        "Content-Type": "application/json",
                    },
                    json=data or {},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    body = await resp.text()
                    logger.error(f"Supervisor POST {path}: {resp.status} {body[:200]}")
                    return None
        except Exception as e:
            logger.error(f"Supervisor POST {path}: {e}")
            return None

    # --- Core API (discovered at runtime) ---

    async def _core_get(self, path: str) -> Optional[Any]:
        """GET from HA Core API (using whichever method works)."""
        if not self._core_api_url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._core_api_url}{path}",
                    headers={"Authorization": f"Bearer {self.core_token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"Core GET {path}: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Core GET {path}: {e}")
            return None

    # --- WebSocket ---

    async def _listen(self):
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")
                    if msg_type == "auth_required":
                        logger.info(
                            f"WS auth_required (HA {data.get('ha_version', '?')})"
                        )
                        await self._authenticate()
                    elif msg_type == "auth_ok":
                        self.authenticated = True
                        self._auth_event.set()
                    elif msg_type == "auth_invalid":
                        logger.error(f"WS auth_invalid: {data.get('message', '?')}")
                        self.authenticated = False
                        self._auth_event.set()
                    elif msg_type == "result":
                        mid = data.get("id")
                        if mid in self._pending:
                            self._pending[mid].set_result(data)
                            del self._pending[mid]
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except Exception as e:
            logger.error(f"WS listen: {e}")
        self.connected = False
        self.authenticated = False

    async def _authenticate(self):
        if self.ws:
            # Try SUPERVISOR_TOKEN first
            await self.ws.send_json(
                {
                    "type": "auth",
                    "access_token": self.auth_token,
                }
            )

    async def _send_ws(self, payload: dict) -> Optional[dict]:
        if not self.ws or not self.authenticated:
            return None
        self._message_id += 1
        mid = self._message_id
        payload["id"] = mid
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[mid] = future
        await self.ws.send_json(payload)
        try:
            return await asyncio.wait_for(future, timeout=10)
        except asyncio.TimeoutError:
            self._pending.pop(mid, None)
            return None

    # --- State/Entity access ---

    async def get_states(self) -> List[Dict]:
        result = await self._core_get("/states")
        return result if isinstance(result, list) else []

    async def get_config_entries(self) -> List[Dict]:
        # Try REST first, then WS
        result = await self._core_get("/config/config_entries/entry")
        if isinstance(result, list) and result:
            return result

        if self.authenticated:
            resp = await self._send_ws({"type": "config_entries/get"})
            if resp and resp.get("success"):
                return resp.get("result", [])

        return []

    async def get_device_registry(self) -> List[Dict]:
        """Get HA device registry (has configuration_url with IP for network devices)."""
        if self.authenticated:
            resp = await self._send_ws({"type": "config/device_registry/list"})
            if resp and resp.get("success"):
                return resp.get("result", [])
        return []

    # --- WLED Discovery ---

    async def discover_wled_devices(self) -> List[Dict]:
        logger.info(
            f"Discovery (core_api={'OK' if self._core_api_url else 'NONE'}, "
            f"ws={self.authenticated})"
        )

        # Strategy 1: Config entries + device registry (best — has IP)
        entries = await self.get_config_entries()
        if entries:
            wled = [e for e in entries if e.get("domain") == "wled"]
            if wled:
                logger.info(f"Found {len(wled)} WLED config entries")
                return await self._from_entries(wled)

        # Strategy 2: Broad state scan
        return await self._from_states()

    async def _extract_ip(self, url: str) -> str:
        """Extract IP/host from a URL like http://192.168.0.100."""
        if not url:
            return ""
        # Strip protocol and trailing slashes/paths
        host = url.split("://")[-1].split("/")[0].split(":")[0]
        return host

    async def _from_entries(self, wled_entries: List[Dict]) -> List[Dict]:
        entries_map: Dict[str, Dict] = {}
        for e in wled_entries:
            eid = e.get("entry_id", "")
            host = e.get("data", {}).get("host", "")
            entries_map[eid] = {
                "host": host,
                "title": e.get("title", ""),
            }
            logger.info(
                f"  Config entry: {e.get('title')} entry_id={eid} host={host or '?'}"
            )

        # Get device registry to find configuration_url (contains IP)
        dev_registry = await self.get_device_registry()
        # Map config_entry_id -> configuration_url
        entry_ip_map: Dict[str, str] = {}
        for dev in dev_registry:
            config_entries = dev.get("config_entries", [])
            config_url = dev.get("configuration_url", "") or ""
            for ce_id in config_entries:
                if ce_id in entries_map and config_url:
                    ip = await self._extract_ip(config_url)
                    if ip:
                        entry_ip_map[ce_id] = ip
                        logger.info(
                            f"  Device registry: {dev.get('name')} -> {config_url} (ip={ip})"
                        )

        # Resolve entity IDs from entity registry
        entity_map: Dict[str, str] = {}
        if self.authenticated:
            resp = await self._send_ws({"type": "config/entity_registry/list"})
            if resp and resp.get("success"):
                for ent in resp.get("result", []):
                    ce = ent.get("config_entry_id", "")
                    eid = ent.get("entity_id", "")
                    if ce in entries_map and eid.startswith("light."):
                        entity_map.setdefault(ce, eid)

        states = await self.get_states()
        state_map = {s["entity_id"]: s for s in states}

        devices: List[Dict] = []
        for entry_id, info in entries_map.items():
            eid = entity_map.get(entry_id, "")
            state = state_map.get(eid, {})
            attrs = state.get("attributes", {})
            # IP priority: config entry data > device registry > entity attributes
            ip = (
                info["host"]
                or entry_ip_map.get(entry_id, "")
                or attrs.get("ip_address", "")
                or ""
            )
            devices.append(
                {
                    "entity_id": eid,
                    "name": attrs.get("friendly_name", info["title"]),
                    "ip_address": ip,
                    "state": state.get("state", "unknown"),
                    "attributes": attrs,
                }
            )
            logger.info(
                f"  Result: {eid} name={attrs.get('friendly_name', info['title'])} ip={ip}"
            )
        logger.info(f"Config entries -> {len(devices)} devices")
        return devices

    async def _from_states(self) -> List[Dict]:
        states = await self.get_states()
        logger.info(f"State scan: {len(states)} entities")

        devices: List[Dict] = []
        seen: set = set()

        for entity in states:
            eid = entity.get("entity_id", "")
            attrs = entity.get("attributes", {})

            if not eid.startswith("light."):
                continue

            is_wled = False
            if "wled" in eid:
                is_wled = True
            elif "wled" in attrs.get("friendly_name", "").lower():
                is_wled = True
            elif isinstance(attrs.get("effect_list"), list):
                effects = set(attrs["effect_list"])
                if (
                    len({"Solid", "Blink", "Breathe", "Rainbow", "Fire 2012"} & effects)
                    >= 3
                ):
                    is_wled = True

            if is_wled and eid not in seen:
                seen.add(eid)
                ip = attrs.get("ip_address") or attrs.get("host", "")
                devices.append(
                    {
                        "entity_id": eid,
                        "name": attrs.get("friendly_name", eid),
                        "ip_address": ip,
                        "state": entity.get("state", "unknown"),
                        "attributes": attrs,
                    }
                )
                logger.info(f"  Found: {eid} ip={ip}")

        logger.info(f"State scan: {len(devices)} WLED devices")
        return devices

    # --- Diagnostics ---

    async def get_diagnostics(self) -> Dict[str, Any]:
        diag: Dict[str, Any] = {
            "token_len": len(self.auth_token),
            "core_api_url": self._core_api_url or "NOT_FOUND",
            "ws_authenticated": self.authenticated,
        }

        # Addon self info (permissions)
        addon_info = await self._supervisor_get("/addons/self/info")
        if addon_info:
            d = addon_info.get("data", {})
            diag["addon_permissions"] = {
                "homeassistant_api": d.get("homeassistant_api"),
                "hassio_api": d.get("hassio_api"),
                "ingress": d.get("ingress"),
                "slug": d.get("slug"),
                "state": d.get("state"),
                "version": d.get("version"),
            }
        else:
            diag["addon_permissions"] = "FAILED_TO_GET"

        # Supervisor connectivity
        ping = await self._supervisor_get("/supervisor/ping")
        diag["supervisor_ping"] = "ok" if ping else "failed"

        # Core info
        core_info = await self._supervisor_get("/core/info")
        if core_info:
            d = core_info.get("data", {})
            diag["core_info"] = {
                "version": d.get("version"),
                "state": d.get("state"),
            }

        # Probe all possible Core API URLs
        probe_urls = [
            "http://supervisor/core/api",
            "http://supervisor/homeassistant/api",
            "http://homeassistant:8123/api",
            "http://core:8123/api",
        ]
        diag["core_api_probes"] = {}
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        for url in probe_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{url}/config",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as resp:
                        diag["core_api_probes"][url] = resp.status
            except Exception as e:
                diag["core_api_probes"][url] = str(e)

        # States count
        states = await self.get_states()
        diag["total_entities"] = len(states)
        lights = [s for s in states if s.get("entity_id", "").startswith("light.")]
        diag["light_count"] = len(lights)
        diag["light_ids"] = [s["entity_id"] for s in lights]

        # Config entries
        entries = await self.get_config_entries()
        if entries:
            wled = [e for e in entries if e.get("domain") == "wled"]
            diag["wled_entries"] = [
                {"title": e.get("title"), "host": e.get("data", {}).get("host", "?")}
                for e in wled
            ]
        else:
            diag["wled_entries"] = []

        # Environment
        diag["env"] = {
            "SUPERVISOR_TOKEN": bool(os.getenv("SUPERVISOR_TOKEN")),
            "HASSIO_TOKEN": bool(os.getenv("HASSIO_TOKEN")),
            "s6_SUPERVISOR_TOKEN": Path(
                "/run/s6/container_environment/SUPERVISOR_TOKEN"
            ).exists(),
        }

        return diag

    # --- Message handler ---

    async def handle_message(self, data: str) -> dict:
        try:
            msg = json.loads(data)
            action = msg.get("action")
            if action == "discover_devices":
                return {"type": "devices", "data": await self.discover_wled_devices()}
            elif action == "get_states":
                return {"type": "states", "data": await self.get_states()}
            elif action == "call_service":
                return await self._call_service(msg)
            else:
                return {"type": "error", "message": f"Unknown: {action}"}
        except Exception as e:
            return {"type": "error", "message": str(e)}

    async def _call_service(self, data: Dict[str, Any]) -> Dict[str, Any]:
        domain = data.get("domain")
        service = data.get("service")
        if not domain or not service:
            return {"error": "Missing domain/service"}
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
