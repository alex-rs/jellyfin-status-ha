"""Config flow for the Jellyfin Status integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_POLL_INTERVAL,
    CONF_SHOW_RECENTLY_ADDED,
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the server URL (and optionally the API key) of the entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            # An empty API key keeps the stored one.
            api_key = user_input.get(CONF_API_KEY) or entry.data[CONF_API_KEY]

            # A new unique_id must not collide with another entry.
            if url != entry.unique_id and any(
                other.entry_id != entry.entry_id and other.unique_id == url
                for other in self.hass.config_entries.async_entries(DOMAIN)
            ):
                return self.async_abort(reason="already_configured")

            try:
                await self._validate_connection(url, api_key)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during reconfigure validation")
                errors["base"] = "unknown"
            else:
                # The update listener reloads the entry. Avoid scheduling a
                # second reload from the flow.
                self.hass.config_entries.async_update_entry(
                    entry,
                    unique_id=url,
                    title=url,
                    data={**entry.data, CONF_URL: url, CONF_API_KEY: api_key},
                )
                if not entry.update_listeners:
                    # The entry is not loaded (for example during setup retry).
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_URL): str,
                        vol.Optional(CONF_API_KEY): str,
                    }
                ),
                {
                    CONF_URL: (
                        user_input[CONF_URL]
                        if user_input is not None
                        else entry.data[CONF_URL]
                    )
                },
            ),
            errors=errors,
        )

    async def _validate_connection(self, url: str, api_key: str) -> None:
        """Validate the connection to the Jellyfin server."""
        session = async_get_clientsession(self.hass)
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
        except (aiohttp.ClientError, TimeoutError) as err:
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
        current_show_recent = self.config_entry.options.get(
            CONF_SHOW_RECENTLY_ADDED, False
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL, default=current_interval
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL)),
                    vol.Optional(
                        CONF_SHOW_RECENTLY_ADDED, default=current_show_recent
                    ): bool,
                }
            ),
        )


class CannotConnectError(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuthError(Exception):
    """Error to indicate there is invalid auth."""
