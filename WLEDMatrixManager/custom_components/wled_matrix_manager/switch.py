"""Switch platform for WLED Matrix Manager scenes."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WLEDMatrixCoordinator

logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scene switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WLEDMatrixCoordinator = data["coordinator"]
    base_url: str = data["base_url"]
    session = async_get_clientsession(hass)

    known_ids: set[int] = set()

    @callback
    def _async_add_new_scenes() -> None:
        """Add switch entities for newly discovered scenes."""
        scenes = coordinator.data.get("scenes", []) if coordinator.data else []
        new_entities = []
        for scene in scenes:
            sid = scene["id"]
            if sid not in known_ids:
                known_ids.add(sid)
                new_entities.append(
                    WLEDSceneSwitch(coordinator, session, base_url, scene)
                )
        if new_entities:
            async_add_entities(new_entities)

    # Add entities for the scenes we already know about
    _async_add_new_scenes()
    # Re-check when coordinator updates (new scenes may appear)
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_scenes))


class WLEDSceneSwitch(CoordinatorEntity[WLEDMatrixCoordinator], SwitchEntity):
    """A switch that starts/stops a WLED-MM scene."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:led-strip-variant"

    def __init__(
        self,
        coordinator: WLEDMatrixCoordinator,
        session: aiohttp.ClientSession,
        base_url: str,
        scene: dict,
    ) -> None:
        super().__init__(coordinator)
        self._session = session
        self._base_url = base_url
        self._scene_id: int = scene["id"]
        self._attr_unique_id = f"wled_matrix_scene_{self._scene_id}"
        self._attr_name = scene.get("name", f"Scene {self._scene_id}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "wled_matrix_manager")},
            name="WLED Matrix Manager",
            manufacturer="WLED Matrix Manager",
            model="LED Matrix Scene Controller",
            sw_version="1.2.0",
        )

    @property
    def is_on(self) -> bool:
        """Return True if the scene is currently playing."""
        if not self.coordinator.data:
            return False
        playback = self.coordinator.data.get("playback", {})
        # Playback keys can be int or str depending on JSON serialisation
        status = playback.get(self._scene_id) or playback.get(str(self._scene_id))
        if status:
            return status.get("is_playing", False)
        return False

    @property
    def available(self) -> bool:
        """Return True if the scene still exists in the backend."""
        if not self.coordinator.data:
            return False
        scenes = self.coordinator.data.get("scenes", [])
        return any(s["id"] == self._scene_id for s in scenes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Surface useful scene metadata."""
        if not self.coordinator.data:
            return {}
        for scene in self.coordinator.data.get("scenes", []):
            if scene["id"] == self._scene_id:
                return {
                    "scene_id": self._scene_id,
                    "frame_count": scene.get("frame_count", 0),
                    "matrix_size": (
                        f"{scene.get('matrix_width', 16)}x"
                        f"{scene.get('matrix_height', 16)}"
                    ),
                    "loop_mode": scene.get("loop_mode", "once"),
                    "device_count": len(scene.get("device_ids", [])),
                }
        return {}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start scene playback."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/scenes/{self._scene_id}/play",
                json={},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
        except Exception as exc:
            logger.error("Failed to start scene %s: %s", self._scene_id, exc)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop scene playback."""
        try:
            async with self._session.post(
                f"{self._base_url}/api/scenes/{self._scene_id}/stop",
                json={},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
        except Exception as exc:
            logger.error("Failed to stop scene %s: %s", self._scene_id, exc)
        await self.coordinator.async_request_refresh()
