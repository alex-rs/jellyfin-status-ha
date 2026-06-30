"""The Jellyfin Status integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import JellyfinStatusCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

STATIC_DIR = Path(__file__).parent / "static"
CARD_URL_PREFIX = "/jellyfin-card"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jellyfin Status from a config entry."""
    coordinator = JellyfinStatusCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PREFIX, str(STATIC_DIR), False)]
    )

    await _register_lovelace_resource(hass)

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


async def _register_lovelace_resource(hass: HomeAssistant) -> None:
    """Register the jellyfin-status-card as a Lovelace resource."""
    card_resource_url = f"{CARD_URL_PREFIX}/jellyfin-status-card.js"

    # Verify the file exists
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
