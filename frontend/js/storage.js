const memory = new Map();

/** Storage access that degrades to an in-memory map when browser storage is blocked. */
export const safeStorage = {
  get(key) {
    try {
      const value = window.localStorage.getItem(key);
      if (value !== null) memory.set(key, value);
      return value ?? memory.get(key) ?? null;
    } catch {
      return memory.get(key) ?? null;
    }
  },
  set(key, value) {
    const text = String(value);
    memory.set(key, text);
    try {
      window.localStorage.setItem(key, text);
    } catch {
      // The in-memory copy remains available for this page session.
    }
  },
  remove(key) {
    memory.delete(key);
    try {
      window.localStorage.removeItem(key);
    } catch {
      // The in-memory copy is already cleared.
    }
  },
};

/** @param {string} key @returns {string|null} */
export function safeSessionGet(key) {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

/** @param {string} key @param {string} value */
export function safeSessionSet(key, value) {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // Session-only preferences may safely fall back to defaults.
  }
}
