import { clearScans } from "../db.js";
import { icon, toast } from "../components/ui.js";
import { state } from "../state.js";

/** Render a persistent preference switch. @param {string} key @param {string} label @param {string} description @returns {string} */
function settingToggle(key, label, description) {
  return `<div class="setting-row"><span><strong>${label}</strong><small>${description}</small></span><button type="button" class="toggle" role="switch" aria-label="${label}" aria-checked="${Boolean(state.settings[key])}" data-setting="${key}"></button></div>`;
}

/** Render appearance, language, offline and privacy settings. @param {HTMLElement} root @returns {void} */
export function settingsPage(root) {
  root.innerHTML = `<section class="page-shell"><div class="container"><header class="page-header"><div><span class="eyebrow">Your Fieldnote</span><h1>Settings</h1><p>Choose how the app feels and how your scan history is kept on this device.</p></div></header><div class="settings-layout"><nav class="card settings-nav" aria-label="Settings sections"><a href="#appearance" aria-current="page"><span data-settings-icon="appearance"></span> Appearance</a><a href="#preferences"><span data-settings-icon="preferences"></span> Preferences</a><a href="#privacy"><span data-settings-icon="privacy"></span> Privacy</a></nav><div>
    <section class="card settings-section" id="appearance"><h2>Appearance</h2><div class="setting-row"><span><strong>Color theme</strong><small>Choose a light or dark look.</small></span><select class="form-control" id="theme-choice" style="max-width:170px"><option value="light">Light</option><option value="dark">Dark</option></select></div></section>
    <section class="card settings-section" id="preferences"><h2>Preferences</h2><div class="setting-row"><span><strong>Language</strong><small>Used for scan requests and selected interface labels.</small></span><select class="form-control" id="language-choice" style="max-width:170px"><option value="en">English</option><option value="hi">हिन्दी</option><option value="sw">Kiswahili</option><option value="ta">தமிழ்</option></select></div><div class="setting-row"><span><strong>Units</strong><small>Choose your preferred measurement system.</small></span><select class="form-control" id="units-choice" style="max-width:170px"><option value="metric">Metric</option><option value="imperial">Imperial</option></select></div><div class="setting-row"><span><strong>Offline field guide</strong><small>Keep the app shell and disease guide available without a connection.</small></span><button type="button" class="button button-secondary button-small" id="offline-pack">${icon("download")} Save offline pack</button></div></section>
    <section class="card settings-section" id="privacy"><h2>Data &amp; privacy</h2>${settingToggle("privacy", "Save scan history on this device", "Photos and results stay in this browser’s local database; they are sent to the API only when you request a scan.")}<div class="setting-row"><span><strong>Clear scan history</strong><small>Remove saved scan photos and results from this device.</small></span><button type="button" class="button button-danger button-small" id="clear-history">Clear data</button></div><p class="severity-meta" style="margin:14px 0 0">Camera access is requested only after you tap Camera. You can also upload a photo instead.</p></section>
    </div></div></div></section>`;
  root.querySelector("#theme-choice").value = state.settings.theme === "dark" ? "dark" : "light";
  root.querySelector("#language-choice").value = state.settings.language;
  root.querySelector("#units-choice").value = state.settings.units;
  root.querySelectorAll("[data-settings-icon]").forEach(async (holder) => {
    const name = holder.dataset.settingsIcon;
    const response = await fetch(`/assets/icons/${name}.svg`);
    if (response.ok) holder.innerHTML = await response.text();
  });
  root.querySelectorAll(".settings-nav a").forEach((link) => link.addEventListener("click", (event) => { event.preventDefault(); root.querySelectorAll(".settings-nav a").forEach(item => item.removeAttribute("aria-current")); link.setAttribute("aria-current", "page"); root.querySelector(link.getAttribute("href"))?.scrollIntoView({ behavior: "smooth" }); }));
  root.querySelectorAll("[data-setting]").forEach((button) =>
    button.addEventListener("click", () => {
      const key = button.dataset.setting;
      const next = button.getAttribute("aria-checked") !== "true";
      state.updateSetting(key, next);
      button.setAttribute("aria-checked", String(next));
    }),
  );
  root.querySelector("#theme-choice").addEventListener("change", (event) => {
    state.updateSetting("theme", event.currentTarget.value);
    document.documentElement.dataset.theme = event.currentTarget.value;
  });
  root
    .querySelector("#language-choice")
    .addEventListener("change", async (event) => {
      state.updateSetting("language", event.currentTarget.value);
      const { setLanguage } = await import("../i18n.js");
      await setLanguage(event.currentTarget.value);
      window.dispatchEvent(new Event("hashchange"));
    });
  root
    .querySelector("#units-choice")
    .addEventListener("change", (event) => state.updateSetting("units", event.currentTarget.value));
  root.querySelector("#clear-history").addEventListener("click", async () => {
    if (window.confirm("Delete all scan history stored in this browser?")) {
      await clearScans();
      toast("Saved scan history cleared from this device.");
    }
  });
  const offlineButton = root.querySelector("#offline-pack");
  offlineButton.addEventListener("click", async () => {
    if (!("serviceWorker" in navigator))
      return toast("Offline storage is not supported by this browser.", true);
    try {
      const registration = await navigator.serviceWorker.ready;
      if (!registration.active) throw new Error("Offline worker is not active");
      offlineButton.disabled = true;
      const onMessage = (event) => {
        if (event.data?.type !== "OFFLINE_PACK_SAVED") return;
        navigator.serviceWorker.removeEventListener("message", onMessage);
        window.clearTimeout(timeout);
        offlineButton.disabled = false;
        toast("Offline pack saved on this device.");
      };
      const timeout = window.setTimeout(() => {
        navigator.serviceWorker.removeEventListener("message", onMessage);
        offlineButton.disabled = false;
        toast("Offline pack could not be confirmed. Try again while online.", true);
      }, 12000);
      navigator.serviceWorker.addEventListener("message", onMessage);
      registration.active?.postMessage({ type: "CACHE_OFFLINE_PACK" });
    } catch {
      offlineButton.disabled = false;
      toast("Could not save the offline pack.", true);
    }
  });
}
