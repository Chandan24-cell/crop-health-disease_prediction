/**
 * Multi-leaf / Batch Scan aggregation module.
 * Aggregates up to 5 leaves of the same plant using majority vote
 * and confidence-weighted voting for a reliable plant-level verdict.
 */

/**
 * @typedef {Object} LeafResult
 * @property {number} leafIndex
 * @property {string} [name]
 * @property {Object} prediction
 */

/**
 * Aggregate multiple leaf predictions into a plant-level verdict.
 * @param {Array<LeafResult>} leaves
 * @returns {Object}
 */
export function aggregateLeaves(leaves) {
  if (!leaves || leaves.length === 0) {
    return {
      status: "unsupported",
      finalLabel: "Unknown",
      majorityLabel: "Unknown",
      weightedLabel: "Unknown",
      crop: "Unknown",
      disease: "Unknown",
      confidence: 0,
      totalLeaves: 0,
      agreement: false,
      voteBreakdown: {},
      weightedScores: {},
    };
  }

  const voteBreakdown = {};
  const weightedScores = {};
  const statuses = [];

  for (const leaf of leaves) {
    const pred = leaf.prediction || {};
    statuses.push(pred.status || "ok");
    const top = pred.top3?.[0] || { label: "Unknown", probability: 0 };
    const label = top.label || "Unknown";
    const conf = Number(pred.calibrated_confidence ?? top.probability ?? 0.5);

    voteBreakdown[label] = (voteBreakdown[label] || 0) + 1;
    weightedScores[label] = Number(((weightedScores[label] || 0) + conf).toFixed(4));
  }

  // Find majority vote
  let majorityLabel = "Unknown";
  let maxVotes = -1;
  for (const [lbl, count] of Object.entries(voteBreakdown)) {
    if (count > maxVotes) {
      maxVotes = count;
      majorityLabel = lbl;
    }
  }

  // Find confidence-weighted winner
  let weightedLabel = "Unknown";
  let maxWeight = -1;
  for (const [lbl, weight] of Object.entries(weightedScores)) {
    if (weight > maxWeight) {
      maxWeight = weight;
      weightedLabel = lbl;
    }
  }

  const finalLabel = weightedLabel;
  const agreement = majorityLabel === weightedLabel;
  const aggConfidence = Number((weightedScores[finalLabel] / leaves.length).toFixed(4));

  // Determine overall status
  let overallStatus = "ok";
  if (statuses.every((s) => s === "retake")) {
    overallStatus = "retake";
  } else if (statuses.every((s) => s === "unsupported")) {
    overallStatus = "unsupported";
  } else if (aggConfidence < 0.75 || !agreement) {
    overallStatus = "uncertain";
  }

  const parts = finalLabel.split("_");
  const crop = parts[0] || "Unknown";
  const disease = parts.slice(1).join(" ").replace(/_/g, " ") || finalLabel;

  return {
    status: overallStatus,
    finalLabel,
    majorityLabel,
    weightedLabel,
    crop,
    disease,
    confidence: aggConfidence,
    totalLeaves: leaves.length,
    agreement,
    voteBreakdown,
    weightedScores,
  };
}

/**
 * Send batch of images to the batch predict API endpoint.
 * @param {Array<File|Blob>} files
 * @param {string} [language]
 * @returns {Promise<Object>}
 */
export async function sendBatchPredict(files, language = "en") {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("images", file);
  });
  formData.append("language", language);

  const response = await fetch("./api/v1/predict/batch", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Batch scan failed (${response.status}): ${errorText}`);
  }

  return response.json();
}
