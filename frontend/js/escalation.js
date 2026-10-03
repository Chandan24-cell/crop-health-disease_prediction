/**
 * Expert escalation helper.
 * Generates instant deep links for WhatsApp and Email to share scan reports
 * with local agronomists, extension officers, and co-op managers.
 */

/**
 * Generate a formatted agronomic summary message.
 * @param {Object} options
 * @param {Object} options.result
 * @param {string} [options.plantLabel]
 * @returns {string}
 */
export function formatEscalationSummary({ result, plantLabel }) {
  const top = result?.top3?.[0] || { crop: "Unknown", disease: "Unknown", probability: 0 };
  const conf = Math.round((result?.calibrated_confidence ?? top.probability) * 100);
  const sevCat = result?.severity?.category || "Unknown";
  const sevPct = result?.severity?.percent !== undefined ? Number(result.severity.percent).toFixed(1) : "0";

  return `🌿 *Fieldnote Crop Health Scan Report*
• *Crop*: ${top.crop}
• *Suspected Issue*: ${top.disease || top.label.replace(/_/g, " ")}
• *Model Confidence*: ${conf}%
• *Visible Severity*: ${sevPct}% (${sevCat})
${plantLabel ? `• *Plot/Plant ID*: ${plantLabel}` : ""}
• *Scan ID*: ${result?.request_id || "N/A"}

_Hello Extension Officer / Agronomist, I captured this scan using the Fieldnote crop health app. Could you please review these symptoms and advise on the best local treatment strategy?_`;
}

/**
 * Open WhatsApp with pre-filled diagnosis report.
 * @param {Object} options
 * @param {string} [options.phoneNumber] Optional agronomist phone number (international format)
 * @param {Object} options.result
 * @param {string} [options.plantLabel]
 */
export function escalateViaWhatsApp({ phoneNumber = "", result, plantLabel }) {
  const text = formatEscalationSummary({ result, plantLabel });
  const cleanPhone = phoneNumber.replace(/[^0-9]/g, "");
  const url = cleanPhone
    ? `https://wa.me/${cleanPhone}?text=${encodeURIComponent(text)}`
    : `https://wa.me/?text=${encodeURIComponent(text)}`;

  window.open(url, "_blank");
}

/**
 * Open Email client with pre-filled diagnosis report.
 * @param {Object} options
 * @param {string} [options.email] Optional recipient email address
 * @param {Object} options.result
 * @param {string} [options.plantLabel]
 */
export function escalateViaEmail({ email = "", result, plantLabel }) {
  const top = result?.top3?.[0] || { crop: "Crop", disease: "Issue" };
  const subject = `Agronomic Consultation Request: ${top.crop} - ${top.disease}`;
  const body = formatEscalationSummary({ result, plantLabel });

  const url = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  window.location.href = url;
}
