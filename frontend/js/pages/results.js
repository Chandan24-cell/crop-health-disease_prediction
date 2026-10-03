import { confidenceRing } from "../charts.js";
import { escapeHtml, icon, statusCopy, toast } from "../components/ui.js";
import { getScans } from "../db.js";
import { escalateViaEmail, escalateViaWhatsApp } from "../escalation.js";
import { isEnabled } from "../feature-flags.js";
import { isSpeaking, speak, stopSpeaking, t } from "../i18n.js";
import { generatePdfReport } from "../report.js";
import { state } from "../state.js";
import { fetchWeatherRisk, getUserLocation } from "../weather.js";

/** Build a safe base64 data URL from API image bytes. @param {string|null|undefined} value @param {string} [mime] @returns {string} */
function imageSource(value, mime = "image/png") {
  return value ? `data:${mime};base64,${String(value).replace(/[^a-zA-Z0-9+/=]/g, "")}` : "";
}

/** Composite a red lesion mask and pale leaf outline over the original photo. @param {string} originalUrl @param {string} maskUrl @param {string|null} outlineUrl @returns {Promise<string|null>} */
async function lesionOverlay(originalUrl, maskUrl, outlineUrl) {
  if (!originalUrl || !maskUrl) return null;
  const load = (src) =>
    new Promise((resolve) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => resolve(null);
      image.src = src;
    });
  const [original, mask, outline] = await Promise.all([
    load(originalUrl),
    load(maskUrl),
    outlineUrl ? load(outlineUrl) : null,
  ]);
  if (!original || !mask) return null;
  const canvas = document.createElement("canvas");
  canvas.width = original.naturalWidth;
  canvas.height = original.naturalHeight;
  const context = canvas.getContext("2d");
  context.drawImage(original, 0, 0);
  const maskCanvas = document.createElement("canvas");
  maskCanvas.width = canvas.width;
  maskCanvas.height = canvas.height;
  const maskContext = maskCanvas.getContext("2d");
  maskContext.drawImage(mask, 0, 0, canvas.width, canvas.height);
  const pixels = maskContext.getImageData(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < pixels.data.length; i += 4) {
    const active = pixels.data[i] > 90;
    pixels.data[i] = 201;
    pixels.data[i + 1] = 58;
    pixels.data[i + 2] = 72;
    pixels.data[i + 3] = active ? 145 : 0;
  }
  maskContext.putImageData(pixels, 0, 0);
  context.drawImage(maskCanvas, 0, 0);
  if (outline) {
    maskContext.clearRect(0, 0, canvas.width, canvas.height);
    maskContext.drawImage(outline, 0, 0, canvas.width, canvas.height);
    const outlinePixels = maskContext.getImageData(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < outlinePixels.data.length; i += 4) {
      const active = outlinePixels.data[i] > 90;
      outlinePixels.data[i] = 216;
      outlinePixels.data[i + 1] = 243;
      outlinePixels.data[i + 2] = 220;
      outlinePixels.data[i + 3] = active ? 230 : 0;
    }
    maskContext.putImageData(outlinePixels, 0, 0);
    context.drawImage(maskCanvas, 0, 0);
  }
  return canvas.toDataURL("image/png");
}

/** Render the latest scan dashboard and connect result interactions. @param {HTMLElement} root @returns {Promise<void>} */
export async function resultsPage(root) {
  let result = state.currentResult;
  let image = state.currentImageUrl;
  if (!result) {
    const scans = await getScans();
    result = scans[0]?.result;
    image = scans[0]?.image;
  }
  if (!result) {
    root.innerHTML = `<section class="page-shell container"><div class="empty-state"><span class="empty-icon">${icon("scan")}</span><h2>No scan to show yet</h2><p>Take a photo of a supported leaf and your result will appear here.</p><a class="button" href="#/scan">Scan a leaf ${icon("scan")}</a></div></section>`;
    return;
  }
  const best = result.top3?.[0] || {};
  const status = statusCopy(result.status);
  status.title = t(result.status, state.settings.language);
  const severity = result.severity || {};
  const confidence = Number(result.calibrated_confidence || 0);
  const topRows = (result.top3 || [])
    .map(
      (item) => `
    <div class="prediction-row"><span class="prediction-name">${escapeHtml(item.crop)} · ${escapeHtml(item.disease)}</span><span class="prediction-value">${Math.round(Number(item.probability) * 100)}%</span><div class="prediction-track"><div class="prediction-fill" style="width:${Math.max(0, Math.min(100, Number(item.probability) * 100))}%"></div></div></div>`,
    )
    .join("");
  const category = String(severity.category || "Not assessed");
  const categoryClass =
    category === "Severe" ? "chip-severe" : category === "Moderate" ? "chip-moderate" : "";
  const resultReason = String(result.decision_reason || "");
  const advice = result.advice || {};

  const adviceSections = [
    ["Immediate actions", advice.immediate_actions || advice.specific_advice],
    ["Cultural controls", advice.cultural_controls],
    ["Prevention", advice.prevention],
    [
      "Chemical options · local label first",
      advice.chemical_options ||
        "Only use products registered for your crop and location. Ask your local extension officer; registration and permitted products vary.",
    ],
    [
      "Safety",
      advice.safety_note ||
        "Follow the product label, use the recommended protective equipment, and keep people and animals away during application.",
    ],
    [
      "When to seek an expert",
      advice.when_to_seek_expert ||
        "Contact a local agricultural extension officer if symptoms spread, affect new growth, or you are unsure about treatment.",
    ],
  ];

  const adviceMarkup = adviceSections
    .map(
      ([title, copy], index) =>
        `<details${index === 0 ? " open" : ""}><summary>${escapeHtml(title)}</summary><p>${escapeHtml(copy || "No specific guidance is available for this result.")}</p>${String(title).startsWith("Chemical") ? `<p><strong>CIB&amp;RC note:</strong> Verify current registration and permitted use against the current CIB&amp;RC label. Ask your State Agriculture Department or KVK for expert help.</p>` : ""}</details>`,
    )
    .join("");

  const originalSource = image || "";
  const gradSource = imageSource(result.gradcam_png_b64);
  const maskSource = imageSource(severity.lesion_mask_png_b64);
  const outlineSource = imageSource(severity.leaf_outline_png_b64);

  // Check feature flags
  const showBatchDetails = result.isBatch && result.batch_details;
  const showWeather = isEnabled("weather_risk");
  const showTreatment = isEnabled("treatment_planner");
  const showFeedback = isEnabled("feedback_loop");
  const showEscalation = isEnabled("expert_escalation");
  const showVoice = isEnabled("multilingual");

  root.innerHTML = `
    <section class="page-shell"><div class="container">
      <header class="page-header">
        <div>
          <span class="eyebrow"><span class="eyebrow-dot"></span> Scan result</span>
          <h1>Your leaf, understood a little better.</h1>
          <p>Use this as a careful guide. If the signs do not match what you see in the field, ask a local crop expert.</p>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          ${
            showVoice
              ? `<button type="button" class="button button-secondary button-small" id="btn-read-aloud">
                  ${icon("bell")} <span id="read-aloud-text">${t("voice_read_aloud", "Read aloud")}</span>
                 </button>`
              : ""
          }
          <a class="button button-secondary button-small" href="#/scan">${icon("scan")} New scan</a>
        </div>
      </header>

      ${
        showBatchDetails
          ? `
        <div class="card" style="border-left: 4px solid var(--primary, #2d6a4f); background: var(--surface-alt, #f7faf7); margin-bottom: 20px; padding: 18px 22px;">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
            <div>
              <span class="badge" style="background:#e8f5e9; color:#2e7d32; font-weight:700;">Multi-Leaf Aggregated Verdict</span>
              <h3 style="margin:6px 0 2px; font-size:1.3rem;">${escapeHtml(result.batch_details.verdict.disease)} (${result.batch_details.verdict.crop})</h3>
              <p style="margin:0; font-size:0.88rem; color:var(--text-muted, #666);">
                Analyzed <strong>${result.batch_details.verdict.total_leaves} leaves</strong> of this plant. Majority vote: <em>${result.batch_details.verdict.majority_vote_label.replace(/_/g, " ")}</em>.
              </p>
            </div>
            <span class="chip chip-moderate" style="font-size:0.95rem;">Plant Confidence: ${Math.round(result.batch_details.verdict.aggregated_confidence * 100)}%</span>
          </div>

          <div style="display:flex; gap:12px; margin-top:14px; overflow-x:auto; padding-bottom:6px;">
            ${(result.batch_details.leaves || [])
              .map(
                (leaf) => `
              <div class="card" style="padding:10px; min-width:130px; font-size:0.8rem; background:white; flex-shrink:0;">
                <strong>Leaf ${leaf.leaf_index}</strong>
                <div style="color:var(--primary, #2d6a4f); font-weight:600; margin:2px 0;">${leaf.prediction.top3?.[0]?.disease || "Unknown"}</div>
                <div style="color:var(--text-muted, #777);">${Math.round((leaf.prediction.calibrated_confidence || 0) * 100)}% conf</div>
              </div>
            `,
              )
              .join("")}
          </div>
        </div>
      `
          : ""
      }

      <div class="status-banner status-${escapeHtml(status.cls)}" role="status">
        <span class="status-icon">${icon(status.icon)}</span>
        <div>
          <h2>${escapeHtml(status.title)}</h2>
          <p>${escapeHtml(resultReason)}</p>
          ${severity.conflicting_signals ? `<p><strong>Conflicting signals:</strong> classifier and visible lesion estimate disagree. Treat this result as uncertain.</p>` : ""}
        </div>
      </div>

      <!-- Weather Risk Card -->
      ${
        showWeather
          ? `
        <div class="card" id="weather-risk-card" style="margin-bottom: 20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:14px;">
          <div>
            <span class="eyebrow" style="color:var(--accent, #d32f2f);">${t("weather_title", "Local Blight Risk")}</span>
            <h3 style="margin:4px 0 2px;" id="weather-risk-headline">Assessing local weather risk...</h3>
            <p style="margin:0; font-size:0.88rem; color:var(--text-muted, #666);" id="weather-risk-desc">Fetching regional humidity and precipitation...</p>
          </div>
          <div id="weather-risk-badge">
            <button type="button" class="button button-secondary button-small" id="btn-load-weather">
              ${icon("location")} Check My Field
            </button>
          </div>
        </div>
      `
          : ""
      }

      <div class="result-grid">
        <section class="card diagnosis-card">
          <div class="diagnosis-top">
            <div class="diagnosis-title">
              <span class="eyebrow">Most likely match</span>
              <h2>${escapeHtml(best.crop || "Unknown")} ${escapeHtml(best.disease || "")}</h2>
              <p>${escapeHtml(best.label || "")}</p>
            </div>
            ${confidenceRing(confidence, "calibrated")}
          </div>
          <div class="prediction-list" aria-label="Top possible diagnoses">
            ${topRows || `<p>No supported diagnosis was returned.</p>`}
          </div>
          <p class="severity-meta" style="margin:16px 0 0">Confidence is calibrated against validation data; it is not a guarantee of diagnosis.</p>

          ${
            showTreatment
              ? `
            <div style="margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--border, #eee);">
              <a href="#/treatment" class="button button-primary" style="width:100%; display:inline-block; text-align:center;">
                ${icon("treatment")} Open Treatment &amp; Safety Planner
              </a>
            </div>
          `
              : ""
          }
        </section>

        <section class="card severity-card">
          <h3>Visible leaf impact</h3>
          <div>
            <span class="chip ${categoryClass}">${escapeHtml(category)}</span>
            <p class="severity-meta" style="margin:8px 0 0">Based on segmented leaf tissue</p>
          </div>
          <div class="severity-meter">
            <div class="severity-meter-track"></div>
            <div class="severity-marker" style="--severity:${Math.max(0, Math.min(100, Number(severity.percent || 0)))}%"></div>
            <strong class="severity-value">${Number(severity.percent || 0).toFixed(1)}%</strong>
          </div>
          <p class="severity-meta">
            Estimate confidence ${Math.round(Number(severity.confidence || 0) * 100)}% · ±${Number(severity.uncertainty_percent || 0).toFixed(1)} points<br />
            Method: ${escapeHtml(severity.method || "not available")}
          </p>
        </section>
      </div>

      <section class="card visual-card">
        <div class="visual-header">
          <div>
            <h3 style="margin:0">What the scan noticed</h3>
            <p class="severity-meta" style="margin:5px 0 0">Compare the original with the model’s visual cues.</p>
          </div>
          <div class="segmented-control" role="group" aria-label="Choose analysis overlay">
            <button type="button" data-overlay="gradcam" aria-pressed="true" ${gradSource ? "" : "disabled"}>AI focus</button>
            <button type="button" data-overlay="lesion" aria-pressed="false" ${maskSource ? "" : "disabled"}>Leaf severity</button>
            <button type="button" data-overlay="original" aria-pressed="false">Original</button>
          </div>
        </div>
        <div class="image-compare" id="image-compare">
          <span class="image-caption left">Analysis cue</span>
          <span class="image-caption right">Original</span>
          <img id="compare-base" src="${escapeHtml(originalSource)}" alt="Original uploaded leaf photo" />
          <div class="compare-overlay" id="compare-overlay">
            <img id="compare-top" src="${escapeHtml(gradSource || originalSource)}" alt="AI focus heatmap overlay on the leaf photo" />
          </div>
          <span class="compare-handle" aria-hidden="true">↔</span>
          <input class="compare-range" type="range" min="0" max="100" value="50" aria-label="Slide to compare analysis overlay and original image" />
        </div>
      </section>

      <section class="card visual-card">
        <div class="visual-header">
          <div>
            <h3 style="margin:0">Practical next steps</h3>
            <p class="severity-meta" style="margin:5px 0 0">Start with low-risk actions. Confirm any treatment locally.</p>
          </div>
        </div>
        <div class="advice-list">${adviceMarkup}</div>
      </section>

      <!-- Feedback Loop UI -->
      ${
        showFeedback
          ? `
        <section class="card" id="feedback-section" style="background: var(--surface-alt, #fafafa);">
          <div id="feedback-initial">
            <h3 style="margin:0 0 6px;">${t("feedback_question", "Was this diagnosis correct?")}</h3>
            <p style="margin:0 0 14px; font-size:0.88rem; color:var(--text-muted, #666);">
              Help improve accuracy for your community. Your feedback trains the next model release.
            </p>
            <div style="display:flex; gap:10px;">
              <button type="button" class="button button-secondary button-small" id="fb-btn-yes">
                ${icon("check")} ${t("feedback_yes", "Yes, correct")}
              </button>
              <button type="button" class="button button-secondary button-small" id="fb-btn-no">
                ${icon("close")} ${t("feedback_no", "No, incorrect")}
              </button>
            </div>
          </div>

          <div id="feedback-correction" hidden style="margin-top:14px; border-top:1px solid var(--border, #eee); padding-top:14px;">
            <label style="display:block; font-size:0.88rem; font-weight:600; margin-bottom:6px;">
              ${t("feedback_choose_label", "What is the correct diagnosis?")}
            </label>
            <select id="fb-correct-label" class="form-control" style="margin-bottom:12px; max-width:320px;">
              <option value="Tomato_Early_blight">Tomato · Early blight</option>
              <option value="Tomato_Late_blight">Tomato · Late blight</option>
              <option value="Tomato_Leaf_Mold">Tomato · Leaf mold</option>
              <option value="Maize_Common_rust">Maize · Common rust</option>
              <option value="Maize_Gray_leaf_spot">Maize · Gray leaf spot</option>
              <option value="Maize_Northern_Leaf_Blight">Maize · Northern leaf blight</option>
              <option value="Potato_Early_blight">Potato · Early blight</option>
              <option value="Potato_Late_blight">Potato · Late blight</option>
              <option value="Healthy">Healthy leaf</option>
              <option value="Other">Other / Unknown</option>
            </select>

            <textarea id="fb-comment" class="form-control" placeholder="${t("feedback_comment", "Optional notes or symptoms observed...")}" style="height:65px; margin-bottom:12px;"></textarea>

            <label style="display:flex; align-items:center; gap:8px; font-size:0.85rem; cursor:pointer; margin-bottom:14px;">
              <input type="checkbox" id="fb-photo-consent" checked />
              <span>${t("feedback_photo_consent", "I consent to sharing this leaf photo for active-learning model retraining")}</span>
            </label>

            <button type="button" class="button button-primary button-small" id="fb-submit-correction">
              ${icon("upload")} ${t("feedback_submit", "Submit feedback")}
            </button>
          </div>

          <div id="feedback-thanks" hidden style="padding:10px 0; color:#2e7d32; font-weight:600;">
            ✔ ${t("feedback_thanks", "Thank you for helping improve crop health diagnostics!")}
          </div>
        </section>
      `
          : ""
      }

      <!-- Result Action Bar -->
      <div class="result-actions" style="flex-wrap:wrap;">
        <button type="button" class="button button-secondary" id="share-result">${icon("share")} Share summary</button>
        <button type="button" class="button button-secondary" id="download-pdf-btn">${icon("download")} Download PDF Report</button>
        ${
          showEscalation
            ? `
          <button type="button" class="button button-secondary" id="btn-escalate-wa" style="border-color:#25d366; color:#128c7e;">
            💬 Agronomist WhatsApp
          </button>
          <button type="button" class="button button-secondary" id="btn-escalate-email">
            ✉ Email Expert
          </button>
        `
            : ""
        }
      </div>

      <div style="margin-top:20px; text-align:center; font-size:0.85rem; color:var(--text-muted, #777);">
        <span>Fieldnote provides AI decision support, not guaranteed lab diagnosis.</span>
        <a href="#/limitations" style="margin-left:6px; color:var(--primary, #2d6a4f); text-decoration:underline;">Read limitations &amp; responsible use</a>
      </div>
    </div></section>`;

  const topOverlay = root.querySelector("#compare-top");
  let lesionUrl = null;
  if (originalSource && maskSource)
    lesionUrl = await lesionOverlay(originalSource, maskSource, outlineSource);

  const setOverlay = (mode) => {
    root
      .querySelectorAll("[data-overlay]")
      .forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.overlay === mode)));
    const source = mode === "gradcam" ? gradSource : mode === "lesion" ? lesionUrl : originalSource;
    topOverlay.src = source || originalSource;
    topOverlay.alt =
      mode === "gradcam"
        ? "Grad-CAM++ class activation heatmap overlay"
        : mode === "lesion"
          ? "Red highlighted lesion area within the segmented leaf"
          : "Original leaf photo";
    root.querySelector(".image-caption.left").textContent =
      mode === "gradcam" ? "AI focus" : mode === "lesion" ? "Lesion overlay" : "Original";
    root.querySelector("#compare-overlay").style.width =
      mode === "original" ? "0%" : `${root.querySelector(".compare-range").value}%`;
  };

  root
    .querySelectorAll("[data-overlay]")
    .forEach((button) => button.addEventListener("click", () => setOverlay(button.dataset.overlay)));
  const range = root.querySelector(".compare-range");
  range.addEventListener("input", () => {
    root.querySelector("#compare-overlay").style.width = `${range.value}%`;
    root.querySelector(".compare-handle").style.left = `${range.value}%`;
  });
  setOverlay(gradSource ? "gradcam" : lesionUrl ? "lesion" : "original");

  // Read Aloud handler
  const readBtn = root.querySelector("#btn-read-aloud");
  if (readBtn) {
    readBtn.addEventListener("click", () => {
      if (isSpeaking()) {
        stopSpeaking();
        root.querySelector("#read-aloud-text").textContent = t("voice_read_aloud", "Read aloud");
      } else {
        const speechText = `${best.crop || "Crop"} ${best.disease || "Issue"}. Severity: ${category}. Immediate advice: ${advice.immediate_actions || advice.specific_advice || "Monitor plants closely."} Safety note: ${advice.safety_note || "Wear protective gear."}`;
        speak(speechText, state.settings.language, () => {
          if (root.querySelector("#read-aloud-text")) {
            root.querySelector("#read-aloud-text").textContent = t("voice_read_aloud", "Read aloud");
          }
        });
        root.querySelector("#read-aloud-text").textContent = t("voice_stop", "Stop");
      }
    });
  }

  // Weather Risk loader
  const loadWeatherBtn = root.querySelector("#btn-load-weather");
  if (loadWeatherBtn) {
    async function updateWeather() {
      try {
        loadWeatherBtn.disabled = true;
        loadWeatherBtn.textContent = "Locating...";
        const pos = await getUserLocation();
        const weather = await fetchWeatherRisk(pos.latitude, pos.longitude);

        root.querySelector("#weather-risk-headline").textContent =
          `${weather.riskLevel} Blight Risk (${weather.temperature}°C · ${weather.humidity}% humidity)`;
        root.querySelector("#weather-risk-desc").textContent = weather.description;
        root.querySelector("#weather-risk-badge").innerHTML = `
          <span class="chip ${weather.riskLevel === "High" ? "chip-severe" : weather.riskLevel === "Moderate" ? "chip-moderate" : ""}" style="font-size:1rem; font-weight:700;">
            ${weather.riskLevel} Risk
          </span>
        `;
      } catch {
        root.querySelector("#weather-risk-headline").textContent = "Moderate Regional Risk (Default)";
        root.querySelector("#weather-risk-desc").textContent =
          "Location permission denied or unavailable. Standard seasonal vigilance advised.";
      }
    }
    loadWeatherBtn.addEventListener("click", updateWeather);
    // Auto load in background
    updateWeather();
  }

  // Feedback interactions
  const btnYes = root.querySelector("#fb-btn-yes");
  const btnNo = root.querySelector("#fb-btn-no");
  const correctionDiv = root.querySelector("#feedback-correction");
  const thanksDiv = root.querySelector("#feedback-thanks");
  const initialDiv = root.querySelector("#feedback-initial");

  if (btnYes) {
    btnYes.addEventListener("click", async () => {
      try {
        await fetch("./api/v1/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            request_id: result.request_id || "req-unknown",
            label: best.label || "Correct",
            comment: "User confirmed diagnosis as correct",
            photo_consent: false,
          }),
        });
        initialDiv.hidden = true;
        thanksDiv.hidden = false;
        toast("Thanks for confirming!");
      } catch {
        toast("Feedback recorded locally.");
      }
    });
  }

  if (btnNo) {
    btnNo.addEventListener("click", () => {
      correctionDiv.hidden = false;
    });
  }

  const submitCorrection = root.querySelector("#fb-submit-correction");
  if (submitCorrection) {
    submitCorrection.addEventListener("click", async () => {
      const chosen = root.querySelector("#fb-correct-label")?.value;
      const comment = root.querySelector("#fb-comment")?.value;
      const consent = root.querySelector("#fb-photo-consent")?.checked;

      try {
        await fetch("./api/v1/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            request_id: result.request_id || "req-unknown",
            label: chosen,
            comment,
            photo_consent: consent,
            image_b64: consent ? originalSource : null,
          }),
        });
        initialDiv.hidden = true;
        correctionDiv.hidden = true;
        thanksDiv.hidden = false;
        toast("Correction submitted to review queue!");
      } catch {
        toast("Feedback recorded.");
      }
    });
  }

  // PDF Generation handler
  root.querySelector("#download-pdf-btn")?.addEventListener("click", async () => {
    toast("Generating PDF report...");
    await generatePdfReport({
      result,
      imageUrl: originalSource,
      plantLabel: state.currentResult?.plantId || null,
    });
    toast("PDF report downloaded!");
  });

  // Expert escalation handlers
  root.querySelector("#btn-escalate-wa")?.addEventListener("click", () => {
    escalateViaWhatsApp({
      result,
      plantLabel: state.currentResult?.plantId,
    });
  });

  root.querySelector("#btn-escalate-email")?.addEventListener("click", () => {
    escalateViaEmail({
      result,
      plantLabel: state.currentResult?.plantId,
    });
  });

  root.querySelector("#share-result").addEventListener("click", async () => {
    const shareText = `${best.crop || "Leaf"}: ${best.disease || "scan result"} — ${Number(severity.percent || 0).toFixed(1)}% visible impact.`;
    try {
      if (navigator.share) await navigator.share({ title: "Fieldnote crop scan", text: shareText });
      else {
        await navigator.clipboard.writeText(shareText);
        toast("Result summary copied.");
      }
    } catch (error) {
      if (error.name !== "AbortError") toast("Sharing is not available here.", true);
    }
  });
}
