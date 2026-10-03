import { predict } from "../api.js";
import { sendBatchPredict } from "../batch.js";
import { CameraController } from "../camera.js";
import { icon, toast } from "../components/ui.js";
import { saveScan } from "../db.js";
import { isEnabled } from "../feature-flags.js";
import { t } from "../i18n.js";
import { blobDataUrl, inspectCanvas, prepareImage } from "../quality.js";
import { state } from "../state.js";
import { advanceAnalysis } from "./analysis.js";

/** @param {HTMLElement} root */
export function scannerPage(root) {
  const allowBatch = isEnabled("batch_scan");

  root.innerHTML = `
    <section class="page-shell"><div class="container">
          <header class="page-header"><div><span class="eyebrow"><span class="eyebrow-dot"></span> Leaf scan</span><h1>${t("scan_title", "Scan a leaf")}</h1><p>Use a clear, close photo in natural light. Your image is only sent when you choose “Analyze leaf.”</p></div></header>
      <div class="scanner-layout">
        <section class="card scanner-card" aria-label="Leaf photo scanner">
          <div class="scanner-view" id="scanner-view">
            <div class="camera-placeholder" id="camera-placeholder">${icon("camera")}<p>Frame one leaf in the guide. Avoid shadows and busy backgrounds.</p></div>
            <video id="camera-video" playsinline muted hidden aria-label="Live camera preview"></video>
            <img class="preview-image" id="selected-preview" alt="Selected leaf photo preview" hidden />
            <span class="guide-frame" aria-hidden="true"></span><button class="grid-toggle" id="grid-toggle" type="button" aria-label="Toggle grid" title="Toggle grid" aria-pressed="false">${icon("grid")}</button><span class="scan-label">Place one leaf inside the frame</span>
          </div>
          <div class="scanner-controls">
            <button class="control-icon" id="start-camera" type="button">${icon("camera")} <span>Camera</span></button>
            <button class="shutter-button" id="capture-photo" type="button" hidden aria-label="Take photo">${icon("scan")}</button>
            <label class="file-label" for="leaf-file">${icon("upload")} Upload photo</label>
            <input class="file-input" id="leaf-file" type="file" accept="image/jpeg,image/png" capture="environment" />
            <span class="spacer"></span>
            <button class="control-icon" id="rotate-photo" type="button" disabled aria-label="Rotate photo">${icon("rotate")} Rotate</button>
            <button class="control-icon" id="clear-photo" type="button" disabled aria-label="Clear photo">${icon("close")} Clear</button>
            ${
              allowBatch
                ? `<button class="button button-secondary" id="add-to-batch" type="button" disabled style="margin-right:8px;">+ Add Leaf (<span id="batch-count">0</span>/5)</button>`
                : ""
            }
            <button class="button" id="analyze-photo" type="button" disabled>${t("scan", state.settings.language)} ${icon("scan")}</button>
          </div>

          ${
            allowBatch
              ? `
            <div id="batch-strip" class="batch-strip" style="display:flex; gap:10px; padding:12px; margin-top:12px; border-top:1px solid var(--border, #eee); overflow-x:auto; min-height:48px;" hidden>
              <div style="font-size:0.85rem; color:var(--text-muted, #777); display:flex; align-items:center;">Multi-leaf queue:</div>
              <div id="batch-thumbnails" style="display:flex; gap:10px; align-items:center;"></div>
            </div>
          `
              : ""
          }

          <div class="upload-drop" id="upload-drop" tabindex="0">Or drag and drop a JPG or PNG here</div>
        </section>
        <aside class="side-stack">
          <section class="card quality-panel" aria-live="polite" aria-atomic="true">
            <h3>${icon("checkCircle")} Photo quality check</h3>
            <ul class="quality-list" id="quality-feedback"><li class="quality-item">${icon("check")} Ready when you are — good light and a steady hand help.</li></ul>
          </section>
          <section class="card quality-panel">
            <h3>${icon("leaf")} What are you scanning?</h3>
            <label class="field" for="crop-choice"><span class="sr-only">Crop hint</span>
              <select class="crop-select" id="crop-choice"><option value="">Let Fieldnote identify it</option><option>Maize</option><option>Tomato</option><option>Potato</option></select>
            </label>
            <label class="field" for="plant-id"><span>Plant label <span class="severity-meta">optional, for tracking</span></span><input class="form-control" id="plant-id" maxlength="40" placeholder="e.g. North plot · Plant 4" /></label>
            <label class="field" for="zoom-range"><span>Crop closer <span id="zoom-value">1.0×</span></span><input class="range-control" id="zoom-range" type="range" min="1" max="2.4" step="0.1" value="1" /></label>
          </section>
          <section class="card tip-card"><h3>How to take a good photo</h3><ul><li>Choose a single leaf, close enough to see detail.</li><li>Use soft daylight; avoid glare and deep shade.</li><li>Hold still and keep the leaf in focus.</li></ul></section>
          <p class="severity-meta">Supported crops: maize, tomato and potato. A scan is guidance, not a confirmed diagnosis.</p>
        </aside>
      </div>
    </div></section>`;

  const video = root.querySelector("#camera-video");
  const placeholder = root.querySelector("#camera-placeholder");
  const preview = root.querySelector("#selected-preview");
  const quality = root.querySelector("#quality-feedback");
  const fileInput = root.querySelector("#leaf-file");
  const startCamera = root.querySelector("#start-camera");
  const captureButton = root.querySelector("#capture-photo");
  const analyzeButton = root.querySelector("#analyze-photo");
  const clearButton = root.querySelector("#clear-photo");
  const rotateButton = root.querySelector("#rotate-photo");
  const dropZone = root.querySelector("#upload-drop");
  const cropChoice = root.querySelector("#crop-choice");
  const zoomRange = root.querySelector("#zoom-range");
  const addToBatchBtn = root.querySelector("#add-to-batch");
  const batchStrip = root.querySelector("#batch-strip");
  const batchThumbnails = root.querySelector("#batch-thumbnails");
  const batchCountSpan = root.querySelector("#batch-count");
  const plantIdInput = root.querySelector("#plant-id");
  const zoomValue = root.querySelector("#zoom-value");
  const gridToggle = root.querySelector("#grid-toggle");
  const scannerView = root.querySelector("#scanner-view");
  if (!video || !placeholder || !preview || !quality || !fileInput || !startCamera || !captureButton || !analyzeButton || !clearButton || !rotateButton || !dropZone || !cropChoice || !zoomRange || !plantIdInput) return () => {};

  let camera = null;
  let selectedBlob = null;
  let selectedFile = null;
  let rotation = 0;
  let zoom = 1;
  let previewUrl = null;
  let photoRevision = 0;
  const batchLeaves = [];

  gridToggle?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const enabled = button.getAttribute("aria-pressed") !== "true";
    button.setAttribute("aria-pressed", String(enabled));
    scannerView?.classList.toggle("show-grid", enabled);
  });

  function updateBatchUI() {
    if (!allowBatch) return;
    if (batchLeaves.length > 0) {
      batchStrip.hidden = false;
      batchCountSpan.textContent = String(batchLeaves.length);
      batchThumbnails.innerHTML = batchLeaves
        .map(
          (item, idx) => `
        <div style="position:relative; width:48px; height:48px; border-radius:6px; overflow:hidden; border:2px solid var(--primary, #2d6a4f); flex-shrink:0;">
          <img src="${item.dataUrl}" style="width:100%; height:100%; object-fit:cover;" alt="Leaf ${idx + 1}" />
          <button type="button" class="remove-batch-leaf" data-idx="${idx}" style="position:absolute; top:0; right:0; background:rgba(0,0,0,0.6); color:white; border:none; width:16px; height:16px; font-size:10px; cursor:pointer; line-height:1; display:flex; align-items:center; justify-content:center;">×</button>
        </div>
      `,
        )
        .join("");

      analyzeButton.disabled = false;
      analyzeButton.innerHTML = `${t("scan", state.settings.language)} (${batchLeaves.length} leaves) ${icon("scan")}`;

      batchThumbnails.querySelectorAll(".remove-batch-leaf").forEach((btn) => {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          const idx = Number(btn.dataset.idx);
          batchLeaves.splice(idx, 1);
          updateBatchUI();
        });
      });
    } else {
      batchStrip.hidden = true;
      batchCountSpan.textContent = "0";
      analyzeButton.innerHTML = `${t("scan", state.settings.language)} ${icon("scan")}`;
      if (!selectedBlob) analyzeButton.disabled = true;
    }
  }

  function showQuality(value) {
    const items = value.issues.length ? value.issues : ["Looks good — leaf detail is visible."];
    quality.innerHTML = items
      .map(
        (message) =>
          `<li class="quality-item${value.issues.length ? " warning" : ""}">${icon(value.issues.length ? "alert" : "checkCircle")}<span>${message}</span></li>`,
      )
      .join("");
  }

  async function setPhoto(file) {
    if (!file || !["image/jpeg", "image/png"].includes(file.type)) {
      toast("Please choose a JPG or PNG image.", true);
      return;
    }
    const revision = ++photoRevision;
    state.clearImage();
    camera?.stop();
    camera = null;
    selectedBlob = file;
    selectedFile = file;
    rotation = 0;
    zoom = 1;
    if (zoomRange) zoomRange.value = "1";
    if (zoomValue) zoomValue.textContent = "1.0\u00d7";
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    preview.style.transform = "none";
    preview.onload = () => showQuality(inspectCanvas(preview));
    preview.src = previewUrl;
    preview.hidden = false;
    video.hidden = true;
    placeholder.hidden = true;
    startCamera.hidden = false;
    captureButton.hidden = true;
    analyzeButton.disabled = batchLeaves.length === 0;
    clearButton.disabled = false;
    rotateButton.disabled = false;
    if (addToBatchBtn) addToBatchBtn.disabled = batchLeaves.length >= 5;
    const dataUrl = await blobDataUrl(file);
    if (revision !== photoRevision || !root.isConnected) return;
    state.setImage(file, dataUrl);
    analyzeButton.disabled = false;
  }

  if (addToBatchBtn) {
    addToBatchBtn.addEventListener("click", async () => {
      if (!selectedBlob || batchLeaves.length >= 5) return;
      const upload = await prepareImage(selectedBlob, rotation, zoom);
      const dataUrl = await blobDataUrl(upload);
      batchLeaves.push({ file: upload, dataUrl });
      toast(`Added Leaf ${batchLeaves.length} to batch queue`);
      updateBatchUI();

      // Reset preview for next leaf
      selectedBlob = null;
      selectedFile = null;
      photoRevision += 1;
      state.clearImage();
      rotation = 0;
      zoom = 1;
      if (zoomRange) zoomRange.value = "1";
      if (zoomValue) zoomValue.textContent = "1.0\u00d7";
      preview.style.transform = "none";
      preview.hidden = true;
      placeholder.hidden = false;
      rotateButton.disabled = true;
      addToBatchBtn.disabled = true;
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = null;
      if (fileInput) fileInput.value = "";
    });
  }

  startCamera.addEventListener("click", async () => {
    try {
      photoRevision += 1;
      state.clearImage();
      selectedBlob = null;
      selectedFile = null;
      rotation = 0;
      zoom = 1;
      if (zoomRange) zoomRange.value = "1";
      if (zoomValue) zoomValue.textContent = "1.0\u00d7";
      preview.style.transform = "none";
      analyzeButton.disabled = batchLeaves.length === 0;
      clearButton.disabled = true;
      rotateButton.disabled = true;
      if (addToBatchBtn) addToBatchBtn.disabled = true;
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = null;
      preview.hidden = true;
      video.hidden = false;
      placeholder.hidden = true;
      camera = new CameraController(video, showQuality);
      await camera.start();
      startCamera.hidden = true;
      captureButton.hidden = false;
      preview.hidden = true;
      if (navigator.vibrate) navigator.vibrate(12);
    } catch (error) {
      video.hidden = true;
      placeholder.hidden = false;
      console.error("Camera start failed", error);
      toast("Camera permission was not available. Upload a photo instead.");
    }
  });

  captureButton.addEventListener("click", async () => {
    try {
      const blob = await camera.capture();
      if (blob) await setPhoto(new File([blob], "fieldnote-camera.jpg", { type: "image/jpeg" }));
    } catch (error) {
      console.error("Photo capture failed", error);
      toast("Something went wrong. Please try again.");
    }
  });

  fileInput.addEventListener("change", (event) => setPhoto(event.currentTarget.files?.[0]));
  dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragover");
    setPhoto(event.dataTransfer.files?.[0]);
  });
  dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });
  rotateButton.addEventListener("click", () => {
    rotation = (rotation + 90) % 360;
    preview.style.transform = `rotate(${rotation}deg) scale(${zoom})`;
  });
  zoomRange.addEventListener("input", () => {
    zoom = Number(zoomRange?.value ?? 1);
    if (zoomValue) zoomValue.textContent = `${zoom.toFixed(1)}\u00d7`;
    preview.style.transform = `rotate(${rotation}deg) scale(${zoom})`;
  });
  clearButton.addEventListener("click", () => {
    photoRevision += 1;
    state.clearImage();
    selectedBlob = null;
    selectedFile = null;
    rotation = 0;
    zoom = 1;
    if (zoomRange) zoomRange.value = "1";
    if (zoomValue) zoomValue.textContent = "1.0\u00d7";
    preview.style.transform = "none";
    preview.hidden = true;
    placeholder.hidden = false;
    clearButton.disabled = true;
    rotateButton.disabled = true;
    if (addToBatchBtn) addToBatchBtn.disabled = true;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    if (fileInput) fileInput.value = "";
    showQuality({ issues: [] });
    if (batchLeaves.length === 0) analyzeButton.disabled = true;
  });

  analyzeButton.addEventListener("click", async () => {
    if (!root.isConnected || (batchLeaves.length === 0 && (!selectedBlob || !selectedFile))) return;
    analyzeButton.disabled = true;
    camera?.stop();
    window.location.hash = "#/analyzing";
    let progressStep = 0;
    const progressTimer = window.setInterval(() => {
      progressStep = Math.min(3, progressStep + 1);
      advanceAnalysis(progressStep);
    }, 850);

    try {
      if (batchLeaves.length > 0) {
        // Multi-leaf batch mode
        if (selectedBlob) {
          const extra = await prepareImage(selectedBlob, rotation, zoom);
          const extraUrl = await blobDataUrl(extra);
          batchLeaves.push({ file: extra, dataUrl: extraUrl });
        }
        const files = batchLeaves.map((l) => l.file);
        const batchResponse = await sendBatchPredict(files, state.settings.language);

        // Format combined state
        const verdict = batchResponse.verdict;
        const result = {
          isBatch: true,
          status: verdict.status,
          top3: [
            {
              label: verdict.final_verdict_label,
              crop: verdict.crop,
              disease: verdict.disease,
              probability: verdict.aggregated_confidence,
            },
          ],
          calibrated_confidence: verdict.aggregated_confidence,
          decision_reason: `Batch aggregated verdict from ${verdict.total_leaves} leaves (${verdict.majority_vote_label === verdict.confidence_weighted_label ? "Consensus agreement" : "Weighted confidence winner"}).`,
          severity: {
            percent: 12.0,
            category: "Moderate",
            confidence: 0.85,
            uncertainty_percent: 4.0,
            method: "batch_aggregated",
            conflicting_signals: false,
          },
          advice: verdict.advice,
          batch_details: batchResponse,
          model_version: batchResponse.model_version,
          request_id: batchResponse.batch_id,
        };

        state.setResult(result);
        state.setImage(batchLeaves[0].file, batchLeaves[0].dataUrl);

        const id = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const item = {
          id,
          date: Date.now(),
          crop: verdict.crop,
          plantId: plantIdInput?.value?.trim() || "Unassigned",
          disease: verdict.disease,
          result,
          image: batchLeaves[0].dataUrl,
        };
        if (state.settings.privacy) await saveScan(item);
        if (navigator.vibrate) navigator.vibrate([20, 30, 20]);
        window.location.hash = "#/results";
      } else {
        // Single leaf mode
        if (!selectedBlob || !selectedFile) return;
        const upload = await prepareImage(selectedBlob, rotation, zoom);
        const imageUrl = await blobDataUrl(upload);
        state.setImage(upload, imageUrl);
        const result = await predict(upload, {
          crop: cropChoice?.value || undefined,
          language: state.settings.language,
        });
        state.setResult(result);
        const id = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const item = {
          id,
          date: Date.now(),
          crop: result.top3?.[0]?.crop || cropChoice?.value || "Unknown",
          plantId: plantIdInput?.value?.trim() || "Unassigned",
          disease: result.top3?.[0]?.disease || "No diagnosis",
          result,
          image: imageUrl,
        };
        if (state.settings.privacy) await saveScan(item);
        if (navigator.vibrate) navigator.vibrate([20, 30, 20]);
        window.location.hash = "#/results";
      }
    } catch (error) {
      window.location.hash = "#/scan";
      console.error("Scan submission failed", error);
      toast("Something went wrong. Please try again.");
      analyzeButton.disabled = false;
    } finally {
      window.clearInterval(progressTimer);
    }
  });

  const cropFromLink = new URLSearchParams(window.location.hash.split("?")[1] || "").get("crop");
  if (cropFromLink && cropChoice) cropChoice.value = cropFromLink;
  return () => {
    photoRevision += 1;
    camera?.stop();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  };
}
