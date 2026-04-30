/**
 * toast.js — shared floating toast notifications
 * Usage: showToast("Message", "ok"|"error"|"info", durationMs?)
 * Include this script in any HTML page and call window.showToast()
 */
(function () {
  "use strict";

  var container = null;

  function ensureContainer() {
    if (container && document.body.contains(container)) return;
    container = document.createElement("div");
    container.id = "rs-toast-container";
    Object.assign(container.style, {
      position: "fixed",
      bottom: "24px",
      right: "24px",
      zIndex: "9999",
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-end",
      gap: "8px",
      pointerEvents: "none",
    });
    document.body.appendChild(container);
  }

  /**
   * @param {string} message
   * @param {"ok"|"error"|"info"} [kind="info"]
   * @param {number} [duration=3500]
   */
  window.showToast = function (message, kind, duration) {
    if (!document.body) { return; }
    ensureContainer();
    kind = kind || "info";
    duration = typeof duration === "number" ? duration : 3500;

    var isDark = document.documentElement.getAttribute("data-theme") === "dark";
    var bg = kind === "ok" ? "#1f8a4c"
            : kind === "error" ? "#b42318"
            : (isDark ? "#1b2d27" : "#fff");
    var textColor = (kind === "ok" || kind === "error") ? "#fff"
                  : (isDark ? "#e7f5ee" : "#0e2c1d");
    var icon = kind === "ok" ? "✓" : kind === "error" ? "✕" : "ℹ";

    var toast = document.createElement("div");
    Object.assign(toast.style, {
      background: bg,
      color: textColor,
      border: "1px solid " + (kind === "ok" ? "rgba(255,255,255,.25)" : kind === "error" ? "rgba(255,255,255,.25)" : "rgba(14,44,29,.15)"),
      borderRadius: "10px",
      padding: "10px 16px",
      fontSize: ".9rem",
      fontFamily: '"Roboto","Segoe UI",sans-serif',
      fontWeight: "600",
      boxShadow: "0 4px 16px rgba(0,0,0,.18)",
      maxWidth: "340px",
      pointerEvents: "auto",
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      gap: "8px",
      opacity: "0",
      transform: "translateY(10px)",
      transition: "opacity .2s, transform .2s",
    });

    var iconSpan = document.createElement("span");
    iconSpan.textContent = icon;
    iconSpan.style.flexShrink = "0";

    var textSpan = document.createElement("span");
    textSpan.textContent = String(message || "");

    toast.appendChild(iconSpan);
    toast.appendChild(textSpan);
    container.appendChild(toast);

    // Animate in
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        toast.style.opacity = "1";
        toast.style.transform = "translateY(0)";
      });
    });

    function dismiss() {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 250);
    }

    toast.addEventListener("click", dismiss);
    setTimeout(dismiss, duration);
  };
})();
