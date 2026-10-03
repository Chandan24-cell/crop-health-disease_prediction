/**
 * Treatment data registry providing:
 * - Cost estimates (currency adaptable)
 * - Spray schedules & intervals
 * - Pre-Harvest Interval (PHI)
 * - Re-Entry Interval (REI)
 * - Protective gear (PPE) checklist
 */

export const TREATMENT_DATA = {
  Maize_Common_rust: {
    recommendedProduct: "Azoxystrobin + Difenoconazole or Mancozeb",
    type: "Fungicide (Systemic & Contact)",
    costEstimate: {
      usd: 18,
      kes: 2400,
      inr: 1500,
      basis: "per acre per application",
    },
    phiDays: 14,
    reiHours: 24,
    schedule: [
      {
        day: 1,
        action: "First application upon seeing pustules on lower leaves",
        notes: "Full coverage spray",
      },
      {
        day: 10,
        action: "Follow-up spray if weather remains cool and damp",
        notes: "Alternate active ingredients to prevent resistance",
      },
      { day: 21, action: "Final assessment before tasseling", notes: "Check upper leaves" },
    ],
    ppe: [
      { id: "mask", name: "Particle respirator or chemical mask (N95/FFP2)", required: true },
      { id: "gloves", name: "Chemical-resistant nitrile gloves", required: true },
      { id: "goggles", name: "Sealed eye protection goggles", required: true },
      { id: "boots", name: "Rubber boots (no leather/fabric)", required: true },
      { id: "suit", name: "Long-sleeved overalls / protective apron", required: true },
    ],
  },
  Maize_Gray_leaf_spot: {
    recommendedProduct: "Pyraclostrobin or Propiconazole",
    type: "Fungicide (Triazole / Strobilurin)",
    costEstimate: {
      usd: 22,
      kes: 2900,
      inr: 1800,
      basis: "per acre per application",
    },
    phiDays: 21,
    reiHours: 24,
    schedule: [
      {
        day: 1,
        action: "Initial targeted spray upon lesion detection",
        notes: "Apply before lesions reach ear leaf",
      },
      { day: 14, action: "Second application during high humidity or rain", notes: "Check lower canopy" },
    ],
    ppe: [
      { id: "mask", name: "Chemical mist respirator", required: true },
      { id: "gloves", name: "Heavy-duty nitrile gloves", required: true },
      { id: "goggles", name: "Wrap-around safety goggles", required: true },
      { id: "boots", name: "Non-slip rubber boots", required: true },
      { id: "suit", name: "Full-body coverall", required: true },
    ],
  },
  Maize_Northern_Leaf_Blight: {
    recommendedProduct: "Mancozeb or Azoxystrobin",
    type: "Protective / Curative Fungicide",
    costEstimate: {
      usd: 20,
      kes: 2600,
      inr: 1650,
      basis: "per acre per application",
    },
    phiDays: 14,
    reiHours: 24,
    schedule: [
      {
        day: 1,
        action: "Spray lower canopy as soon as cigar-shaped spots appear",
        notes: "Ensure thorough underside leaf coverage",
      },
      { day: 10, action: "Repeat spray if humid weather persists", notes: "Scout upper 3 canopy leaves" },
      {
        day: 20,
        action: "Optional prophylactic application before silking",
        notes: "Only if disease pressure is high",
      },
    ],
    ppe: [
      { id: "mask", name: "Respirator mask", required: true },
      { id: "gloves", name: "Nitrile or neoprene gloves", required: true },
      { id: "goggles", name: "Splash-proof safety goggles", required: true },
      { id: "boots", name: "Waterproof rubber boots", required: true },
      { id: "suit", name: "Protective jacket and trousers", required: true },
    ],
  },
  Potato_Early_blight: {
    recommendedProduct: "Chlorothalonil or Mancozeb",
    type: "Contact Protectant Fungicide",
    costEstimate: {
      usd: 16,
      kes: 2100,
      inr: 1300,
      basis: "per acre per application",
    },
    phiDays: 7,
    reiHours: 12,
    schedule: [
      {
        day: 1,
        action: "First spray when target spots appear on older leaves",
        notes: "Maintain even pressure",
      },
      {
        day: 7,
        action: "Second protective application",
        notes: "Repeat every 7-10 days under warm conditions",
      },
      {
        day: 14,
        action: "Third spray during tuber initiation",
        notes: "Protect foliage to preserve tuber yield",
      },
    ],
    ppe: [
      { id: "mask", name: "Vapor/mist mask", required: true },
      { id: "gloves", name: "Waterproof gloves", required: true },
      { id: "goggles", name: "Protective eye wear", required: true },
      { id: "boots", name: "Rubber field boots", required: true },
      { id: "suit", name: "Overalls", required: true },
    ],
  },
  Potato_Late_blight: {
    recommendedProduct: "Metalaxyl + Mancozeb (Ridomil) or Cymoxanil",
    type: "Systemic + Contact Oomyceticide (Urgent Action)",
    costEstimate: {
      usd: 28,
      kes: 3700,
      inr: 2300,
      basis: "per acre per application",
    },
    phiDays: 14,
    reiHours: 48,
    schedule: [
      {
        day: 1,
        action: "Immediate curative spray on first water-soaked spot",
        notes: "Act fast; late blight destroys foliage within days",
      },
      {
        day: 5,
        action: "Secondary booster application",
        notes: "Do not delay if wet or cool weather continues",
      },
      {
        day: 12,
        action: "Protective contact spray (e.g. Copper hydroxide)",
        notes: "Switch class to prevent resistance",
      },
      {
        day: 19,
        action: "Final maintenance check before harvest vine kill",
        notes: "Ensure tubers are well hilled",
      },
    ],
    ppe: [
      { id: "mask", name: "Organic vapor dual-cartridge respirator", required: true },
      { id: "gloves", name: "Heavy chemical elbow-length gloves", required: true },
      { id: "goggles", name: "Full seal chemical splash goggles", required: true },
      { id: "boots", name: "Acid/chemical resistant rubber boots", required: true },
      { id: "suit", name: "Waterproof protective chemical suit", required: true },
    ],
  },
  Tomato_Early_blight: {
    recommendedProduct: "Copper Hydroxide or Difenoconazole",
    type: "Fungicide / Protectant",
    costEstimate: {
      usd: 15,
      kes: 2000,
      inr: 1200,
      basis: "per acre per application",
    },
    phiDays: 5,
    reiHours: 12,
    schedule: [
      { day: 1, action: "Prune infected bottom leaves and spray stems", notes: "Do not touch wet foliage" },
      { day: 7, action: "Second targeted spray on new foliage", notes: "Ensure mulch covers bare soil" },
      { day: 14, action: "Maintenance spray", notes: "Check blossoming clusters" },
    ],
    ppe: [
      { id: "mask", name: "Dust and mist face mask", required: true },
      { id: "gloves", name: "Chemical protective gloves", required: true },
      { id: "goggles", name: "Safety glasses or visor", required: true },
      { id: "boots", name: "Rubber field boots", required: true },
      { id: "suit", name: "Cotton overalls or apron", required: true },
    ],
  },
  Tomato_Late_blight: {
    recommendedProduct: "Dimethomorph or Metalaxyl + Mancozeb",
    type: "Systemic Oomyceticide (Urgent Action)",
    costEstimate: {
      usd: 30,
      kes: 4000,
      inr: 2500,
      basis: "per acre per application",
    },
    phiDays: 7,
    reiHours: 48,
    schedule: [
      {
        day: 1,
        action: "Immediate full-canopy spray",
        notes: "Destroy heavily collapsed plants immediately",
      },
      {
        day: 4,
        action: "Booster application to protect young green stems",
        notes: "High humidity accelerates infection",
      },
      {
        day: 10,
        action: "Contact protectant (Copper) to seal leaf surfaces",
        notes: "Inspect fruit for greasy dark rot",
      },
    ],
    ppe: [
      { id: "mask", name: "Chemical cartridge respirator", required: true },
      { id: "gloves", name: "Heavy duty nitrile gloves", required: true },
      { id: "goggles", name: "Vented safety goggles", required: true },
      { id: "boots", name: "Rubber knee boots", required: true },
      { id: "suit", name: "Chemical spray suit with hood", required: true },
    ],
  },
  Tomato_Leaf_Mold: {
    recommendedProduct: "Copper Oxychloride or Chlorothalonil",
    type: "Fungicide / Ventilation Management",
    costEstimate: {
      usd: 14,
      kes: 1850,
      inr: 1100,
      basis: "per acre per application",
    },
    phiDays: 3,
    reiHours: 12,
    schedule: [
      {
        day: 1,
        action: "Open greenhouse sides / prune for airflow + initial spray",
        notes: "Spray underside of leaves where olive mold sits",
      },
      {
        day: 8,
        action: "Second application if humidity stays above 80%",
        notes: "Ensure drip irrigation is leak-free",
      },
    ],
    ppe: [
      { id: "mask", name: "Standard particulate mask", required: true },
      { id: "gloves", name: "Latex or nitrile gloves", required: true },
      { id: "goggles", name: "Safety goggles", required: true },
      { id: "boots", name: "Clean rubber boots", required: true },
      { id: "suit", name: "Work overalls", required: true },
    ],
  },
};

/**
 * Get treatment planning details for a disease label.
 * @param {string} diseaseLabel
 * @returns {Object}
 */
export function getTreatmentPlan(diseaseLabel) {
  return (
    TREATMENT_DATA[diseaseLabel] || {
      recommendedProduct: "Registered broad-spectrum agricultural protectant",
      type: "Consult local extension officer",
      costEstimate: { usd: 15, kes: 2000, inr: 1200, basis: "per acre estimated" },
      phiDays: 7,
      reiHours: 24,
      schedule: [
        {
          day: 1,
          action: "Isolate affected plants and apply approved treatment",
          notes: "Follow package instructions",
        },
        {
          day: 10,
          action: "Monitor crop recovery and apply follow-up if needed",
          notes: "Inspect new growth",
        },
      ],
      ppe: [
        { id: "mask", name: "Protective face mask", required: true },
        { id: "gloves", name: "Chemical resistant gloves", required: true },
        { id: "goggles", name: "Protective eye wear", required: true },
        { id: "boots", name: "Rubber boots", required: true },
        { id: "suit", name: "Protective coverall", required: true },
      ],
    }
  );
}
