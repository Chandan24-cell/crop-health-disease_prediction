import { safeStorage } from "./storage.js";

const DATABASE = "fieldnote-local";
const VERSION = 1;
const STORE = "scans";
let memoryScans = [];

function fallbackScans() {
  try {
    const stored = JSON.parse(safeStorage.get("fieldnote-scans") || "[]");
    if (Array.isArray(stored)) memoryScans = stored;
  } catch {
    // Preserve the in-memory list if stored data is invalid.
  }
  return memoryScans;
}

function saveFallback(scans) {
  memoryScans = scans;
  safeStorage.set("fieldnote-scans", JSON.stringify(scans));
}

/** @returns {Promise<IDBDatabase|null>} */
function openDatabase() {
  try {
    if (!window.indexedDB) return Promise.resolve(null);
    return new Promise((resolve) => {
      let request;
      try {
        request = window.indexedDB.open(DATABASE, VERSION);
      } catch {
        resolve(null);
        return;
      }
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "id" });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
      request.onblocked = () => resolve(null);
    });
  } catch {
    return Promise.resolve(null);
  }
}

/** @param {Object} value @returns {Promise<void>} */
export async function saveScan(value) {
  const db = await openDatabase();
  if (db) {
    try {
      await new Promise((resolve, reject) => {
        const request = db.transaction(STORE, "readwrite").objectStore(STORE).put(value);
        request.onsuccess = resolve;
        request.onerror = () => reject(request.error);
      });
      db.close();
      const scans = fallbackScans().filter((scan) => scan.id !== value.id);
      saveFallback([value, ...scans]);
      return;
    } catch {
      try { db.close(); } catch { /* already closed */ }
    }
  }
  saveFallback([value, ...fallbackScans().filter((scan) => scan.id !== value.id)]);
}

/** @returns {Promise<Array<Object>>} */
export async function getScans() {
  const db = await openDatabase();
  if (db) {
    try {
      const values = await new Promise((resolve) => {
        const request = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
        request.onsuccess = () => resolve(request.result || []);
        request.onerror = () => resolve(null);
      });
      db.close();
      if (Array.isArray(values)) {
        memoryScans = values;
        return values.sort((a, b) => b.date - a.date);
      }
    } catch {
      try { db.close(); } catch { /* already closed */ }
    }
  }
  return [...fallbackScans()].sort((a, b) => b.date - a.date);
}

/** @returns {Promise<void>} */
export async function clearScans() {
  const db = await openDatabase();
  if (db) {
    try {
      await new Promise((resolve) => {
        const request = db.transaction(STORE, "readwrite").objectStore(STORE).clear();
        request.onsuccess = resolve;
        request.onerror = resolve;
      });
      db.close();
    } catch {
      try { db.close(); } catch { /* already closed */ }
    }
  }
  memoryScans = [];
  safeStorage.remove("fieldnote-scans");
}

/** @param {string} id @returns {Promise<void>} */
export async function deleteScan(id) {
  const db = await openDatabase();
  if (db) {
    try {
      await new Promise((resolve) => {
        const request = db.transaction(STORE, "readwrite").objectStore(STORE).delete(id);
        request.onsuccess = resolve;
        request.onerror = resolve;
      });
      db.close();
    } catch {
      try { db.close(); } catch { /* already closed */ }
    }
  }
  saveFallback(fallbackScans().filter((scan) => scan.id !== id));
}
