"""DataUpdateCoordinator for WLED Matrix Manager."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_SECONDS

logger = logging.getLogger(__name__)


class WLEDMatrixCoordinator(DataUpdateCoordinator):
    """Fetch scene list and playback status from the addon API."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        base_url: str,
    ) -> None:
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self._session = session
        self._base_url = base_url

    async def _async_update_data(self) -> dict:
        try:
            async with self._session.get(
                f"{self._base_url}/api/scenes",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                scenes = await resp.json()
        except Exception as err:
            raise UpdateFailed(f"Error fetching scenes: {err}") from err

        try:
            async with self._session.get(
                f"{self._base_url}/api/playback/status",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                resp.raise_for_status()
                playback = await resp.json()
        except Exception:
            playback = {}

        return {"scenes": scenes, "playback": playback}
