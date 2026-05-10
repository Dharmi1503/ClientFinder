const {
  fetchJson,
  safeNum,
  escapeHtml,
} = window.ClientFinderUI;

const filterForm = document.getElementById("filterForm");
const refreshSavedBtn = document.getElementById("refreshSavedBtn");
const savedLeadsBody = document.getElementById("savedLeadsBody");
const urlParams = new URLSearchParams(window.location.search);
const labelFilter = urlParams.get("label") || "";

function renderSavedLeads(rows) {
  if (!rows.length) {
    savedLeadsBody.innerHTML = `<tr><td colspan="6" class="table-empty">No leads found for these filters.</td></tr>`;
    return;
  }

  savedLeadsBody.innerHTML = rows.map((row) => `
    <tr>
      <td>
        <strong>${escapeHtml(row.company_name || "")}</strong><br>
        <span class="helper-text">${escapeHtml(row.email || row.phone || row.website || "")}</span>
      </td>
      <td>${escapeHtml(row.city || "")}</td>
      <td>${escapeHtml(row.industry || "")}</td>
      <td>${escapeHtml(row.source || "")}</td>
      <td>${safeNum(row.composite_score)}</td>
      <td>${escapeHtml(row.status || "")}</td>
    </tr>
  `).join("");
}

async function loadSavedLeads(event) {
  if (event) {
    event.preventDefault();
  }

  const formData = new FormData(filterForm);
  const params = new URLSearchParams({ page: "1", page_size: "20" });

  for (const [key, value] of formData.entries()) {
    if (value) {
      params.set(key, value.toString());
    }
  }

  try {
    const data = await fetchJson(`/api/leads?${params.toString()}`);
    let rows = data.results || [];
    if (labelFilter) {
      rows = rows.filter((row) => (row.label || "").toUpperCase() === labelFilter.toUpperCase());
    }
    renderSavedLeads(rows);
  } catch (error) {
    savedLeadsBody.innerHTML = `<tr><td colspan="6" class="table-empty">${escapeHtml(error.message)}</td></tr>`;
  }
}

filterForm.addEventListener("submit", loadSavedLeads);
refreshSavedBtn.addEventListener("click", loadSavedLeads);
loadSavedLeads();
