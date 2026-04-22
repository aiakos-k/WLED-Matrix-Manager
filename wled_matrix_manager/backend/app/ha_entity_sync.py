"""
Home Assistant Entity Sync — manages scene switch entities in HA.

Uses REST entities + WS call_service listener (immediate, zero setup):
- POST /api/states/switch.wled_scene_* creates visible entities
- WebSocket subscribes to call_service events for toggle handling
- On toggle: starts/stops playback + updates entity state
"""

import asyncio
import json
import logging
import re
from typing import Optional

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
        self._listen_task: asyncio.Task | None = None
        self._ws = None
        self._ws_session: aiohttp.ClientSession | None = None
        self._scene_meta: dict[int, dict] = {}  # scene_id -> meta

    def _entity_id(self, scene_id: int, name: str) -> str:
        return f"switch.wled_mm_scene_{_sanitize_name(name)}"

    async def start(self):
        from .ha_client import get_ha_client

        client = get_ha_client()
        self._core_api_url = client._core_api_url
        self._token = client.core_token

        if not self._core_api_url or not self._token:
            logger.warning("HAEntitySync: No Core API — entities will not be synced")
            return

        self._running = True
        self._listen_task = asyncio.create_task(self._listen_for_service_calls())
        logger.info("HAEntitySync: REST entities + WS call_service listener active")

    async def stop(self):
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.debug(f"WS close: {e}")
        if self._ws_session:
            try:
                await self._ws_session.close()
            except Exception as e:
                logger.debug(f"WS session close: {e}")

    # ─── Public API (called from router.py / scene_playback.py) ──

    async def sync_all_scenes(self):
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from .database import async_session
        from .models import Scene

        await self._cleanup_legacy_entities()

        async with async_session() as db:
            result = await db.execute(
                select(Scene)
                .where(Scene.is_active)
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

    async def _cleanup_legacy_entities(self):
        """Remove old-format switch.wled_scene_* entities left over from previous naming."""
        if not self._core_api_url:
            return
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

            legacy = [
                s["entity_id"] for s in states if s["entity_id"].startswith("switch.wled_scene_")
            ]
            for eid in legacy:
                await self._delete_state(eid)
                logger.info(f"HAEntitySync: removed legacy entity {eid}")
        except Exception as e:
            logger.warning(f"HAEntitySync: legacy cleanup failed: {e}")

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
                        logger.error(f"Set state {entity_id}: {resp.status} {body[:200]}")
        except Exception as e:
            logger.error(f"Set state {entity_id}: {e}")

    async def _get_state(self, entity_id: str) -> dict | None:
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
                        await self._ws.send_json({"type": "auth", "access_token": self._token})
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
                        logger.warning("HAEntitySync: Failed to subscribe to call_service")
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
                        except Exception as e:
                            logger.debug(f"WS close: {e}")
                        self._ws = None
                    if self._ws_session:
                        try:
                            await self._ws_session.close()
                        except Exception as e:
                            logger.debug(f"WS session close: {e}")
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
            if not entity_id.startswith("switch.wled_mm_scene_"):
                continue

            scene_id = self._find_scene(entity_id)
            if scene_id is None:
                continue

            from .scene_playback import get_all_playback_status

            status = get_all_playback_status()
            is_playing = scene_id in status and status[scene_id].get("is_playing")

            logger.info(f"HAEntitySync: {service} scene {scene_id} (playing={is_playing})")

            if service == "turn_on":
                for sid in list(self._scene_meta):
                    if sid != scene_id:
                        sid_status = status.get(sid, {})
                        if sid_status.get("is_playing"):
                            await self._stop_scene(sid)
                if not is_playing:
                    await self._start_scene(scene_id)
            elif service == "turn_off" and is_playing:
                await self._stop_scene(scene_id)
            elif service == "toggle":
                if is_playing:
                    await self._stop_scene(scene_id)
                else:
                    await self._start_scene(scene_id)

    def _find_scene(self, entity_id: str) -> int | None:
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
                    "ha_entity_id": getattr(d, "ha_entity_id", None),
                    "communication_protocol": d.communication_protocol,
                    "matrix_width": d.matrix_width,
                    "matrix_height": d.matrix_height,
                    "chain_count": d.chain_count,
                    "segment_id": d.segment_id,
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
