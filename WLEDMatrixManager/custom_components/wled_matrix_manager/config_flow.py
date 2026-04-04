"""Config flow for WLED Matrix Manager."""

from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HOST, CONF_PORT, DEFAULT_HOST, DEFAULT_PORT, DOMAIN


class WLEDMatrixManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WLED Matrix Manager."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step (manual setup)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            session = async_get_clientsession(self.hass)
            try:
                async with session.get(
                    f"http://{host}:{port}/api/status",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        await self.async_set_unique_id(DOMAIN)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title="WLED Matrix Manager",
                            data=user_input,
                        )
                    errors["base"] = "cannot_connect"
            except AbortFlow:
                raise
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )
