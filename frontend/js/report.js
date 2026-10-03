/**
 * Client-side PDF Report Generator using jsPDF.
 * Generates an executive crop health assessment report containing:
 * - Leaf image
 * - Top diagnosis and confidence
 * - Severity analysis
 * - Categorized advice (immediate, cultural, chemical, safety)
 * - Model version, timestamp, request ID
 */

function ensureJsPdf() {
  return new Promise((resolve, reject) => {
    if (window.jspdf?.jsPDF) return resolve(window.jspdf.jsPDF);

    const script = document.createElement("script");
    script.src = "/assets/vendor/jspdf.umd.min.js";
    script.onload = () => resolve(window.jspdf.jsPDF);
    script.onerror = () => reject(new Error("Failed to load jsPDF library"));
    document.body.appendChild(script);
  });
}

/**
 * Generate and download a PDF report for a scan.
 * @param {Object} options
 * @param {Object} options.result Scan result object
 * @param {string} [options.imageUrl] Base64 or object URL of the leaf photo
 * @param {string} [options.plantLabel] Optional plant identifier
 */
export async function generatePdfReport({ result, imageUrl, plantLabel }) {
  const jsPDF = await ensureJsPdf();
  const doc = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
  });

  const primaryColor = [45, 106, 79]; // Forest green #2d6a4f
  const textColor = [33, 33, 33];
  const mutedColor = [110, 110, 110];

  // ── Header Banner ──────────────────────────────────────────────────
  doc.setFillColor(...primaryColor);
  doc.rect(0, 0, 210, 24, "F");

  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("Fieldnote — Crop Health Scan Report", 14, 15);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.text("Digital Diagnostic & Advisory Summary", 140, 15);

  // ── Metadata Strip ────────────────────────────────────────────────
  let y = 32;
  doc.setTextColor(...mutedColor);
  doc.setFontSize(8.5);
  const scanDate = new Date().toLocaleString();
  const reqId = result.request_id || "N/A";
  doc.text(
    `Generated: ${scanDate}   |   Model: ${result.model_version || "v2"}   |   Scan ID: ${reqId.slice(0, 16)}`,
    14,
    y,
  );

  if (plantLabel) {
    y += 5;
    doc.setTextColor(...primaryColor);
    doc.setFont("helvetica", "bold");
    doc.text(`Target Plot / Plant: ${plantLabel}`, 14, y);
    doc.setFont("helvetica", "normal");
  }

  y += 8;
  doc.setDrawColor(220, 220, 220);
  doc.setLineWidth(0.5);
  doc.line(14, y, 196, y);
  y += 8;

  // ── Diagnosis Block ────────────────────────────────────────────────
  const top = result.top3?.[0] || { label: "Unknown", crop: "Unknown", disease: "Unknown", probability: 0 };
  const confPercent = Math.round((result.calibrated_confidence ?? top.probability) * 100);

  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.setTextColor(...primaryColor);
  doc.text("Primary Diagnostic Findings", 14, y);
  y += 7;

  doc.setFontSize(11);
  doc.setTextColor(...textColor);
  doc.text(`Crop: ${top.crop || "Unknown"}`, 14, y);
  doc.text(`Diagnosis: ${top.disease || top.label.replace(/_/g, " ")}`, 70, y);
  doc.text(`Calibrated Confidence: ${confPercent}%`, 145, y);
  y += 8;

  // ── Severity Block ─────────────────────────────────────────────────
  const sev = result.severity || {};
  const sevCat = sev.category || "Not assessed";
  const sevPct = sev.percent !== undefined ? Number(sev.percent).toFixed(1) : "0.0";

  doc.setFont("helvetica", "normal");
  doc.setFontSize(9.5);
  doc.text(
    `Visible Lesion Area: ${sevPct}%   |   Severity Band: ${sevCat}   |   Status: ${result.status.toUpperCase()}`,
    14,
    y,
  );
  y += 10;

  // ── Leaf Photo (if base64) ─────────────────────────────────────────
  if (imageUrl && imageUrl.startsWith("data:image")) {
    try {
      doc.addImage(imageUrl, "JPEG", 14, y, 55, 55);
      // Box beside image for Top 3 breakdown
      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      doc.text("Top Candidate Classifications:", 76, y + 6);

      let subY = y + 14;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      (result.top3 || []).forEach((item, idx) => {
        const pct = Math.round(item.probability * 100);
        doc.text(`${idx + 1}. ${item.disease || item.label.replace(/_/g, " ")}: ${pct}%`, 78, subY);
        subY += 7;
      });

      y += 62;
    } catch {
      y += 5;
    }
  }

  // ── Advisory Section ───────────────────────────────────────────────
  const adv = result.advice || {};

  doc.setDrawColor(220, 220, 220);
  doc.line(14, y, 196, y);
  y += 8;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(...primaryColor);
  doc.text("Recommended Action Plan", 14, y);
  y += 7;

  const sections = [
    {
      title: "Immediate Action:",
      text: adv.immediate_actions || "Isolate heavily affected foliage and monitor plot.",
    },
    {
      title: "Cultural Controls:",
      text: adv.cultural_controls || "Improve plant spacing for airflow and avoid excess leaf moisture.",
    },
    {
      title: "Specific Advice:",
      text: adv.specific_advice || "Refer to local agricultural extension guidelines.",
    },
    {
      title: "Prevention:",
      text: adv.prevention || "Rotate crops and use certified clean seed/planting stock.",
    },
    {
      title: "Chemical / Protective Safety:",
      text: adv.safety_note || "Wear full PPE (mask, gloves, boots) when handling registered treatments.",
    },
  ];

  doc.setFontSize(9);
  sections.forEach((sec) => {
    if (y > 270) {
      doc.addPage();
      y = 20;
    }
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...textColor);
    doc.text(sec.title, 14, y);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(60, 60, 60);

    const splitText = doc.splitTextToSize(sec.text, 180);
    doc.text(splitText, 14, y + 4.5);
    y += 5 + splitText.length * 4.2;
  });

  // ── Footer Disclaimer ──────────────────────────────────────────────
  doc.setFontSize(7.5);
  doc.setTextColor(...mutedColor);
  const disclaimer =
    "Notice: This automated report is generated as diagnostic guidance and does not replace professional agronomic field inspection or national pesticide label regulations.";
  doc.text(doc.splitTextToSize(disclaimer, 180), 14, 285);

  // Save the PDF
  const filename = `Fieldnote_Report_${top.crop}_${new Date().toISOString().slice(0, 10)}.pdf`;
  doc.save(filename);
}
