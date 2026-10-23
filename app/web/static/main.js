// Revenue Intelligence Inbox — main.js
// Light JS: route correction modal, popovers, toast, import/export API calls

const ROUTES = [
  { id: "customer_follow_up",    label: "Customer Follow-Up",    cls: "route-cfu" },
  { id: "deal_next_steps",       label: "Deal Next Steps",        cls: "route-dns" },
  { id: "sales_coaching",        label: "Sales Coaching",         cls: "route-sc" },
  { id: "support_account_admin", label: "Support / Account Admin",cls: "route-saa" },
  { id: "internal_vendor_note",  label: "Internal / Vendor Note", cls: "route-ivn" },
  { id: "needs_human_decision",  label: "Needs Human Decision",   cls: "route-nhd" },
];

// ── Route badge helper ────────────────────────────────────
function routeBadge(routeId) {
  const r = ROUTES.find(x => x.id === routeId) || { label: routeId, cls: "" };
  return `<span class="badge ${r.cls}">${r.label}</span>`;
}

// ── Toast ─────────────────────────────────────────────────
function showToast(msg, duration = 2800) {
  const t = document.getElementById("toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), duration);
}

// ── Route Correction Modal ────────────────────────────────
let _correctionTarget = null;

function openCorrectionModal(sourceType, sourceId, currentRoutes) {
  _correctionTarget = { sourceType, sourceId };
  const modal = document.getElementById("correction-modal");
  const overlay = document.getElementById("modal-overlay");
  if (!modal) return;

  // Build checkboxes
  const container = document.getElementById("route-checkboxes");
  container.innerHTML = "";
  const current = Array.isArray(currentRoutes) ? currentRoutes : JSON.parse(currentRoutes || "[]");
  ROUTES.forEach(r => {
    const checked = current.includes(r.id) ? "checked" : "";
    container.innerHTML += `
      <div class="route-checkbox">
        <input type="checkbox" id="chk-${r.id}" value="${r.id}" ${checked}>
        <label for="chk-${r.id}">
          <span class="badge ${r.cls}">${r.label}</span>
        </label>
      </div>`;
  });

  document.getElementById("correction-reason").value = "";
  overlay.classList.add("open");
}

function closeCorrectionModal() {
  document.getElementById("modal-overlay")?.classList.remove("open");
  _correctionTarget = null;
}

async function submitCorrection() {
  if (!_correctionTarget) return;
  const checkboxes = document.querySelectorAll("#route-checkboxes input[type=checkbox]:checked");
  const manual_routes = Array.from(checkboxes).map(c => c.value);
  const manual_reason = document.getElementById("correction-reason")?.value || "";

  try {
    const resp = await fetch("/api/route/correct", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_type: _correctionTarget.sourceType,
        source_id: _correctionTarget.sourceId,
        manual_routes,
        manual_reason,
      })
    });
    if (resp.ok) {
      showToast("✓ Route correction saved");
      closeCorrectionModal();
      setTimeout(() => location.reload(), 600);
    } else {
      showToast("⚠ Error saving correction");
    }
  } catch (e) {
    showToast("⚠ Network error");
  }
}

async function resetManualRoute(sourceType, sourceId) {
  if (!confirm("Reset to suggested routes?")) return;
  try {
    await fetch(`/api/route/reset?source_type=${sourceType}&source_id=${sourceId}`, { method: "POST" });
    showToast("✓ Manual route cleared");
    setTimeout(() => location.reload(), 600);
  } catch (e) {
    showToast("⚠ Error resetting route");
  }
}

// ── Export ────────────────────────────────────────────────
async function triggerExport() {
  showToast("⏳ Exporting…");
  try {
    const resp = await fetch("/api/export", { method: "POST" });
    const data = await resp.json();
    showToast(`✓ Exported ${data.total} records → exports/`);
  } catch (e) {
    showToast("⚠ Export failed");
  }
}

// ── Definition popovers ───────────────────────────────────
// handled by CSS :hover, but support click toggle on mobile
document.addEventListener("DOMContentLoaded", () => {
  // Close modal on overlay background click
  const overlay = document.getElementById("modal-overlay");
  if (overlay) {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeCorrectionModal();
    });
  }

  // Highlight transcript turn from evidence link
  document.querySelectorAll("[data-turn-ref]").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const turnNum = parseInt(link.dataset.turnRef);
      const turn = document.getElementById(`turn-${turnNum}`);
      if (turn) {
        turn.scrollIntoView({ behavior: "smooth", block: "center" });
        turn.classList.add("turn-highlight");
        setTimeout(() => turn.classList.remove("turn-highlight"), 2000);
      }
    });
  });

  // Auto-animate stat cards
  document.querySelectorAll(".stat-card").forEach((card, i) => {
    card.style.animationDelay = `${i * 50}ms`;
    card.classList.add("animate-in");
  });
});
