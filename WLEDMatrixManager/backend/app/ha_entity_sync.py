"""
Home Assistant Entity Sync — manages scene switch entities in HA.

Two mechanisms work together:

1. REST entities + WS call_service listener (immediate, zero setup):
   - POST /api/states/switch.wled_scene_* creates visible entities
   - WebSocket subscribes to call_service events for toggle handling
   - On toggle: starts/stops playback + updates entity state

2. Custom integration auto-setup (device grouping, automatic):
   - Addon copies custom_components/ to HA config dir on start
   - After HA restart: integration domain is loaded by HA Core
   - Addon periodically tries to auto-create config entry via config flow
   - Integration provides proper Device grouping + native switch control
   - REST entities are cleaned up once integration takes over
   - If integration not loaded yet, a notification asks the user to restart HA
"""

import asyncio
import json
import logging
import re
from typing import Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

_instance: Optional["HAEntitySync"] = None


def get_entity_sync() -> "HAEntitySync":
    global _instance
    if _instance is None:
        _instance = HAEntitySync()
    return _instance


def _sanitize_name(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "unnamed"


class HAEntitySync:
    """Creates REST switch entities and listens for HA service calls."""

    def __init__(self):
        self._core_api_url: str = ""
        self._token: str = ""
        self._running = False
        self._listen_task: Optional[asyncio.Task] = None
        self._auto_setup_task: Optional[asyncio.Task] = None
        self._ws = None
        self._ws_session: Optional[aiohttp.ClientSession] = None
        self._scene_meta: Dict[int, dict] = {}  # scene_id -> meta
        self._integration_active = False

    def _entity_id(self, scene_id: int, name: str) -> str:
        return f"switch.wled_scene_{scene_id}_{_sanitize_name(name)}"

    async def start(self):
        from .ha_client import get_ha_client

        client = get_ha_client()
        self._core_api_url = client._core_api_url
        self._token = client.core_token

        if not self._core_api_url or not self._token:
            logger.warning("HAEntitySync: No Core API — entities will not be synced")
            return

        # Check if the custom integration is already handling entities
        self._integration_active = await self._check_integration_active()

        if self._integration_active:
            logger.info(
                "HAEntitySync: Custom integration active — cleaning up REST entities"
            )
            await self._cleanup_rest_entities()
            return

        # No integration yet: use REST entities + WS listener
        self._running = True
        self._listen_task = asyncio.create_task(self._listen_for_service_calls())
        logger.info("HAEntitySync: REST entities + WS call_service listener active")

        # Try auto-configuring the custom integration (delayed — server not up yet)
        self._auto_setup_task = asyncio.create_task(self._delayed_auto_setup())

    async def stop(self):
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
        if self._auto_setup_task:
            self._auto_setup_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._ws_session:
            try:
                await self._ws_session.close()
            except Exception:
                pass

    # ─── Public API (called from router.py / scene_playback.py) ──

    async def sync_all_scenes(self):
        if self._integration_active:
            return

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from .database import async_session
        from .models import Scene

        async with async_session() as db:
            result = await db.execute(
                select(Scene)
                .where(Scene.is_active == True)
                .options(selectinload(Scene.frames), selectinload(Scene.devices))
            )
            scenes = result.scalars().all()

        for scene in scenes:
            await self.register_scene(
                scene_id=scene.id,
                name=scene.name,
                frame_count=len(scene.frames),
                matrix_width=scene.matrix_width,
                matrix_height=scene.matrix_height,
                loop_mode=scene.loop_mode,
                device_count=len(scene.devices),
                is_playing=False,
            )
        logger.info(f"HAEntitySync: registered {len(scenes)} REST entities")

    async def register_scene(
        self,
        scene_id: int = 0,
        name: str = "",
        frame_count: int = 0,
        matrix_width: int = 16,
        matrix_height: int = 16,
        loop_mode: str = "once",
        device_count: int = 0,
        is_playing: bool = False,
        **kwargs,
    ):
        if self._integration_active:
            return

        eid = self._entity_id(scene_id, name)
        self._scene_meta[scene_id] = {
            "name": name,
            "entity_id": eid,
            "frame_count": frame_count,
            "matrix_width": matrix_width,
            "matrix_height": matrix_height,
            "loop_mode": loop_mode,
            "device_count": device_count,
        }

        state = "on" if is_playing else "off"
        attributes = {
            "friendly_name": f"WLED-MM Scene: {name}",
            "icon": "mdi:led-strip-variant",
            "scene_id": scene_id,
            "frame_count": frame_count,
            "matrix_size": f"{matrix_width}x{matrix_height}",
            "loop_mode": loop_mode,
            "device_count": device_count,
            "attribution": "WLED Matrix Manager",
        }
        await self._set_state(eid, state, attributes)

    async def update_scene_playing(self, scene_id: int, is_playing: bool):
        if self._integration_active:
            return

        meta = self._scene_meta.get(scene_id)
        if not meta:
            return

        eid = meta["entity_id"]
        state = "on" if is_playing else "off"
        # Preserve existing attributes
        current = await self._get_state(eid)
        attrs = current.get("attributes", {}) if current else {}
        if not attrs:
            attrs = {
                "friendly_name": f"WLED-MM Scene: {meta['name']}",
                "icon": "mdi:led-strip-variant",
                "scene_id": scene_id,
            }
        await self._set_state(eid, state, attrs)

    async def remove_scene(self, scene_id: int):
        if self._integration_active:
            return
        meta = self._scene_meta.pop(scene_id, None)
        if meta:
            await self._delete_state(meta["entity_id"])

    # ─── REST API helpers ──────────────────────────────────────

    async def _set_state(self, entity_id: str, state: str, attributes: dict):
        if not self._core_api_url:
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self._core_api_url}/states/{entity_id}",
                    json={"state": state, "attributes": attributes},
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status in (200, 201):
                        logger.debug(f"Entity {entity_id} -> {state}")
                    else:
                        body = await resp.text()
                        logger.error(
                            f"Set state {entity_id}: {resp.status} {body[:200]}"
                        )
        except Exception as e:
            logger.error(f"Set state {entity_id}: {e}")

    async def _get_state(self, entity_id: str) -> Optional[dict]:
        if not self._core_api_url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._core_api_url}/states/{entity_id}",
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.debug(f"Get state {entity_id}: {e}")
        return None

    async def _delete_state(self, entity_id: str):
        if not self._core_api_url:
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{self._core_api_url}/states/{entity_id}",
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    logger.debug(f"Delete entity {entity_id}: {resp.status}")
        except Exception as e:
            logger.error(f"Delete state {entity_id}: {e}")

    # ─── WS call_service listener ─────────────────────────────

    async def _listen_for_service_calls(self):
        """Subscribe to call_service events to handle HA-side switch toggles.

        When a user toggles a REST-created switch in the HA UI, HA fires a
        call_service event (switch.turn_on / turn_off / toggle). The switch
        platform handler won't find the entity (it's REST-only), but the
        EVENT is still fired. We catch it here and start/stop playback.
        """
        ws_urls = [
            "ws://supervisor/core/websocket",
            "ws://homeassistant:8123/api/websocket",
        ]

        while self._running:
            for ws_url in ws_urls:
                if not self._running:
                    return
                try:
                    self._ws_session = aiohttp.ClientSession()
                    self._ws = await self._ws_session.ws_connect(
                        ws_url, timeout=aiohttp.ClientTimeout(total=10)
                    )

                    # Auth handshake
                    auth_msg = await self._ws.receive_json()
                    if auth_msg.get("type") == "auth_required":
                        await self._ws.send_json(
                            {"type": "auth", "access_token": self._token}
                        )
                        auth_result = await self._ws.receive_json()
                        if auth_result.get("type") != "auth_ok":
                            logger.warning(f"HAEntitySync WS auth failed at {ws_url}")
                            continue

                    logger.info(f"HAEntitySync: WS connected at {ws_url}")

                    # Subscribe to call_service events
                    await self._ws.send_json(
                        {
                            "id": 1,
                            "type": "subscribe_events",
                            "event_type": "call_service",
                        }
                    )
                    sub_resp = await self._ws.receive_json()
                    if not sub_resp.get("success", False):
                        logger.warning(
                            "HAEntitySync: Failed to subscribe to call_service"
                        )
                        continue

                    logger.info("HAEntitySync: Listening for switch service calls")

                    async for msg in self._ws:
                        if not self._running:
                            return
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "event":
                                await self._handle_service_call(data.get("event", {}))
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break

                    break  # Connected OK, exit URL loop

                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.debug(f"HAEntitySync WS {ws_url}: {e}")
                finally:
                    if self._ws:
                        try:
                            await self._ws.close()
                        except Exception:
                            pass
                        self._ws = None
                    if self._ws_session:
                        try:
                            await self._ws_session.close()
                        except Exception:
                            pass
                        self._ws_session = None

            # Reconnect after delay
            if self._running:
                logger.info("HAEntitySync: WS reconnecting in 10s...")
                await asyncio.sleep(10)

    async def _handle_service_call(self, event: dict):
        """Handle call_service event for switch / homeassistant domain."""
        data = event.get("data", {})
        domain = data.get("domain", "")
        service = data.get("service", "")

        # Handle both switch.turn_on and homeassistant.turn_on
        if domain not in ("switch", "homeassistant"):
            return
        if service not in ("turn_on", "turn_off", "toggle"):
            return

        service_data = data.get("service_data", {})
        entity_ids = service_data.get("entity_id", [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        for entity_id in entity_ids:
            if not entity_id.startswith("switch.wled_scene_"):
                continue

            scene_id = self._find_scene(entity_id)
            if scene_id is None:
                continue

            from .scene_playback import get_all_playback_status

            status = get_all_playback_status()
            is_playing = scene_id in status and status[scene_id].get("is_playing")

            logger.info(
                f"HAEntitySync: {service} scene {scene_id} (playing={is_playing})"
            )

            if service == "turn_on" and not is_playing:
                await self._start_scene(scene_id)
            elif service == "turn_off" and is_playing:
                await self._stop_scene(scene_id)
            elif service == "toggle":
                if is_playing:
                    await self._stop_scene(scene_id)
                else:
                    await self._start_scene(scene_id)

    def _find_scene(self, entity_id: str) -> Optional[int]:
        for sid, meta in self._scene_meta.items():
            if meta["entity_id"] == entity_id:
                return sid
        return None

    # ─── Scene playback control (triggered by HA toggle) ──────

    async def _start_scene(self, scene_id: int):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from .database import async_session
        from .models import Scene
        from .scene_playback import start_scene_playback

        async with async_session() as db:
            result = await db.execute(
                select(Scene)
                .where(Scene.id == scene_id)
                .options(selectinload(Scene.frames), selectinload(Scene.devices))
            )
            scene = result.scalar_one_or_none()
            if not scene or not scene.devices:
                logger.warning(f"Scene {scene_id} not found or no devices")
                return

            devices_info = [
                {
                    "ip_address": d.ip_address,
                    "communication_protocol": d.communication_protocol,
                    "matrix_width": d.matrix_width,
                    "matrix_height": d.matrix_height,
                    "chain_count": d.chain_count,
                    "segment_id": d.segment_id,
                    "base_brightness": getattr(d, "base_brightness", 255) or 255,
                    "scale_mode": getattr(d, "scale_mode", "stretch") or "stretch",
                }
                for d in scene.devices
            ]

            frames_data = [
                {
                    "frame_index": f.frame_index,
                    "pixel_data": f.pixel_data or {},
                    "duration": f.duration or scene.default_frame_duration,
                    "brightness": f.brightness or 255,
                    "color_r": f.color_r or 100,
                    "color_g": f.color_g or 100,
                    "color_b": f.color_b or 100,
                }
                for f in sorted(scene.frames, key=lambda x: x.frame_index)
            ]

            start_scene_playback(scene.id, devices_info, frames_data, scene.loop_mode)
            await self.update_scene_playing(scene_id, True)
            logger.info(f"HAEntitySync: Started scene {scene_id} via HA")

    async def _stop_scene(self, scene_id: int):
        from .scene_playback import stop_scene_playback

        stop_scene_playback(scene_id)
        await self.update_scene_playing(scene_id, False)
        logger.info(f"HAEntitySync: Stopped scene {scene_id} via HA")

    # ─── Custom integration auto-setup ────────────────────────

    async def _check_integration_active(self) -> bool:
        """Check if the custom integration created entities (states API)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._core_api_url}/states",
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        states = await resp.json()
                        return any(
                            s.get("entity_id", "").startswith(
                                "switch.wled_matrix_manager_"
                            )
                            for s in states
                        )
        except Exception as e:
            logger.debug(f"Integration check: {e}")
        return False

    async def _delayed_auto_setup(self):
        """Wait for FastAPI, then periodically try to auto-configure the integration."""
        try:
            await asyncio.sleep(15)  # Wait for uvicorn to accept connections
            notified = False

            for _ in range(360):  # Try for up to ~3 hours
                if not self._running or self._integration_active:
                    return

                # Check if integration entities appeared (user may have set it up)
                if await self._check_integration_active():
                    logger.info(
                        "HAEntitySync: Custom integration detected — "
                        "switching to native mode"
                    )
                    self._integration_active = True
                    await self._cleanup_rest_entities()
                    return

                # Try auto-setup (config flow)
                if await self._try_auto_setup():
                    return

                # If integration domain not loaded, notify user once
                if not notified:
                    notified = True
                    await self._notify_restart_needed()

                await asyncio.sleep(30)

        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.debug(f"Integration auto-setup: {e}")

    def _get_addon_ip(self) -> str:
        """Get this addon's IP on the hassio Docker network."""
        import socket

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("172.30.32.1", 80))  # hassio network gateway
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return ""

    async def _notify_restart_needed(self):
        """Create a persistent notification asking the user to restart HA."""
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{self._core_api_url}/services/persistent_notification/create",
                    json={
                        "title": "WLED Matrix Manager",
                        "message": (
                            "Bitte starte Home Assistant einmalig neu, um die "
                            "WLED Matrix Manager Integration zu aktivieren. "
                            "Danach werden die Scene-Entities automatisch unter "
                            "einem Gerät gruppiert.\n\n"
                            "**Einstellungen → System → Neustart**"
                        ),
                        "notification_id": "wled_mm_restart",
                    },
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception:
            pass

    async def _dismiss_notification(self):
        """Remove the restart notification."""
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{self._core_api_url}/services/persistent_notification/dismiss",
                    json={"notification_id": "wled_mm_restart"},
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=5),
                )
        except Exception:
            pass

    async def _try_auto_setup(self) -> bool:
        """Try to create a config entry for the integration.

        Returns True if the integration is now active (created or already exists).
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Start config flow
                async with session.post(
                    f"{self._core_api_url}/config/config_entries/flow",
                    json={
                        "handler": "wled_matrix_manager",
                        "show_advanced_options": False,
                    },
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.debug(
                            f"Config flow start: {resp.status} — "
                            "integration domain not loaded yet"
                        )
                        return False
                    flow = await resp.json()

                flow_id = flow.get("flow_id")
                flow_type = flow.get("type")

                if flow_type == "abort":
                    reason = flow.get("reason", "")
                    logger.info(
                        f"HAEntitySync: Integration already configured ({reason})"
                    )
                    self._integration_active = True
                    await self._cleanup_rest_entities()
                    await self._dismiss_notification()
                    return True

                if not flow_id:
                    return False

                # Try hostname first (works in production), fall back to IP
                hosts_to_try = ["addon_local_wled_matrix_manager"]
                addon_ip = self._get_addon_ip()
                if addon_ip:
                    hosts_to_try.append(addon_ip)

                for host in hosts_to_try:
                    async with session.post(
                        f"{self._core_api_url}/config/config_entries/flow/{flow_id}",
                        json={"host": host, "port": 8000},
                        headers={
                            "Authorization": f"Bearer {self._token}",
                            "Content-Type": "application/json",
                        },
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            if result.get("type") in ("create_entry", "abort"):
                                logger.info(
                                    "HAEntitySync: Custom integration "
                                    f"auto-configured (host={host})! "
                                    "Device grouping active."
                                )
                                self._integration_active = True
                                await self._cleanup_rest_entities()
                                await self._dismiss_notification()
                                return True
                            # If cannot_connect with this host, the flow
                            # stays open — try next host
                            errors = result.get("errors", {})
                            if errors.get("base") == "cannot_connect":
                                logger.debug(
                                    f"Config flow: cannot_connect with host={host}"
                                )
                                continue
                            logger.debug(f"Auto-setup flow result: {result}")
                        else:
                            body = await resp.text()
                            logger.debug(f"Auto-setup flow: {resp.status} {body[:200]}")
                            break
        except Exception as e:
            logger.debug(f"Auto-setup attempt: {e}")
        return False

    async def _cleanup_rest_entities(self):
        """Remove REST-created switch.wled_scene_* entities."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._core_api_url}/states",
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return
                    states = await resp.json()

            removed = 0
            for state in states:
                eid = state.get("entity_id", "")
                if eid.startswith("switch.wled_scene_"):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.delete(
                                f"{self._core_api_url}/states/{eid}",
                                headers={"Authorization": f"Bearer {self._token}"},
                                timeout=aiohttp.ClientTimeout(total=5),
                            ) as resp:
                                if resp.status in (200, 204):
                                    removed += 1
                    except Exception:
                        pass

            if removed:
                logger.info(f"HAEntitySync: cleaned up {removed} REST entities")
        except Exception as e:
            logger.debug(f"Cleanup failed: {e}")
