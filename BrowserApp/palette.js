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

  var PALETTES = {
    woodland: {
      name: "Woodland",
      light: {
        "--bg": "#d6ece0",
        "--panel": "#ffffff",
        "--panel-soft": "#f5f9ff",
        "--card": "rgba(248,255,251,.9)",
        "--text": "#0e2c1d",
        "--muted": "#4d6f60",
        "--accent": "#1f8a4c",
        "--accent-dark": "#166337",
        "--line": "rgba(14,44,29,.16)",
        "--bg-a": "#f3fbf6",
        "--bg-b": "#def0e6"
      },
      dark: {
        "--bg": "#0f1f16",
        "--panel": "#1a2e22",
        "--panel-soft": "#1b2d27",
        "--card": "rgba(30,48,37,.9)",
        "--text": "#d4edda",
        "--muted": "#7faa8e",
        "--accent": "#2ab561",
        "--accent-dark": "#1d8748",
        "--line": "rgba(180,220,195,.16)",
        "--bg-a": "#101b17",
        "--bg-b": "#0b1411"
      }
    },
    reef: {
      name: "Reef",
      light: {
        "--bg": "#e6f4f8",
        "--panel": "#ffffff",
        "--panel-soft": "#f2f9fc",
        "--card": "rgba(248,253,255,.92)",
        "--text": "#0f2d38",
        "--muted": "#4a6a75",
        "--accent": "#0f7ea8",
        "--accent-dark": "#0b6486",
        "--line": "rgba(15,45,56,.16)",
        "--bg-a": "#f2fbff",
        "--bg-b": "#d8eef7"
      },
      dark: {
        "--bg": "#0c1a22",
        "--panel": "#142833",
        "--panel-soft": "#17303d",
        "--card": "rgba(23,48,61,.88)",
        "--text": "#d8edf6",
        "--muted": "#8ab3c3",
        "--accent": "#2aa4d2",
        "--accent-dark": "#1d89b2",
        "--line": "rgba(149,201,221,.18)",
        "--bg-a": "#0f202a",
        "--bg-b": "#0a141b"
      }
    },
    canyon: {
      name: "Canyon",
      light: {
        "--bg": "#fff1e8",
        "--panel": "#ffffff",
        "--panel-soft": "#fff7f2",
        "--card": "rgba(255,250,246,.93)",
        "--text": "#3a2117",
        "--muted": "#795445",
        "--accent": "#d06b2c",
        "--accent-dark": "#ab531e",
        "--line": "rgba(58,33,23,.15)",
        "--bg-a": "#fff8f3",
        "--bg-b": "#ffe7d6"
      },
      dark: {
        "--bg": "#241711",
        "--panel": "#332018",
        "--panel-soft": "#3b251c",
        "--card": "rgba(59,37,28,.9)",
        "--text": "#fae7da",
        "--muted": "#d2a88f",
        "--accent": "#f08a49",
        "--accent-dark": "#d97433",
        "--line": "rgba(247,205,180,.2)",
        "--bg-a": "#2b1a12",
        "--bg-b": "#1d120d"
      }
    },
    tundra: {
      name: "Tundra",
      light: {
        "--bg": "#eceef2",
        "--panel": "#ffffff",
        "--panel-soft": "#f6f7f9",
        "--card": "rgba(250,251,253,.93)",
        "--text": "#222831",
        "--muted": "#5f6673",
        "--accent": "#4a5f91",
        "--accent-dark": "#3c4c74",
        "--line": "rgba(34,40,49,.16)",
        "--bg-a": "#f4f5f8",
        "--bg-b": "#dde1e8"
      },
      dark: {
        "--bg": "#151921",
        "--panel": "#202634",
        "--panel-soft": "#262d3d",
        "--card": "rgba(38,45,61,.9)",
        "--text": "#e4e9f2",
        "--muted": "#9aa5bd",
        "--accent": "#7c96d6",
        "--accent-dark": "#627fc3",
        "--line": "rgba(199,210,233,.2)",
        "--bg-a": "#1b212d",
        "--bg-b": "#12161f"
      }
    },
    desert: {
      name: "Desert",
      light: {
        "--bg": "#f8efe0",
        "--panel": "#fffdf8",
        "--panel-soft": "#fdf6ea",
        "--card": "rgba(255,250,242,.92)",
        "--text": "#3f2d1c",
        "--muted": "#7e6650",
        "--accent": "#c8873f",
        "--accent-dark": "#a86f30",
        "--line": "rgba(63,45,28,.16)",
        "--bg-a": "#fff8ed",
        "--bg-b": "#f1dfc6"
      },
      dark: {
        "--bg": "#231911",
        "--panel": "#332519",
        "--panel-soft": "#3e2c1e",
        "--card": "rgba(62,44,30,.9)",
        "--text": "#f7eadc",
        "--muted": "#d2b596",
        "--accent": "#e2a55f",
        "--accent-dark": "#c88e4f",
        "--line": "rgba(247,227,205,.2)",
        "--bg-a": "#2a1d13",
        "--bg-b": "#1a120c"
      }
    },
    glacier: {
      name: "Glacier",
      light: {
        "--bg": "#e8f6fb",
        "--panel": "#ffffff",
        "--panel-soft": "#f2fbff",
        "--card": "rgba(247,253,255,.92)",
        "--text": "#173241",
        "--muted": "#587a8d",
        "--accent": "#2d9cc7",
        "--accent-dark": "#217ba0",
        "--line": "rgba(23,50,65,.16)",
        "--bg-a": "#f4fcff",
        "--bg-b": "#d7ecf6"
      },
      dark: {
        "--bg": "#0f1b23",
        "--panel": "#172a35",
        "--panel-soft": "#1c3341",
        "--card": "rgba(28,51,65,.9)",
        "--text": "#d9edf7",
        "--muted": "#8eb3c7",
        "--accent": "#4db9e2",
        "--accent-dark": "#359bc1",
        "--line": "rgba(181,216,232,.2)",
        "--bg-a": "#122230",
        "--bg-b": "#0a141a"
      }
    },
    savanna: {
      name: "Savanna",
      light: {
        "--bg": "#eef4db",
        "--panel": "#ffffff",
        "--panel-soft": "#f7faec",
        "--card": "rgba(251,254,243,.92)",
        "--text": "#2d3517",
        "--muted": "#687449",
        "--accent": "#889f31",
        "--accent-dark": "#6c8126",
        "--line": "rgba(45,53,23,.16)",
        "--bg-a": "#f9fcef",
        "--bg-b": "#e0eabf"
      },
      dark: {
        "--bg": "#171d0e",
        "--panel": "#242e16",
        "--panel-soft": "#2b361a",
        "--card": "rgba(43,54,26,.9)",
        "--text": "#e8efd5",
        "--muted": "#a9bb7b",
        "--accent": "#b8cf58",
        "--accent-dark": "#9bb344",
        "--line": "rgba(217,232,171,.2)",
        "--bg-a": "#202813",
        "--bg-b": "#111608"
      }
    },
    lagoon: {
      name: "Lagoon",
      light: {
        "--bg": "#dff6f1",
        "--panel": "#ffffff",
        "--panel-soft": "#effcf8",
        "--card": "rgba(246,255,253,.92)",
        "--text": "#124237",
        "--muted": "#4d7d72",
        "--accent": "#159b85",
        "--accent-dark": "#0f7c6a",
        "--line": "rgba(18,66,55,.16)",
        "--bg-a": "#f1fffb",
        "--bg-b": "#cdeee6"
      },
      dark: {
        "--bg": "#0d201c",
        "--panel": "#14322c",
        "--panel-soft": "#194038",
        "--card": "rgba(25,64,56,.9)",
        "--text": "#d5f1ea",
        "--muted": "#90c1b5",
        "--accent": "#31c3a8",
        "--accent-dark": "#22a38b",
        "--line": "rgba(173,223,212,.2)",
        "--bg-a": "#123029",
        "--bg-b": "#081511"
      }
    },
    volcanic: {
      name: "Volcanic",
      light: {
        "--bg": "#f4e8e5",
        "--panel": "#ffffff",
        "--panel-soft": "#fbf2f0",
        "--card": "rgba(255,248,247,.92)",
        "--text": "#3d201c",
        "--muted": "#805651",
        "--accent": "#ba4d3d",
        "--accent-dark": "#97392c",
        "--line": "rgba(61,32,28,.16)",
        "--bg-a": "#fdf5f3",
        "--bg-b": "#ebd5d1"
      },
      dark: {
        "--bg": "#201311",
        "--panel": "#321d1a",
        "--panel-soft": "#3d2420",
        "--card": "rgba(61,36,32,.9)",
        "--text": "#f3dfdc",
        "--muted": "#c59a93",
        "--accent": "#e16d5a",
        "--accent-dark": "#c55544",
        "--line": "rgba(233,197,190,.2)",
        "--bg-a": "#2a1916",
        "--bg-b": "#120a09"
      }
    },
    meadow: {
      name: "Meadow",
      light: {
        "--bg": "#e6f7df",
        "--panel": "#ffffff",
        "--panel-soft": "#f2fceb",
        "--card": "rgba(248,255,244,.92)",
        "--text": "#1e3817",
        "--muted": "#5a814f",
        "--accent": "#4baf3d",
        "--accent-dark": "#398b2f",
        "--line": "rgba(30,56,23,.16)",
        "--bg-a": "#f6fff1",
        "--bg-b": "#d5efc9"
      },
      dark: {
        "--bg": "#12200f",
        "--panel": "#1d3218",
        "--panel-soft": "#24401d",
        "--card": "rgba(36,64,29,.9)",
        "--text": "#dcedd3",
        "--muted": "#9fc392",
        "--accent": "#6fd35e",
        "--accent-dark": "#56b148",
        "--line": "rgba(192,224,180,.2)",
        "--bg-a": "#183016",
        "--bg-b": "#0b1408"
      }
    },
    aurora: {
      name: "Aurora",
      light: {
        "--bg": "#e7f3fb",
        "--panel": "#ffffff",
        "--panel-soft": "#f2f9ff",
        "--card": "rgba(247,252,255,.92)",
        "--text": "#162c45",
        "--muted": "#58708f",
        "--accent": "#4a84d9",
        "--accent-dark": "#3868ad",
        "--line": "rgba(22,44,69,.16)",
        "--bg-a": "#f2f8ff",
        "--bg-b": "#d7e7fa"
      },
      dark: {
        "--bg": "#111a26",
        "--panel": "#1a2738",
        "--panel-soft": "#203147",
        "--card": "rgba(32,49,71,.9)",
        "--text": "#dbe9fb",
        "--muted": "#9ab6de",
        "--accent": "#70a3ef",
        "--accent-dark": "#5587d0",
        "--line": "rgba(202,222,252,.2)",
        "--bg-a": "#182537",
        "--bg-b": "#0d141f"
      }
    },
    espresso: {
      name: "Espresso",
      light: {
        "--bg": "#f4ece7",
        "--panel": "#fffdfb",
        "--panel-soft": "#faf2ec",
        "--card": "rgba(255,250,246,.92)",
        "--text": "#3b2b24",
        "--muted": "#7b655a",
        "--accent": "#b36a47",
        "--accent-dark": "#8f5236",
        "--line": "rgba(59,43,36,.16)",
        "--bg-a": "#fdf7f2",
        "--bg-b": "#ead8cc"
      },
      dark: {
        "--bg": "#1d1411",
        "--panel": "#2b1d18",
        "--panel-soft": "#36231d",
        "--card": "rgba(54,35,29,.9)",
        "--text": "#f1e2d8",
        "--muted": "#c2a493",
        "--accent": "#d38b67",
        "--accent-dark": "#b56f4d",
        "--line": "rgba(235,210,194,.2)",
        "--bg-a": "#271a15",
        "--bg-b": "#120c0a"
      }
    },
    arctic: {
      name: "Arctic",
      light: {
        "--bg": "#edf6f8",
        "--panel": "#ffffff",
        "--panel-soft": "#f6fbfd",
        "--card": "rgba(250,254,255,.92)",
        "--text": "#1e3440",
        "--muted": "#5f7c8b",
        "--accent": "#5f95ad",
        "--accent-dark": "#4a7588",
        "--line": "rgba(30,52,64,.15)",
        "--bg-a": "#f7fcfd",
        "--bg-b": "#dbeaf0"
      },
      dark: {
        "--bg": "#121d22",
        "--panel": "#1d2d35",
        "--panel-soft": "#233741",
        "--card": "rgba(35,55,65,.9)",
        "--text": "#d9e9f0",
        "--muted": "#9eb8c5",
        "--accent": "#89bfd6",
        "--accent-dark": "#6ca5bc",
        "--line": "rgba(195,222,234,.2)",
        "--bg-a": "#1a2a32",
        "--bg-b": "#0d1419"
      }
    }
  };

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
    try {
      var raw = localStorage.getItem(CUSTOM_STORAGE_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return null;
      return {
        name: sanitizeCustomName(parsed.name),
        accent: normalizeHexColor(parsed.accent, "#4a84d9"),
        bgA: normalizeHexColor(parsed.bgA, "#f2f8ff"),
        bgB: normalizeHexColor(parsed.bgB, "#d7e7fa")
      };
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
    localStorage.setItem(CUSTOM_STORAGE_KEY, JSON.stringify(next));
    return next;
  }

  function buildCustomPalette(config) {
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

  function includeCustomPalette() {
    var cfg = getCustomPaletteConfig();
    PALETTES.custom = buildCustomPalette(cfg || undefined);
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

  // Apply as soon as script loads.
  applyPalette(getPaletteKey());

  // Keep palette in sync when pages toggle light/dark mode.
  var observer = new MutationObserver(function () {
    applyPalette(getPaletteKey());
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  window.RSPalette = {
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
