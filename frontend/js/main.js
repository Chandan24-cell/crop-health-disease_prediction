import { icon, toast } from "./components/ui.js";
import { HashRouter } from "./router.js";
import { state } from "./state.js";
import { setLanguage, t } from "./i18n.js";

const BUILD_ID = "ui-fixes-cache-v3-20261003";
// eslint-disable-next-line no-console
console.info("fieldnote build", BUILD_ID);

window.addEventListener("error", e => console.error("GLOBAL", e.message, e.filename, e.lineno, e.error?.stack));
window.addEventListener("unhandledrejection", e => console.error("REJECT", e.reason?.stack || e.reason));

const themeButton = document.querySelector(".theme-toggle");
const router = new HashRouter(document.querySelector("#main-content"));

/** @param {"auto"|"light"|"dark"} theme */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const shown = theme === "dark" ? "sun" : "moon";
  themeButton.innerHTML = icon(shown);
  themeButton.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
}

state.subscribe("settings", (settings) => {
  if (settings.theme) applyTheme(settings.theme);
});

applyTheme(state.settings.theme || "light");
themeButton.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme;
  const next = current === "dark" ? "light" : "dark";
  state.updateSetting("theme", next);
  applyTheme(next);
});

const languageToggle = document.querySelector(".language-toggle");
const languageMenu = document.querySelector(".language-options");
function syncLanguage() {
  const lang = state.settings.language || "en";
  languageToggle.querySelector("span").textContent = ({ en: "EN", hi: "\u0939\u093f\u0902", ne: "\u0928\u0947" })[lang] || "EN";
  document.documentElement.lang = lang;
  const labels = {
    scan: "nav_scan",
    "outbreak-map": "nav_map",
    treatment: "nav_treatment",
    "my-scans": "nav_history",
    "plant-guide": "nav_library",
    safety: "nav_safety",
  };
  document.querySelectorAll(".desktop-nav [data-nav]").forEach((link) => {
    const key = labels[link.dataset.nav];
    if (key) link.textContent = t(key, link.textContent);
  });
}
languageToggle.addEventListener("click", () => {
  const open = languageMenu.hidden;
  languageMenu.hidden = !open;
  languageToggle.setAttribute("aria-expanded", String(open));
  if (open) languageMenu.querySelector("button")?.focus();
});
languageMenu.addEventListener("click", async (event) => {
  const option = event.target.closest("[data-language]");
  if (!option) return;
  state.updateSetting("language", option.dataset.language);
  await setLanguage(option.dataset.language);
  syncLanguage();
  languageMenu.hidden = true;
  languageToggle.setAttribute("aria-expanded", "false");
  await router.navigate();
  languageToggle.focus();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !languageMenu.hidden) {
    languageMenu.hidden = true;
    languageToggle.setAttribute("aria-expanded", "false");
    languageToggle.focus();
  }
});
window.addEventListener("fieldnote:language", syncLanguage);
syncLanguage();

const offlineBanner = document.querySelector("#offline-banner");
/** Keep the accessible offline notice in sync with browser connectivity. */
function syncNetworkStatus() {
  offlineBanner.hidden = navigator.onLine;
}
window.addEventListener("online", () => {
  syncNetworkStatus();
  toast("You’re back online.");
});
window.addEventListener("offline", syncNetworkStatus);
syncNetworkStatus();

window.addEventListener("unhandledrejection", () => {
  toast("Something went wrong. Please try again.", true);
});

const isLocalDevelopment = ["localhost", "127.0.0.1"].includes(location.hostname);
if ("serviceWorker" in navigator && isLocalDevelopment) {
  try {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map((registration) => registration.unregister()));
  } catch {
    // Local development always runs without relying on service worker storage.
  }
  if ("caches" in window) {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key.startsWith("fieldnote-")).map((key) => caches.delete(key)));
    } catch {
      // Browser storage may be blocked; the app still loads from the network.
    }
  }
} else if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("/service-worker.js").catch(() => {});
}

router.navigate();
