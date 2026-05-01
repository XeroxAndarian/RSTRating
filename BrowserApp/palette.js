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

  window.RSPalette = { get: function () { return "woodland"; }, apply: applyPalette, reapply: applyPalette };
})();
