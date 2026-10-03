import { icon } from "../components/ui.js";

/** @param {HTMLElement} root */
export function limitationsPage(root) {
  root.innerHTML = `
    <section class="page-shell">
      <div class="container" style="max-width: 860px;">
        <header class="page-header">
          <div>
            <span class="eyebrow" style="color: var(--primary, #2d6a4f);">Safety &amp; Ethics</span>
            <h1>Limitations &amp; Responsible Use</h1>
            <p>Fieldnote is designed to assist smallholders and agronomists with early symptom detection. Here is how to interpret its findings safely and responsibly.</p>
          </div>
        </header>

        <div style="display: flex; flex-direction: column; gap: 24px;">
          <!-- Card 1: Guidance vs Lab Diagnosis -->
          <section class="card" style="border-left: 4px solid var(--primary, #2d6a4f); padding: 22px;">
            <div style="display: flex; gap: 14px; align-items: flex-start;">
              <span style="font-size: 1.6rem;">🔬</span>
              <div>
                <h2 style="margin: 0 0 6px; font-size: 1.25rem;">1. Decision Support, Not Guaranteed Diagnosis</h2>
                <p style="margin: 0 0 10px; font-size: 0.92rem; line-height: 1.5; color: var(--text, #333);">
                  Computer vision models detect visual surface patterns on leaves. They cannot replace physical tissue cultures, PCR molecular tests, or the hands-on experience of certified agricultural extension officers.
                </p>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.88rem; color: var(--text-muted, #555);">
                  <li>Always cross-check uncertain or low-confidence scans with your local agronomy extension service.</li>
                  <li>Do not initiate high-cost eradication programs solely based on a single image scan.</li>
                </ul>
              </div>
            </div>
          </section>

          <!-- Card 2: Lookalikes and Nutrient Deficiencies -->
          <section class="card" style="border-left: 4px solid var(--warning, #f59e0b); padding: 22px;">
            <div style="display: flex; gap: 14px; align-items: flex-start;">
              <span style="font-size: 1.6rem;">🍃</span>
              <div>
                <h2 style="margin: 0 0 6px; font-size: 1.25rem;">2. Lookalike Symptoms &amp; Abiotic Stresses</h2>
                <p style="margin: 0 0 10px; font-size: 0.92rem; line-height: 1.5; color: var(--text, #333);">
                  Nutrient deficiencies (such as Potassium or Magnesium deficiency), drought scorch, chemical burns, and viral infections can closely mimic fungal leaf spots.
                </p>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.88rem; color: var(--text-muted, #555);">
                  <li>Inspect multiple leaves across different canopy heights (lower, middle, upper).</li>
                  <li>Use the <strong>Multi-Leaf Batch Scan</strong> mode to reduce false positive risks.</li>
                </ul>
              </div>
            </div>
          </section>

          <!-- Card 3: Chemical Safety & Label Precedence -->
          <section class="card" style="border-left: 4px solid #d32f2f; padding: 22px;">
            <div style="display: flex; gap: 14px; align-items: flex-start;">
              <span style="font-size: 1.6rem;">⚠️</span>
              <div>
                <h2 style="margin: 0 0 6px; font-size: 1.25rem;">3. Chemical Application Safety &amp; Label Precedence</h2>
                <p style="margin: 0 0 10px; font-size: 0.92rem; line-height: 1.5; color: var(--text, #333);">
                  The physical manufacturer label on registered pesticide products is legally binding. National regulations govern what active ingredients may be legally sold and applied.
                </p>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.88rem; color: var(--text-muted, #555);">
                  <li>In India, verify pesticide registration and permitted use against the current <strong>CIB&amp;RC (Central Insecticides Board &amp; Registration Committee)</strong> label. Ask your State Agriculture Department or local <strong>KVK (Krishi Vigyan Kendra)</strong> for expert help.</li>
                  <li>Strictly obey <strong>Pre-Harvest Intervals (PHI)</strong> and <strong>Re-Entry Intervals (REI)</strong> before harvesting or allowing field entry.</li>
                  <li>Always wear full personal protective equipment (PPE): respirator mask, chemical gloves, goggles, rubber boots, and coveralls.</li>
                </ul>
              </div>
            </div>
          </section>

          <!-- Card 4: Privacy & Surveillance Ethics -->
          <section class="card" style="border-left: 4px solid #1976d2; padding: 22px;">
            <div style="display: flex; gap: 14px; align-items: flex-start;">
              <span style="font-size: 1.6rem;">🛡️</span>
              <div>
                <h2 style="margin: 0 0 6px; font-size: 1.25rem;">4. Privacy &amp; Ethical Community Surveillance</h2>
                <p style="margin: 0 0 10px; font-size: 0.92rem; line-height: 1.5; color: var(--text, #333);">
                  We believe agricultural data belongs to growers. Fieldnote adheres to strict privacy-by-default architecture:
                </p>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.88rem; color: var(--text-muted, #555);">
                  <li>Zero personally identifiable information (PII) is stored or tracked.</li>
                  <li>GPS coordinates on the community outbreak map are rounded to ~1.1 km to prevent pinpointing individual properties.</li>
                  <li>Photos are only retained for model retraining if explicit active consent is granted.</li>
                </ul>
              </div>
            </div>
          </section>

          <div style="text-align: center; margin-top: 10px;">
            <a href="#/scan" class="button button-primary">
              ${icon("scan")} Back to Leaf Scanner
            </a>
          </div>
        </div>
      </div>
    </section>
  `;
}
