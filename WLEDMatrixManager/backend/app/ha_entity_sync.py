"""
Home Assistant Entity Sync — exposes each scene as a switch entity in HA.

Primary: MQTT Discovery (proper device grouping + native on/off control)
Fallback: REST API states + WS call_service listener

MQTT creates entities under a "WLED Matrix Manager" device in the HA device registry.
When MQTT is unavailable, falls back to REST API state entities (ungrouped).
"""

import asyncio
import json
import logging
import re
from typing import Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)

_instance: Optional["HAEntitySync"] = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None

MQTT_PREFIX = "wled_matrix_manager"
ADDON_VERSION = "1.2.0"


def get_entity_sync() -> "HAEntitySync":
    global _instance
    if _instance is None:
        _instance = HAEntitySync()
    return _instance


def _sanitize_name(name: str) -> str:
    """Convert scene name to a valid HA entity ID suffix."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "unnamed"


class HAEntitySync:
    """Syncs scene states to HA as switch entities via MQTT or REST."""

    def __init__(self):
        self._core_api_url: str = ""
        self._token: str = ""
        self._mqtt_client = None
        self._mqtt_available = False
        self._ws = None
        self._ws_session: Optional[aiohttp.ClientSession] = None
        self._listen_task: Optional[asyncio.Task] = None
        # scene_id -> {name, frame_count, matrix_width, matrix_height, loop_mode, device_count}
        self._scene_meta: Dict[int, dict] = {}
        self._running = False
        self._ignoring_state_updates: set = set()  # scene_ids to ignore (we triggered)

    async def start(self):
        """Initialize: try MQTT first, fall back to REST+WS."""
        global _event_loop
        _event_loop = asyncio.get_running_loop()

        from .ha_client import get_ha_client

        client = get_ha_client()
        self._core_api_url = client._core_api_url
        self._token = client.core_token

        if not self._token:
            logger.warning("HAEntitySync: No token — entities will not be synced")
            return

        self._running = True

        # Try MQTT first
        mqtt_info = await self._get_mqtt_info()
        if mqtt_info:
            self._setup_mqtt(mqtt_info)
        else:
            logger.info("HAEntitySync: MQTT unavailable — using REST fallback")
            if self._core_api_url:
                self._listen_task = asyncio.create_task(
                    self._listen_for_service_calls()
                )

        logger.info(
            f"HAEntitySync: ready (mqtt={self._mqtt_available}, "
            f"core={bool(self._core_api_url)})"
        )

    async def stop(self):
        """Clean up MQTT or WS listener."""
        self._running = False
        if self._mqtt_client:
            try:
                # Publish offline availability
                self._mqtt_client.publish(
                    f"{MQTT_PREFIX}/availability", "offline", retain=True
                )
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass
        if self._listen_task:
            self._listen_task.cancel()
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

    # ─── Public API ────────────────────────────────────────────

    async def sync_all_scenes(self):
        """Register all active scenes as HA entities. Call on startup."""
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
        logger.info(f"HAEntitySync: synced {len(scenes)} scenes to HA")

    async def register_scene(
        self,
        scene_id: int,
        name: str,
        frame_count: int = 0,
        matrix_width: int = 16,
        matrix_height: int = 16,
        loop_mode: str = "once",
        device_count: int = 0,
        is_playing: bool = False,
    ):
        """Create or update a scene entity in HA."""
        self._scene_meta[scene_id] = {
            "name": name,
            "frame_count": frame_count,
            "matrix_width": matrix_width,
            "matrix_height": matrix_height,
            "loop_mode": loop_mode,
            "device_count": device_count,
        }

        if self._mqtt_available:
            self._publish_discovery(
                scene_id,
                name,
                frame_count,
                matrix_width,
                matrix_height,
                loop_mode,
                device_count,
            )
            state = "ON" if is_playing else "OFF"
            self._mqtt_client.publish(
                f"{MQTT_PREFIX}/scene/{scene_id}/state", state, retain=True
            )
            self._publish_attributes(
                scene_id,
                frame_count,
                matrix_width,
                matrix_height,
                loop_mode,
                device_count,
            )
        elif self._core_api_url:
            eid = self._rest_entity_id(scene_id, name)
            state = "on" if is_playing else "off"
            attrs = self._build_rest_attributes(
                name,
                scene_id,
                frame_count,
                matrix_width,
                matrix_height,
                loop_mode,
                device_count,
            )
            await self._set_state_rest(eid, state, attrs)

    async def update_scene_playing(self, scene_id: int, is_playing: bool):
        """Update the on/off state of a scene entity."""
        if self._mqtt_available:
            state = "ON" if is_playing else "OFF"
            self._mqtt_client.publish(
                f"{MQTT_PREFIX}/scene/{scene_id}/state", state, retain=True
            )
        elif self._core_api_url:
            meta = self._scene_meta.get(scene_id)
            if not meta:
                return
            eid = self._rest_entity_id(scene_id, meta["name"])
            state = "on" if is_playing else "off"
            current = await self._get_state_rest(eid)
            attrs = current.get("attributes", {}) if current else {}
            attrs["icon"] = "mdi:led-strip-variant"
            # Mark that we're updating this ourselves (to avoid feedback loop)
            self._ignoring_state_updates.add(scene_id)
            await self._set_state_rest(eid, state, attrs)
            # Remove from ignore set after a short delay
            asyncio.get_event_loop().call_later(
                2.0, lambda: self._ignoring_state_updates.discard(scene_id)
            )

    async def remove_scene(self, scene_id: int):
        """Remove a scene entity from HA."""
        if self._mqtt_available:
            unique_id = f"wled_matrix_scene_{scene_id}"
            self._mqtt_client.publish(
                f"homeassistant/switch/{unique_id}/config", "", retain=True
            )
            self._mqtt_client.publish(
                f"{MQTT_PREFIX}/scene/{scene_id}/state", "", retain=True
            )
            self._mqtt_client.publish(
                f"{MQTT_PREFIX}/scene/{scene_id}/attributes", "", retain=True
            )
        elif self._core_api_url:
            meta = self._scene_meta.get(scene_id)
            if meta:
                eid = self._rest_entity_id(scene_id, meta["name"])
                await self._delete_state_rest(eid)
        self._scene_meta.pop(scene_id, None)

    def get_scene_id_for_command_topic(self, topic: str) -> Optional[int]:
        """Extract scene_id from MQTT command topic."""
        # Topic: wled_matrix_manager/scene/{id}/set
        parts = topic.split("/")
        if len(parts) == 4 and parts[0] == MQTT_PREFIX and parts[3] == "set":
            try:
                return int(parts[2])
            except ValueError:
                pass
        return None

    # ─── MQTT Discovery ───────────────────────────────────────

    async def _get_mqtt_info(self) -> Optional[dict]:
        """Get MQTT broker info from Supervisor services API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "http://supervisor/services/mqtt",
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        mqtt_data = data.get("data", {})
                        if mqtt_data.get("host"):
                            logger.info(
                                f"MQTT service found: {mqtt_data.get('host')}:"
                                f"{mqtt_data.get('port', 1883)}"
                            )
                            return mqtt_data
                    else:
                        logger.debug(f"MQTT service check: {resp.status}")
        except Exception as e:
            logger.debug(f"MQTT service check failed: {e}")
        return None

    def _setup_mqtt(self, mqtt_info: dict):
        """Connect to MQTT broker and set up callbacks."""
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            client_id=f"wled_matrix_manager_{id(self)}",
            protocol=mqtt.MQTTv311,
        )

        username = mqtt_info.get("username", "")
        password = mqtt_info.get("password", "")
        if username:
            client.username_pw_set(username, password)

        # Last Will: mark offline on disconnect
        client.will_set(f"{MQTT_PREFIX}/availability", "offline", retain=True)

        client.on_connect = self._on_mqtt_connect
        client.on_message = self._on_mqtt_message
        client.on_disconnect = self._on_mqtt_disconnect

        host = mqtt_info.get("host", "core-mosquitto")
        port = int(mqtt_info.get("port", 1883))

        try:
            client.connect(host, port, keepalive=60)
            client.loop_start()
            self._mqtt_client = client
            self._mqtt_available = True
            logger.info(f"MQTT connected to {host}:{port}")
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            self._mqtt_available = False

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT: connected, subscribing to command topics")
            client.subscribe(f"{MQTT_PREFIX}/scene/+/set")
            client.publish(f"{MQTT_PREFIX}/availability", "online", retain=True)
        else:
            logger.error(f"MQTT connect failed: rc={rc}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning(f"MQTT unexpected disconnect: rc={rc}")

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle MQTT command messages (runs in MQTT thread)."""
        topic = msg.topic
        payload = msg.payload.decode("utf-8", errors="replace").strip()

        scene_id = self.get_scene_id_for_command_topic(topic)
        if scene_id is None:
            return

        logger.info(f"MQTT command: scene {scene_id} -> {payload}")

        if _event_loop and _event_loop.is_running():
            if payload.upper() == "ON":
                asyncio.run_coroutine_threadsafe(
                    self._start_scene_from_ha(scene_id), _event_loop
                )
            elif payload.upper() == "OFF":
                asyncio.run_coroutine_threadsafe(
                    self._stop_scene_from_ha(scene_id), _event_loop
                )

    def _publish_discovery(
        self,
        scene_id,
        name,
        frame_count,
        matrix_width,
        matrix_height,
        loop_mode,
        device_count,
    ):
        """Publish MQTT discovery config for a scene switch."""
        if not self._mqtt_client:
            return

        unique_id = f"wled_matrix_scene_{scene_id}"
        object_id = f"wled_scene_{scene_id}_{_sanitize_name(name)}"

        config = {
            "name": name,
            "unique_id": unique_id,
            "object_id": object_id,
            "state_topic": f"{MQTT_PREFIX}/scene/{scene_id}/state",
            "command_topic": f"{MQTT_PREFIX}/scene/{scene_id}/set",
            "payload_on": "ON",
            "payload_off": "OFF",
            "state_on": "ON",
            "state_off": "OFF",
            "icon": "mdi:led-strip-variant",
            "availability_topic": f"{MQTT_PREFIX}/availability",
            "payload_available": "online",
            "payload_not_available": "offline",
            "json_attributes_topic": f"{MQTT_PREFIX}/scene/{scene_id}/attributes",
            "device": {
                "identifiers": ["wled_matrix_manager"],
                "name": "WLED Matrix Manager",
                "manufacturer": "WLED Matrix Manager",
                "model": "LED Matrix Scene Controller",
                "sw_version": ADDON_VERSION,
            },
        }

        self._mqtt_client.publish(
            f"homeassistant/switch/{unique_id}/config",
            json.dumps(config),
            retain=True,
        )
        logger.debug(f"MQTT discovery published for scene {scene_id}: {object_id}")

    def _publish_attributes(
        self,
        scene_id,
        frame_count,
        matrix_width,
        matrix_height,
        loop_mode,
        device_count,
    ):
        """Publish JSON attributes for a scene."""
        if not self._mqtt_client:
            return
        attrs = {
            "scene_id": scene_id,
            "frame_count": frame_count,
            "matrix_size": f"{matrix_width}x{matrix_height}",
            "loop_mode": loop_mode,
            "device_count": device_count,
        }
        self._mqtt_client.publish(
            f"{MQTT_PREFIX}/scene/{scene_id}/attributes",
            json.dumps(attrs),
            retain=True,
        )

    # ─── REST API fallback ─────────────────────────────────────

    @staticmethod
    def _rest_entity_id(scene_id: int, name: str) -> str:
        return f"switch.wled_scene_{scene_id}_{_sanitize_name(name)}"

    @staticmethod
    def _build_rest_attributes(
        name,
        scene_id,
        frame_count,
        matrix_width,
        matrix_height,
        loop_mode,
        device_count,
    ):
        return {
            "friendly_name": f"WLED Scene: {name}",
            "icon": "mdi:led-strip-variant",
            "scene_id": scene_id,
            "frame_count": frame_count,
            "matrix_size": f"{matrix_width}x{matrix_height}",
            "loop_mode": loop_mode,
            "device_count": device_count,
            "attribution": "WLED Matrix Manager",
        }

    async def _set_state_rest(self, entity_id: str, state: str, attributes: dict):
        if not self._core_api_url:
            return
        url = f"{self._core_api_url}/states/{entity_id}"
        payload = {"state": state, "attributes": attributes}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status in (200, 201):
                        logger.debug(f"REST entity {entity_id} -> {state}")
                    else:
                        body = await resp.text()
                        logger.error(
                            f"REST set state {entity_id}: {resp.status} {body[:200]}"
                        )
        except Exception as e:
            logger.error(f"REST set state {entity_id}: {e}")

    async def _get_state_rest(self, entity_id: str) -> Optional[dict]:
        if not self._core_api_url:
            return None
        url = f"{self._core_api_url}/states/{entity_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.debug(f"REST get state {entity_id}: {e}")
        return None

    async def _delete_state_rest(self, entity_id: str):
        if not self._core_api_url:
            return
        url = f"{self._core_api_url}/states/{entity_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    url,
                    headers={"Authorization": f"Bearer {self._token}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    logger.debug(f"REST delete entity {entity_id}: {resp.status}")
        except Exception as e:
            logger.error(f"REST delete state {entity_id}: {e}")

    # ─── WS call_service listener (REST fallback) ─────────────

    async def _listen_for_service_calls(self):
        """Subscribe to call_service events to detect HA-side switch toggles.
        Used as fallback when MQTT is not available."""
        from .ha_client import get_ha_client

        client = get_ha_client()
        if not client.authenticated:
            logger.info("HAEntitySync: No WS auth — HA-side toggle disabled")
            return

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

                    logger.info(
                        "HAEntitySync: Listening for switch service calls (REST mode)"
                    )

                    # Process events
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

                    break  # Connected successfully, exit URL loop

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
                    if self._ws_session:
                        try:
                            await self._ws_session.close()
                        except Exception:
                            pass

            # Reconnect after a delay
            if self._running:
                logger.info("HAEntitySync: WS reconnecting in 10s...")
                await asyncio.sleep(10)

    async def _handle_service_call(self, event: dict):
        """Handle call_service event for switch.turn_on / switch.turn_off."""
        data = event.get("data", {})
        domain = data.get("domain", "")
        service = data.get("service", "")

        if domain != "switch" or service not in ("turn_on", "turn_off", "toggle"):
            return

        service_data = data.get("service_data", {})
        entity_ids = service_data.get("entity_id", [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]

        for entity_id in entity_ids:
            if not entity_id.startswith("switch.wled_scene_"):
                continue

            # Find the scene_id from our entity map
            scene_id = self._find_scene_for_rest_entity(entity_id)
            if scene_id is None:
                continue

            if scene_id in self._ignoring_state_updates:
                continue

            logger.info(
                f"HAEntitySync: service {service} on {entity_id} (scene {scene_id})"
            )

            from .scene_playback import get_all_playback_status

            status = get_all_playback_status()
            is_playing = scene_id in status and status[scene_id].get("is_playing")

            if service == "turn_on" and not is_playing:
                await self._start_scene_from_ha(scene_id)
                await self.update_scene_playing(scene_id, True)
            elif service == "turn_off" and is_playing:
                await self._stop_scene_from_ha(scene_id)
                await self.update_scene_playing(scene_id, False)
            elif service == "toggle":
                if is_playing:
                    await self._stop_scene_from_ha(scene_id)
                    await self.update_scene_playing(scene_id, False)
                else:
                    await self._start_scene_from_ha(scene_id)
                    await self.update_scene_playing(scene_id, True)

    def _find_scene_for_rest_entity(self, entity_id: str) -> Optional[int]:
        """Find scene_id matching a REST entity_id."""
        for sid, meta in self._scene_meta.items():
            eid = self._rest_entity_id(sid, meta["name"])
            if eid == entity_id:
                return sid
        return None

    # ─── Shared playback control ──────────────────────────────

    async def _start_scene_from_ha(self, scene_id: int):
        """Load scene from DB and start playback — triggered by HA toggle."""
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
            if not scene:
                logger.error(f"HAEntitySync: Scene {scene_id} not found")
                return

            if not scene.devices:
                logger.warning(f"HAEntitySync: Scene {scene_id} has no devices")
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
            logger.info(f"HAEntitySync: Started playback for scene {scene_id} via HA")

            # Publish ON state for MQTT
            if self._mqtt_available:
                self._mqtt_client.publish(
                    f"{MQTT_PREFIX}/scene/{scene_id}/state", "ON", retain=True
                )

    async def _stop_scene_from_ha(self, scene_id: int):
        """Stop playback — triggered by HA toggle."""
        from .scene_playback import stop_scene_playback

        stop_scene_playback(scene_id)
        logger.info(f"HAEntitySync: Stopped playback for scene {scene_id} via HA")

        if self._mqtt_available:
            self._mqtt_client.publish(
                f"{MQTT_PREFIX}/scene/{scene_id}/state", "OFF", retain=True
            )
