console.log("jellyfin-status-card: loading...");

(function () {
  "use strict";

  function formatTime(seconds) {
    if (seconds == null || isNaN(seconds) || seconds < 0) return "0:00";
    var total = Math.floor(seconds);
    var h = Math.floor(total / 3600);
    var m = Math.floor((total % 3600) / 60);
    var s = total % 60;
    if (h > 0) return h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
    return m + ":" + String(s).padStart(2, "0");
  }

  function findJellyfinEntity(hass) {
    if (!hass) return null;
    var keys = Object.keys(hass.states || {});
    for (var i = 0; i < keys.length; i++) {
      if (keys[i].startsWith("sensor.jellyfin_status_")) return keys[i];
    }
    return null;
  }

  function htmlEscape(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function buildMediaCard(attrs, playState, lastUpdated) {
    var isResume = playState === "idle_resume";
    var isRecent = playState === "idle_recent";

    var title, coverUrl, type, series, episode;

    if (isRecent) {
      title = attrs.recent_title;
      coverUrl = attrs.recent_cover_url;
      type = attrs.recent_type;
      series = null;
      episode = null;
    } else {
      title = isResume ? attrs.resume_title : attrs.title;
      coverUrl = isResume ? attrs.resume_cover_url : attrs.cover_url;
      type = isResume ? attrs.resume_type : attrs.type;
      series = attrs.series;
      episode = attrs.episode;
    }

    var subtitle = "";
    if (isRecent) {
      subtitle = "Recently Added";
      if (type) subtitle += " \u00b7 " + type;
      if (attrs.recent_year) subtitle += " \u00b7 " + attrs.recent_year;
    } else if (series) {
      subtitle = series;
      if (episode != null) subtitle += " \u00b7 E" + episode;
    } else {
      subtitle = type || "";
    }

    var statusText, stateLabel, stateClass;

    if (isResume) {
      var pct = Math.round(attrs.resume_progress || 0);
      statusText = pct + "% watched";
      stateLabel = "Continue";
      stateClass = "idle_resume";
    } else if (isRecent) {
      var recentDuration = attrs.recent_duration || 0;
      statusText = formatTime(recentDuration);
      stateLabel = "New";
      stateClass = "idle_resume";
    } else {
      var duration = attrs.duration || 0;
      var position = attrs.position || 0;
      var isPlaying = playState === "playing";

      if (isPlaying) {
        var now = new Date();
        var lastUpd = new Date(lastUpdated);
        var elapsedMs = now - lastUpd;
        var livePosition = position;
        if (elapsedMs > 0) {
          livePosition = position + elapsedMs / 1000;
          if (livePosition > duration) livePosition = duration;
        }
        var remaining = Math.max(0, duration - livePosition);
        statusText = "−" + formatTime(remaining);
      } else {
        statusText = "−" + formatTime(duration - position);
      }

      stateLabel = isPlaying ? "Playing" : "Paused";
      stateClass = isPlaying ? "playing" : "paused";
    }

    var imgHtml = coverUrl
      ? '<img class="jsc-cover-image" src="' + htmlEscape(coverUrl) + '" alt="" />'
      : '<div class="jsc-cover-placeholder"><ha-icon icon="mdi:movie-open"></ha-icon></div>';

    return [
      '<div class="jsc-card">',
        '<div class="jsc-cover-wrapper">', imgHtml, '</div>',
        '<div class="jsc-info">',
          '<div class="jsc-title" title="', htmlEscape(title || ""), '">', htmlEscape(title || "Unknown"), '</div>',
          subtitle ? '<div class="jsc-subtitle">' + htmlEscape(subtitle) + '</div>' : '',
          '<div class="jsc-status-row">',
            '<span class="jsc-state-dot ', stateClass, '"></span>',
            '<span>', htmlEscape(statusText), ' · ', htmlEscape(stateLabel), '</span>',
          '</div>',
        '</div>',
      '</div>'
    ].join("");
  }

  function buildIdleCard() {
    return [
      '<div class="jsc-card">',
        '<div class="jsc-idle-card">',
          '<ha-icon class="jsc-idle-icon" icon="mdi:monitor-off"></ha-icon>',
          '<span class="jsc-idle-text">Idle</span>',
        '</div>',
      '</div>'
    ].join("");
  }

  var css = [
    "jellyfin-status-card{",
      "--jsc-accent:var(--accent-color,#03a9f4);",
      "--jsc-text:var(--primary-text-color,#212121);",
      "--jsc-text-secondary:var(--secondary-text-color,#757575);",
      "--jsc-bg:var(--card-background-color,#ffffff);",
      "--jsc-placeholder-bg:rgba(128,128,128,0.1);",
      "--jsc-radius:var(--ha-card-border-radius,12px);",
      "display:block;",
    "}",
    ".jsc-card{background:var(--jsc-bg);border-radius:var(--jsc-radius);overflow:hidden}",
    ".jsc-cover-wrapper{width:100%;height:200px;overflow:hidden;background:var(--jsc-placeholder-bg);border-radius:var(--jsc-radius)}",
    "img.jsc-cover-image{width:100%!important;height:200px!important;object-fit:cover!important;display:block}",
    ".jsc-cover-placeholder{width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--jsc-text-secondary);font-size:48px}",
    ".jsc-info{padding:12px}",
    ".jsc-title{font-size:1.05rem;font-weight:600;color:var(--jsc-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3}",
    ".jsc-subtitle{font-size:0.85rem;color:var(--jsc-text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:3px}",
    ".jsc-status-row{display:flex;align-items:center;gap:6px;margin-top:6px;font-size:0.82rem;color:var(--jsc-text-secondary)}",
    ".jsc-state-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}",
    ".jsc-state-dot.playing{background:#4caf50;animation:jsc-pulse 1.5s ease-in-out infinite}",
    ".jsc-state-dot.paused{background:#ff9800}",
    ".jsc-state-dot.idle_resume{background:var(--jsc-accent)}",
    "@keyframes jsc-pulse{0%,100%{opacity:1}50%{opacity:0.4}}",
    ".jsc-idle-card{display:flex;align-items:center;gap:10px;padding:14px}",
    ".jsc-idle-icon{font-size:1.4rem;color:var(--jsc-text-secondary)}",
    ".jsc-idle-text{font-size:0.95rem;color:var(--jsc-text-secondary)}",
    ".jsc-config-error{padding:14px;color:var(--error-color,#c62828);font-size:0.85rem}"
  ].join("");

  try {
    var styleEl = document.createElement("style");
    styleEl.textContent = css;
    if (document.head) {
      document.head.appendChild(styleEl);
    } else {
      document.addEventListener("DOMContentLoaded", function () {
        document.head.appendChild(styleEl);
      });
    }
  } catch (e) {
    console.warn("jellyfin-status-card: failed to inject styles", e);
  }

  var JellyfinStatusCard = (function () {
    function JellyfinStatusCard() {
      this._hass = null;
      this._config = null;
    }

    JellyfinStatusCard.prototype = Object.create(HTMLElement.prototype);
    JellyfinStatusCard.prototype.constructor = JellyfinStatusCard;

    Object.defineProperty(JellyfinStatusCard.prototype, "hass", {
      set: function (hass) {
        if (!hass) return;
        this._hass = hass;
        this._render();
      }
    });

    JellyfinStatusCard.prototype.setConfig = function (config) {
      this._config = { entity: config.entity || config.entity_id || null };
      this._render();
    };

    JellyfinStatusCard.prototype.getCardSize = function () {
      return 5;
    };

    JellyfinStatusCard.getStubConfig = function () {
      return { entity: "sensor.jellyfin_status_chrome" };
    };

    JellyfinStatusCard.prototype._render = function () {
      try {
        if (!this._config) return;

        if (!this._hass) {
          this.innerHTML = '<div class="jsc-card"><div class="jsc-idle-card"><span class="jsc-idle-text">Loading...</span></div></div>';
          return;
        }

        var entityId = this._config.entity || findJellyfinEntity(this._hass);
        if (!entityId) {
          this.innerHTML = '<div class="jsc-card"><div class="jsc-config-error">No Jellyfin Status entity found.</div></div>';
          return;
        }

        var stateObj = this._hass.states[entityId];
        if (!stateObj) {
          this.innerHTML = '<div class="jsc-card"><div class="jsc-idle-card"><span class="jsc-idle-text">Waiting for entity: ' + htmlEscape(entityId) + '</span></div></div>';
          return;
        }

        var attrs = stateObj.attributes;
        var playState = attrs.play_state || "idle";

        if (playState === "idle" && !attrs.resume_title) {
          this.innerHTML = buildIdleCard();
        } else {
          this.innerHTML = buildMediaCard(attrs, playState, stateObj.last_updated);
          var img = this.querySelector(".jsc-cover-image");
          if (img) {
            img.addEventListener("error", function () {
              var wrapper = this.parentElement;
              if (wrapper) {
                wrapper.innerHTML = '<div class="jsc-cover-placeholder"><ha-icon icon="mdi:movie-open"></ha-icon></div>';
              }
            });
          }
        }
      } catch (e) {
        console.error("jellyfin-status-card: render error", e);
        this.innerHTML = '<div class="jsc-card"><div class="jsc-config-error">Card error: ' + htmlEscape(String(e.message || e)) + '</div></div>';
      }
    };

    return JellyfinStatusCard;
  })();

  try {
    customElements.define("jellyfin-status-card", JellyfinStatusCard);
    console.log("jellyfin-status-card: registered");
  } catch (e) {
    console.error("jellyfin-status-card: failed to register", e);
  }

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "jellyfin-status-card",
    name: "Jellyfin Status Card",
    description: "Displays currently playing media from Jellyfin with cover art, title, and remaining time.",
    preview: false,
  });
})();
