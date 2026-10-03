import { t } from "../i18n.js";
import { icon } from "../components/ui.js";

/** @param {HTMLElement} root */
export async function adminAnalyticsPage(root) {
  root.innerHTML = `
    <section class="page-shell">
      <div class="container">
        <header class="page-header">
          <div>
            <span class="eyebrow">Privacy-First Telemetry</span>
            <h1>${t("admin_analytics_title", "Analytics & Model Health Dashboard")}</h1>
            <p>Aggregated telemetry monitoring scan volumes, pathogen spread, inference confidence, and distribution drift. Zero PII stored.</p>
          </div>
          <div>
            <button type="button" class="button button-secondary button-small" id="refresh-analytics">
              ${icon("refresh")} Refresh
            </button>
          </div>
        </header>

        <div id="analytics-content">
          <div class="card" style="text-align:center; padding: 40px;">
            <p>Loading analytics metrics...</p>
          </div>
        </div>
      </div>
    </section>
  `;

  async function loadData() {
    const container = root.querySelector("#analytics-content");
    if (!container) return;

    try {
      const res = await fetch("./api/v1/admin/analytics/summary");
      if (!res.ok) throw new Error("Could not load analytics summary");
      const data = await res.json();

      const confPct = Math.round(data.average_confidence * 100);

      // Render Dashboard
      container.innerHTML = `
        ${
          data.drift_alert
            ? `
          <div class="card" style="border-left: 4px solid #d32f2f; background: #fff5f5; margin-bottom: 24px; padding: 16px 20px;">
            <div style="display:flex; align-items:center; gap: 12px;">
              <span style="font-size: 1.5rem;">⚠️</span>
              <div>
                <strong style="color: #c62828; display:block; font-size: 1.05rem;">Model Drift Alert Triggered</strong>
                <p style="margin: 4px 0 0; font-size: 0.9rem; color: #555;">${data.drift_message}</p>
              </div>
            </div>
          </div>
        `
            : ""
        }

        <!-- 4 KPI Cards -->
        <div class="grid grid-4" style="gap: 16px; margin-bottom: 24px;">
          <div class="card" style="padding: 18px;">
            <small style="color: var(--text-muted, #777); font-weight:600; text-transform:uppercase; font-size: 0.75rem;">Total Scans</small>
            <div style="font-size: 2rem; font-weight: 700; color: var(--primary, #2d6a4f); margin-top: 4px;">${data.total_scans}</div>
            <div style="font-size: 0.8rem; color: var(--text-muted, #888); margin-top: 2px;">Recorded anonymized scans</div>
          </div>

          <div class="card" style="padding: 18px;">
            <small style="color: var(--text-muted, #777); font-weight:600; text-transform:uppercase; font-size: 0.75rem;">Average Confidence</small>
            <div style="font-size: 2rem; font-weight: 700; color: #1976d2; margin-top: 4px;">${confPct}%</div>
            <div style="font-size: 0.8rem; color: var(--text-muted, #888); margin-top: 2px;">Across all candidate classes</div>
          </div>

          <div class="card" style="padding: 18px;">
            <small style="color: var(--text-muted, #777); font-weight:600; text-transform:uppercase; font-size: 0.75rem;">Rejection Rate</small>
            <div style="font-size: 2rem; font-weight: 700; color: ${data.rejection_rate_percent > 20 ? "#e53935" : "#388e3c"}; margin-top: 4px;">
              ${data.rejection_rate_percent}%
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted, #888); margin-top: 2px;">Retakes + unsupported leaves</div>
          </div>

          <div class="card" style="padding: 18px;">
            <small style="color: var(--text-muted, #777); font-weight:600; text-transform:uppercase; font-size: 0.75rem;">Drift Status</small>
            <div style="font-size: 1.5rem; font-weight: 700; color: ${data.drift_alert ? "#d32f2f" : "#2e7d32"}; margin-top: 8px;">
              ${data.drift_alert ? "⚠️ Drift Detected" : "✔ Healthy"}
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted, #888); margin-top: 2px;">Rolling baseline comparison</div>
          </div>
        </div>

        <!-- 2 Chart Cards -->
        <div class="grid grid-2" style="gap: 24px;">
          <!-- Scans per Day Chart -->
          <div class="card">
            <span class="eyebrow">${t("analytics_scans_day", "Scans per day")}</span>
            <h3 style="margin: 4px 0 16px;">Daily Activity Trend</h3>
            <div style="height: 220px; width: 100%; display: flex; align-items: flex-end; gap: 12px; padding-bottom: 24px; border-bottom: 1px solid var(--border, #eee); box-sizing: border-box;">
              ${renderDailyBars(data.scans_past_7_days)}
            </div>
          </div>

          <!-- Class Distribution Chart -->
          <div class="card">
            <span class="eyebrow">${t("analytics_class_dist", "Class distribution")}</span>
            <h3 style="margin: 4px 0 16px;">Identified Conditions</h3>
            <div style="display:flex; flex-direction:column; gap: 10px;">
              ${renderClassBars(data.class_distribution)}
            </div>
          </div>
        </div>
      `;
    } catch (err) {
      container.innerHTML = `<div class="card" style="color:red;">Error loading dashboard: ${err.message}</div>`;
    }
  }

  function renderDailyBars(daysDict) {
    const entries = Object.entries(daysDict);
    const maxVal = Math.max(...Object.values(daysDict), 1);

    return entries
      .map(([date, count]) => {
        const heightPct = Math.round((count / maxVal) * 85) + 10;
        const shortDate = date.slice(5);
        return `
          <div style="flex:1; display:flex; flex-direction:column; align-items:center; height:100%; justify-content:flex-end;">
            <div style="font-size:0.75rem; font-weight:700; margin-bottom:4px; color:var(--text, #333);">${count}</div>
            <div style="width:100%; height:${heightPct}%; background:linear-gradient(180deg, #40916c, #1b4332); border-radius:4px 4px 0 0; min-height: 4px;"></div>
            <span style="font-size:0.7rem; color:var(--text-muted, #777); margin-top:6px;">${shortDate}</span>
          </div>
        `;
      })
      .join("");
  }

  function renderClassBars(classDict) {
    const sorted = Object.entries(classDict).sort((a, b) => b[1] - a[1]);
    const maxVal = Math.max(...Object.values(classDict), 1);

    return sorted
      .slice(0, 6)
      .map(([cls, count]) => {
        const cleanName = cls.replace(/_/g, " ");
        const widthPct = Math.round((count / maxVal) * 100);
        return `
          <div>
            <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom: 2px;">
              <span><strong>${cleanName}</strong></span>
              <span>${count} scans</span>
            </div>
            <div style="background: var(--surface-alt, #eee); height: 8px; border-radius: 4px; overflow:hidden;">
              <div style="background: var(--primary, #2d6a4f); width: ${widthPct}%; height:100%; border-radius: 4px;"></div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  root.querySelector("#refresh-analytics")?.addEventListener("click", loadData);
  loadData();
}
