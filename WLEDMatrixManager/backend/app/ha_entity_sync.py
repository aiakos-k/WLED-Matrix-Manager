"""
Home Assistant Entity Sync — stub module.

The actual entity management is handled by the custom integration
(custom_components/wled_matrix_manager/) which is installed automatically
when the addon starts. This module only cleans up legacy REST-created entities.

All public methods are no-ops so existing callers in router.py / scene_playback.py
continue to work without changes.
"""

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

_instance: Optional["HAEntitySync"] = None


def get_entity_sync() -> "HAEntitySync":
    global _instance
    if _instance is None:
        _instance = HAEntitySync()
    return _instance


class HAEntitySync:
    """Stub — the real work is done by the HA custom integration."""

    def __init__(self):
        self._core_api_url: str = ""
        self._token: str = ""

    async def start(self):
        """Clean up legacy REST-created entities, then do nothing."""
        from .ha_client import get_ha_client

        client = get_ha_client()
        self._core_api_url = client._core_api_url
        self._token = client.core_token

        if self._core_api_url and self._token:
            await self._cleanup_legacy_entities()

        logger.info(
            "HAEntitySync: stub ready (entities managed by custom integration)"
        )

    async def stop(self):
        pass

    async def sync_all_scenes(self):
        pass

    async def register_scene(self, **kwargs):
        pass

    async def update_scene_playing(self, scene_id: int, is_playing: bool):
        pass

    async def remove_scene(self, scene_id: int):
        pass

    # --- Legacy cleanup ---

    async def _cleanup_legacy_entities(self):
        """Remove old REST-created switch.wled_scene_* entities."""
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
                                headers={
                                    "Authorization": f"Bearer {self._token}"
                                },
                                timeout=aiohttp.ClientTimeout(total=5),
                            ) as resp:
                                if resp.status in (200, 204):
                                    removed += 1
                                    logger.debug(f"Removed legacy entity: {eid}")
                    except Exception:
                        pass

            if removed:
                logger.info(
                    f"HAEntitySync: cleaned up {removed} legacy REST entities"
                )
        except Exception as e:
            logger.debug(f"Legacy cleanup failed: {e}")
