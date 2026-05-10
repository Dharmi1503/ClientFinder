const {
  stageProgress,
  fetchJson,
  safeNum,
  escapeHtml,
} = window.ClientFinderUI;

let activeJobId = null;
let activePoller = null;

const pipelineForm = document.getElementById("pipelineForm");
const runBtn = document.getElementById("runBtn");
const jobBadge = document.getElementById("jobBadge");
const jobMessage = document.getElementById("jobMessage");
const jobStage = document.getElementById("jobStage");
const progressBar = document.getElementById("progressBar");
const freshLeads = document.getElementById("freshLeads");
const intentLeads = document.getElementById("intentLeads");
const openAllLeads = document.getElementById("openAllLeads");
const openHotLeads = document.getElementById("openHotLeads");
const openWarmLeads = document.getElementById("openWarmLeads");
const openColdLeads = document.getElementById("openColdLeads");

function setBadge(status, text = status) {
  jobBadge.className = `badge ${status}`;
  jobBadge.textContent = text;
}

function updateSummary(result) {
  document.getElementById("sumSaved").textContent = safeNum(result.total_saved);
  document.getElementById("sumHot").textContent = safeNum(result.hot);
  document.getElementById("sumWarm").textContent = safeNum(result.warm);
  document.getElementById("sumCold").textContent = safeNum(result.cold);
}

function renderFreshLeads(leads) {
  if (!leads.length) {
    freshLeads.className = "result-grid empty-box";
    freshLeads.textContent = "No fresh leads in the current result.";
    return;
  }

  freshLeads.className = "result-grid";
  freshLeads.innerHTML = leads.map((lead) => `
    <article class="result-card">
      <h4>${escapeHtml(lead.company_name || "Unnamed Lead")}</h4>
      <p class="result-meta">${escapeHtml(lead.city || "")} • ${escapeHtml(lead.source || "")}</p>
      <p class="result-copy">${escapeHtml(lead.hot_reason || lead.intent_signal || "No extra context available.")}</p>
      <div class="pill-row">
        <span class="pill ${(lead.label || "cold").toLowerCase()}">${escapeHtml(lead.label || "COLD")}</span>
        <span class="pill">Fit ${safeNum(lead.fit_score)}</span>
        <span class="pill">Intent ${safeNum(lead.intent_score)}</span>
        <span class="pill">Contact ${safeNum(lead.contact_score)}</span>
      </div>
    </article>
  `).join("");
}

function renderIntentLeads(leads) {
  if (!leads.length) {
    intentLeads.className = "result-grid empty-box";
    intentLeads.textContent = "No intent leads in the current result.";
    return;
  }

  intentLeads.className = "result-grid";
  intentLeads.innerHTML = leads.map((lead) => `
    <article class="result-card">
      <h4>${escapeHtml(lead.company_name || "Unnamed Lead")}</h4>
      <p class="result-meta">${escapeHtml(lead.city || "")} • ${escapeHtml(lead.source || "")}</p>
      <p class="result-copy">${escapeHtml(lead.hot_reason || lead.intent_signal || "No extra context available.")}</p>
      <div class="pill-row">
        <span class="pill ${(lead.label || "cold").toLowerCase()}">${escapeHtml(lead.label || "COLD")}</span>
        <span class="pill">Fit ${safeNum(lead.fit_score)}</span>
        <span class="pill">Intent ${safeNum(lead.intent_score)}</span>
        <span class="pill">Contact ${safeNum(lead.contact_score)}</span>
      </div>
      ${lead.contact_link ? `<p class="result-copy"><a href="${escapeHtml(lead.contact_link)}" target="_blank" rel="noopener noreferrer">Open source post</a></p>` : ""}
    </article>
  `).join("");
}

function applyJobState(job) {
  setBadge(job.status, job.status);
  jobMessage.textContent = job.message || "Working...";
  jobStage.textContent = `Stage: ${job.stage || "unknown"}`;
  progressBar.style.width = `${stageProgress[job.stage] || 12}%`;

  if (job.status === "done" && job.result) {
    const directoryResult = job.result.directory_pipeline || job.result;
    const intentResult = job.result.intent_pipeline || { hot: 0, warm: 0, cold: 0, total_saved: 0, leads: [] };
    updateSummary(directoryResult);
    renderFreshLeads(directoryResult.leads || []);
    document.getElementById("intentHot").textContent = safeNum(intentResult.hot);
    document.getElementById("intentWarm").textContent = safeNum(intentResult.warm);
    document.getElementById("intentCold").textContent = safeNum(intentResult.cold);
    document.getElementById("intentSaved").textContent = safeNum(intentResult.total_saved);
    renderIntentLeads(intentResult.leads || []);
  }
}

async function pollJob(jobId) {
  try {
    const job = await fetchJson(`/api/jobs/${jobId}`);
    applyJobState(job);
    if (job.status === "done" || job.status === "error") {
      clearInterval(activePoller);
      activePoller = null;
      runBtn.disabled = false;
    }
  } catch (error) {
    setBadge("error", "error");
    jobMessage.textContent = error.message;
    clearInterval(activePoller);
    activePoller = null;
    runBtn.disabled = false;
  }
}

async function runPipeline(event) {
  event.preventDefault();

  if (activePoller) {
    clearInterval(activePoller);
  }

  const formData = new FormData(pipelineForm);
  const service = formData.get("service");
  const industry = formData.get("industry");

  const payload = {
    service: `${service} for ${industry}`,
    industry,
    location: formData.get("location"),
    budget_range: formData.get("budget_range"),
    max_leads: Number(formData.get("max_leads")),
    fast_mode: pipelineForm.elements.fast_mode.checked,
  };

  runBtn.disabled = true;
  setBadge("running", "running");
  jobMessage.textContent = "Starting pipeline job...";
  jobStage.textContent = "Stage: queued";
  progressBar.style.width = "12%";

  try {
    const result = await fetchJson("/api/find-clients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    activeJobId = result.job_id;
    jobMessage.textContent = result.message;
    activePoller = setInterval(() => pollJob(activeJobId), 2500);
    pollJob(activeJobId);
  } catch (error) {
    setBadge("error", "error");
    jobMessage.textContent = error.message;
    runBtn.disabled = false;
  }
}

pipelineForm.addEventListener("submit", runPipeline);

function goToLeads(label = "") {
  const url = new URL("./leads.html", window.location.href);
  if (label) {
    url.searchParams.set("label", label);
  }
  window.location.href = url.toString();
}

openAllLeads.addEventListener("click", () => goToLeads());
openHotLeads.addEventListener("click", () => goToLeads("HOT"));
openWarmLeads.addEventListener("click", () => goToLeads("WARM"));
openColdLeads.addEventListener("click", () => goToLeads("COLD"));
