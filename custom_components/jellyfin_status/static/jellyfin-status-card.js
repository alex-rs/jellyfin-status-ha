console.log("jellyfin-status-card: loading");

(function () {
  "use strict";

  if (typeof customElements === "undefined") return;

  function esc(s) {
    s = String(s || "");
    return s.replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }
  function fmtime(s) {
    if (s == null || isNaN(s) || s < 0) return "0:00";
    var t = Math.floor(s), h = Math.floor(t/3600), m = Math.floor((t%3600)/60), sec = t%60;
    if (h) return h + ":" + String(m).padStart(2,"0") + ":" + String(sec).padStart(2,"0");
    return m + ":" + String(sec).padStart(2,"0");
  }
  function findEntity(hass) {
    if (!hass || !hass.states) return null;
    var ks = Object.keys(hass.states);
    for (var i = 0; i < ks.length; i++) if (ks[i].startsWith("sensor.jellyfin_status_")) return ks[i];
    return null;
  }

  // Inject just the keyframe animation (tiny, unlikely to fail)
  try {
    var animStyle = document.createElement("style");
    animStyle.textContent = "@keyframes jsc-pulse{0%,100%{opacity:1}50%{opacity:0.4}}";
    if (document.head) document.head.appendChild(animStyle);
  } catch(e) {}

  var cardBg     = "background:var(--card-background-color,#fff);border-radius:var(--ha-card-border-radius,12px)";
  var coverBg    = "background:rgba(128,128,128,0.1)";
  var coverStyle = "width:100%;height:200px;overflow:hidden;" + coverBg + ";border-radius:var(--ha-card-border-radius,12px)";
  var imgStyle   = "width:100%;height:200px;object-fit:cover;display:block";
  var placeholderStyle = "width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:var(--secondary-text-color,#757575);font-size:48px";
  var text       = "color:var(--primary-text-color,#212121)";
  var textSec    = "color:var(--secondary-text-color,#757575)";
  var infoPad    = "padding:10px 12px 12px 12px";
  var titleStyle = "font-size:1.05rem;font-weight:600;" + text + ";white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3";
  var subStyle   = "font-size:0.85rem;" + textSec + ";white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:3px";
  var rowStyle   = "display:flex;align-items:center;gap:6px;margin-top:6px;font-size:0.82rem;" + textSec;
  function dotStyle(color, extra) {
    return "width:7px;height:7px;border-radius:50%;flex-shrink:0;background:" + color + ";" + (extra||"");
  }
  var idleCardStyle = "display:flex;align-items:center;gap:10px;padding:14px;" + textSec + ";font-size:0.95rem";
  function configErrorStyle() { return "padding:14px;color:var(--error-color,#c62828);font-size:0.85rem"; }

  function renderCard() {
    var a = this._attrs, ps = this._playState, lu = this._lastUpdated;
    try {
      if (ps === "idle" && !a.resume_title && !a.recent_title) {
        this.innerHTML = [
          '<div style="', cardBg, '">',
            '<div style="', idleCardStyle, '">',
              '<ha-icon style="font-size:1.4rem" icon="mdi:monitor-off"></ha-icon>',
              '<span>Idle</span>',
            '</div>',
          '</div>'
        ].join("");
        return;
      }

      var isRc = ps === "idle_recent", isRs = ps === "idle_resume";
      var title = isRc ? a.recent_title : (isRs ? a.resume_title : a.title);
      var cover = isRc ? a.recent_cover_url : (isRs ? a.resume_cover_url : a.cover_url);
      var type  = isRc ? a.recent_type : (isRs ? a.resume_type : a.type);

      var sub = "";
      if (isRc) {
        sub = "Recently Added";
        if (type) sub += " · " + type;
        if (a.recent_year) sub += " · " + a.recent_year;
      } else if (a.series) {
        sub = a.series;
        if (a.episode != null) sub += " · E" + a.episode;
      } else {
        sub = type || "";
      }

      var stxt, slbl, dColor, dAnim;
      if (isRs) {
        stxt = Math.round(a.resume_progress || 0) + "% watched"; slbl = "Continue"; dColor = "var(--accent-color,#03a9f4)"; dAnim = "";
      } else if (isRc) {
        stxt = fmtime(a.recent_duration || 0); slbl = "New"; dColor = "var(--accent-color,#03a9f4)"; dAnim = "";
      } else {
        var dur = a.duration || 0, pos = a.position || 0, playing = ps === "playing";
        var rem;
        if (playing) {
          var elapsed = (new Date() - new Date(lu)) / 1000;
          var livePos = pos + (elapsed > 0 ? elapsed : 0);
          if (livePos > dur) livePos = dur;
          rem = Math.max(0, dur - livePos);
        } else { rem = Math.max(0, dur - pos); }
        stxt = "−" + fmtime(rem);
        slbl = playing ? "Playing" : "Paused";
        dColor = playing ? "#4caf50" : "#ff9800";
        dAnim = playing ? "animation:jsc-pulse 1.5s ease-in-out infinite" : "";
      }

      this.innerHTML = [
        '<div style="', cardBg, '">',
          '<div style="', coverStyle, '">',
            cover
              ? '<img src="' + esc(cover) + '" alt="" style="' + imgStyle + '" onerror="var p=this.parentElement;if(p)p.innerHTML=\'<div style=\'' + placeholderStyle + '\'><ha-icon icon=mdi:movie-open></ha-icon></div>\'" />'
              : '<div style="' + placeholderStyle + '"><ha-icon icon="mdi:movie-open"></ha-icon></div>',
          '</div>',
          '<div style="', infoPad, '">',
            '<div style="', titleStyle, '" title="', esc(title||""), '">', esc(title||"Unknown"), '</div>',
            sub ? '<div style="' + subStyle + '">' + esc(sub) + '</div>' : '',
            '<div style="', rowStyle, '">',
              '<span style="', dotStyle(dColor, dAnim), '"></span>',
              '<span>', esc(stxt), ' · ', esc(slbl), '</span>',
            '</div>',
          '</div>',
        '</div>'
      ].join("");
    } catch (e) {
      this.innerHTML = '<div style="' + cardBg + ';' + configErrorStyle() + '">Card error: ' + esc(e.message||String(e)) + '</div>';
    }
  }

  try {
    var proto = Object.create(HTMLElement.prototype);
    var cls = function () { this._hass = null; this._config = null; this._attrs = {}; this._playState = "idle"; this._lastUpdated = ""; };
    cls.prototype = proto;
    cls.prototype.constructor = cls;

    Object.defineProperty(proto, "hass", { set: function (v) { if (!v) return; this._hass = v; this._refresh(); } });

    proto.setConfig = function (cfg) { this._config = { entity: cfg.entity || cfg.entity_id || null }; this._refresh(); };
    proto.getCardSize = function () { return 5; };
    cls.getStubConfig = function () { return { entity: "sensor.jellyfin_status_chrome" }; };

    proto._refresh = function () {
      if (!this._config || !this._hass) { this.innerHTML = ""; return; }
      var eid = this._config.entity || findEntity(this._hass);
      if (!eid) { this.innerHTML = '<div style="' + cardBg + ';' + configErrorStyle() + '">No Jellyfin Status entity found.</div>'; return; }
      var so = this._hass.states[eid];
      if (!so) { this.innerHTML = '<div style="' + cardBg + ';padding:14px;' + textSec + ';font-size:0.95rem">Waiting for entity: ' + esc(eid) + '</div>'; return; }
      this._attrs = so.attributes || {};
      this._playState = this._attrs.play_state || "idle";
      this._lastUpdated = so.last_updated || "";
      renderCard.call(this);
    };

    customElements.define("jellyfin-status-card", cls);
    console.log("jellyfin-status-card: registered");
  } catch (e) {
    console.error("jellyfin-status-card: define failed", e);
  }

  try {
    window.customCards = window.customCards || [];
    window.customCards.push({ type: "jellyfin-status-card", name: "Jellyfin Status Card", description: "Displays currently playing media from Jellyfin with cover art, title, and remaining time.", preview: false });
  } catch (e) {}
})();
