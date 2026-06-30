import { LitElement, html, css } from "https://cdn.jsdelivr.net/npm/lit@3/+esm";

function formatTime(seconds) {
  if (seconds == null || isNaN(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function findJellyfinEntity(hass) {
  if (!hass) return null;
  return Object.keys(hass.states || {}).find(
    (eid) => eid.startsWith("sensor.jellyfin_status_")
  ) || null;
}

class JellyfinStatusCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object, attribute: false },
      _config: { type: Object, state: true },
    };
  }

  static get styles() {
    return css`
      :host {
        --jsc-accent: var(--accent-color, #03a9f4);
        --jsc-text: var(--primary-text-color, #212121);
        --jsc-text-secondary: var(--secondary-text-color, #757575);
        --jsc-bg: var(--card-background-color, #ffffff);
        --jsc-placeholder-bg: rgba(128, 128, 128, 0.1);
        --jsc-radius: var(--ha-card-border-radius, 12px);
        display: block;
      }
      .card {
        background: var(--jsc-bg);
        border-radius: var(--jsc-radius);
        overflow: hidden;
      }
      .cover-wrapper {
        position: relative;
        width: 100%;
        aspect-ratio: 16 / 9;
        overflow: hidden;
        background: var(--jsc-placeholder-bg);
      }
      .cover-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
      .cover-placeholder {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--jsc-text-secondary);
        font-size: 48px;
      }
      .info {
        padding: 12px;
      }
      .title {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--jsc-text);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 1.3;
      }
      .subtitle {
        font-size: 0.85rem;
        color: var(--jsc-text-secondary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-top: 3px;
      }
      .status-row {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-top: 6px;
        font-size: 0.82rem;
        color: var(--jsc-text-secondary);
      }
      .state-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      .state-dot.playing {
        background: #4caf50;
        animation: pulse 1.5s ease-in-out infinite;
      }
      .state-dot.paused {
        background: #ff9800;
      }
      .state-dot.idle_resume {
        background: var(--jsc-accent);
      }
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
      }
      .idle-card {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px;
      }
      .idle-icon {
        font-size: 1.4rem;
        color: var(--jsc-text-secondary);
      }
      .idle-text {
        font-size: 0.95rem;
        color: var(--jsc-text-secondary);
      }
      .config-error {
        padding: 14px;
        color: var(--error-color, #c62828);
        font-size: 0.85rem;
      }
    `;
  }

  set hass(hass) {
    this._hass = hass;
    this.requestUpdate();
  }

  get hass() {
    return this._hass;
  }

  setConfig(config) {
    this._config = {
      entity: config.entity || config.entity_id || null,
    };
  }

  getCardSize() {
    return 5;
  }

  static getConfigElement() {
    return document.createElement("div");
  }

  static getStubConfig() {
    return { entity: "sensor.jellyfin_status_chrome" };
  }

  render() {
    if (!this._config) return html``;
    if (!this._hass) {
      return html`<div class="card"><div class="idle-card"><span class="idle-text">Loading...</span></div></div>`;
    }

    const entityId = this._config.entity || findJellyfinEntity(this._hass);
    if (!entityId) {
      return html`<div class="card"><div class="config-error">No Jellyfin Status entity found.</div></div>`;
    }

    const stateObj = this._hass.states[entityId];
    if (!stateObj) {
      return html`<div class="card"><div class="idle-card"><span class="idle-text">Waiting for entity: ${entityId}</span></div></div>`;
    }

    const attrs = stateObj.attributes;
    const playState = attrs.play_state || "idle";

    if (playState === "idle" && !attrs.resume_title) {
      return this._renderIdle(attrs);
    }

    return this._renderMedia(attrs, playState, stateObj);
  }

  _renderIdle(attrs) {
    const deviceName = attrs.device_name || "Unknown";
    return html`
      <div class="card">
        <div class="idle-card">
          <ha-icon class="idle-icon" icon="mdi:monitor-off"></ha-icon>
          <span class="idle-text">${deviceName} &middot; Idle</span>
        </div>
      </div>
    `;
  }

  _renderMedia(attrs, playState, stateObj) {
    const isResume = playState === "idle_resume";
    const title = isResume ? attrs.resume_title : attrs.title;
    const coverUrl = isResume ? attrs.resume_cover_url : attrs.cover_url;
    const type = isResume ? attrs.resume_type : attrs.type;
    const series = attrs.series;
    const episode = attrs.episode;

    let subtitle = type || "";
    if (series) {
      subtitle = series;
      if (episode != null) subtitle += ` \u00b7 E${episode}`;
    }

    let statusText;
    let stateLabel;
    let stateClass;

    if (isResume) {
      const pct = Math.round(attrs.resume_progress || 0);
      statusText = `${pct}% watched`;
      stateLabel = "Continue";
      stateClass = "idle_resume";
    } else {
      const duration = attrs.duration || 0;
      const position = attrs.position || 0;
      const isPlaying = playState === "playing";

      if (isPlaying) {
        const now = new Date();
        const lastUpdated = new Date(stateObj.last_updated);
        const elapsedMs = now - lastUpdated;
        let livePosition = position;
        if (elapsedMs > 0) {
          livePosition = position + elapsedMs / 1000;
          if (livePosition > duration) livePosition = duration;
        }
        const remaining = Math.max(0, duration - livePosition);
        statusText = `\u2212${formatTime(remaining)}`;
      } else {
        statusText = `\u2212${formatTime(duration - position)}`;
      }

      stateLabel = isPlaying ? "Playing" : "Paused";
      stateClass = isPlaying ? "playing" : "paused";
    }

    return html`
      <div class="card">
        <div class="cover-wrapper">
          ${coverUrl
            ? html`<img class="cover-image" src="${coverUrl}" alt="" @error="${this._onImageError}" />`
            : html`<div class="cover-placeholder"><ha-icon icon="mdi:movie-open"></ha-icon></div>`
          }
        </div>
        <div class="info">
          <div class="title" title="${title || ""}">${title || "Unknown"}</div>
          ${subtitle ? html`<div class="subtitle">${subtitle}</div>` : ""}
          <div class="status-row">
            <span class="state-dot ${stateClass}"></span>
            <span>${statusText} &middot; ${stateLabel}</span>
          </div>
        </div>
      </div>
    `;
  }

  _onImageError(e) {
    const wrapper = e.target.parentElement;
    if (wrapper) {
      wrapper.innerHTML = '<div class="cover-placeholder"><ha-icon icon="mdi:movie-open"></ha-icon></div>';
    }
  }
}

customElements.define("jellyfin-status-card", JellyfinStatusCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "jellyfin-status-card",
  name: "Jellyfin Status Card",
  description: "Displays currently playing media from Jellyfin with cover art, title, and remaining time.",
  preview: false,
});
