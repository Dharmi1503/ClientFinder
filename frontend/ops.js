const {
  fetchJson,
  safeNum,
  escapeHtml,
} = window.ClientFinderUI;

const refreshOpsBtn = document.getElementById("refreshOpsBtn");
const scraperHealth = document.getElementById("scraperHealth");
const sourceQuality = document.getElementById("sourceQuality");
const reviewQueue = document.getElementById("reviewQueue");

function renderCards(target, items, emptyText, formatter) {
  if (!items.length) {
    target.className = "stack-grid empty-box";
    target.textContent = emptyText;
    return;
  }

  target.className = "stack-grid";
  target.innerHTML = items.map(formatter).join("");
}

async function loadOpsData() {
  try {
    const [scrapers, quality, queue] = await Promise.all([
      fetchJson("/api/scrapers/health"),
      fetchJson("/api/sources/quality"),
      fetchJson("/api/leads/review-queue?limit=8"),
    ]);

    renderCards(
      scraperHealth,
      scrapers.sources || [],
      "No scraper health data available.",
      (item) => `
        <div class="stack-card">
          <div>
            <strong>${escapeHtml(item.source || "")}</strong>
            <span>${escapeHtml(item.status || "")}</span>
          </div>
          <div>
            <strong>${safeNum(item.success_rate)}%</strong>
            <span>${safeNum(item.leads_saved)} saved</span>
          </div>
        </div>
      `
    );

    renderCards(
      sourceQuality,
      (quality.sources || []).slice(0, 8),
      "No source quality data available.",
      (item) => `
        <div class="stack-card">
          <div>
            <strong>${escapeHtml(item.source || "")}</strong>
            <span>${safeNum(item.total_leads)} leads</span>
          </div>
          <div>
            <strong>${safeNum(item.quality_score)}%</strong>
            <span>weight ${safeNum(item.weight)}</span>
          </div>
        </div>
      `
    );

    renderCards(
      reviewQueue,
      queue.leads || [],
      "No pending review leads.",
      (item) => `
        <div class="stack-card">
          <div>
            <strong>${escapeHtml(item.company_name || "")}</strong>
            <span>${escapeHtml(item.source || "")} • ${escapeHtml(item.city || "")}</span>
          </div>
          <div>
            <strong>${safeNum(item.composite_score)}</strong>
            <span>${escapeHtml(item.review_status || "")}</span>
          </div>
        </div>
      `
    );
  } catch (error) {
    scraperHealth.className = "stack-grid empty-box";
    scraperHealth.textContent = error.message;
  }
}

refreshOpsBtn.addEventListener("click", loadOpsData);
loadOpsData();
