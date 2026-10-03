import { icon } from "../components/ui.js";

/** Render the product landing page. @returns {string} */
export function homePage() {
  return `
    <h1 class="sr-only">Fieldnote crop health</h1>
    <section class="leaf-explode" data-leaf-explode>
      <div class="leaf-explode__sticky">
        <div class="container leaf-explode__layout">
          <div class="leaf-explode__visual">
            <div class="leaf-explode__stage" data-leaf-stage>
              <img class="leaf-explode__poster" src="/assets/leaf-sequence/webp/frame-001.webp" alt="" fetchpriority="high" />
              <canvas class="leaf-explode__canvas" role="img" aria-label="Animated exploded view of a leaf"></canvas>
            </div>
          </div>
        </div>
      </div>
    </section>
    <section class="section"><div class="container">
      <div class="section-heading"><div><span class="eyebrow">Your everyday crop companion</span><h2>Start with the crops you grow.</h2><p>Get a focused leaf check and practical guidance for the crops Fieldnote currently supports.</p></div><a class="button button-secondary button-small" href="#/library">Open plant guide ${icon("book")}</a></div>
      <div class="crop-grid">
        <a class="crop-card" href="#/scan?crop=Maize" data-crop="Maize"><img class="crop-photo" src="/assets/crops/maize.webp" onerror="this.onerror=null;this.src='/assets/crops/maize.jpg'" alt="Maize leaf" width="112" height="112" loading="lazy" /><span><h3>Maize</h3><p>Common rust, gray leaf spot, northern leaf blight</p></span></a>
        <a class="crop-card" href="#/scan?crop=Tomato" data-crop="Tomato"><img class="crop-photo" src="/assets/crops/tomato.webp" onerror="this.onerror=null;this.src='/assets/crops/tomato.jpg'" alt="Tomato leaf" width="112" height="112" loading="lazy" /><span><h3>Tomato</h3><p>Early blight, late blight, leaf mold</p></span></a>
        <a class="crop-card" href="#/scan?crop=Potato" data-crop="Potato"><img class="crop-photo" src="/assets/crops/potato.webp" onerror="this.onerror=null;this.src='/assets/crops/potato.jpg'" alt="Potato leaf" width="112" height="112" loading="lazy" /><span><h3>Potato</h3><p>Early blight and late blight</p></span></a>
      </div>
    </div></section>
    <section class="section"><div class="container feature-band"><div><span class="eyebrow" style="color:var(--mint-strong)">A useful second opinion</span><h2>Clear steps. Honest uncertainty.</h2><p>Fieldnote helps you notice patterns and choose a sensible next action. It is a guide, not a replacement for local agricultural expertise.</p></div><div class="feature-points">
      <div class="feature-point">${icon("scan")}<span><strong>Image quality first</strong><p>Get photo tips before a scan can mislead.</p></span></div>
      <div class="feature-point">${icon("shield")}<span><strong>Safety in every answer</strong><p>Follow product labels and local advice.</p></span></div>
      <div class="feature-point">${icon("history")}<span><strong>Keep a field record</strong><p>Compare your saved scans over time.</p></span></div>
      <div class="feature-point">${icon("book")}<span><strong>Learn as you go</strong><p>Browse symptoms and prevention guidance.</p></span></div>
    </div></div></section>`;
}
