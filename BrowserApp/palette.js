(function () {
  "use strict";

  var STORAGE_KEY = "rs_palette";
  var DEFAULT_PALETTE = "forest";

  var PALETTES = {
    forest: {
      name: "Forest",
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
    ocean: {
      name: "Ocean",
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
    sunset: {
      name: "Sunset",
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
    graphite: {
      name: "Graphite",
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
    }
  };

  function getThemeMode() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function getPaletteKey() {
    var key = localStorage.getItem(STORAGE_KEY) || DEFAULT_PALETTE;
    if (!PALETTES[key]) return DEFAULT_PALETTE;
    return key;
  }

  function applyPalette(key) {
    var selected = PALETTES[key] ? key : DEFAULT_PALETTE;
    var palette = PALETTES[selected];
    var mode = getThemeMode();
    var vars = palette[mode];
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
    get: getPaletteKey,
    apply: applyPalette,
    reapply: function () { return applyPalette(getPaletteKey()); }
  };
})();
