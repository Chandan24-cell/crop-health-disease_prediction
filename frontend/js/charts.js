/** Render an accessible calibrated confidence ring. @param {number} value @param {string} [label] @returns {string} */
export function confidenceRing(value, label = "confidence") {
  const percent = Math.max(0, Math.min(100, value * 100));
  return `<div class="confidence-ring" style="--ring:${percent}%" role="img" aria-label="${Math.round(percent)} percent ${label}"><div><strong>${Math.round(percent)}%</strong><small>${label}</small></div></div>`;
}

/** Render a simple SVG severity trend. @param {Array<{date:number,result:Object}>} scans @returns {string} */
export function severitySparkline(scans) {
  const ordered = [...scans].sort((a, b) => a.date - b.date);
  if (ordered.length < 2)
    return `<p class="severity-meta">Save another scan of this crop to compare changes over time.</p>`;
  const values = ordered.map((scan) =>
    Math.max(0, Math.min(100, Number(scan.result?.severity?.percent || 0))),
  );
  const width = 600;
  const height = 120;
  const max = Math.max(10, ...values);
  const points = values
    .map((value, index) => `${(index / (values.length - 1)) * width},${height - (value / max) * 90 - 10}`)
    .join(" ");
  const path = `M ${points.replaceAll(" ", " L ")}`;
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="Severity trend from ${values.map((value) => `${value.toFixed(1)} percent`).join(", ")}" preserveAspectRatio="none"><path d="${path}" fill="none" stroke="var(--leaf)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/><path d="${path} L ${width},${height} L 0,${height} Z" fill="var(--mint)" opacity=".6"/>${values.map((value, index) => `<circle cx="${(index / (values.length - 1)) * width}" cy="${height - (value / max) * 90 - 10}" r="5" fill="var(--surface)" stroke="var(--forest)" stroke-width="3"/>`).join("")}</svg>`;
}
