"""Fixtures for the Jellyfin Status tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.jellyfin_status.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in every test."""
    yield


@pytest.fixture(autouse=True)
def mock_setup_entry(request):
    """Prevent the real setup from registering views and polling."""
    if "real_setup" in request.keywords:
        yield None
        return

    with (
        patch(
            f"custom_components.{DOMAIN}.async_setup_entry", return_value=True
        ) as setup_entry,
        patch(f"custom_components.{DOMAIN}.async_unload_entry", return_value=True),
    ):
        yield setup_entry
