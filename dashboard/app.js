const state = {
  runs: [],
  selectedRunId: null,
  selectedRunDetail: null,
  compareRunIds: new Set(),
  caseSortKey: "instance_id",
  caseSortDirection: "asc",
  selectedCaseId: null,
  selectedCaseTrace: null,
  selectedCaseTraceStatus: "idle",
  selectedCaseTraceError: null,
  caseTraceCache: new Map(),
};

const CASE_COLUMNS = [
  { key: "instance_id", label: "case_id", defaultDirection: "asc" },
  { key: "resolved", label: "resolved", defaultDirection: "desc" },
  { key: "f2p_rate", label: "f2p", defaultDirection: "desc" },
  { key: "p2p_rate", label: "p2p", defaultDirection: "desc" },
  { key: "cli_total_cost_usd", label: "cost", defaultDirection: "desc" },
  { key: "cli_duration_ms", label: "duration", defaultDirection: "desc" },
  { key: "tool_use_count", label: "tools", defaultDirection: "desc" },
  { key: null, label: "artifacts" },
];

const COMPARISON_METRICS = [
  ["status", "status"],
  ["inference_done", "inference"],
  ["eval_reports", "eval reports"],
  ["resolved_true_cases", "resolved"],
  ["resolution_rate", "resolved rate"],
  ["f2p_micro_rate", "f2p micro"],
  ["p2p_micro_pass_rate", "p2p micro"],
  ["total_cli_cost_usd", "total cost"],
  ["avg_cli_duration_ms", "avg duration"],
];

const els = {
  refreshButton: document.getElementById("refreshButton"),
  lastRefresh: document.getElementById("lastRefresh"),
  runList: document.getElementById("runList"),
  comparisonEmpty: document.getElementById("comparisonEmpty"),
  comparisonTableWrap: document.getElementById("comparisonTableWrap"),
  comparisonTable: document.getElementById("comparisonTable"),
  selectedRunTitle: document.getElementById("selectedRunTitle"),
  selectedRunSubtitle: document.getElementById("selectedRunSubtitle"),
  summaryCards: document.getElementById("summaryCards"),
  toolMix: document.getElementById("toolMix"),
  anomalyList: document.getElementById("anomalyList"),
  searchInput: document.getElementById("searchInput"),
  resolvedFilter: document.getElementById("resolvedFilter"),
  anomalyFilter: document.getElementById("anomalyFilter"),
  caseSortHint: document.getElementById("caseSortHint"),
  caseTableHead: document.getElementById("caseTableHead"),
  caseTableBody: document.getElementById("caseTableBody"),
  caseDetailEmpty: document.getElementById("caseDetailEmpty"),
  caseDetailPanel: document.getElementById("caseDetailPanel"),
  caseDetailTitle: document.getElementById("caseDetailTitle"),
  caseDetailSubtitle: document.getElementById("caseDetailSubtitle"),
  caseDetailMetrics: document.getElementById("caseDetailMetrics"),
  caseDetailArtifacts: document.getElementById("caseDetailArtifacts"),
  caseTraceSummary: document.getElementById("caseTraceSummary"),
  caseTraceTimeline: document.getElementById("caseTraceTimeline"),
  closeCaseDetail: document.getElementById("closeCaseDetail"),
};

function percent(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function money(value) {
  return typeof value === "number" ? `$${value.toFixed(2)}` : "n/a";
}

function duration(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  const totalSeconds = Math.round(value / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function numberish(value) {
  return typeof value === "number" ? value.toLocaleString() : "n/a";
}

function safeText(value) {
  return value === null || value === undefined || value === "" ? "n/a" : String(value);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[char]));
}

function statusClass(status) {
  if (status === "completed") return "status-completed";
  if (status === "running") return "status-running";
  return "status-idle";
}

function formatTimestamp(value) {
  return typeof value === "number" ? new Date(value).toLocaleString() : "n/a";
}

function buildChip(label, value) {
  return `<span class="detail-chip"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></span>`;
}

function artifactLinksHtml(artifacts) {
  return Object.entries(artifacts || {})
    .filter(([, url]) => Boolean(url))
    .map(([name, url]) => `<a href="${url}" target="_blank" rel="noreferrer">${escapeHtml(name)}</a>`)
    .join("");
}

function inputValue(element, fallback = "") {
  if (!element || typeof element.value !== "string") return fallback;
  return element.value;
}

function currentCases() {
  return state.selectedRunDetail?.cases || [];
}

function currentSelectedCase() {
  return currentCases().find((row) => row.instance_id === state.selectedCaseId) || null;
}

function clearSelectedCase() {
  state.selectedCaseId = null;
  state.selectedCaseTrace = null;
  state.selectedCaseTraceStatus = "idle";
  state.selectedCaseTraceError = null;
}

function defaultSortDirection(sortKey) {
  return CASE_COLUMNS.find((column) => column.key === sortKey)?.defaultDirection || "desc";
}

function compareCaseValues(left, right, sortKey) {
  const a = left[sortKey];
  const b = right[sortKey];
  const aMissing = a === null || a === undefined || a === "";
  const bMissing = b === null || b === undefined || b === "";
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "boolean" && typeof b === "boolean") return Number(a) - Number(b);
  return String(a).localeCompare(String(b));
}

function filteredCases() {
  let rows = [...currentCases()];
  const search = inputValue(els.searchInput).trim().toLowerCase();
  const resolvedFilter = inputValue(els.resolvedFilter, "all");
  const anomalyFilter = inputValue(els.anomalyFilter, "all");

  if (search) {
    rows = rows.filter((row) => `${row.instance_id} ${row.repo || ""}`.toLowerCase().includes(search));
  }
  if (resolvedFilter === "resolved") rows = rows.filter((row) => row.resolved === true);
  if (resolvedFilter === "unresolved") rows = rows.filter((row) => row.resolved === false);
  if (anomalyFilter === "with") rows = rows.filter((row) => row.anomaly_flags?.length);
  if (anomalyFilter === "without") rows = rows.filter((row) => !row.anomaly_flags?.length);

  rows.sort((left, right) => {
    const comparison = compareCaseValues(left, right, state.caseSortKey);
    return state.caseSortDirection === "asc" ? comparison : -comparison;
  });
  return rows;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} -> ${response.status}`);
  }
  return response.json();
}

async function loadRuns() {
  const data = await fetchJson("/api/runs");
  state.runs = data.runs || [];
  if (!state.selectedRunId && state.runs.length) {
    state.selectedRunId = state.runs[0].run_id;
    state.compareRunIds.add(state.selectedRunId);
  }
  if (state.selectedRunId && !state.runs.find((run) => run.run_id === state.selectedRunId)) {
    state.selectedRunId = state.runs[0]?.run_id ?? null;
    clearSelectedCase();
  }
}

async function loadRunDetail() {
  if (!state.selectedRunId) {
    state.selectedRunDetail = null;
    clearSelectedCase();
    return;
  }
  state.selectedRunDetail = await fetchJson(`/api/run/${encodeURIComponent(state.selectedRunId)}`);
  if (state.selectedCaseId && !currentCases().some((row) => row.instance_id === state.selectedCaseId)) {
    clearSelectedCase();
  }
}

async function loadCaseTrace(instanceId) {
  if (!state.selectedRunId || !instanceId) return;
  const runId = state.selectedRunId;
  const cacheKey = `${runId}:${instanceId}`;

  state.selectedCaseTraceError = null;
  state.selectedCaseTraceStatus = "loading";
  state.selectedCaseTrace = null;
  renderCaseDetail();

  if (state.caseTraceCache.has(cacheKey)) {
    state.selectedCaseTrace = state.caseTraceCache.get(cacheKey);
    state.selectedCaseTraceStatus = "loaded";
    renderCaseDetail();
    return;
  }

  try {
    const trace = await fetchJson(`/api/run/${encodeURIComponent(runId)}/case/${encodeURIComponent(instanceId)}/trace`);
    if (state.selectedRunId !== runId || state.selectedCaseId !== instanceId) return;
    state.caseTraceCache.set(cacheKey, trace);
    state.selectedCaseTrace = trace;
    state.selectedCaseTraceStatus = "loaded";
    renderCaseDetail();
  } catch (error) {
    if (state.selectedRunId !== runId || state.selectedCaseId !== instanceId) return;
    state.selectedCaseTraceStatus = "error";
    state.selectedCaseTraceError = error.message;
    renderCaseDetail();
  }
}

function renderRuns() {
  if (!els.runList) return;
  els.runList.innerHTML = "";
  for (const run of state.runs) {
    const card = document.createElement("article");
    card.className = `run-card ${run.run_id === state.selectedRunId ? "selected" : ""}`;
    card.addEventListener("click", () => {
      const changed = state.selectedRunId !== run.run_id;
      state.selectedRunId = run.run_id;
      if (changed) clearSelectedCase();
      if (!state.compareRunIds.size) state.compareRunIds.add(run.run_id);
      refreshDetail();
    });

    const checked = state.compareRunIds.has(run.run_id) ? "checked" : "";
    card.innerHTML = `
      <div class="run-card-top">
        <div>
          <p class="run-id">${escapeHtml(run.run_id)}</p>
          <div class="run-updated">${escapeHtml(safeText(run.updated_at))}</div>
        </div>
        <span class="status-badge ${statusClass(run.status)}">${escapeHtml(run.status)}</span>
      </div>
      <div class="mini-stats">
        <div class="mini-stat">
          <div class="mini-stat-label">Inference</div>
          <div class="mini-stat-value">${run.inference_done}/${run.total_cases}</div>
        </div>
        <div class="mini-stat">
          <div class="mini-stat-label">Eval</div>
          <div class="mini-stat-value">${run.eval_reports}/${run.total_cases}</div>
        </div>
        <div class="mini-stat">
          <div class="mini-stat-label">Resolved</div>
          <div class="mini-stat-value">${numberish(run.resolved_true_cases)}</div>
        </div>
      </div>
      <label class="compare-toggle" onclick="event.stopPropagation()">
        <input type="checkbox" data-run-id="${escapeHtml(run.run_id)}" ${checked} />
        Compare this run
      </label>
    `;
    els.runList.appendChild(card);
  }

  els.runList.querySelectorAll("input[type=checkbox]").forEach((input) => {
    input.addEventListener("change", (event) => {
      const runId = event.target.dataset.runId;
      if (event.target.checked) state.compareRunIds.add(runId);
      else state.compareRunIds.delete(runId);
      renderComparison();
    });
  });
}

function renderComparison() {
  if (!els.comparisonEmpty || !els.comparisonTableWrap || !els.comparisonTable) return;
  const selectedRuns = state.runs.filter((run) => state.compareRunIds.has(run.run_id));
  if (!selectedRuns.length) {
    els.comparisonEmpty.classList.remove("hidden");
    els.comparisonTableWrap.classList.add("hidden");
    return;
  }

  els.comparisonEmpty.classList.add("hidden");
  els.comparisonTableWrap.classList.remove("hidden");

  const thead = `
    <thead>
      <tr>
        <th>metric</th>
        ${selectedRuns.map((run) => `<th>${escapeHtml(run.run_id)}</th>`).join("")}
      </tr>
    </thead>
  `;
  const rows = COMPARISON_METRICS.map(([key, label]) => {
    const cells = selectedRuns.map((run) => {
      let rendered = escapeHtml(safeText(run[key]));
      if (key.includes("rate")) rendered = escapeHtml(percent(run[key]));
      if (key.includes("cost")) rendered = escapeHtml(money(run[key]));
      if (key.includes("duration")) rendered = escapeHtml(duration(run[key]));
      if (key === "inference_done" || key === "eval_reports") rendered = escapeHtml(`${run[key]}/${run.total_cases}`);
      return `<td>${rendered}</td>`;
    });
    return `<tr><th>${escapeHtml(label)}</th>${cells.join("")}</tr>`;
  }).join("");

  els.comparisonTable.innerHTML = `${thead}<tbody>${rows}</tbody>`;
}

function renderSummary() {
  const detail = state.selectedRunDetail;
  if (!els.selectedRunTitle || !els.selectedRunSubtitle || !els.summaryCards || !els.toolMix || !els.anomalyList) return;
  if (!detail) {
    els.selectedRunTitle.textContent = "No run selected";
    els.selectedRunSubtitle.textContent = "Choose a run card to inspect its summary and cases.";
    els.summaryCards.innerHTML = "";
    els.toolMix.innerHTML = "";
    els.anomalyList.innerHTML = "";
    renderCases();
    renderCaseDetail();
    return;
  }

  const run = detail.run;
  const summary = detail.summary || {};
  els.selectedRunTitle.textContent = run.run_id;
  els.selectedRunSubtitle.textContent = `${run.status} · ${safeText(run.updated_at)} · ${run.eval_reports}/${run.total_cases} reports`;

  const cards = [
    ["Resolved", `${numberish(summary.resolved_true_cases)}/${numberish(summary.total_cases)}`, percent(summary.resolution_rate_known_only)],
    ["F2P Micro", percent(summary.f2p_micro_rate_known_only), "targeted failing tests repaired"],
    ["P2P Micro", percent(summary.p2p_micro_pass_rate_known_only), "previously passing tests retained"],
    ["Total Cost", money(summary.total_cli_cost_usd), "session-level model usage"],
    ["Avg Duration", duration(summary.avg_cli_duration_ms), "per case"],
    ["Avg Tool Uses", numberish(summary.avg_tool_use_count), "unique tool_use ids per case"],
  ];

  els.summaryCards.innerHTML = cards.map(([title, value, foot]) => `
    <article class="summary-card">
      <h3>${escapeHtml(title)}</h3>
      <div class="summary-card-value">${escapeHtml(value)}</div>
      <div class="summary-card-foot">${escapeHtml(foot)}</div>
    </article>
  `).join("");

  const toolMix = summary.aggregate_tool_names || {};
  const totalTools = Object.values(toolMix).reduce((sum, value) => sum + value, 0) || 1;
  els.toolMix.innerHTML = Object.entries(toolMix).map(([name, count]) => `
    <div class="tool-bar">
      <div>${escapeHtml(name)}</div>
      <div class="tool-track"><div class="tool-fill" style="width:${(count / totalTools) * 100}%"></div></div>
      <div>${numberish(count)}</div>
    </div>
  `).join("") || `<div class="empty-state">No tool data.</div>`;

  const anomalies = summary.anomaly_counts || {};
  els.anomalyList.innerHTML = Object.keys(anomalies).length
    ? Object.entries(anomalies).map(([name, count]) => `<span class="anomaly-pill">${escapeHtml(name)}: ${count}</span>`).join("")
    : `<div class="empty-state">No anomalies recorded.</div>`;

  renderCases();
  renderCaseDetail();
}

function renderCaseTableHead() {
  if (!els.caseTableHead) return;
  const columns = CASE_COLUMNS.map((column) => {
    if (!column.key) {
      return `<th aria-sort="none">${escapeHtml(column.label)}</th>`;
    }
    const isActive = state.caseSortKey === column.key;
    const ariaSort = isActive ? (state.caseSortDirection === "asc" ? "ascending" : "descending") : "none";
    return `
      <th class="sortable" aria-sort="${ariaSort}">
        <button class="sort-button" type="button" data-sort-key="${escapeHtml(column.key)}">
          <span>${escapeHtml(column.label)}</span>
          <span class="sort-arrows" aria-hidden="true">
            <span class="sort-arrow ${isActive && state.caseSortDirection === "asc" ? "active" : ""}">▲</span>
            <span class="sort-arrow ${isActive && state.caseSortDirection === "desc" ? "active" : ""}">▼</span>
          </span>
        </button>
      </th>
    `;
  }).join("");

  els.caseTableHead.innerHTML = `<tr>${columns}</tr>`;
  if (els.caseSortHint) {
    els.caseSortHint.textContent = `Sorting by ${state.caseSortKey} (${state.caseSortDirection}). Click a header to toggle order.`;
  }

  els.caseTableHead.querySelectorAll("[data-sort-key]").forEach((button) => {
    button.addEventListener("click", () => {
      const sortKey = button.dataset.sortKey;
      if (!sortKey) return;
      if (state.caseSortKey === sortKey) {
        state.caseSortDirection = state.caseSortDirection === "asc" ? "desc" : "asc";
      } else {
        state.caseSortKey = sortKey;
        state.caseSortDirection = defaultSortDirection(sortKey);
      }
      renderCases();
    });
  });
}

function renderCases() {
  if (!els.caseTableBody) return;
  renderCaseTableHead();
  const rows = filteredCases();

  if (!rows.length) {
    els.caseTableBody.innerHTML = `<tr><td colspan="8" class="empty-state">No cases match the current filters.</td></tr>`;
    return;
  }

  els.caseTableBody.innerHTML = rows.map((row) => {
    const resolved = row.resolved === true
      ? `<span class="bool-true">true</span>`
      : row.resolved === false
        ? `<span class="bool-false">false</span>`
        : "n/a";
    const artifactLinks = artifactLinksHtml(row.artifacts);
    const selectedClass = row.instance_id === state.selectedCaseId ? "selected" : "";

    return `
      <tr class="case-row ${selectedClass}" data-instance-id="${escapeHtml(row.instance_id)}">
        <td class="case-id">${escapeHtml(row.instance_id)}</td>
        <td>${resolved}</td>
        <td>${numberish(row.f2p_success)}/${numberish(row.f2p_total)} <br /><span class="run-updated">${escapeHtml(percent(row.f2p_rate))}</span></td>
        <td>${numberish(row.p2p_success)}/${numberish(row.p2p_total)} <br /><span class="run-updated">${escapeHtml(percent(row.p2p_rate))}</span></td>
        <td>${escapeHtml(money(row.cli_total_cost_usd))}</td>
        <td>${escapeHtml(duration(row.cli_duration_ms))}</td>
        <td>${numberish(row.tool_use_count)} <br /><span class="run-updated">err ${numberish(row.tool_error_count)}</span></td>
        <td><div class="artifact-links">${artifactLinks || "n/a"}</div></td>
      </tr>
    `;
  }).join("");

  els.caseTableBody.querySelectorAll("[data-instance-id]").forEach((row) => {
    row.addEventListener("click", () => {
      const instanceId = row.dataset.instanceId;
      if (!instanceId) return;
      state.selectedCaseId = instanceId;
      state.selectedCaseTrace = null;
      state.selectedCaseTraceError = null;
      state.selectedCaseTraceStatus = "loading";
      renderCases();
      renderCaseDetail();
      loadCaseTrace(instanceId);
    });
  });
}

function renderTraceListItems(items, kind) {
  return items.map((item) => {
    const title = escapeHtml(item.tool_name || "tool");
    const statusClass = kind === "result" ? (item.is_error ? "error" : "ok") : "";
    const statusText = kind === "result" ? (item.is_error ? "error" : "ok") : safeText(item.tool_use_id);
    const summary = item.tool_summary || item.summary;
    const payload = kind === "result" ? item.content : item.input_json;
    return `
      <div class="trace-item">
        <div class="trace-item-top">
          <div class="trace-item-title">${title}</div>
          <div class="trace-item-status ${statusClass}">${escapeHtml(statusText)}</div>
        </div>
        ${summary ? `<div class="trace-item-summary">${escapeHtml(summary)}</div>` : ""}
        ${payload ? `<pre class="trace-code">${escapeHtml(payload)}</pre>` : ""}
      </div>
    `;
  }).join("");
}

function renderTraceRequestMessage(message) {
  if (message.kind === "user_text") {
    return `
      <section class="trace-message trace-message-user">
        <div class="trace-label">User</div>
        <pre class="trace-text">${escapeHtml(message.text)}</pre>
      </section>
    `;
  }
  if (message.kind === "tool_results") {
    return `
      <section class="trace-message trace-message-tool">
        <div class="trace-label">Tool Results</div>
        <div class="trace-list">${renderTraceListItems(message.results || [], "result")}</div>
      </section>
    `;
  }
  return "";
}

function renderTraceAssistantMessage(assistant) {
  const hasText = Boolean(assistant?.text);
  const toolCalls = assistant?.tool_calls || [];
  const toolCallSection = toolCalls.length
    ? `<div class="trace-list">${renderTraceListItems(toolCalls, "call")}</div>`
    : "";
  const emptyText = !hasText && !toolCalls.length ? `<div class="trace-empty">No assistant text captured for this step.</div>` : "";

  return `
    <section class="trace-message trace-message-assistant">
      <div class="trace-label">Assistant</div>
      ${hasText ? `<pre class="trace-text">${escapeHtml(assistant.text)}</pre>` : ""}
      ${toolCallSection}
      ${emptyText}
    </section>
  `;
}

function renderTraceTurn(turn) {
  const assistant = turn.assistant || {};
  const requestMessages = turn.request_messages || [];
  const meta = [
    buildChip(`turn ${turn.index}`, formatTimestamp(turn.timestamp)),
    buildChip("http", safeText(turn.response_status)),
    buildChip("latency", duration(turn.duration_ms)),
    buildChip("stop", safeText(assistant.stop_reason)),
  ].join("");

  return `
    <article class="trace-turn">
      <div class="trace-turn-meta">${meta}</div>
      ${requestMessages.map(renderTraceRequestMessage).join("")}
      ${renderTraceAssistantMessage(assistant)}
    </article>
  `;
}

function renderCaseDetail() {
  if (
    !els.caseDetailEmpty || !els.caseDetailPanel || !els.caseDetailTitle || !els.caseDetailSubtitle
    || !els.caseDetailMetrics || !els.caseDetailArtifacts || !els.caseTraceSummary || !els.caseTraceTimeline
  ) {
    return;
  }
  const selectedCase = currentSelectedCase();
  if (!selectedCase) {
    els.caseDetailEmpty.classList.remove("hidden");
    els.caseDetailPanel.classList.add("hidden");
    els.caseDetailTitle.textContent = "No case selected";
    els.caseDetailSubtitle.textContent = "Trace will appear here after you select a case.";
    els.caseDetailMetrics.innerHTML = "";
    els.caseDetailArtifacts.innerHTML = "";
    els.caseTraceSummary.innerHTML = "";
    els.caseTraceTimeline.innerHTML = "";
    return;
  }

  els.caseDetailEmpty.classList.add("hidden");
  els.caseDetailPanel.classList.remove("hidden");
  els.caseDetailTitle.textContent = selectedCase.instance_id;
  els.caseDetailSubtitle.textContent = `${safeText(selectedCase.repo)} · resolved ${safeText(selectedCase.resolved)} · ${numberish(selectedCase.cli_num_turns)} CLI turns`;

  const metrics = [
    ["f2p", `${numberish(selectedCase.f2p_success)}/${numberish(selectedCase.f2p_total)} (${percent(selectedCase.f2p_rate)})`],
    ["p2p", `${numberish(selectedCase.p2p_success)}/${numberish(selectedCase.p2p_total)} (${percent(selectedCase.p2p_rate)})`],
    ["cost", money(selectedCase.cli_total_cost_usd)],
    ["duration", duration(selectedCase.cli_duration_ms)],
    ["tool uses", numberish(selectedCase.tool_use_count)],
    ["tool errors", numberish(selectedCase.tool_error_count)],
  ];
  els.caseDetailMetrics.innerHTML = metrics.map(([label, value]) => buildChip(label, value)).join("");
  els.caseDetailArtifacts.innerHTML = artifactLinksHtml(selectedCase.artifacts) || "n/a";

  if (state.selectedCaseTraceStatus === "loading") {
    els.caseTraceSummary.innerHTML = buildChip("trace", "loading...");
    els.caseTraceTimeline.innerHTML = `<div class="trace-empty">Loading parsed trace...</div>`;
    return;
  }

  if (state.selectedCaseTraceStatus === "error") {
    els.caseTraceSummary.innerHTML = buildChip("trace", "load failed");
    els.caseTraceTimeline.innerHTML = `<div class="trace-empty">${escapeHtml(state.selectedCaseTraceError || "Trace request failed.")}</div>`;
    return;
  }

  if (!state.selectedCaseTrace) {
    els.caseTraceSummary.innerHTML = buildChip("trace", "not loaded");
    els.caseTraceTimeline.innerHTML = `<div class="trace-empty">Select the case again to load trace data.</div>`;
    return;
  }

  const trace = state.selectedCaseTrace;
  const traceSummary = [
    buildChip("requests", numberish(trace.trace_count)),
    buildChip("tool calls", numberish(trace.total_tool_calls)),
    buildChip("input toks", numberish(trace.total_input_tokens)),
    buildChip("output toks", numberish(trace.total_output_tokens)),
    buildChip("duration", duration(trace.total_duration_ms)),
    buildChip("protocols", safeText((trace.protocols || []).join(", "))),
    buildChip("models", safeText((trace.models || []).join(", "))),
  ];
  if (trace.trace_artifact_url) {
    traceSummary.push(`<a href="${trace.trace_artifact_url}" target="_blank" rel="noreferrer" class="detail-chip"><strong>raw trace</strong></a>`);
  }
  els.caseTraceSummary.innerHTML = traceSummary.join("");
  els.caseTraceTimeline.innerHTML = (trace.turns || []).length
    ? trace.turns.map(renderTraceTurn).join("")
    : `<div class="trace-empty">No trace turns were parsed from this case.</div>`;
}

async function refreshDetail() {
  await loadRunDetail();
  renderRuns();
  renderComparison();
  renderSummary();
}

async function refreshAll() {
  if (els.lastRefresh) {
    els.lastRefresh.textContent = "Refreshing...";
  }
  try {
    await loadRuns();
    await loadRunDetail();
    renderRuns();
    renderComparison();
    renderSummary();
    if (els.lastRefresh) {
      els.lastRefresh.textContent = `Updated ${new Date().toLocaleTimeString()}`;
    }
  } catch (error) {
    console.error(error);
    if (els.lastRefresh) {
      els.lastRefresh.textContent = `Refresh failed: ${error.message}`;
    }
  }
}

function initDashboard() {
  els.refreshButton?.addEventListener("click", refreshAll);
  els.searchInput?.addEventListener("input", renderCases);
  els.resolvedFilter?.addEventListener("change", renderCases);
  els.anomalyFilter?.addEventListener("change", renderCases);
  els.closeCaseDetail?.addEventListener("click", () => {
    clearSelectedCase();
    renderCases();
    renderCaseDetail();
  });

  refreshAll();
  setInterval(refreshAll, 30000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initDashboard, { once: true });
} else {
  initDashboard();
}
