/** @typedef {Object} PredictionResult */

import { isEnabled } from "./feature-flags.js";
import { runOfflineInference } from "./offline-inference.js";

const API_ROOT = "/api/v1";

/**
 * Helper to turn a File or Blob into an HTMLImageElement for canvas rendering.
 * @param {Blob|File} blob
 * @returns {Promise<HTMLImageElement>}
 */
function blobToImage(blob) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(blob);
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = (err) => {
      URL.revokeObjectURL(url);
      reject(err);
    };
    img.src = url;
  });
}

/**
 * Send one image for crop-health analysis.
 * Automatically falls back to on-device WASM inference when offline.
 * @param {File|Blob} image
 * @param {{crop?: string, language?: string, latitude?: number, longitude?: number}} options
 */
export async function predict(image, options = {}) {
  // Check if offline and offline inference feature flag is enabled
  if (!navigator.onLine && isEnabled("pwa_offline_inference")) {
    const imgElement = await blobToImage(image);
    return runOfflineInference(imgElement, options.crop);
  }

  const body = new FormData();
  body.append("image", image, image instanceof File ? image.name : "leaf-scan.jpg");
  if (options.crop) body.append("crop_hint", options.crop);
  if (options.language) body.append("language", options.language);
  if (options.latitude) body.append("latitude", String(options.latitude));
  if (options.longitude) body.append("longitude", String(options.longitude));

  try {
    const response = await fetch(`${API_ROOT}/predict`, { method: "POST", body });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `Scan failed (${response.status})`);
    return payload;
  } catch (networkError) {
    if (isEnabled("pwa_offline_inference")) {
      console.warn("Network request failed, falling back to on-device inference:", networkError);
      const imgElement = await blobToImage(image);
      return runOfflineInference(imgElement, options.crop);
    }
    throw networkError;
  }
}

/**
 * @param {string} [signal]
 * @param {string} [language]
 */
export async function fetchDiseases(signal, language = "en") {
  const url =
    language && language !== "en" ? `${API_ROOT}/diseases?lang=${language}` : `${API_ROOT}/diseases`;
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error("Could not load the plant guide.");
  return response.json();
}

/**
 * @param {string} id
 * @param {string} [signal]
 * @param {string} [language]
 */
export async function fetchDisease(id, signal, language = "en") {
  const url =
    language && language !== "en"
      ? `${API_ROOT}/diseases/${encodeURIComponent(id)}?lang=${language}`
      : `${API_ROOT}/diseases/${encodeURIComponent(id)}`;
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error("Disease details are unavailable.");
  return response.json();
}

export async function health() {
  const response = await fetch(`${API_ROOT}/health`, { cache: "no-store" });
  if (!response.ok) throw new Error("API unavailable");
  return response.json();
}
