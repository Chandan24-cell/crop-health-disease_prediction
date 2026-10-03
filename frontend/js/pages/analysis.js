import { icon } from "../components/ui.js";
import { t } from "../i18n.js";
import { state } from "../state.js";

/** Render the progressive analysis state. @returns {string} */
export function analysisPage() {
  const steps = ["Quality check", "Diagnosis", "Severity", "Advice"];
  return `<section class="page-shell container"><div class="card analysis-card" role="status" aria-live="polite"><span class="analysis-icon">${icon("scan")}</span><span class="eyebrow">A moment for a careful look</span><h1 style="margin:12px auto;font-size:var(--text-xl)">${t("scanning", state.settings.language)}</h1><p class="severity-meta">We’re working through each step so you get a useful answer.</p><div class="progress-steps">${steps.map((step, index) => `<div class="progress-step ${index === 0 ? "active" : ""}" data-progress="${index}"><span class="step-dot">${index === 0 ? icon("check") : index + 1}</span><span>${step}</span></div>`).join("")}</div><div class="skeleton skeleton-line"></div><div class="skeleton skeleton-line" style="width:46%"></div></div></section>`;
}

/** @param {number} step */
export function advanceAnalysis(step) {
  document.querySelectorAll("[data-progress]").forEach((item) => {
    const index = Number(item.dataset.progress);
    item.classList.toggle("done", index < step);
    item.classList.toggle("active", index === step);
  });
}
