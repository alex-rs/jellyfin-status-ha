"""Constants for the Jellyfin Status integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "jellyfin_status"

CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_SHOW_RECENTLY_ADDED: Final = "show_recently_added"

DEFAULT_POLL_INTERVAL: Final = 10
MIN_POLL_INTERVAL: Final = 5

TICKS_PER_SECOND: Final = 10_000_000

ATTR_TITLE: Final = "title"
ATTR_COVER_URL: Final = "cover_url"
ATTR_DURATION: Final = "duration"
ATTR_POSITION: Final = "position"
ATTR_REMAINING: Final = "remaining"
ATTR_PROGRESS: Final = "progress"
ATTR_TYPE: Final = "type"
ATTR_PLAY_STATE: Final = "play_state"
ATTR_DEVICE_NAME: Final = "device_name"
ATTR_CLIENT: Final = "client"
ATTR_USER_NAME: Final = "user_name"
ATTR_SERIES: Final = "series"
ATTR_EPISODE: Final = "episode"
ATTR_ALBUM: Final = "album"
ATTR_ARTIST: Final = "artist"
ATTR_RESUME_TITLE: Final = "resume_title"
ATTR_RESUME_COVER_URL: Final = "resume_cover_url"
ATTR_RESUME_PROGRESS: Final = "resume_progress"
ATTR_RESUME_TYPE: Final = "resume_type"
ATTR_RESUME_DURATION: Final = "resume_duration"
ATTR_RECENT_TITLE: Final = "recent_title"
ATTR_RECENT_COVER_URL: Final = "recent_cover_url"
ATTR_RECENT_TYPE: Final = "recent_type"
ATTR_RECENT_YEAR: Final = "recent_year"
ATTR_RECENT_DURATION: Final = "recent_duration"

STATE_PLAYING: Final = "playing"
STATE_PAUSED: Final = "paused"
STATE_IDLE: Final = "idle"
STATE_IDLE_RESUME: Final = "idle_resume"
STATE_IDLE_RECENT: Final = "idle_recent"


def ticks_to_seconds(ticks: int | None) -> float:
    """Convert Jellyfin ticks (100ns units) to seconds."""
    if ticks is None:
        return 0.0
    return ticks / TICKS_PER_SECOND


def format_remaining(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    if seconds < 0:
        seconds = 0
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
