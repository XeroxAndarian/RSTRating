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
    "--line": rgba("#1a2530", 0.16), "--bg-a": BGA, "--bg-b": BGB,
    "--danger": "#b42318"
  };
  var DARK = {
    "--bg": darkBg, "--panel": darkPanel, "--panel-soft": darkPanelSoft,
    "--card": rgba(darkPanel, 0.9), "--text": "#e8eef5", "--muted": "#9fb1c3",
    "--accent": darkAccent, "--accent-dark": mix(darkAccent, "#000000", 0.2),
    "--line": rgba("#e8eef5", 0.2), "--bg-a": darkBgA, "--bg-b": darkBgB,
    "--danger": "#b42318"
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
      + ".rs-notif-badge{position:absolute;top:-6px;right:-6px;min-width:18px;height:18px;padding:0 5px;border-radius:999px;background:var(--danger,#b42318);color:#fff;font-size:.7rem;display:none;align-items:center;justify-content:center;}"
      + ".notif-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:80;}"
      + ".notif-drawer{position:fixed;top:0;right:0;width:min(400px,100vw);height:100vh;background:var(--panel-strong,var(--panel,#fff));border-left:1px solid var(--border,var(--line,rgba(0,0,0,.15)));display:flex;flex-direction:column;z-index:90;transform:translateX(100%);transition:transform .25s ease;overflow:hidden;}"
      + ".notif-drawer.open{transform:translateX(0);}"
      + ".notif-drawer-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border,var(--line,rgba(0,0,0,.15)));}"
      + ".notif-drawer-header h3{margin:0;font-size:1.05rem;}"
      + ".notif-drawer-actions{padding:10px 20px;border-bottom:1px solid var(--border,var(--line,rgba(0,0,0,.15)));}"
      + ".notif-list{flex:1;overflow-y:auto;padding:12px;}"
      + ".notif-item{padding:12px;border-radius:8px;margin-bottom:8px;background:var(--bg);border:1px solid var(--border,var(--line,rgba(0,0,0,.15)));cursor:pointer;transition:background .12s;}"
      + ".notif-item:hover{background:var(--card);}"
      + ".notif-item.unread{border-left:3px solid var(--accent);}"
      + ".notif-item-title{font-weight:600;font-size:.9rem;margin-bottom:3px;}"
      + ".notif-item-msg{font-size:.82rem;color:var(--muted,#666);}"
      + ".notif-item-time{font-size:.75rem;color:var(--muted,#666);margin-top:4px;}"
      + ".icon-button{background:transparent;border:none;cursor:pointer;color:var(--muted,#666);font-size:1rem;padding:6px;border-radius:6px;transition:background .12s,color .12s;}"
      + ".icon-button:hover{background:var(--bg);color:var(--text,#0e2c1d);}"
      + ".notif-tab-bar{display:flex;gap:8px;padding:10px 20px;border-bottom:1px solid var(--border,var(--line,rgba(0,0,0,.15)));background:var(--panel-strong,var(--panel-soft,#f5f9ff));}"
      + ".notif-tab-btn{appearance:none;border:1px solid var(--line,rgba(0,0,0,.15));border-radius:999px;padding:5px 16px;background:var(--card,var(--panel,#fff));color:var(--muted,#666);font:inherit;font-size:.85rem;font-weight:700;cursor:pointer;transition:background .12s,color .12s;}"
      + ".notif-tab-btn.active{background:var(--accent,#1f8a4c);color:#fff;border-color:transparent;}";
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
    if (document.getElementById("notifDrawer")) return;
    var activeNotifTab = "unread";
    var notifications = [];

    var backdrop = document.createElement("div");
    backdrop.id = "notifBackdrop";
    backdrop.className = "notif-backdrop";
    backdrop.style.display = "none";
    var drawer = document.createElement("aside");
    drawer.id = "notifDrawer";
    drawer.className = "notif-drawer";
    drawer.innerHTML = ""
      + '<div class="notif-drawer-header"><h3>Notifications</h3><button class="icon-button" id="closeNotifButton" type="button" aria-label="Close">✕</button></div>'
      + '<div class="notif-tab-bar">'
      + '<button class="notif-tab-btn active" id="notifTabUnread" type="button">Unread</button>'
      + '<button class="notif-tab-btn" id="notifTabRead" type="button">Read</button>'
      + '<button class="notif-tab-btn" id="notifTabHistory" type="button">See All</button>'
      + '</div>'
      + '<div class="notif-drawer-actions"><button class="ghost" id="markAllReadButton" type="button" style="font-size:0.85rem;padding:6px 12px;">Mark all as read</button></div>'
      + '<div class="notif-list" id="notifList"></div>';
    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);

    function closeDrawer() {
      drawer.classList.remove("open");
      backdrop.style.display = "none";
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
      if (d.league_id) return "./league.html?id=" + d.league_id;
      if (d.from_user_id) return "./player.html?id=" + d.from_user_id;
      return "";
    }

    function formatRelativeTime(isoStr) {
      if (!isoStr) return "";
      var d = new Date(isoStr);
      if (Number.isNaN(d.getTime())) return String(isoStr);
      var diff = Math.floor((Date.now() - d.getTime()) / 1000);
      if (diff < 60) return "Just now";
      if (diff < 3600) return Math.floor(diff / 60) + "m ago";
      if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
      return d.toLocaleDateString();
    }

    function notifEmoji(type, data) {
      if (type === "fan_player_match_event" && data && data.event_type) {
        var eventType = String(data.event_type);
        if (eventType === "goal") return "⚽";
        if (eventType === "assist") return "🅰️";
        if (eventType === "own_goal") return "🥅";
        if (eventType === "yellow_card") return "🟨";
        if (eventType === "red_card") return "🟥";
        if (eventType === "offside") return "🚩";
        if (eventType === "corner") return "🏳️";
        if (eventType === "foul") return "🤚";
        if (eventType === "injury") return "🚑";
        return "📋";
      }
      if (["new_match", "match_started", "fan_player_started_match"].indexOf(type) >= 0) return "⚽";
      if (type === "match_result") return "🏁";
      if (type === "match_cancelled") return "❌";
      if (type === "waitlist_offer") return "📨";
      if (type === "friend_request") return "👋";
      if (type === "friend_request_accepted") return "🤝";
      if (type === "league_approved") return "✅";
      if (type === "league_rejected") return "❌";
      if (type === "league_announcement") return "📢";
      if (["fan_event", "fan_player_registered"].indexOf(type) >= 0) return "⭐";
      return "🔔";
    }

    function setNotifTab(tab) {
      if (tab === "history") {
        try { sessionStorage.setItem("rs_notifications_allowed", "1"); } catch (_) {}
        window.location.href = "./notifications.html?from=drawer";
        return;
      }
      activeNotifTab = tab;
      var tabUnread = drawer.querySelector("#notifTabUnread");
      var tabRead = drawer.querySelector("#notifTabRead");
      var tabHistory = drawer.querySelector("#notifTabHistory");
      if (tabUnread) tabUnread.classList.toggle("active", tab === "unread");
      if (tabRead) tabRead.classList.toggle("active", tab === "read");
      if (tabHistory) tabHistory.classList.remove("active");
      renderNotifList();
    }

    function renderNotifList() {
      var list = drawer.querySelector("#notifList");
      if (!list) return;
      var filtered = notifications.filter(function (n) { return activeNotifTab === "unread" ? !n.read : !!n.read; });
      if (!filtered.length) {
        var msg = notifications.length === 0
          ? "No notifications yet."
          : (activeNotifTab === "unread" ? "No unread notifications." : "No read notifications.");
        list.innerHTML = '<p class="hint" style="padding:16px;">' + msg + '</p>';
        return;
      }
      list.innerHTML = filtered.map(function (n) {
        var d = n && n.data ? n.data : {};
        var link = notifLink(n);
        var emoji = notifEmoji(n.notif_type, n.data || {});
        return '<div class="notif-item ' + (n.read ? '' : 'unread') + '" data-notif-id="' + n.id + '" data-match-id="' + (d.match_id ? d.match_id : '') + '" data-link="' + link + '">'
          + '<div class="notif-item-title">' + emoji + ' ' + String(n.title || "Notification") + '</div>'
          + '<div class="notif-item-msg">' + String(n.message || "") + '</div>'
          + '<div class="notif-item-time">' + formatRelativeTime(n.created_at) + '</div>'
          + '</div>';
      }).join("");
    }

    async function renderNotifications() {
      try {
        var rows = await apiFetch("/notifications", { method: "GET" });
        notifications = Array.isArray(rows) ? rows : [];
        var unread = notifications.filter(function (n) { return !n.read; }).length;
        updateBadgeCount(unread);
        renderNotifList();
      } catch (_) {
        var list = drawer.querySelector("#notifList");
        if (list) list.innerHTML = '<p class="hint" style="padding:16px;">Unable to load notifications.</p>';
      }
    }

    async function markAllRead() {
      try {
        await apiFetch("/notifications/read-all", { method: "PATCH" });
        notifications = notifications.map(function (n) {
          var c = Object.assign({}, n);
          c.read = true;
          return c;
        });
        renderNotifList();
        updateBadgeCount(0);
      } catch (_) {}
    }

    function openDrawer() {
      var unread = notifications.filter(function (n) { return !n.read; }).length;
      setNotifTab(unread > 0 ? "unread" : "read");
      drawer.classList.add("open");
      backdrop.style.display = "block";
      renderNotifications();
    }

    backdrop.addEventListener("click", closeDrawer);
    drawer.querySelector("#closeNotifButton").addEventListener("click", closeDrawer);
    drawer.querySelector("#notifTabUnread").addEventListener("click", function () { setNotifTab("unread"); });
    drawer.querySelector("#notifTabRead").addEventListener("click", function () { setNotifTab("read"); });
    drawer.querySelector("#notifTabHistory").addEventListener("click", function () { setNotifTab("history"); });
    drawer.querySelector("#markAllReadButton").addEventListener("click", markAllRead);
    drawer.querySelector("#notifList").addEventListener("click", async function (ev) {
      var item = ev.target.closest(".notif-item");
      if (!item) return;
      var id = Number(item.getAttribute("data-notif-id") || 0);
      var matchId = Number(item.getAttribute("data-match-id") || 0);
      var link = item.getAttribute("data-link") || "";
      try {
        if (item.classList.contains("unread") && id) {
          await apiFetch("/notifications/" + id + "/read", { method: "PATCH" });
          item.classList.remove("unread");
          notifications.forEach(function (n) { if (Number(n.id) === id) n.read = true; });
          updateBadgeCount(notifications.filter(function (n) { return !n.read; }).length);
        }
      } catch (_) {}
      if (link) {
        window.location.href = link;
      } else if (matchId) {
        window.location.href = "./match.html?id=" + matchId;
      }
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
    var existingBell = document.querySelector("#notifBellButton, #notifBellBtn");
    if (existingBell && typeof existingBell.click === "function") {
      existingBell.click();
      return;
    }
    ensureFallbackNotifDrawer();
    var drawer = document.getElementById("notifDrawer");
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
    if (topNotifBtn && !topNotifBtn.getAttribute("data-rs-notif-bound-palette")) {
      topNotifBtn.setAttribute("data-rs-notif-bound-palette", "1");
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

    // Never inject admin into the generic top menu.
    document.querySelectorAll('a[href*="admin.html"], #rsTopAdminBtn').forEach(function (a) {
      a.style.display = "none";
    });

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

    // Bind any existing native #logoutButton instances that don't have handlers yet
    document.querySelectorAll("#logoutButton").forEach(function (nativeLogout) {
      if (!nativeLogout.getAttribute("data-rs-logout-bound")) {
        nativeLogout.setAttribute("data-rs-logout-bound", "1");
        nativeLogout.addEventListener("click", function () {
          localStorage.removeItem(TOKEN_KEY);
          window.location.href = "./index.html";
        });
      }
    });

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
    ensureFallbackNotifDrawer(); // ensure sidebar is in DOM on every non-lobby page
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

  window.RSPalette = {
    get: function () { return "woodland"; },
    apply: function () { applyPalette(); applyLobbyBackground(); syncDarkButtons(); },
    reapply: function () { applyPalette(); applyLobbyBackground(); syncDarkButtons(); },
    openNotifMenu: openUniversalNotifMenu
  };
})();
