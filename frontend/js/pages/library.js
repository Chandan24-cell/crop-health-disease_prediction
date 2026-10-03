import { diseaseData } from "../disease-data.js";
import { escapeHtml, icon } from "../components/ui.js";

function imageSlug(value) { return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }

/** Render the searchable eight-disease guide. @param {HTMLElement} root @returns {void} */
export function libraryPage(root) {
  root.innerHTML = `<section class="page-shell"><div class="container"><header class="page-header"><div><span class="eyebrow">Field guide</span><h1>Know what to look for.</h1><p>Explore common leaf symptoms and prevention ideas. Similar symptoms can have different causes, so confirm uncertain cases locally.</p></div></header><div class="toolbar"><label class="search-wrap">${icon("search")}<span class="sr-only">Search the plant guide</span><input id="disease-search" class="form-control" type="search" placeholder="Search by disease or symptom" /></label><select id="disease-crop" class="form-control" style="max-width:190px"><option value="">All supported crops</option><option>Maize</option><option>Potato</option><option>Tomato</option></select></div><div class="disease-grid" id="disease-grid"></div><p class="severity-meta" style="margin-top:20px">Photos are examples from the PlantVillage dataset. Confirm diagnoses and verify any pesticide use against the current CIB&RC label; ask your State Agriculture Department or local KVK for expert advice.</p></div></section>`;
  const grid = root.querySelector("#disease-grid");
  function draw() {
    const query = root.querySelector("#disease-search").value.trim().toLowerCase();
    const crop = root.querySelector("#disease-crop").value;
    const results = diseaseData.filter(
      (item) =>
        (!crop || item.crop === crop) &&
        (!query ||
          `${item.crop} ${item.name} ${item.symptoms} ${item.prevention}`.toLowerCase().includes(query)),
    );
    if (!results.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><span class="empty-icon">${icon("search")}</span><h2>No guide entry found</h2><p>Try another crop or symptom.</p></div>`;
      return;
    }
    grid.innerHTML = results
      .map((item) => {
        const key = `${imageSlug(item.crop)}-${imageSlug(item.name)}`;
        const photos = [1, 2, 3].map((n) => `/assets/guide/${key}-${n}.webp`);
        return `<article class="card disease-card"><img class="disease-photo" src="${photos[0]}" alt="${escapeHtml(item.crop)} leaf showing ${escapeHtml(item.name)}" loading="lazy" width="512" height="320"><span class="eyebrow">${escapeHtml(item.crop)}</span><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.symptoms)}</p><div class="disease-prevention"><details><summary>Prevention &amp; first steps</summary><p><strong>Prevention:</strong> ${escapeHtml(item.prevention)}</p><p><strong>First steps:</strong> ${escapeHtml(item.actions)}</p><div class="guide-gallery">${photos.map((src,index)=>`<button class="guide-photo-button" type="button" data-photo="${src}" aria-label="View ${escapeHtml(item.crop)} ${escapeHtml(item.name)} photo ${index+1}"><img src="${src}" alt="${escapeHtml(item.crop)} leaf showing ${escapeHtml(item.name)}" loading="lazy" width="512" height="320"></button>`).join("")}</div></details></div></article>`;
      })
      .join("");
  }
  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-photo]");
    if (!button) return;
    const dialog = document.createElement("dialog");
    dialog.className = "guide-lightbox";
    dialog.innerHTML = `<form method="dialog"><button class="icon-button" aria-label="Close photo">?</button></form><img src="${button.dataset.photo}" alt="${button.getAttribute("aria-label")}">`;
    root.append(dialog); dialog.showModal(); dialog.addEventListener("close", () => dialog.remove());
  });
  root.querySelector("#disease-search").addEventListener("input", draw);
  root.querySelector("#disease-crop").addEventListener("change", draw);
  draw();
}
