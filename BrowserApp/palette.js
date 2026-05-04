(function () {
  "use strict";

  // Default Woodland palette - only palette used.
  // Selection, custom, and multi-palette logic removed.

  function clamp(v, mn, mx) { return Math.max(mn, Math.min(mx, v)); }
  function hexToRgb(hex) {
    var h = String(hex || "").trim().toLowerCase();
    if (h[0] !== "#") h = "#" + h;
    if (/^#[0-9a-f]{3}$/.test(h)) h = "#" + h[1] + h[1] + h[2] + h[2] + h[3] + h[3];
    return { r: parseInt(h.slice(1, 3), 16), g: parseInt(h.slice(3, 5), 16), b: parseInt(h.slice(5, 7), 16) };
  }
  function rgbToHex(c) {
    function p(v) { return clamp(Math.round(v), 0, 255).toString(16).padStart(2, "0"); }
    return "#" + p(c.r) + p(c.g) + p(c.b);
  }
  function mix(a, b, r) {
    var x = clamp(Number(r || 0), 0, 1), ra = hexToRgb(a), rb = hexToRgb(b);
    return rgbToHex({ r: ra.r * (1 - x) + rb.r * x, g: ra.g * (1 - x) + rb.g * x, b: ra.b * (1 - x) + rb.b * x });
  }
  function rgba(hex, a) { var c = hexToRgb(hex); return "rgba(" + c.r + "," + c.g + "," + c.b + "," + clamp(a, 0, 1) + ")"; }

  var ACCENT = "#1f8a4c", BGA = "#f3fbf6", BGB = "#def0e6";
  var lightBg = mix(BGA, BGB, 0.5);
  var darkBgA = mix(BGA, "#000000", 0.78), darkBgB = mix(BGB, "#000000", 0.86);
  var darkBg = mix(darkBgA, darkBgB, 0.55);
  var darkPanel = mix(darkBg, ACCENT, 0.16);
  var darkPanelSoft = mix(darkPanel, "#000000", 0.12);
  var darkAccent = mix(ACCENT, "#ffffff", 0.2);

  var LIGHT = {
    "--bg": lightBg, "--panel": "#ffffff", "--panel-soft": mix("#ffffff", lightBg, 0.25),
    "--card": rgba("#ffffff", 0.92), "--text": "#1a2530", "--muted": mix("#1a2530", lightBg, 0.52),
    "--accent": ACCENT, "--accent-dark": mix(ACCENT, "#000000", 0.2),
    "--line": rgba("#1a2530", 0.16), "--bg-a": BGA, "--bg-b": BGB
  };
  var DARK = {
    "--bg": darkBg, "--panel": darkPanel, "--panel-soft": darkPanelSoft,
    "--card": rgba(darkPanel, 0.9), "--text": "#e8eef5", "--muted": "#9fb1c3",
    "--accent": darkAccent, "--accent-dark": mix(darkAccent, "#000000", 0.2),
    "--line": rgba("#e8eef5", 0.2), "--bg-a": darkBgA, "--bg-b": darkBgB
  };

  function applyPalette() {
    var isDark = document.documentElement.getAttribute("data-theme") === "dark";
    var vars = isDark ? DARK : LIGHT;
    var root = document.documentElement;
    Object.keys(vars).forEach(function (k) { root.style.setProperty(k, vars[k]); });
    root.style.setProperty("--surface", vars["--panel"]);
    root.style.setProperty("--border", vars["--line"]);
    root.style.setProperty("--success", vars["--accent"]);
    root.style.setProperty("--success-dark", vars["--accent-dark"]);
  }

  applyPalette();
  new MutationObserver(applyPalette).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  function ensureQuickNavStyles() {
    if (document.getElementById("rsQuickNavStyles")) return;
    var st = document.createElement("style");
    st.id = "rsQuickNavStyles";
    st.textContent = ""
      + ".rs-quick-link{border:none;border-radius:9px;padding:9px 14px;font:inherit;font-weight:700;cursor:pointer;"
      + "text-decoration:none;display:inline-flex;align-items:center;gap:6px;line-height:1;"
      + "background:var(--panel-soft,#f5f9ff);border:1px solid var(--line,rgba(14,44,29,.15));color:var(--text,#0e2c1d);}"
      + ".rs-quick-link:hover{opacity:.85;}"
      + ".rs-quick-float{position:fixed;top:12px;right:12px;z-index:9999;display:flex;gap:8px;}"
      + ".rs-quick-float .rs-quick-link{box-shadow:0 6px 18px rgba(0,0,0,.12);}";
    document.head.appendChild(st);
  }

  function makeQuickLink(href, title, text, id) {
    var a = document.createElement("a");
    a.id = id;
    a.href = href;
    a.className = "rs-quick-link";
    a.title = title;
    a.textContent = text;
    return a;
  }

  function addQuickNavButtons() {
    if (!document.body || document.body.getAttribute("data-rs-quick-nav") === "1") return;
    var path = (window.location.pathname || "").toLowerCase();

    var hasNotifShortcut = !!document.querySelector('#rsQuickNotifBtn, a[href*="notifications.html"], .notif-bell, #notifBellBtn');
    var hasAccountShortcut = !!document.querySelector('#rsQuickAccountBtn, a[href*="account.html"], #accountBtn');

    var wantNotif = !hasNotifShortcut && path.indexOf("notifications.html") === -1;
    var wantAccount = !hasAccountShortcut && path.indexOf("account.html") === -1;
    if (!wantNotif && !wantAccount) {
      document.body.setAttribute("data-rs-quick-nav", "1");
      return;
    }

    ensureQuickNavStyles();

    var darkBtn = document.getElementById("darkModeToggle");
    var host = darkBtn && darkBtn.parentElement ? darkBtn.parentElement : null;

    if (host) {
      if (wantNotif) host.appendChild(makeQuickLink("./notifications.html", "Notifications", "🔔", "rsQuickNotifBtn"));
      if (wantAccount) host.appendChild(makeQuickLink("./account.html", "Account settings", "👤", "rsQuickAccountBtn"));
    } else {
      var wrap = document.createElement("div");
      wrap.className = "rs-quick-float";
      if (wantNotif) wrap.appendChild(makeQuickLink("./notifications.html", "Notifications", "🔔", "rsQuickNotifBtn"));
      if (wantAccount) wrap.appendChild(makeQuickLink("./account.html", "Account settings", "👤", "rsQuickAccountBtn"));
      if (wrap.children.length) document.body.appendChild(wrap);
    }

    document.body.setAttribute("data-rs-quick-nav", "1");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addQuickNavButtons, { once: true });
  } else {
    addQuickNavButtons();
  }

  window.RSPalette = { get: function () { return "woodland"; }, apply: applyPalette, reapply: applyPalette };
})();
