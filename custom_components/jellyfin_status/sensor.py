"""Sensor platform for Jellyfin Status."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ALBUM,
    ATTR_ARTIST,
    ATTR_CLIENT,
    ATTR_COVER_URL,
    ATTR_DEVICE_NAME,
    ATTR_DURATION,
    ATTR_EPISODE,
    ATTR_PLAY_STATE,
    ATTR_POSITION,
    ATTR_PROGRESS,
    ATTR_REMAINING,
    ATTR_RESUME_COVER_URL,
    ATTR_RESUME_DURATION,
    ATTR_RESUME_PROGRESS,
    ATTR_RESUME_TITLE,
    ATTR_RESUME_TYPE,
    ATTR_RECENT_COVER_URL,
    ATTR_RECENT_DURATION,
    ATTR_RECENT_TITLE,
    ATTR_RECENT_TYPE,
    ATTR_RECENT_YEAR,
    ATTR_SERIES,
    ATTR_TITLE,
    ATTR_TYPE,
    ATTR_USER_NAME,
    CONF_SHOW_RECENTLY_ADDED,
    STATE_IDLE,
    STATE_IDLE_RECENT,
    STATE_IDLE_RESUME,
    STATE_PAUSED,
    STATE_PLAYING,
    TICKS_PER_SECOND,
    DOMAIN,
)
from .coordinator import JellyfinStatusCoordinator


class JellyfinStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing a Jellyfin session."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JellyfinStatusCoordinator,
        entry_id: str,
        device_id: str,
        session_data: dict[str, Any],
        entity_id: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._entry_id = entry_id

        device_name = session_data.get("DeviceName", "Unknown")
        self._attr_name = device_name

        if entity_id is not None:
            self.entity_id = entity_id

        self._attr_unique_id = f"{entry_id}_{device_id}"
        self._attr_extra_state_attributes = {}
        self._attr_icon = "mdi:play-circle-outline"
        self._attr_should_poll = False

        self._update_from_data()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_data()
        self.async_write_ha_state()

    def _find_session(self) -> dict[str, Any] | None:
        """Find the session data for this entity's device."""
        sessions = self.coordinator.data.get("sessions", [])
        for session in sessions:
            if session.get("DeviceId") == self._device_id:
                return session
        return None

    def _update_from_data(self) -> None:
        """Update entity state and attributes from coordinator data."""
        session = self._find_session()

        if session is None:
            self._attr_available = False
            return

        self._attr_available = True

        device_name = session.get("DeviceName", "Unknown")
        client = session.get("Client", "")
        user_name = session.get("UserName", "")
        play_state = session.get("PlayState", {})
        now_playing = session.get("NowPlayingItem")

        base_attrs: dict[str, Any] = {
            ATTR_DEVICE_NAME: device_name,
            ATTR_CLIENT: client,
            ATTR_USER_NAME: user_name,
        }

        if now_playing and now_playing.get("RunTimeTicks") is not None:
            self._populate_now_playing(session, now_playing, play_state, base_attrs)
        else:
            self._populate_resume_or_idle(session, base_attrs)

    def _populate_now_playing(
        self,
        session: dict[str, Any],
        item: dict[str, Any],
        play_state: dict[str, Any],
        attrs: dict[str, Any],
    ) -> None:
        """Populate attributes for an actively playing/played session."""
        runtime_ticks = item.get("RunTimeTicks", 0) or 0
        position_ticks = play_state.get("PositionTicks") or 0
        is_paused = play_state.get("IsPaused", False)

        duration_sec = runtime_ticks / TICKS_PER_SECOND
        position_sec = position_ticks / TICKS_PER_SECOND
        remaining_sec = duration_sec - position_sec
        if remaining_sec < 0:
            remaining_sec = 0

        progress = 0.0
        if runtime_ticks > 0:
            progress = (position_ticks / runtime_ticks) * 100

        item_type = item.get("Type", "")
        title = item.get("Name", "Unknown")

        cover_url = self.coordinator.build_cover_url(
            item.get("Id", ""), item.get("ImageTags", {})
        )

        attrs[ATTR_TITLE] = title
        attrs[ATTR_COVER_URL] = cover_url
        attrs[ATTR_DURATION] = round(duration_sec)
        attrs[ATTR_POSITION] = round(position_sec)
        attrs[ATTR_REMAINING] = round(remaining_sec)
        attrs[ATTR_PROGRESS] = round(progress, 1)
        attrs[ATTR_TYPE] = item_type
        attrs[ATTR_PLAY_STATE] = STATE_PAUSED if is_paused else STATE_PLAYING

        if item_type == "Episode":
            attrs[ATTR_SERIES] = item.get("SeriesName")
            attrs[ATTR_EPISODE] = item.get("IndexNumber")
        elif item_type == "Audio":
            attrs[ATTR_ALBUM] = item.get("Album")
            artists = item.get("Artists", [])
            if artists:
                attrs[ATTR_ARTIST] = ", ".join(artists)

        self._attr_native_value = title
        self._attr_icon = "mdi:pause-circle" if is_paused else "mdi:play-circle"
        self._attr_entity_picture = cover_url
        self._attr_extra_state_attributes = attrs

    def _populate_resume_or_idle(
        self, session: dict[str, Any], attrs: dict[str, Any]
    ) -> None:
        """Populate attributes for an idle session, with optional resume item."""
        user_id = session.get("UserId")
        resume_items = self.coordinator.data.get("resume_items", {})

        resume_item = resume_items.get(user_id) if user_id else None

        if resume_item:
            item_type = resume_item.get("Type", "")
            title = resume_item.get("Name", "Unknown")
            cover_url = self.coordinator.build_cover_url(
                resume_item.get("Id", ""), resume_item.get("ImageTags", {})
            )
            user_data = resume_item.get("UserData", {})
            played_pct = user_data.get("PlayedPercentage", 0)
            runtime_ticks = resume_item.get("RunTimeTicks", 0) or 0
            resume_duration = runtime_ticks / TICKS_PER_SECOND

            attrs[ATTR_RESUME_TITLE] = title
            attrs[ATTR_RESUME_COVER_URL] = cover_url
            attrs[ATTR_RESUME_PROGRESS] = round(played_pct, 1)
            attrs[ATTR_RESUME_TYPE] = item_type
            attrs[ATTR_RESUME_DURATION] = round(resume_duration)
            attrs[ATTR_PLAY_STATE] = STATE_IDLE_RESUME

            self._attr_native_value = STATE_IDLE
            self._attr_icon = "mdi:play-circle-outline"
            self._attr_entity_picture = cover_url
        else:
            show_recent = self.coordinator._config_entry.options.get(
                CONF_SHOW_RECENTLY_ADDED, False
            )
            recent_item = self.coordinator.data.get("recently_added")

            if show_recent and recent_item:
                item_type = recent_item.get("Type", "")
                title = recent_item.get("Name", "Unknown")
                cover_url = self.coordinator.build_cover_url(
                    recent_item.get("Id", ""), recent_item.get("ImageTags", {})
                )
                runtime_ticks = recent_item.get("RunTimeTicks", 0) or 0
                recent_duration = runtime_ticks / TICKS_PER_SECOND
                year = recent_item.get("ProductionYear")

                attrs[ATTR_RECENT_TITLE] = title
                attrs[ATTR_RECENT_COVER_URL] = cover_url
                attrs[ATTR_RECENT_TYPE] = item_type
                attrs[ATTR_RECENT_YEAR] = year
                attrs[ATTR_RECENT_DURATION] = round(recent_duration)
                attrs[ATTR_PLAY_STATE] = STATE_IDLE_RECENT

                self._attr_native_value = STATE_IDLE
                self._attr_icon = "mdi:new-box"
                self._attr_entity_picture = cover_url
            else:
                attrs[ATTR_PLAY_STATE] = STATE_IDLE
                self._attr_native_value = STATE_IDLE
                self._attr_icon = "mdi:monitor-off"
                self._attr_entity_picture = None

        self._attr_extra_state_attributes = attrs


def _make_entity_id(device_name: str, slug_counts: dict[str, int]) -> str:
    """Generate a unique entity_id from a device name, handling duplicates."""
    slug = re.sub(r"[^a-z0-9_]+", "_", device_name.lower()).strip("_")
    count = slug_counts.get(slug, 0)
    slug_counts[slug] = count + 1
    if count == 0:
        return f"sensor.{DOMAIN}_{slug}"
    return f"sensor.{DOMAIN}_{slug}_{count + 1}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin Status sensors."""
    coordinator: JellyfinStatusCoordinator = hass.data[DOMAIN][entry.entry_id]

    tracked_device_ids: set[str] = set()
    slug_counts: dict[str, int] = {}
    entities: list[JellyfinStatusSensor] = []

    sessions = coordinator.data.get("sessions", [])
    for session in sessions:
        device_id = session.get("DeviceId")
        if not device_id or device_id in tracked_device_ids:
            continue
        tracked_device_ids.add(device_id)
        device_name = session.get("DeviceName", "Unknown")
        eid = _make_entity_id(device_name, slug_counts)
        entities.append(
            JellyfinStatusSensor(coordinator, entry.entry_id, device_id, session, eid)
        )

    async_add_entities(entities)

    @callback
    def _handle_new_data() -> None:
        """Handle coordinator updates to add new sensors."""
        current_data = coordinator.data
        sessions_list = current_data.get("sessions", [])
        current_device_ids = {
            s.get("DeviceId") for s in sessions_list if s.get("DeviceId")
        }

        new_device_ids = current_device_ids - tracked_device_ids
        if new_device_ids:
            new_entities: list[JellyfinStatusSensor] = []
            for device_id in new_device_ids:
                session = next(
                    (s for s in sessions_list if s.get("DeviceId") == device_id),
                    {"DeviceName": "Unknown"},
                )
                device_name = session.get("DeviceName", "Unknown")
                eid = _make_entity_id(device_name, slug_counts)
                new_entities.append(
                    JellyfinStatusSensor(
                        coordinator, entry.entry_id, device_id, session, eid
                    )
                )
                tracked_device_ids.add(device_id)
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_new_data))
