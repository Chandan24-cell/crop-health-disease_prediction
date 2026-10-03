import { t } from "../i18n.js";
import { icon, toast } from "../components/ui.js";

/** @param {HTMLElement} root */
export async function adminFeedbackPage(root) {
  root.innerHTML = `
    <section class="page-shell">
      <div class="container">
        <header class="page-header">
          <div>
            <span class="eyebrow">Active Learning Pipeline</span>
            <h1>${t("admin_feedback_title", "Feedback Review Queue")}</h1>
            <p>Review community correction submissions and verify images for retraining dataset exports.</p>
          </div>
          <div style="display:flex; gap: 10px; align-items:center;">
            <select id="feedback-filter" class="form-control" style="max-width: 140px;">
              <option value="all">All</option>
              <option value="pending" selected>Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
            <button type="button" class="button button-secondary button-small" id="btn-export-retrain">
              ${icon("download")} Export Retraining Dataset
            </button>
          </div>
        </header>

        <div id="feedback-list" style="display:flex; flex-direction:column; gap: 16px;">
          <div class="card" style="text-align:center; padding: 40px;">
            <p>Loading feedback items...</p>
          </div>
        </div>
      </div>
    </section>
  `;

  async function loadItems(status = "all") {
    const listDiv = root.querySelector("#feedback-list");
    if (!listDiv) return;

    try {
      const res = await fetch(`./api/v1/admin/feedback?status=${status}`);
      if (!res.ok) throw new Error("Could not load feedback queue");
      const items = await res.json();

      if (items.length === 0) {
        listDiv.innerHTML = `
          <div class="card" style="text-align:center; padding: 40px; color: var(--text-muted, #777);">
            <p style="margin:0; font-size: 1.05rem;">No feedback submissions matching "<strong>${status}</strong>".</p>
          </div>
        `;
        return;
      }

      listDiv.innerHTML = items
        .map(
          (item) => `
        <div class="card" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap: 16px; border-left: 4px solid ${
          item.status === "approved" ? "#2e7d32" : item.status === "rejected" ? "#c62828" : "#f57c00"
        };">
          <div style="flex: 1; min-width: 260px;">
            <div style="display:flex; align-items:center; gap: 8px; margin-bottom: 6px;">
              <span class="badge" style="background:${
                item.status === "approved" ? "#e8f5e9" : item.status === "rejected" ? "#ffebee" : "#fff3e0"
              }; color:${
                item.status === "approved" ? "#2e7d32" : item.status === "rejected" ? "#c62828" : "#f57c00"
              }; font-weight:700; text-transform:uppercase;">
                ${item.status}
              </span>
              <small style="color:var(--text-muted, #888);">${new Date(item.timestamp).toLocaleString()}</small>
              ${item.has_photo ? '<span class="badge" style="background:#e3f2fd; color:#1565c0;">📷 Photo Attached</span>' : ""}
            </div>

            <div style="display:flex; gap: 20px; align-items:baseline; margin: 8px 0;">
              <div>
                <small style="color:var(--text-muted, #666); display:block;">Model Predicted:</small>
                <strong style="color:#d32f2f;">${item.predicted_label.replace(/_/g, " ")}</strong>
              </div>
              <span style="font-size:1.2rem; color:var(--text-muted, #aaa);">➔</span>
              <div>
                <small style="color:var(--text-muted, #666); display:block;">Grower Corrected To:</small>
                <strong style="color:#2e7d32; font-size:1.05rem;">${item.user_label.replace(/_/g, " ")}</strong>
              </div>
            </div>

            ${
              item.comment
                ? `<p style="margin: 6px 0 0; font-size: 0.88rem; background: var(--surface-alt, #fafafa); padding: 8px 12px; border-radius: 4px; color: var(--text, #333);">
                    "${item.comment}"
                   </p>`
                : ""
            }
          </div>

          <div style="display:flex; gap: 8px; align-items:center;">
            ${
              item.status !== "approved"
                ? `<button type="button" class="button button-primary button-small btn-action" data-id="${item.id}" data-action="approve">
                    ${icon("check")} Approve
                   </button>`
                : ""
            }
            ${
              item.status !== "rejected"
                ? `<button type="button" class="button button-danger button-small btn-action" data-id="${item.id}" data-action="reject">
                    ${icon("x")} Reject
                   </button>`
                : ""
            }
          </div>
        </div>
      `,
        )
        .join("");

      // Action listener
      listDiv.querySelectorAll(".btn-action").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const id = btn.dataset.id;
          const action = btn.dataset.action;
          try {
            const actRes = await fetch(`./api/v1/admin/feedback/${id}/review?action=${action}`, {
              method: "POST",
            });
            if (actRes.ok) {
              toast(`Feedback marked as ${action}d`);
              loadItems(root.querySelector("#feedback-filter")?.value || "all");
            } else {
              toast("Review action failed", true);
            }
          } catch {
            toast("Action failed", true);
          }
        });
      });
    } catch (err) {
      listDiv.innerHTML = `<div class="card" style="color:red;">Error loading feedback items: ${err.message}</div>`;
    }
  }

  root.querySelector("#feedback-filter")?.addEventListener("change", (e) => {
    loadItems(e.target.value);
  });

  root.querySelector("#btn-export-retrain")?.addEventListener("click", async () => {
    try {
      const res = await fetch("./api/v1/admin/feedback?status=approved");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `retraining_dataset_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast("Retraining dataset exported!");
    } catch {
      toast("Export failed", true);
    }
  });

  loadItems("pending");
}
