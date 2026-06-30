"""DataUpdateCoordinator for the Jellyfin Status integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class JellyfinStatusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches Jellyfin sessions and resume items."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._config_entry = entry
        self._base_url: str = entry.data[CONF_URL].rstrip("/")
        self._api_key: str = entry.data[CONF_API_KEY]

        update_interval = timedelta(
            seconds=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    def update_interval_from_options(self) -> None:
        """Update the poll interval from config entry options."""
        seconds = self._config_entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )
        self.update_interval = timedelta(seconds=seconds)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch sessions and resume items from Jellyfin."""
        async with aiohttp.ClientSession() as session:
            sessions = await self._fetch_sessions(session)
            resume_items = await self._fetch_resume_items(session, sessions)

        return {
            "sessions": sessions,
            "resume_items": resume_items,
        }

    async def _fetch_sessions(
        self, session: aiohttp.ClientSession
    ) -> list[dict[str, Any]]:
        """Fetch all sessions from the Jellyfin API."""
        url = f"{self._base_url}/Sessions"
        headers = self._build_headers()

        try:
            async with session.get(url, headers=headers, timeout=30) as resp:
                if resp.status == 401:
                    raise ConfigEntryAuthFailed("Invalid API key")
                if resp.status != 200:
                    raise UpdateFailed(
                        f"Unexpected status {resp.status} from /Sessions"
                    )
                try:
                    data = await resp.json()
                except ValueError as err:
                    raise UpdateFailed(
                        f"Invalid JSON from /Sessions: {err}"
                    ) from err
                if not isinstance(data, list):
                    raise UpdateFailed(
                        f"Unexpected response type from /Sessions: {type(data).__name__}, expected list"
                    )
                return data
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error fetching sessions: {err}") from err

    async def _fetch_resume_items(
        self,
        session: aiohttp.ClientSession,
        sessions: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Fetch the first resume item for each unique user in the sessions."""
        user_ids: set[str] = set()
        for s in sessions:
            uid = s.get("UserId")
            if uid:
                user_ids.add(uid)

        resume_items: dict[str, dict[str, Any]] = {}
        headers = self._build_headers()

        async def fetch_for_user(user_id: str) -> None:
            url = (
                f"{self._base_url}/UserItems/Resume"
                f"?UserId={user_id}"
                f"&Limit=1&ImageTypeLimit=1&Recursive=true"
                f"&Fields=PrimaryImageAspectRatio"
                f"&IncludeItemTypes=Movie,Episode"
            )
            try:
                async with session.get(url, headers=headers, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("Items", []) if isinstance(data, dict) else []
                        if items:
                            resume_items[user_id] = items[0]
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                pass

        await asyncio.gather(*[fetch_for_user(uid) for uid in user_ids])
        return resume_items

    def _build_headers(self) -> dict[str, str]:
        """Build the Authorization header for Jellyfin API."""
        return {
            "Authorization": f'MediaBrowser Token="{self._api_key}"',
            "Accept": "application/json",
        }

    def build_cover_url(
        self, item_id: str, image_tags: dict[str, str], tag_key: str = "Primary"
    ) -> str | None:
        """Build a cover art URL for a given item."""
        tag = image_tags.get(tag_key)
        if not tag or not item_id:
            return None
        return (
            f"{self._base_url}/Items/{item_id}/Images/{tag_key}"
            f"?tag={tag}&maxWidth=600&quality=90&api_key={self._api_key}"
        )
