# Jellyfin Status

A Home Assistant custom integration that tracks currently playing media from your Jellyfin server, paired with a clean Lovelace card showing cover art, title, and remaining time.

<p align="center">
  <img src="https://img.shields.io/badge/HA-2024.1%2B-blue" alt="Home Assistant">
  <img src="https://img.shields.io/badge/HACS-✓-41bdf5" alt="HACS">
  <img src="https://img.shields.io/github/license/alex-rs/jellyfin-status-ha" alt="License">
  <br>
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=alex-rs&repository=jellyfin-status-ha&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open this repository in HACS">
  </a>
</p>

## Features

- **API key authentication** — no username/password needed, create an API key in your Jellyfin dashboard
- **Per-device sensors** — each device gets its own entity (`sensor.jellyfin_status_chrome`, etc.)
- **Continue Watching fallback** — when nothing is playing, shows your first resume item
- **Configurable poll interval** — control how often the server is checked (min 5s)
- **Clean Lovelace card** — large cover art, title, and remaining time or watch progress
- **Zero extra dependencies** — uses only `aiohttp` already bundled with Home Assistant

## Screenshots

| Playing | Continue Watching |
|---------|-------------------|
| Large cover art, title, remaining time with live progress | Resume item with % watched |

## Installation

### HACS

**Add the repository:**

1. Click the button above or in HACS add this as a **custom repository** (Integration type)
2. Install **Jellyfin Status** from HACS
3. Restart Home Assistant
4. Add the integration via **Settings → Devices & Services → Add Integration → Jellyfin Status**

**Add the card resource:**

1. Go to **Settings → Dashboards → ⋮ → Resources → Add Resource**
2. URL: `https://cdn.jsdelivr.net/gh/alex-rs/jellyfin-status-ha@main/jellyfin-status-card.js`
3. Type: **JavaScript Module**

> Alternatively, download [`jellyfin-status-card.js`](https://raw.githubusercontent.com/alex-rs/jellyfin-status-ha/main/jellyfin-status-card.js) to your HA `config/www/` directory and use `/local/jellyfin-status-card.js` as the URL.

### Manual

```bash
cd /tmp
git clone https://github.com/alex-rs/jellyfin-status-ha.git
cp -r jellyfin-status-ha/custom_components/jellyfin_status /path/to/your/ha/config/custom_components/
cp jellyfin-status-ha/jellyfin-status-card.js /path/to/your/ha/config/www/
```

Then:
1. Restart Home Assistant
2. Add the integration via **Settings → Devices & Services → Add Integration → Jellyfin Status**
3. Add the Lovelace card resource:
   - **Settings → Dashboards → ⋮ → Resources → Add Resource**
   - URL: `/local/jellyfin-status-card.js`
   - Type: **JavaScript Module**

## Configuration

| Field | Description |
|-------|-------------|
| **Server URL** | Your Jellyfin server (e.g. `http://192.168.1.100:8096`) |
| **API Key** | Create one in Jellyfin Dashboard → API Keys |
| **Poll Interval** | How often to check for updates (seconds, default 10, min 5) |

After setup, you can change the poll interval anytime via the **Configure** button on the integration.

## Sensors

One sensor is created per device that has an active session on your Jellyfin server.

**Entity ID**: `sensor.jellyfin_status_{device_name}`  
**State**: media title when playing, `Idle` otherwise

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `play_state` | string | `playing`, `paused`, `idle`, or `idle_resume` |
| `title` | string | Currently playing media title |
| `cover_url` | string | Full URL to cover art |
| `duration` | number | Total duration in seconds |
| `position` | number | Current playback position in seconds |
| `remaining` | number | Remaining time in seconds |
| `progress` | number | Progress percentage (0–100) |
| `type` | string | `Movie`, `Episode`, `Audio`, etc. |
| `series` | string | Series name (for episodes) |
| `episode` | number | Episode number |
| `device_name` | string | Friendly device name |
| `client` | string | Client app name |
| `user_name` | string | Active user |

**Resume attributes** (present when `play_state` is `idle_resume`):

| Attribute | Type | Description |
|-----------|------|-------------|
| `resume_title` | string | Title of continue-watching item |
| `resume_cover_url` | string | Cover art URL |
| `resume_progress` | number | Percentage watched |
| `resume_type` | string | Media type |
| `resume_duration` | number | Total duration in seconds |

## Lovelace Card

### Basic usage

```yaml
type: custom:jellyfin-status-card
```

If no entity is specified, the card auto-detects the first `sensor.jellyfin_status_*` entity.

### With explicit entity

```yaml
type: custom:jellyfin-status-card
entity: sensor.jellyfin_status_chrome
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `entity` | string | auto-detect | The sensor entity to display |

## How It Works

```
Every N seconds:
  ┌─ GET /Sessions ──────────────┐
  │  Find devices with sessions   │
  │  Extract NowPlayingItem data  │
  └──────────────────────────────┘
          │
  ┌───────┴──────────────────────┐
  │  If nothing is playing:      │
  │  GET /UserItems/Resume       │
  │  Show first continue-watch   │
  └──────────────────────────────┘
          │
          ▼
  HA Sensor Entities ◄── Card renders cover, title, time
```

## Development

```bash
# Run a local HA instance for testing
docker run -d --name ha-test \
  -v $(pwd)/custom_components/jellyfin_status:/config/custom_components/jellyfin_status \
  -v $(pwd)/jellyfin-status-card.js:/config/www/jellyfin-status-card.js \
  -p 8123:8123 \
  homeassistant/home-assistant:stable
```

## License

MIT
