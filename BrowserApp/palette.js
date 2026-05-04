(function () {
  "use strict";

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
  function rgba(hex, a) {
    var c = hexToRgb(hex);
    return "rgba(" + c.r + "," + c.g + "," + c.b + "," + clamp(a, 0, 1) + ")";
  }

  var TOKEN_KEY = "rs_access_token";
  var API_BASE_KEY = "rs_api_base_override";
  var DEFAULT_API_BASE = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://127.0.0.1:8000"
    : "https://rstrating-accounts-api.onrender.com";

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

  function getApiBase() {
    return (localStorage.getItem(API_BASE_KEY) || DEFAULT_API_BASE).trim();
  }

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

  function applyLobbyBackground() {
    if (!document.body) return;
    document.body.style.background = "radial-gradient(circle at 0% 0%, rgba(31, 138, 76, 0.18), transparent 24%), radial-gradient(circle at 100% 20%, rgba(34, 197, 94, 0.14), transparent 22%), linear-gradient(135deg, var(--panel) 0%, var(--bg) 45%, var(--bg) 100%)";
    document.body.style.minHeight = "100vh";
  }

  function toggleTheme() {
    var dark = document.documentElement.getAttribute("data-theme") === "dark";
    if (dark) {
      document.documentElement.removeAttribute("data-theme");
      localStorage.setItem("rs_theme", "light");
    } else {
      document.documentElement.setAttribute("data-theme", "dark");
      localStorage.setItem("rs_theme", "dark");
    }
    applyPalette();
    syncDarkButtons();
  }

  function syncDarkButtons() {
    var isDark = document.documentElement.getAttribute("data-theme") === "dark";
    document.querySelectorAll("#darkModeToggle, #rsTopDarkBtn").forEach(function (b) {
      b.textContent = isDark ? "☀️" : "🌙";
    });
  }

  function ensureStyles() {
    if (document.getElementById("rsQuickNavStyles")) return;
    var st = document.createElement("style");
    st.id = "rsQuickNavStyles";
    st.textContent = ""
      + ".rs-top-controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;justify-content:flex-end;}"
      + ".rs-quick-link{border:none;border-radius:9px;padding:9px 14px;font:inherit;font-weight:700;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:6px;line-height:1;background:var(--panel-soft,#f5f9ff);border:1px solid var(--line,rgba(14,44,29,.15));color:var(--text,#0e2c1d);}"
      + ".rs-quick-link:hover{opacity:.9;}"
      + ".rs-quick-danger{background:var(--danger,#b42318);border-color:transparent;color:#fff;}"
      + ".rs-notif-bell{position:relative;}"
      + ".rs-notif-badge{position:absolute;top:-6px;right:-6px;min-width:18px;height:18px;padding:0 5px;border-radius:999px;background:var(--danger,#b42318);color:#fff;font-size:.7rem;display:none;align-items:center;justify-content:center;}
"
      + ".rs-notif-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;z-index:9998;}"
      + ".rs-notif-backdrop.open{display:block;}"
      + ".rs-notif-drawer{position:fixed;top:0;right:0;height:100%;width:min(420px,92vw);transform:translateX(100%);transition:transform .18s ease;z-index:9999;background:var(--panel,#fff);border-left:1px solid var(--line,rgba(0,0,0,.15));display:flex;flex-direction:column;}"
      + ".rs-notif-drawer.open{transform:translateX(0);}"
      + ".rs-notif-head{display:flex;justify-content:space-between;align-items:center;padding:14px;border-bottom:1px solid var(--line,rgba(0,0,0,.15));}"
      + ".rs-notif-list{flex:1;overflow-y:auto;padding:10px 14px;display:flex;flex-direction:column;gap:8px;}"
      + ".rs-notif-item{border:1px solid var(--line,rgba(0,0,0,.15));border-radius:10px;padding:9px 10px;background:var(--panel-soft,#f5f9ff);cursor:pointer;}"
      + ".rs-notif-item.unread{background:rgba(31,138,76,.1);border-color:rgba(31,138,76,.35);}"
      + ".rs-notif-item-title{font-weight:700;font-size:.9rem;}"
      + ".rs-notif-item-msg{font-size:.82rem;color:var(--muted,#666);margin-top:2px;}"
      + ".rs-notif-actions{padding:14px;border-top:1px solid var(--line,rgba(0,0,0,.15));display:flex;justify-content:space-between;align-items:center;gap:8px;}";
    document.head.appendChild(st);
  }

  function makeBtn(id, title, text, isDanger) {
    var b = document.createElement("button");
    b.id = id;
    b.type = "button";
    b.className = "rs-quick-link" + (isDanger ? " rs-quick-danger" : "");
    b.title = title;
    b.setAttribute("aria-label", title);
    b.textContent = text;
    return b;
  }

  function makeLink(id, title, text, href) {
    var a = document.createElement("a");
    a.id = id;
    a.className = "rs-quick-link";
    a.href = href;
    a.title = title;
    a.textContent = text;
    return a;
  }

  function ensureFallbackNotifDrawer() {
    if (document.getElementById("rsNotifDrawer")) return;
    var backdrop = document.createElement("div");
    backdrop.id = "rsNotifBackdrop";
    backdrop.className = "rs-notif-backdrop";
    var drawer = document.createElement("aside");
    drawer.id = "rsNotifDrawer";
    drawer.className = "rs-notif-drawer";
    drawer.innerHTML = ""
      + '<div class="rs-notif-head"><strong>Notifications</strong><button class="rs-quick-link" id="rsNotifClose" type="button" style="padding:6px 10px;">✕</button></div>'
      + '<div class="rs-notif-list" id="rsNotifList"><div class="rs-notif-item">Loading...</div></div>'
      + '<div class="rs-notif-actions"><button class="rs-quick-link" id="rsNotifMarkAll" type="button">Mark all read</button><a class="rs-quick-link" id="rsNotifShowAll" href="./notifications.html?from=drawer">Show all</a></div>';
    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);

    function closeDrawer() {
      backdrop.classList.remove("open");
      drawer.classList.remove("open");
    }

    async function apiFetch(path, opts) {
      var headers = Object.assign({}, (opts && opts.headers) || {});
      var token = localStorage.getItem(TOKEN_KEY) || "";
      if (token) headers.Authorization = "Bearer " + token;
      var res = await fetch(getApiBase() + path, Object.assign({}, opts || {}, { headers: headers }));
      var body = null;
      try { body = await res.json(); } catch (_) {}
      if (!res.ok) throw new Error((body && body.detail) || "Request failed");
      return body;
    }

    function notifLink(n) {
      var d = n && n.data ? n.data : {};
      if (d.match_id) return "./match.html?id=" + d.match_id;
      if (d.league_id) return "./league.html?id=" + d.league_id;
      if (d.from_user_id) return "./player.html?id=" + d.from_user_id;
      return "";
    }

    async function renderNotifications() {
      var list = drawer.querySelector("#rsNotifList");
      if (!list) return;
      try {
        var rows = await apiFetch("/notifications", { method: "GET" });
        var notifs = Array.isArray(rows) ? rows : [];
        if (!notifs.length) {
          list.innerHTML = '<div class="rs-notif-item">No notifications.</div>';
          updateBadgeCount(0);
          return;
        }
        var unread = notifs.filter(function (n) { return !n.read; }).length;
        updateBadgeCount(unread);
        list.innerHTML = notifs.slice(0, 20).map(function (n) {
          var link = notifLink(n);
          return '<div class="rs-notif-item ' + (n.read ? '' : 'unread') + '" data-id="' + n.id + '" data-link="' + link + '">'
            + '<div class="rs-notif-item-title">' + String(n.title || "Notification") + '</div>'
            + '<div class="rs-notif-item-msg">' + String(n.message || "") + '</div>'
            + '</div>';
        }).join("");
      } catch (_) {
        list.innerHTML = '<div class="rs-notif-item">Unable to load notifications.</div>';
      }
    }

    async function markAllRead() {
      try {
        await apiFetch("/notifications/read-all", { method: "PATCH" });
        await renderNotifications();
      } catch (_) {}
    }

    function openDrawer() {
      backdrop.classList.add("open");
      drawer.classList.add("open");
      renderNotifications();
    }

    backdrop.addEventListener("click", closeDrawer);
    drawer.querySelector("#rsNotifClose").addEventListener("click", closeDrawer);
    drawer.querySelector("#rsNotifShowAll").addEventListener("click", function () {
      try { sessionStorage.setItem("rs_notifications_allowed", "1"); } catch (_) {}
    });
    drawer.querySelector("#rsNotifMarkAll").addEventListener("click", markAllRead);
    drawer.querySelector("#rsNotifList").addEventListener("click", async function (ev) {
      var item = ev.target.closest(".rs-notif-item[data-id]");
      if (!item) return;
      var id = Number(item.getAttribute("data-id") || 0);
      var link = item.getAttribute("data-link") || "";
      try { await apiFetch("/notifications/" + id + "/read", { method: "PATCH" }); } catch (_) {}
      if (link) window.location.href = link;
    });
    drawer._open = openDrawer;
  }

  function updateBadgeCount(count) {
    var n = Number(count || 0);
    document.querySelectorAll("#rsTopNotifBadge").forEach(function (b) {
      b.textContent = String(n);
      b.style.display = n > 0 ? "inline-flex" : "none";
    });
  }

  function openUniversalNotifMenu() {
    var existingBell = document.querySelector("#notifBellButton, #notifBellBtn, .notif-bell");
    if (existingBell && typeof existingBell.click === "function") {
      existingBell.click();
      return;
    }
    ensureFallbackNotifDrawer();
    var drawer = document.getElementById("rsNotifDrawer");
    if (drawer && typeof drawer._open === "function") drawer._open();
  }

  function ensureUniversalTopControls() {
    if (!document.body || document.body.getAttribute("data-rs-universal-controls") === "1") return;
    ensureStyles();

    var darkBtn = document.getElementById("darkModeToggle");
    var host = darkBtn && darkBtn.parentElement ? darkBtn.parentElement : null;
    if (!host) {
      host = document.createElement("div");
      host.className = "rs-top-controls";
      host.style.position = "fixed";
      host.style.top = "12px";
      host.style.right = "12px";
      host.style.zIndex = "9999";
      document.body.appendChild(host);
    }
    if (!host.classList.contains("rs-top-controls")) host.classList.add("rs-top-controls");

    if (!document.getElementById("refreshLobbyBtn") && !document.getElementById("rsTopRefreshBtn")) {
      var refreshBtn = makeBtn("rsTopRefreshBtn", "Refresh", "↺", false);
      refreshBtn.addEventListener("click", function () { window.location.reload(); });
      host.appendChild(refreshBtn);
    }

    if (!document.querySelector("#notifBellButton, #notifBellBtn, .notif-bell, #rsQuickNotifBtn, #topNotifLink")) {
      var notifBtn = makeBtn("rsQuickNotifBtn", "Notifications", "🔔", false);
      notifBtn.classList.add("rs-notif-bell");
      var badge = document.createElement("span");
      badge.id = "rsTopNotifBadge";
      badge.className = "rs-notif-badge";
      badge.textContent = "0";
      notifBtn.appendChild(badge);
      notifBtn.addEventListener("click", function (ev) {
        ev.preventDefault();
        openUniversalNotifMenu();
      });
      host.appendChild(notifBtn);
    }

    var topNotifBtn = document.getElementById("topNotifLink");
    if (topNotifBtn && !topNotifBtn.getAttribute("data-rs-notif-bound")) {
      topNotifBtn.setAttribute("data-rs-notif-bound", "1");
      topNotifBtn.addEventListener("click", function (ev) {
        ev.preventDefault();
        openUniversalNotifMenu();
      });
    }

    if (!document.getElementById("darkModeToggle") && !document.getElementById("rsTopDarkBtn")) {
      var dBtn = makeBtn("rsTopDarkBtn", "Toggle dark mode", "🌙", false);
      dBtn.addEventListener("click", toggleTheme);
      host.appendChild(dBtn);
    }

    if (!document.querySelector('a[href*="player.html"], #rsTopPlayerBtn')) {
      host.appendChild(makeLink("rsTopPlayerBtn", "My player page", "👤", "./player.html"));
    }

    if (!document.querySelector('a[href*="admin.html"], #rsTopAdminBtn')) {
      host.appendChild(makeLink("rsTopAdminBtn", "Admin console", "🛡", "./admin.html"));
    }

    if (!document.querySelector('a[href*="account.html"], #rsTopAccountBtn')) {
      host.appendChild(makeLink("rsTopAccountBtn", "Account settings", "⚙", "./account.html"));
    }

    if (!document.querySelector('#logoutButton, #rsTopLogoutBtn')) {
      var logoutBtn = makeBtn("rsTopLogoutBtn", "Sign out", "🚪", true);
      logoutBtn.addEventListener("click", function () {
        localStorage.removeItem(TOKEN_KEY);
        window.location.href = "./index.html";
      });
      host.appendChild(logoutBtn);
    }

    document.body.setAttribute("data-rs-universal-controls", "1");
    syncDarkButtons();
  }

  if (localStorage.getItem("rs_theme") !== "light") {
    document.documentElement.setAttribute("data-theme", "dark");
  }

  applyPalette();
  new MutationObserver(applyPalette).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  function boot() {
    applyPalette();
    applyLobbyBackground();
    ensureUniversalTopControls();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

  window.RSPalette = {
    get: function () { return "woodland"; },
    apply: function () { applyPalette(); applyLobbyBackground(); syncDarkButtons(); },
    reapply: function () { applyPalette(); applyLobbyBackground(); syncDarkButtons(); }
  };
})();
