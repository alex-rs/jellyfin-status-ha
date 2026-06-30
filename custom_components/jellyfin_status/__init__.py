"""The Jellyfin Status integration."""

from __future__ import annotations

import logging
from pathlib import Path

import aiohttp
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .const import DOMAIN
from .coordinator import JellyfinStatusCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

STATIC_DIR = Path(__file__).parent / "static"
CARD_URL_PREFIX = "/jellyfin-card"


class JellyfinImageProxyView(HomeAssistantView):
    """Proxy Jellyfin images through HA."""

    url = "/jellyfin-card/proxy-image/{item_id}/{image_type}"
    name = "jellyfin_status_image_proxy"
    requires_auth = False

    async def get(
        self, request: aiohttp.web.Request, item_id: str, image_type: str
    ) -> aiohttp.web.Response:
        """Fetch and return the Jellyfin image."""
        hass: HomeAssistant = request.app["hass"]
        tag = request.query.get("tag", "")
        entry_id = request.query.get("entry_id", "")

        coordinator: JellyfinStatusCoordinator | None = None
        if entry_id:
            coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if not coordinator:
            # Fallback: find first coordinator
            for c in hass.data.get(DOMAIN, {}).values():
                coordinator = c
                break
        if not coordinator:
            return aiohttp.web.Response(status=404)

        url = (
            f"{coordinator._base_url}/Items/{item_id}/Images/{image_type}"
            f"?tag={tag}&maxWidth=600&quality=90"
        )
        headers = coordinator._build_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, headers=headers, timeout=30
                ) as resp:
                    if resp.status != 200:
                        return aiohttp.web.Response(status=resp.status)
                    body = await resp.read()
                    return aiohttp.web.Response(
                        body=body,
                        content_type=resp.headers.get("Content-Type", "image/jpeg"),
                    )
        except aiohttp.ClientError as err:
            _LOGGER.debug("Image proxy error: %s", err)
            return aiohttp.web.Response(status=502)


def _build_proxy_url(
    hass: HomeAssistant, entry_id: str, item_id: str, image_tags: dict[str, str], tag_key: str = "Primary"
) -> str | None:
    """Build a proxy cover URL."""
    tag = image_tags.get(tag_key)
    if not tag or not item_id:
        return None
    ha_url = get_url(hass)
    return f"{ha_url}/jellyfin-card/proxy-image/{item_id}/{tag_key}?tag={tag}&entry_id={entry_id}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jellyfin Status from a config entry."""
    coordinator = JellyfinStatusCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.http.register_view(JellyfinImageProxyView())

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PREFIX, str(STATIC_DIR), False)]
    )

    await _register_lovelace_resource(hass)

    # After coordinator stores data, update cover URLs to use proxy
    _update_sensor_cover_urls(hass, entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: JellyfinStatusCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        coordinator.update_interval_from_options()


def _update_sensor_cover_urls(hass: HomeAssistant, entry_id: str) -> None:
    """Replace direct Jellyfin URLs with proxy URLs."""
    coordinator: JellyfinStatusCoordinator | None = hass.data.get(DOMAIN, {}).get(entry_id)
    if not coordinator:
        return

    def proxy_build_cover_url(item_id: str, image_tags: dict[str, str], tag_key: str = "Primary") -> str | None:
        return _build_proxy_url(hass, entry_id, item_id, image_tags, tag_key)

    coordinator.build_cover_url = proxy_build_cover_url  # type: ignore[method-assign]


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    """Register the jellyfin-status-card as a Lovelace resource."""
    card_resource_url = f"{CARD_URL_PREFIX}/jellyfin-status-card.js"

    card_path = STATIC_DIR / "jellyfin-status-card.js"
    if not card_path.is_file():
        _LOGGER.warning("Card file missing: %s. Resource URL: %s", card_path, card_resource_url)
        return

    try:
        from homeassistant.helpers.storage import Store
        store = Store(hass, 1, "lovelace_resources")
        data = await store.async_load() or {"items": []}
        items = data.get("items", [])

        if not any(r.get("url") == card_resource_url for r in items):
            items.append({"url": card_resource_url, "type": "module"})
            data["items"] = items
            await store.async_save(data)
            _LOGGER.info("Registered Lovelace resource: %s", card_resource_url)
        else:
            _LOGGER.debug("Lovelace resource already registered: %s", card_resource_url)
    except Exception as err:
        _LOGGER.warning(
            "Auto-registration failed. Add this resource manually in Settings → Dashboards → Resources: URL=%s Type=JavaScript Module (%s)",
            card_resource_url, err
        )
