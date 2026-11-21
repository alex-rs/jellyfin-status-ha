"""Tests for the Jellyfin Status config flow."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.jellyfin_status.const import (
    CONF_POLL_INTERVAL,
    CONF_SHOW_RECENTLY_ADDED,
    DOMAIN,
)
from custom_components.jellyfin_status.coordinator import JellyfinStatusCoordinator

OLD_URL = "http://old-jellyfin.test"
NEW_URL = "http://new-jellyfin.test"
OTHER_URL = "http://other-jellyfin.test"
API_KEY = "stored-api-key"
NEW_API_KEY = "new-api-key"


def _sessions_url(url: str) -> str:
    return f"{url}/Sessions"


@pytest.fixture
def reconfigurable_entry(hass) -> MockConfigEntry:
    """Add an entry that can be reconfigured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=OLD_URL,
        unique_id=OLD_URL,
        data={
            CONF_URL: OLD_URL,
            CONF_API_KEY: API_KEY,
            CONF_POLL_INTERVAL: 30,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def fake_first_refresh():
    """Skip the real coordinator poll during setup and reload."""

    async def _first_refresh(coordinator: JellyfinStatusCoordinator) -> None:
        coordinator.data = {
            "sessions": [],
            "resume_items": {},
            "recently_added": None,
        }

    with patch.object(
        JellyfinStatusCoordinator,
        "async_config_entry_first_refresh",
        _first_refresh,
    ):
        yield


async def _start_reconfigure(hass, entry: MockConfigEntry):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )


async def test_user_flow_creates_entry(hass, aioclient_mock) -> None:
    """A valid URL and key create a single entry."""
    aioclient_mock.get(_sessions_url("http://jellyfin.test"), json=[])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://jellyfin.test/", CONF_API_KEY: API_KEY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "http://jellyfin.test"
    assert result["data"] == {
        CONF_URL: "http://jellyfin.test",
        CONF_API_KEY: API_KEY,
        CONF_POLL_INTERVAL: 10,
    }
    assert result["result"].unique_id == "http://jellyfin.test"


@pytest.mark.real_setup
@pytest.mark.parametrize(
    ("submitted_key", "expected_key"),
    [(NEW_API_KEY, NEW_API_KEY), ("", API_KEY)],
    ids=["new_api_key", "empty_api_key_keeps_stored"],
)
async def test_reconfigure_updates_entry_and_reloads(
    hass,
    aioclient_mock,
    reconfigurable_entry,
    fake_first_refresh,
    submitted_key,
    expected_key,
) -> None:
    """Reconfiguring updates the entry, reloads it and keeps unexposed data."""
    entry = reconfigurable_entry
    assert await async_setup_component(hass, "http", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    aioclient_mock.get(_sessions_url(NEW_URL), json=[])

    result = await _start_reconfigure(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: NEW_URL, CONF_API_KEY: submitted_key},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert entry.data[CONF_URL] == NEW_URL
    assert entry.data[CONF_API_KEY] == expected_key
    # Data not exposed in the reconfigure form is preserved.
    assert entry.data[CONF_POLL_INTERVAL] == 30
    assert entry.unique_id == NEW_URL
    assert entry.title == NEW_URL

    # The reloaded entry is healthy and uses the new server URL.
    assert entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator._base_url == NEW_URL
    assert coordinator._api_key == expected_key

    # Routes are registered once, not once per reload. Each registration adds
    # one resource (aiohttp adds OPTIONS/HEAD routes on top of it).
    view_path = "/jellyfin-card/proxy-image/{item_id}/{image_type}"
    resources = list(hass.http.app.router.resources())
    assert sum(resource.canonical == view_path for resource in resources) == 1
    # StaticResource plus the explicit file route.
    assert sum(resource.canonical == "/jellyfin-card" for resource in resources) == 2


async def test_reconfigure_reloads_entry_without_update_listener(
    hass, aioclient_mock, mock_setup_entry, reconfigurable_entry
) -> None:
    """An entry without update listeners (setup retry) is reloaded explicitly."""
    entry = reconfigurable_entry
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert mock_setup_entry.call_count == 1
    assert not entry.update_listeners

    aioclient_mock.get(_sessions_url(NEW_URL), json=[])

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: NEW_URL, CONF_API_KEY: NEW_API_KEY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_URL] == NEW_URL
    assert mock_setup_entry.call_count == 2


@pytest.mark.parametrize(
    ("mock_kwargs", "expected_error"),
    [
        ({"status": 401}, "invalid_auth"),
        ({"status": 500}, "cannot_connect"),
        ({"exc": aiohttp.ClientError}, "cannot_connect"),
        ({"exc": TimeoutError}, "cannot_connect"),
    ],
)
async def test_reconfigure_errors_keep_entry_unchanged(
    hass,
    aioclient_mock,
    reconfigurable_entry,
    mock_kwargs,
    expected_error,
) -> None:
    """Failed validation re-renders the form and leaves the entry intact."""
    entry = reconfigurable_entry
    aioclient_mock.get(_sessions_url(NEW_URL), **mock_kwargs)

    result = await _start_reconfigure(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: NEW_URL, CONF_API_KEY: NEW_API_KEY},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}

    assert entry.data[CONF_URL] == OLD_URL
    assert entry.data[CONF_API_KEY] == API_KEY
    assert entry.unique_id == OLD_URL
    assert entry.title == OLD_URL


async def test_reconfigure_aborts_on_duplicate_unique_id(
    hass, reconfigurable_entry
) -> None:
    """Reconfiguring onto another entry's unique_id is rejected."""
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title=OTHER_URL,
        unique_id=OTHER_URL,
        data={CONF_URL: OTHER_URL, CONF_API_KEY: API_KEY},
    )
    other_entry.add_to_hass(hass)

    result = await _start_reconfigure(hass, reconfigurable_entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: OTHER_URL, CONF_API_KEY: API_KEY},
    )

    assert result["type"] is FlowResultType.ABORT
    # The existing entry must not be modified.
    assert reconfigurable_entry.data[CONF_URL] == OLD_URL
    assert reconfigurable_entry.unique_id == OLD_URL
    assert other_entry.data[CONF_URL] == OTHER_URL


@pytest.mark.real_setup
async def test_options_update_reloads_entry(
    hass, reconfigurable_entry, fake_first_refresh
) -> None:
    """Changing options reloads the entry so the new interval applies."""
    entry = reconfigurable_entry
    assert await async_setup_component(hass, "http", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_POLL_INTERVAL: 60,
            CONF_SHOW_RECENTLY_ADDED: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_POLL_INTERVAL] == 60
    assert entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.update_interval == timedelta(seconds=60)
