import { severitySparkline } from "../charts.js";
import { escapeHtml, formatDate, icon, toast } from "../components/ui.js";
import { deleteScan, getScans } from "../db.js";
import { state } from "../state.js";

/** Render, filter, compare and manage this browser's saved scans. @param {HTMLElement} root @returns {Promise<void>} */
export async function historyPage(root) {
  const scans = await getScans();
  const selected = new Set();
  root.innerHTML = `<section class="page-shell"><div class="container"><header class="page-header"><div><span class="eyebrow">Your field record</span><h1>My scans</h1><p>Your photos and results are saved on this device, when scan history is enabled.</p></div><a class="button" href="#/scan">${icon("scan")} New scan</a></header>
    <div class="toolbar"><label class="search-wrap"><span class="sr-only">Search scans</span>${icon("search")}<input class="form-control" id="history-search" type="search" placeholder="Search crop or disease" /></label><select class="form-control" id="history-crop" style="max-width:190px"><option value="">All crops</option>${[
      ...new Set(scans.map((scan) => scan.crop)),
    ]
      .sort()
      .map((crop) => `<option>${escapeHtml(crop)}</option>`)
      .join(
        "",
      )}</select><select class="form-control" id="history-date" style="max-width:190px"><option value="all">Any time</option><option value="30">Past 30 days</option><option value="7">Past 7 days</option></select></div>
    <div id="history-content"></div><div id="compare-panel"></div></div></section>`;
  const content = root.querySelector("#history-content");
  const comparePanel = root.querySelector("#compare-panel");

  function drawCompare() {
    const items = scans.filter((scan) => selected.has(scan.id)).sort((a, b) => a.date - b.date);
    if (items.length < 2) {
      comparePanel.innerHTML = "";
      return;
    }
    comparePanel.innerHTML = `<section class="card compare-panel"><div class="section-heading"><div><span class="eyebrow">Plant timeline</span><h2 style="margin:8px 0 0">${escapeHtml(items[0].plantId)}</h2></div><button class="icon-button" type="button" id="close-compare" aria-label="Close comparison">${icon("close")}</button></div><div class="styleguide-grid">${items.map((item) => `<article><img src="${escapeHtml(item.image || "")}" alt="Leaf photo scanned ${escapeHtml(formatDate(item.date))}" style="width:100%;height:210px;object-fit:cover;border-radius:var(--radius-sm)"/><p style="margin:10px 0 0"><strong>${Number(item.result?.severity?.percent || 0).toFixed(1)}% visible impact</strong><br/><span class="severity-meta">${escapeHtml(formatDate(item.date))} · ${escapeHtml(item.disease)}</span></p></article>`).join("")}</div><h3 style="margin-top:22px">Severity trend</h3>${severitySparkline(items)}</section>`;
    comparePanel.querySelector("#close-compare").addEventListener("click", () => {
      selected.clear();
      drawCompare();
      drawList();
    });
  }

  function drawList() {
    const search = root.querySelector("#history-search").value.trim().toLowerCase();
    const crop = root.querySelector("#history-crop").value;
    const days = root.querySelector("#history-date").value;
    const cutoff = days === "all" ? 0 : Date.now() - Number(days) * 86400000;
    const visible = scans.filter((scan) => {
      const text = `${scan.crop} ${scan.disease} ${scan.plantId || ""}`.toLowerCase();
      return (!search || text.includes(search)) && (!crop || scan.crop === crop) && scan.date >= cutoff;
    });
    if (!visible.length) {
      content.innerHTML = `<div class="empty-state"><span class="empty-icon">${icon(scans.length ? "search" : "history")}</span><h2>${scans.length ? "No scans match that filter" : "Your field record starts here"}</h2><p>${scans.length ? "Try another search or clear a filter." : "Your saved leaf scans will appear here, ready to compare over time."}</p>${scans.length ? "" : `<a class="button" href="#/scan">${icon("scan")} Scan your first leaf</a>`}</div>`;
      return;
    }
    content.innerHTML = `<div class="scan-grid">${visible.map((scan) => `<article class="card scan-card"><button type="button" class="scan-thumb" data-open="${escapeHtml(scan.id)}" aria-label="Open ${escapeHtml(scan.crop)} ${escapeHtml(scan.disease)} scan from ${escapeHtml(formatDate(scan.date))}">${scan.image ? `<img src="${escapeHtml(scan.image)}" alt="Leaf photo for ${escapeHtml(scan.disease)} scan" loading="lazy"/>` : `<span class="scan-thumb-placeholder">${icon("leaf")}</span>`}</button><div class="scan-card-body"><h3>${escapeHtml(scan.crop)} · ${escapeHtml(scan.disease)}</h3><p>${escapeHtml(formatDate(scan.date))} · ${escapeHtml(scan.plantId || "Unassigned")}</p><div class="scan-card-foot"><span class="chip">${Number(scan.result?.severity?.percent || 0).toFixed(1)}% impact</span><label class="severity-meta"><input type="checkbox" data-compare="${escapeHtml(scan.id)}" ${scan.plantId && scan.plantId !== "Unassigned" ? "" : "disabled"} ${selected.has(scan.id) ? "checked" : ""}/> Compare</label><button class="icon-button" type="button" data-delete="${escapeHtml(scan.id)}" aria-label="Delete scan" style="width:38px;height:38px">${icon("close")}</button></div></div></article>`).join("")}</div>`;
    content.querySelectorAll("[data-open]").forEach((button) =>
      button.addEventListener("click", () => {
        const item = scans.find((scan) => scan.id === button.dataset.open);
        if (item) {
          state.setResult(item.result);
          state.currentImageUrl = item.image;
          window.location.hash = "#/results";
        }
      }),
    );
    content.querySelectorAll("[data-delete]").forEach((button) =>
      button.addEventListener("click", async () => {
        await deleteScan(button.dataset.delete);
        const index = scans.findIndex((scan) => scan.id === button.dataset.delete);
        if (index >= 0) scans.splice(index, 1);
        toast("Scan removed from this device.");
        drawList();
      }),
    );
    content.querySelectorAll("[data-compare]").forEach((checkbox) =>
      checkbox.addEventListener("change", () => {
        const scan = scans.find((item) => item.id === checkbox.dataset.compare);
        if (!scan) return;
        if (checkbox.checked) {
          const already = scans.find((item) => selected.has(item.id));
          if (already && already.plantId !== scan.plantId) {
            selected.clear();
            toast("Compare scans with the same plant label.", true);
          }
          if (selected.size >= 2) selected.delete(selected.values().next().value);
          selected.add(scan.id);
        } else selected.delete(scan.id);
        drawCompare();
        drawList();
      }),
    );
  }
  root.querySelector("#history-search").addEventListener("input", drawList);
  root.querySelector("#history-crop").addEventListener("change", drawList);
  root.querySelector("#history-date").addEventListener("change", drawList);
  drawList();
}
