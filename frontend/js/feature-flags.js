/**
 * Feature flags — toggle each feature independently.
 * Set to `true` to enable, `false` to disable.
 * These are compile-time defaults; a future admin panel could override at runtime.
 */
export const FLAGS = {
  /** 1. PWA offline inference via ONNX Runtime Web */
  pwa_offline_inference: true,
  /** 2. Multilingual UI (en, sw, hi, ta) + voice read-aloud */
  multilingual: true,
  /** 3. Multi-leaf / batch scan with aggregated predictions */
  batch_scan: true,
  /** 4. Weather-aware blight risk via Open-Meteo */
  weather_risk: true,
  /** 5. Opt-in outbreak heatmap with anonymous GPS reports */
  outbreak_map: true,
  /** 6. Treatment planner with cost, schedule, reminders */
  treatment_planner: true,
  /** 7. Feedback loop for active-learning retraining */
  feedback_loop: true,
  /** 8. PDF/shareable report with QR code */
  pdf_report: true,
  /** 9. Expert escalation via WhatsApp/email */
  expert_escalation: true,
  /** 10. Privacy-first analytics dashboard */
  analytics_dashboard: true,
};

/** @param {string} flag @returns {boolean} */
export function isEnabled(flag) {
  return FLAGS[flag] === true;
}
