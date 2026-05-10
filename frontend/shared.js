window.ClientFinderUI = (() => {
  const stageProgress = {
    queued: 8,
    scraping: 20,
    qualifying: 32,
    pain_signals: 44,
    validating: 56,
    enriching: 70,
    contact_gate: 78,
    ai_scoring: 88,
    readiness_score: 92,
    messages: 96,
    saving: 98,
    done: 100,
    error: 100,
  };

  const apiBaseInput = document.getElementById("apiBase");
  const healthStatus = document.getElementById("healthStatus");

  function apiUrl(path) {
    return `${apiBaseInput.value.replace(/\/$/, "")}${path}`;
  }

  async function fetchJson(path, options = {}) {
    const response = await fetch(apiUrl(path), options);
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed: ${response.status}`);
    }
    return response.json();
  }

  function safeNum(value) {
    if (value === null || value === undefined || value === "") {
      return "0";
    }
    return String(value);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function checkHealth() {
    if (!healthStatus) {
      return;
    }
    healthStatus.textContent = "Checking backend...";
    try {
      const data = await fetchJson("/api/health");
      healthStatus.textContent = `${data.status} • ${data.service} • ${data.date}`;
    } catch (error) {
      healthStatus.textContent = error.message;
    }
  }

  const healthBtn = document.getElementById("healthBtn");
  if (healthBtn) {
    healthBtn.addEventListener("click", checkHealth);
  }

  checkHealth();

  return {
    stageProgress,
    fetchJson,
    safeNum,
    escapeHtml,
    checkHealth,
  };
})();
