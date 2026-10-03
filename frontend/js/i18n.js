import englishMessages from "../locales/en.js";
import { state } from "./state.js";

const DEFAULT_LANG = "en";
const localeCache = new Map([["en", englishMessages]]);
const localeFlights = new Map();

const BCP47 = {
  en: "en-US",
  hi: "hi-IN",
  ne: "ne-NP",
};

// Fallback embedded strings for immediate synchronous access or offline failure
const fallbackMessages = {
  en: {
    app_name: "Fieldnote",
    nav_home: "Home",
    nav_scan: "Scan",
    nav_history: "My scans",
    nav_library: "Plant guide",
    nav_map: "Outbreak map",
    nav_settings: "Settings",
    btn_scan_leaf: "Scan a leaf",
    scan_ready: "Your leaf scan is ready",
    status_ok: "A clear result",
    status_retake: "Let's get a clearer photo",
    status_unsupported: "This crop is outside the guide",
    status_uncertain: "A closer look is needed",
    voice_read_aloud: "Read aloud",
    voice_stop: "Stop reading",
  },
  sw: {
    app_name: "Fieldnote",
    nav_home: "Nyumbani",
    nav_scan: "Changanua",
    nav_history: "Uchanganuzi wangu",
    nav_library: "Mwongozo wa mimea",
    nav_map: "Ramani ya Magonjwa",
    nav_settings: "Mipangilio",
    btn_scan_leaf: "Changanua jani",
    scan_ready: "Uchanganuzi umekamilika",
    status_ok: "Matokeo yaliyo wazi",
    status_retake: "Piga picha nyingine iliyo wazi",
    status_unsupported: "Zao hili halitumiki bado",
    status_uncertain: "Uchunguzi zaidi unahitajika",
    voice_read_aloud: "Soma kwa sauti",
    voice_stop: "Acha kusoma",
  },
  hi: {
    app_name: "Fieldnote",
    nav_home: "होम",
    nav_scan: "स्कैन",
    nav_history: "मेरे स्कैन",
    nav_library: "फसल गाइड",
    nav_map: "प्रकोप मानचित्र",
    nav_settings: "सेटिंग्स",
    btn_scan_leaf: "पत्ती स्कैन करें",
    scan_ready: "पत्ती की जाँच पूरी हुई",
    status_ok: "स्पष्ट परिणाम",
    status_retake: "कृपया स्पष्ट फोटो लें",
    status_unsupported: "यह पत्ती समर्थित नहीं है",
    status_uncertain: "बारीकी से जांच आवश्यक",
    voice_read_aloud: "बोलकर सुनाएं",
    voice_stop: "पढ़ना बंद करें",
  },
  ta: {
    app_name: "Fieldnote",
    nav_home: "முகப்பு",
    nav_scan: "ஸ்கேன்",
    nav_history: "என் ஸ்கேன்கள்",
    nav_library: "பயிர் வழிகாட்டி",
    nav_map: "நோய் பரவல் வரைபடம்",
    nav_settings: "அமைப்புகள்",
    btn_scan_leaf: "இலையை ஸ்கேன் செய்க",
    scan_ready: "உங்கள் ஸ்கேன் தயார்",
    status_ok: "தெளிவான முடிவு",
    status_retake: "தெளிவான புகைப்படத்தை மீண்டும் எடுப்போம்",
    status_unsupported: "இந்தப் பயிர் வழிகாட்டியில் இல்லை",
    status_uncertain: "நெருக்கமான ஆய்வு தேவை",
    voice_read_aloud: "வாசித்துக் காட்டு",
    voice_stop: "வாசிப்பதை நிறுத்து",
  },
};

let currentLang = ["en", "hi", "ne"].includes(state?.settings?.language) ? state.settings.language : DEFAULT_LANG;

/**
 * Asynchronously load locale JSON file.
 * @param {string} lang
 */
export async function loadLocale(lang = currentLang) {
  lang = ["en", "hi", "ne"].includes(lang) ? lang : DEFAULT_LANG;
  if (localeCache.has(lang)) {
    currentLang = lang;
    return localeCache.get(lang);
  }
  if (!localeFlights.has(lang)) {
    const url = new URL(`../locales/${lang}.json`, import.meta.url);
    localeFlights.set(lang, (async () => {
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data || typeof data !== "object" || Array.isArray(data) || Object.values(data).some((value) => typeof value !== "string")) {
          throw new TypeError(`Expected object<string,string> at ${url.href}`);
        }
        localeCache.set(lang, data);
        return data;
      } catch (error) {
        console.error(`Locale loader failed: frontend/locales/${lang}.json; URL=${url.href}; schema=object<string,string>`, error);
        return fallbackMessages[lang] || fallbackMessages.en;
      }
    })());
  }
  const data = await localeFlights.get(lang);
  if (data) {
      if (lang !== "en" && ["localhost", "127.0.0.1"].includes(location.hostname)) {
        const english = localeCache.get("en");
        if (english) {
          const missing = Object.keys(english).filter((key) => !(key in data));
          if (missing.length) console.warn(`Missing ${lang} translations; using English fallback:`, missing);
        }
      }
      currentLang = lang;
      return data;
  }
  currentLang = lang;
  return fallbackMessages[lang] || fallbackMessages.en;
}

/**
 * Return localized text.
 * @param {string} key
 * @param {string} [fallback]
 * @returns {string}
 */
export function t(key, fallback = "") {
  const currentDict = localeCache.get(currentLang);
  if (currentDict && key in currentDict) {
    return currentDict[key];
  }
  if (fallbackMessages[currentLang]?.[key]) {
    return fallbackMessages[currentLang][key];
  }
  const enDict = localeCache.get("en");
  if (enDict && key in enDict) {
    return enDict[key];
  }
  if (fallbackMessages.en[key]) {
    return fallbackMessages.en[key];
  }
  if (typeof fallback === "string" && fallback && !["en", "hi", "ne", "sw", "ta"].includes(fallback)) return fallback;
  return "";
}

/**
 * Set the active UI language.
 * @param {string} lang
 */
export async function setLanguage(lang) {
  currentLang = ["en", "hi", "ne"].includes(lang) ? lang : DEFAULT_LANG;
  await loadLocale(currentLang);
  document.documentElement.lang = currentLang;
  window.dispatchEvent(new CustomEvent("fieldnote:language", { detail: currentLang }));
}

/**
 * Get the active language code.
 * @returns {string}
 */
export function getLanguage() {
  return currentLang;
}

// ── Web Speech API Read-Aloud ──────────────────────────────────────────

/**
 * Read text aloud using Web Speech API with language BCP-47 tag.
 * @param {string} text
 * @param {string} [lang]
 * @param {Function} [onEnd]
 */
export function speak(text, lang = currentLang, onEnd = null) {
  if (!("speechSynthesis" in window)) {
    console.warn("Web Speech API not supported on this platform.");
    return false;
  }
  stopSpeaking();
  if (!text || !text.trim()) return false;

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = BCP47[lang] || BCP47.en;
  utterance.rate = 0.95; // Slightly slower for clarity in advisory contexts

  utterance.onend = () => {
    if (onEnd) onEnd();
  };
  utterance.onerror = (e) => {
    console.warn("Speech synthesis error:", e);
    if (onEnd) onEnd();
  };

  window.speechSynthesis.speak(utterance);
  return true;
}

/**
 * Stop any current speech playback.
 */
export function stopSpeaking() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

/**
 * Check if speech is currently playing.
 * @returns {boolean}
 */
export function isSpeaking() {
  return "speechSynthesis" in window && window.speechSynthesis.speaking;
}

// Initial locale fetch in background
loadLocale("en").then(() => loadLocale(currentLang));

// Listen to settings changes for language updates
if (state) {
  state.subscribe("settings", (settings) => {
    if (settings.language && settings.language !== currentLang) {
      setLanguage(settings.language);
    }
  });
}
