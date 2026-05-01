(function () {
  "use strict";

  var STORAGE_KEY = "rs_palette";
  var CUSTOM_STORAGE_KEY = "rs_custom_palette_v1";
  var DEFAULT_PALETTE = "woodland";

  var LEGACY_KEYS = {
    forest: "woodland",
    ocean: "reef",
    sunset: "canyon",
    graphite: "tundra"
  };

  // Compact 3-colour seeds — everything else is derived by buildPalette()
  var SEEDS = {
    woodland: { name: "Woodland", accent: "#1f8a4c", bgA: "#f3fbf6", bgB: "#def0e6" },
    reef:     { name: "Reef",     accent: "#0f7ea8", bgA: "#f2fbff", bgB: "#d8eef7" },
    canyon:   { name: "Canyon",   accent: "#d06b2c", bgA: "#fff8f3", bgB: "#ffe7d6" },
    tundra:   { name: "Tundra",   accent: "#4a5f91", bgA: "#f4f5f8", bgB: "#dde1e8" },
    desert:   { name: "Desert",   accent: "#c8873f", bgA: "#fff8ed", bgB: "#f1dfc6" },
    glacier:  { name: "Glacier",  accent: "#2d9cc7", bgA: "#f4fcff", bgB: "#d7ecf6" },
    savanna:  { name: "Savanna",  accent: "#889f31", bgA: "#f9fcef", bgB: "#e0eabf" },
    lagoon:   { name: "Lagoon",   accent: "#159b85", bgA: "#f1fffb", bgB: "#cdeee6" },
    volcanic: { name: "Volcanic", accent: "#ba4d3d", bgA: "#fdf5f3", bgB: "#ebd5d1" },
    meadow:   { name: "Meadow",   accent: "#4baf3d", bgA: "#f6fff1", bgB: "#d5efc9" },
    aurora:   { name: "Aurora",   accent: "#4a84d9", bgA: "#f2f8ff", bgB: "#d7e7fa" },
    espresso: { name: "Espresso", accent: "#b36a47", bgA: "#fdf7f2", bgB: "#ead8cc" },
    arctic:   { name: "Arctic",   accent: "#5f95ad", bgA: "#f7fcfd", bgB: "#dbeaf0" }
  };

  var PALETTES = {};
  var customConfigCache = null;


  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function normalizeHexColor(hex, fallback) {
    var val = String(hex || "").trim().toLowerCase();
    if (!val) return fallback;
    if (val[0] !== "#") val = "#" + val;
    if (/^#[0-9a-f]{3}$/.test(val)) {
      return "#" + val[1] + val[1] + val[2] + val[2] + val[3] + val[3];
    }
    if (/^#[0-9a-f]{6}$/.test(val)) return val;
    return fallback;
  }

  function sanitizeCustomName(name) {
    var n = String(name || "").trim().replace(/\s+/g, " ");
    if (!n) return "Custom";
    return n.slice(0, 24);
  }

  function hexToRgb(hex) {
    var normalized = normalizeHexColor(hex, "#000000");
    return {
      r: parseInt(normalized.slice(1, 3), 16),
      g: parseInt(normalized.slice(3, 5), 16),
      b: parseInt(normalized.slice(5, 7), 16)
    };
  }

  function rgbToHex(rgb) {
    function p(v) { return clamp(Math.round(v), 0, 255).toString(16).padStart(2, "0"); }
    return "#" + p(rgb.r) + p(rgb.g) + p(rgb.b);
  }

  function mixHex(a, b, ratio) {
    var x = clamp(Number(ratio || 0), 0, 1);
    var ra = hexToRgb(a);
    var rb = hexToRgb(b);
    return rgbToHex({
      r: ra.r * (1 - x) + rb.r * x,
      g: ra.g * (1 - x) + rb.g * x,
      b: ra.b * (1 - x) + rb.b * x
    });
  }

  function rgbaFromHex(hex, alpha) {
    var rgb = hexToRgb(hex);
    return "rgba(" + rgb.r + "," + rgb.g + "," + rgb.b + "," + clamp(Number(alpha || 0), 0, 1) + ")";
  }

  function getCustomPaletteConfig() {
    if (customConfigCache) return customConfigCache;
    try {
      var raw = localStorage.getItem(CUSTOM_STORAGE_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return null;
      customConfigCache = {
        name: sanitizeCustomName(parsed.name),
        accent: normalizeHexColor(parsed.accent, "#4a84d9"),
        bgA: normalizeHexColor(parsed.bgA, "#f2f8ff"),
        bgB: normalizeHexColor(parsed.bgB, "#d7e7fa")
      };
      return customConfigCache;
    } catch (_) {
      return null;
    }
  }

  function saveCustomPaletteConfig(config) {
    var next = {
      name: sanitizeCustomName(config && config.name),
      accent: normalizeHexColor(config && config.accent, "#4a84d9"),
      bgA: normalizeHexColor(config && config.bgA, "#f2f8ff"),
      bgB: normalizeHexColor(config && config.bgB, "#d7e7fa")
    };
    customConfigCache = next;
    try {
      localStorage.setItem(CUSTOM_STORAGE_KEY, JSON.stringify(next));
    } catch (_) {
      // Keep the custom palette usable in-memory even if storage is unavailable.
    }
    return next;
  }

  // Shared builder — used for both preset seeds and the user's custom palette.
  function buildPalette(config) {
    var c = config || { name: "Custom", accent: "#4a84d9", bgA: "#f2f8ff", bgB: "#d7e7fa" };
    var name = sanitizeCustomName(c.name);
    var accent = normalizeHexColor(c.accent, "#4a84d9");
    var bgA = normalizeHexColor(c.bgA, "#f2f8ff");
    var bgB = normalizeHexColor(c.bgB, "#d7e7fa");
    var lightBg = mixHex(bgA, bgB, 0.5);
    var darkBgA = mixHex(bgA, "#000000", 0.78);
    var darkBgB = mixHex(bgB, "#000000", 0.86);
    var darkBg = mixHex(darkBgA, darkBgB, 0.55);
    var darkPanel = mixHex(darkBg, accent, 0.16);
    var darkPanelSoft = mixHex(darkPanel, "#000000", 0.12);
    var darkAccent = mixHex(accent, "#ffffff", 0.2);
    return {
      name: name,
      light: {
        "--bg": lightBg,
        "--panel": "#ffffff",
        "--panel-soft": mixHex("#ffffff", lightBg, 0.25),
        "--card": rgbaFromHex("#ffffff", 0.92),
        "--text": "#1a2530",
        "--muted": mixHex("#1a2530", lightBg, 0.52),
        "--accent": accent,
        "--accent-dark": mixHex(accent, "#000000", 0.2),
        "--line": rgbaFromHex("#1a2530", 0.16),
        "--bg-a": bgA,
        "--bg-b": bgB
      },
      dark: {
        "--bg": darkBg,
        "--panel": darkPanel,
        "--panel-soft": darkPanelSoft,
        "--card": rgbaFromHex(darkPanel, 0.9),
        "--text": "#e8eef5",
        "--muted": "#9fb1c3",
        "--accent": darkAccent,
        "--accent-dark": mixHex(darkAccent, "#000000", 0.2),
        "--line": rgbaFromHex("#e8eef5", 0.2),
        "--bg-a": darkBgA,
        "--bg-b": darkBgB
      }
    };
  }

  function buildAllPalettes() {
    Object.keys(SEEDS).forEach(function (key) {
      PALETTES[key] = buildPalette(SEEDS[key]);
    });
  }

  function includeCustomPalette() {
    var cfg = getCustomPaletteConfig();
    PALETTES.custom = buildPalette(cfg || undefined);
  }

  function getThemeMode() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function getPaletteKey() {
    includeCustomPalette();
    var key = localStorage.getItem(STORAGE_KEY) || DEFAULT_PALETTE;
    if (LEGACY_KEYS[key]) key = LEGACY_KEYS[key];
    if (!PALETTES[key]) return DEFAULT_PALETTE;
    return key;
  }

  function applyPalette(key) {
    includeCustomPalette();
    var selected = PALETTES[key] ? key : DEFAULT_PALETTE;
    var palette = PALETTES[selected];
    var mode = getThemeMode();
    var vars = Object.assign({}, palette[mode]);
    if (!vars["--surface"]) vars["--surface"] = vars["--panel"];
    if (!vars["--border"]) vars["--border"] = vars["--line"];
    if (!vars["--success"]) vars["--success"] = vars["--accent"];
    if (!vars["--success-dark"]) vars["--success-dark"] = vars["--accent-dark"];
    var root = document.documentElement;
    Object.keys(vars).forEach(function (name) {
      root.style.setProperty(name, vars[name]);
    });
    localStorage.setItem(STORAGE_KEY, selected);
    return selected;
  }

  // Build all preset palettes from seeds, then apply.
  buildAllPalettes();
  applyPalette(getPaletteKey());

  // Keep palette in sync when pages toggle light/dark mode.
  var observer = new MutationObserver(function () {
    applyPalette(getPaletteKey());
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  window.RSPalette = {
    seeds: SEEDS,
    list: PALETTES,
    storageKey: STORAGE_KEY,
    customStorageKey: CUSTOM_STORAGE_KEY,
    get: getPaletteKey,
    apply: applyPalette,
    getCustom: getCustomPaletteConfig,
    setCustom: function (config) {
      var saved = saveCustomPaletteConfig(config || {});
      includeCustomPalette();
      return saved;
    },
    reapply: function () { return applyPalette(getPaletteKey()); }
  };
})();
