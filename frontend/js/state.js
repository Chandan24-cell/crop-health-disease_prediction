import { safeStorage } from "./storage.js";

const SETTINGS_KEY = "fieldnote-settings";

/** Small observable state store shared by page modules. */
export class AppState {
  constructor() {
    this.listeners = new Set();
    this.currentResult = null;
    this.currentImageUrl = null;
    this.lastRoute = "home";
    this.settings = this.readSettings();
  }

  readSettings() {
    try {
      const saved = JSON.parse(safeStorage.get(SETTINGS_KEY) || "{}");
      const storedLanguage = safeStorage.get("language");
      const language = ["en", "hi", "ne"].includes(storedLanguage) ? storedLanguage : (["en", "hi", "ne"].includes(saved.language) ? saved.language : "en");
      const theme = safeStorage.get("theme") === "dark" || saved.theme === "dark" ? "dark" : "light";
      return { units: "metric", privacy: true, ...saved, language, theme };
    } catch {
      return { language: "en", units: "metric", theme: "light", privacy: true };
    }
  }

  /** @param {string} key @param {unknown} value */
  updateSetting(key, value) {
    this.settings = { ...this.settings, [key]: value };
    safeStorage.set(SETTINGS_KEY, JSON.stringify(this.settings));
    if (key === "theme") {
      safeStorage.set("theme", value);
      document.documentElement.dataset.theme = value;
    }
    if (key === "language") {
      safeStorage.set("language", value);
      document.documentElement.lang = value;
    }
    this.emit("settings", this.settings);
  }

  /** @param {File|Blob} file @param {string} dataUrl */
  setImage(file, dataUrl) {
    this.currentImageUrl = dataUrl;
    this.emit("image", { file, dataUrl });
  }

  clearImage() {
    this.currentImageUrl = null;
    this.emit("image", null);
  }

  /** @param {Object} result */
  setResult(result) {
    this.currentResult = result;
    this.emit("result", result);
  }

  /** @param {string} event @param {Function} callback */
  subscribe(event, callback) {
    const entry = { event, callback };
    this.listeners.add(entry);
    return () => this.listeners.delete(entry);
  }

  /** @param {string} event @param {unknown} value */
  emit(event, value) {
    this.listeners.forEach((listener) => {
      if (listener.event === event) listener.callback(value);
    });
  }
}

export const state = new AppState();

