"""Config flow for the Jellyfin Status integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_URL, CONF_API_KEY

from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MIN_POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL)
        ),
    }
)


class JellyfinStatusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jellyfin Status."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_URL] = user_input[CONF_URL].rstrip("/")

            try:
                await self._validate_connection(
                    user_input[CONF_URL], user_input[CONF_API_KEY]
                )
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow validation")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_URL])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_URL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    async def _validate_connection(url: str, api_key: str) -> None:
        """Validate the connection to the Jellyfin server."""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f'MediaBrowser Token="{api_key}"',
                "Accept": "application/json",
            }
            try:
                async with session.get(
                    f"{url}/Sessions", headers=headers, timeout=15
                ) as resp:
                    if resp.status == 401:
                        raise InvalidAuthError
                    if resp.status != 200:
                        raise CannotConnectError
            except aiohttp.ClientError as err:
                raise CannotConnectError from err

    @staticmethod
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return JellyfinStatusOptionsFlowHandler()


class JellyfinStatusOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Jellyfin Status."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL, default=current_interval
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL)),
                }
            ),
        )


class CannotConnectError(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuthError(Exception):
    """Error to indicate there is invalid auth."""
