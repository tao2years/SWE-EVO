"use client";

import { startTransition, useEffect, useRef, useState } from "react";

const CASE_COLUMNS = [
  { key: "instance_id", label: "case_id", defaultDirection: "asc" },
  { key: "resolved", label: "resolved", defaultDirection: "desc" },
  { key: "f2p_rate", label: "f2p", defaultDirection: "desc" },
  { key: "p2p_rate", label: "p2p", defaultDirection: "desc" },
  { key: "cli_total_cost_usd", label: "cost", defaultDirection: "desc" },
  { key: "cli_duration_ms", label: "duration", defaultDirection: "desc" },
  { key: null, label: "artifacts" },
];

const COMPARISON_METRICS = [
  ["status", "status"],
  ["active_count", "active slots"],
  ["failed_count", "failed"],
  ["inference_done", "inference"],
  ["eval_reports", "eval reports"],
  ["resolved_true_cases", "resolved"],
  ["resolution_rate", "resolved rate"],
  ["f2p_micro_rate", "f2p micro"],
  ["p2p_micro_pass_rate", "p2p micro"],
  ["total_cli_cost_usd", "total cost"],
  ["avg_cli_duration_ms", "avg duration"],
  ["total_cli_turns", "total turns"],
  ["total_cli_model_input_tokens", "input tok"],
  ["total_cli_model_output_tokens", "output tok"],
  ["total_cli_tokens", "total tok"],
  ["cache_hit_rate", "cache hit"],
];

const RUN_STATUS_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "live", label: "Live or needs attention" },
  { value: "completed", label: "Completed" },
  { value: "running", label: "Running" },
  { value: "stalled", label: "Stalled" },
  { value: "timed_out", label: "Timed out" },
  { value: "interrupted", label: "Interrupted" },
  { value: "idle", label: "Idle" },
];

const RUN_TAG_STOPWORDS = new Set([
  "official48",
  "project",
  "coverage",
  "round",
  "rounds",
  "skill",
  "single",
  "trace",
]);

const METRIC_DIRECTIONS = {
  active_count: "lower",
  failed_count: "lower",
  inference_done: "higher",
  eval_reports: "higher",
  resolved_true_cases: "higher",
  resolution_rate: "higher",
  f2p_micro_rate: "higher",
  p2p_micro_pass_rate: "higher",
  total_cli_cost_usd: "lower",
  avg_cli_duration_ms: "lower",
  total_cli_turns: "lower",
  total_cli_model_input_tokens: "lower",
  total_cli_model_output_tokens: "lower",
  total_cli_tokens: "lower",
  cache_hit_rate: "higher",
};

function percent(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function money(value) {
  return typeof value === "number" ? `$${value.toFixed(2)}` : "n/a";
}

function duration(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${(value / 60000).toFixed(1)} min`;
}

function numberish(value) {
  return typeof value === "number" ? value.toLocaleString() : "n/a";
}

function tokenK(value) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${(value / 1000).toFixed(value >= 100000 ? 0 : 1)}k tok`;
}

function metricComparableValue(run, key) {
  if (!run) return null;
  if (key === "inference_done" || key === "eval_reports") {
    return typeof run[key] === "number" && typeof run.total_cases === "number" && run.total_cases > 0
      ? run[key] / run.total_cases
      : null;
  }
  return typeof run[key] === "number" ? run[key] : null;
}

function metricBestRunIds(runs, key) {
  const direction = METRIC_DIRECTIONS[key];
  if (!direction) return new Set();
  const comparable = runs
    .map((run) => [run.run_id, metricComparableValue(run, key)])
    .filter(([, value]) => typeof value === "number" && !Number.isNaN(value));
  if (!comparable.length) return new Set();
  const values = comparable.map(([, value]) => value);
  const target = direction === "lower" ? Math.min(...values) : Math.max(...values);
  return new Set(
    comparable
      .filter(([, value]) => value === target)
      .map(([runId]) => runId),
  );
}

function formatRunMetric(run, key) {
  if (key === "inference_done" || key === "eval_reports") {
    return `${run[key]}/${run.total_cases}`;
  }
  if (key.includes("rate")) {
    return percent(run[key]);
  }
  if (key.includes("cost")) {
    return money(run[key]);
  }
  if (key.includes("duration")) {
    return duration(run[key]);
  }
  if (key.includes("tokens")) {
    return tokenK(run[key]);
  }
  if (key === "cache_hit_rate") {
    return percent(run[key]);
  }
  if (key === "total_cli_turns") {
    return typeof run[key] === "number" ? `${numberish(run[key])} turns` : "n/a";
  }
  if (typeof run[key] === "number") {
    return numberish(run[key]);
  }
  return safeText(run[key]);
}

function safeText(value) {
  return value === null || value === undefined || value === "" ? "n/a" : String(value);
}

function searchTerms(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
}

function runSearchText(run) {
  return [
    run?.display_name,
    run?.run_id,
    run?.status,
    run?.lifecycle_reason,
    run?.updated_at,
    Array.isArray(run?.active_instances) ? run.active_instances.join(" ") : null,
    Array.isArray(run?.failed_instances) ? run.failed_instances.join(" ") : null,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function runTagTokens(run) {
  return runSearchText(run)
    .split(/[^a-z0-9]+/)
    .filter((token) => {
      if (!token || token.length < 3 || token.length > 18) {
        return false;
      }
      if (/^\d+$/.test(token)) {
        return false;
      }
      return !RUN_TAG_STOPWORDS.has(token);
    });
}

function collectRunTags(runs) {
  const counts = new Map();
  for (const run of runs) {
    const uniqueTokens = new Set(runTagTokens(run));
    for (const token of uniqueTokens) {
      counts.set(token, (counts.get(token) || 0) + 1);
    }
  }
  return [...counts.entries()]
    .filter(([, count]) => count >= 2)
    .sort((left, right) => {
      if (left[1] !== right[1]) {
        return right[1] - left[1];
      }
      return left[0].localeCompare(right[0]);
    })
    .slice(0, 10)
    .map(([token]) => token);
}

function runMatchesSearch(run, query) {
  const terms = searchTerms(query);
  if (!terms.length) {
    return true;
  }
  const haystack = runSearchText(run);
  return terms.every((term) => haystack.includes(term));
}

function runMatchesStatus(run, filter) {
  if (filter === "all") {
    return true;
  }
  if (filter === "live") {
    return ["running", "stalled", "timed_out", "interrupted"].includes(run?.status);
  }
  return run?.status === filter;
}

function formatIsoTimestamp(value) {
  if (typeof value !== "string" || !value) {
    return "n/a";
  }
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "n/a" : date.toLocaleString();
}

function analysisFamilyLabel(value) {
  if (value === "inner_advantage") return "inner advantage";
  if (value === "claude_advantage") return "claude advantage";
  if (value === "both_failed") return "both failed";
  if (value === "both_partial") return "both partial";
  if (value === "both_resolved") return "both resolved";
  return safeText(value);
}

function reviewLabel(reviewed) {
  return reviewed ? "reviewed" : "unreviewed";
}

function artifactViewerUrl(url) {
  if (!url) {
    return url;
  }
  if (!url.startsWith("/artifact?")) {
    return url;
  }
  const params = new URLSearchParams(url.split("?", 2)[1] || "");
  const path = params.get("path");
  if (!path) {
    return url;
  }
  return `/artifacts?path=${encodeURIComponent(path)}`;
}

function runDisplayName(run) {
  return run?.display_name || run?.run_id || "n/a";
}

function runActivityText(run) {
  if (!run) {
    return null;
  }

  const parts = [];
  if (run.status === "timed_out" && typeof run.heartbeat_age_minutes === "number") {
    parts.push(`heartbeat timeout ${run.heartbeat_age_minutes}m`);
  } else if (run.status === "interrupted" && run.lifecycle_reason) {
    parts.push(String(run.lifecycle_reason).replaceAll("_", " "));
  }
  if (run.active_count) {
    const activeInstances = Array.isArray(run.active_instances) ? run.active_instances : [];
    if (!activeInstances.length) {
      parts.push(`${run.active_count} infer active`);
    } else {
      const preview = activeInstances.slice(0, 2).join(", ");
      const extra = activeInstances.length > 2 ? ` +${activeInstances.length - 2} more` : "";
      parts.push(`${run.active_count} infer: ${preview}${extra}`);
    }
  }
  if (run.eval_active_count) {
    parts.push(`${run.eval_active_count} eval active`);
  }
  if (run.failed_count) {
    parts.push(`${run.failed_count} failed`);
  }
  if (run.last_router_activity) {
    if (typeof run.router_quiet_minutes === "number" && run.router_quiet_minutes >= 10) {
      parts.push(`router quiet ${run.router_quiet_minutes}m`);
    } else {
      parts.push(`router ${run.last_router_activity}`);
    }
  }
  return parts.length ? parts.join(" · ") : null;
}

function statusClass(status) {
  if (status === "completed") return "status-completed";
  if (status === "running") return "status-running";
  if (status === "stalled") return "status-stalled";
  if (status === "timed_out" || status === "interrupted") return "status-interrupted";
  return "status-idle";
}

function statusLabel(status) {
  if (status === "timed_out") return "timed out";
  return safeText(status);
}

function formatTimestamp(value) {
  return typeof value === "number" ? new Date(value).toLocaleString() : "n/a";
}

function defaultSortDirection(sortKey) {
  return CASE_COLUMNS.find((column) => column.key === sortKey)?.defaultDirection || "desc";
}

function compareCaseValues(left, right, sortKey) {
  const a = left?.[sortKey];
  const b = right?.[sortKey];
  const aMissing = a === null || a === undefined || a === "";
  const bMissing = b === null || b === undefined || b === "";
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  if (typeof a === "boolean" && typeof b === "boolean") return Number(a) - Number(b);
  return String(a).localeCompare(String(b));
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${url} -> ${response.status}`);
  }
  return response.json();
}

function DetailChip({ label, value }) {
  return (
    <span className="detail-chip">
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

function ArtifactLinks({ artifacts }) {
  const entries = Object.entries(artifacts || {}).filter(([, url]) => Boolean(url));
  if (!entries.length) {
    return <span className="empty-inline">n/a</span>;
  }
  return (
    <div className="artifact-links">
      {entries.map(([name, url]) => (
        <a href={artifactViewerUrl(url)} key={name} rel="noreferrer" target="_blank">
          {name}
        </a>
      ))}
    </div>
  );
}

function ToolPayload({ item, kind }) {
  const statusClassName = kind === "result" ? (item.is_error ? "error" : "ok") : "";
  const statusText = kind === "result" ? (item.is_error ? "error" : "ok") : safeText(item.tool_use_id);
  const payload = kind === "result" ? item.content : item.input_json;
  return (
    <div className="trace-item">
      <div className="trace-item-top">
        <div className="trace-item-title">{item.tool_name || "tool"}</div>
        <div className={`trace-item-status ${statusClassName}`.trim()}>{statusText}</div>
      </div>
      {item.tool_summary || item.summary ? (
        <div className="trace-item-summary">{item.tool_summary || item.summary}</div>
      ) : null}
      {payload ? <pre className="trace-code">{payload}</pre> : null}
    </div>
  );
}

function TraceTurn({ turn }) {
  const assistant = turn.assistant || {};
  const requestMessages = turn.request_messages || [];
  return (
    <article className="trace-turn">
      <div className="trace-turn-meta">
        <DetailChip label={`turn ${turn.index}`} value={formatTimestamp(turn.timestamp)} />
        <DetailChip label="http" value={safeText(turn.response_status)} />
        <DetailChip label="latency" value={duration(turn.duration_ms)} />
        <DetailChip label="stop" value={safeText(assistant.stop_reason)} />
      </div>

      {requestMessages.map((message, index) => {
        if (message.kind === "user_text") {
          return (
            <section className="trace-message trace-message-user" key={`user-${turn.index}-${index}`}>
              <div className="trace-label">User</div>
              <pre className="trace-text">{message.text}</pre>
            </section>
          );
        }
        if (message.kind === "tool_results") {
          return (
            <section className="trace-message trace-message-tool" key={`tool-${turn.index}-${index}`}>
              <div className="trace-label">Tool Results</div>
              <div className="trace-list">
                {(message.results || []).map((item, resultIndex) => (
                  <ToolPayload item={item} key={`${item.tool_use_id || resultIndex}-result`} kind="result" />
                ))}
              </div>
            </section>
          );
        }
        return null;
      })}

      <section className="trace-message trace-message-assistant">
        <div className="trace-label">Assistant</div>
        {assistant.text ? <pre className="trace-text">{assistant.text}</pre> : null}
        {assistant.tool_calls?.length ? (
          <div className="trace-list">
            {assistant.tool_calls.map((item, index) => (
              <ToolPayload item={item} key={`${item.tool_use_id || index}-call`} kind="call" />
            ))}
          </div>
        ) : null}
        {!assistant.text && !assistant.tool_calls?.length ? (
          <div className="trace-empty">No assistant text captured for this step.</div>
        ) : null}
      </section>
    </article>
  );
}

export default function DashboardClient({ initialData }) {
  const [runs, setRuns] = useState(initialData?.runs ?? []);
  const [selectedRunId, setSelectedRunId] = useState(initialData?.selectedRunId ?? null);
  const [selectedRunDetail, setSelectedRunDetail] = useState(initialData?.selectedRunDetail ?? null);
  const [analysisOverview, setAnalysisOverview] = useState(initialData?.analysisOverview ?? null);
  const [compareRunIds, setCompareRunIds] = useState(
    () => new Set(initialData?.selectedRunId ? [initialData.selectedRunId] : []),
  );
  const [caseSortKey, setCaseSortKey] = useState("instance_id");
  const [caseSortDirection, setCaseSortDirection] = useState("asc");
  const [runSearch, setRunSearch] = useState("");
  const [runStatusFilter, setRunStatusFilter] = useState("all");
  const [runTagFilter, setRunTagFilter] = useState("all");
  const [showComparedOnly, setShowComparedOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [resolvedFilter, setResolvedFilter] = useState("all");
  const [anomalyFilter, setAnomalyFilter] = useState("all");
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [selectedCaseTrace, setSelectedCaseTrace] = useState(null);
  const [selectedCaseTraceStatus, setSelectedCaseTraceStatus] = useState("idle");
  const [selectedCaseTraceError, setSelectedCaseTraceError] = useState(null);
  const [statusText, setStatusText] = useState("Server-rendered");
  const [displayNameDraft, setDisplayNameDraft] = useState(initialData?.selectedRunDetail?.run?.display_name ?? "");
  const [isSavingDisplayName, setIsSavingDisplayName] = useState(false);
  const [isDeletingRun, setIsDeletingRun] = useState(false);
  const [reviewPendingId, setReviewPendingId] = useState(null);
  const traceCacheRef = useRef(new Map());

  const selectedRuns = runs.filter((run) => compareRunIds.has(run.run_id));
  const runTags = collectRunTags(runs);
  const filteredRuns = runs.filter((run) => {
    if (!runMatchesSearch(run, runSearch)) {
      return false;
    }
    if (!runMatchesStatus(run, runStatusFilter)) {
      return false;
    }
    if (runTagFilter !== "all" && !runTagTokens(run).includes(runTagFilter)) {
      return false;
    }
    if (showComparedOnly && !compareRunIds.has(run.run_id)) {
      return false;
    }
    return true;
  });
  const visibleSelectedRuns = filteredRuns.filter((run) => compareRunIds.has(run.run_id));
  const visibleOtherRuns = filteredRuns.filter((run) => !compareRunIds.has(run.run_id));
  const displayedRuns = [...visibleSelectedRuns, ...visibleOtherRuns];
  const hiddenSelectedCount = selectedRuns.length - visibleSelectedRuns.length;
  const hasRunFilters = Boolean(
    runSearch.trim()
      || runStatusFilter !== "all"
      || runTagFilter !== "all"
      || showComparedOnly,
  );
  const currentCases = selectedRunDetail?.cases ?? [];
  const selectedCase = currentCases.find((item) => item.instance_id === selectedCaseId) ?? null;
  const filteredCases = [...currentCases]
    .filter((row) => {
      if (search.trim()) {
        const haystack = `${row.instance_id} ${row.repo || ""}`.toLowerCase();
        if (!haystack.includes(search.trim().toLowerCase())) {
          return false;
        }
      }
      if (resolvedFilter === "resolved" && row.resolved !== true) {
        return false;
      }
      if (resolvedFilter === "unresolved" && row.resolved !== false) {
        return false;
      }
      if (anomalyFilter === "with" && !(row.anomaly_flags || []).length) {
        return false;
      }
      if (anomalyFilter === "without" && (row.anomaly_flags || []).length) {
        return false;
      }
      return true;
    })
    .sort((left, right) => {
      const comparison = compareCaseValues(left, right, caseSortKey);
      return caseSortDirection === "asc" ? comparison : -comparison;
    });

  useEffect(() => {
    setDisplayNameDraft(selectedRunDetail?.run?.display_name ?? "");
  }, [selectedRunDetail?.run?.run_id, selectedRunDetail?.run?.display_name]);

  useEffect(() => {
    if (showComparedOnly && compareRunIds.size === 0) {
      setShowComparedOnly(false);
    }
  }, [showComparedOnly, compareRunIds]);

  async function handleRefresh(silent = false) {
    if (!silent) {
      setStatusText("Refreshing...");
    }
    try {
      const [nextRunsPayload, nextAnalysisOverview] = await Promise.all([
        fetchJson("/api/runs"),
        fetchJson("/api/analysis"),
      ]);
      const nextRuns = nextRunsPayload.runs || [];
      let nextSelectedRunId = selectedRunId;
      if (!nextSelectedRunId || !nextRuns.some((run) => run.run_id === nextSelectedRunId)) {
        nextSelectedRunId = nextRuns[0]?.run_id ?? null;
      }
      const nextDetail = nextSelectedRunId
        ? await fetchJson(`/api/run/${encodeURIComponent(nextSelectedRunId)}`)
        : null;
      const caseStillExists = nextDetail?.cases?.some((item) => item.instance_id === selectedCaseId) ?? false;

      startTransition(() => {
        setRuns(nextRuns);
        setSelectedRunId(nextSelectedRunId);
        setSelectedRunDetail(nextDetail);
        setAnalysisOverview(nextAnalysisOverview);
        setCompareRunIds((previous) => {
          const next = new Set([...previous].filter((id) => nextRuns.some((run) => run.run_id === id)));
          if (nextSelectedRunId && next.size === 0) {
            next.add(nextSelectedRunId);
          }
          return next;
        });
        if (!caseStillExists) {
          setSelectedCaseId(null);
          setSelectedCaseTrace(null);
          setSelectedCaseTraceStatus("idle");
          setSelectedCaseTraceError(null);
        }
      });
      setStatusText(`Updated ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      setStatusText(`Refresh failed: ${error.message}`);
    }
  }

  async function handleRunSelect(runId) {
    if (!runId || runId === selectedRunId) {
      return;
    }
    setStatusText(`Loading ${runId}...`);
    setSelectedRunId(runId);
    setSelectedRunDetail(null);
    setSelectedCaseId(null);
    setSelectedCaseTrace(null);
    setSelectedCaseTraceStatus("idle");
    setSelectedCaseTraceError(null);
    try {
      const detail = await fetchJson(`/api/run/${encodeURIComponent(runId)}`);
      startTransition(() => {
        setSelectedRunDetail(detail);
        setCompareRunIds((previous) => {
          if (previous.size) {
            return previous;
          }
          return new Set([runId]);
        });
      });
      setStatusText(`Updated ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      setStatusText(`Refresh failed: ${error.message}`);
    }
  }

  async function handleCaseSelect(instanceId) {
    if (!selectedRunId || !instanceId) {
      return;
    }
    const cacheKey = `${selectedRunId}:${instanceId}`;
    setSelectedCaseId(instanceId);
    setSelectedCaseTrace(null);
    setSelectedCaseTraceError(null);
    setSelectedCaseTraceStatus("loading");
    if (traceCacheRef.current.has(cacheKey)) {
      setSelectedCaseTrace(traceCacheRef.current.get(cacheKey));
      setSelectedCaseTraceStatus("loaded");
      return;
    }

    try {
      const trace = await fetchJson(`/api/run/${encodeURIComponent(selectedRunId)}/case/${encodeURIComponent(instanceId)}/trace`);
      traceCacheRef.current.set(cacheKey, trace);
      setSelectedCaseTrace(trace);
      setSelectedCaseTraceStatus("loaded");
    } catch (error) {
      setSelectedCaseTrace(null);
      setSelectedCaseTraceStatus("error");
      setSelectedCaseTraceError(error.message);
    }
  }

  async function handleDisplayNameSave(nextDisplayName) {
    if (!selectedRunId) {
      return;
    }
    setIsSavingDisplayName(true);
    setStatusText("Saving display name...");
    try {
      const detail = await fetch(`/api/run/${encodeURIComponent(selectedRunId)}`, {
        method: "PATCH",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ display_name: nextDisplayName }),
      }).then(async (response) => {
        if (!response.ok) {
          throw new Error(`/api/run/${encodeURIComponent(selectedRunId)} -> ${response.status}`);
        }
        return response.json();
      });

      startTransition(() => {
        setSelectedRunDetail(detail);
        setDisplayNameDraft(detail?.run?.display_name ?? "");
        setRuns((previous) => previous.map((run) => (
          run.run_id === detail.run.run_id ? detail.run : run
        )));
      });
      setStatusText(`Saved display name at ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      setStatusText(`Save failed: ${error.message}`);
    } finally {
      setIsSavingDisplayName(false);
    }
  }

  async function handleDeleteRun() {
    if (!selectedRunDetail?.run?.run_id) {
      return;
    }
    const targetRun = selectedRunDetail.run;
    const targetLabel = runDisplayName(targetRun);
    const confirmed = window.confirm(
      `Delete run "${targetLabel}" (${targetRun.run_id})?\n\nThis removes the run directory and its evaluation logs. Running runs cannot be deleted.`,
    );
    if (!confirmed) {
      return;
    }

    setIsDeletingRun(true);
    setStatusText(`Deleting ${targetRun.run_id}...`);
    try {
      const response = await fetch(`/api/run/${encodeURIComponent(targetRun.run_id)}`, {
        method: "DELETE",
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`/api/run/${encodeURIComponent(targetRun.run_id)} -> ${response.status}`);
      }

      setSelectedCaseId(null);
      setSelectedCaseTrace(null);
      setSelectedCaseTraceStatus("idle");
      setSelectedCaseTraceError(null);
      await handleRefresh(true);
      setStatusText(`Deleted ${targetRun.run_id} at ${new Date().toLocaleTimeString()}`);
    } catch (error) {
      setStatusText(`Delete failed: ${error.message}`);
    } finally {
      setIsDeletingRun(false);
    }
  }

  async function handleAnalysisReview(instanceId, reviewed) {
    if (!instanceId) {
      return;
    }
    setReviewPendingId(instanceId);
    setStatusText(reviewed ? `Marking ${instanceId} reviewed...` : `Clearing review for ${instanceId}...`);
    try {
      const response = await fetch(`/api/analysis/review/${encodeURIComponent(instanceId)}`, {
        method: "PATCH",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reviewed }),
      });
      if (!response.ok) {
        throw new Error(`/api/analysis/review/${encodeURIComponent(instanceId)} -> ${response.status}`);
      }
      await handleRefresh(true);
      setStatusText(
        reviewed
          ? `Marked ${instanceId} reviewed at ${new Date().toLocaleTimeString()}`
          : `Cleared review for ${instanceId} at ${new Date().toLocaleTimeString()}`,
      );
    } catch (error) {
      setStatusText(`Review update failed: ${error.message}`);
    } finally {
      setReviewPendingId(null);
    }
  }

  function toggleCompare(runId, checked) {
    setCompareRunIds((previous) => {
      const next = new Set(previous);
      if (checked) {
        next.add(runId);
      } else {
        next.delete(runId);
      }
      return next;
    });
  }

  function toggleCaseSort(sortKey) {
    if (caseSortKey === sortKey) {
      setCaseSortDirection((previous) => (previous === "asc" ? "desc" : "asc"));
      return;
    }
    setCaseSortKey(sortKey);
    setCaseSortDirection(defaultSortDirection(sortKey));
  }

  function keepCurrentRunOnly() {
    setCompareRunIds(selectedRunId ? new Set([selectedRunId]) : new Set());
  }

  function resetRunFilters() {
    setRunSearch("");
    setRunStatusFilter("all");
    setRunTagFilter("all");
    setShowComparedOnly(false);
  }

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void handleRefresh(true);
    }, 30_000);
    return () => window.clearInterval(intervalId);
  }, [selectedRunId, selectedCaseId]);

  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">SWE-EVO Dashboard</p>
          <h1>Run Observatory</h1>
          <p className="hero-copy">
            Track official48 benchmark rounds, compare completed runs, and drill into case-level outcomes
            without digging through folders.
          </p>
        </div>
        <div className="hero-actions">
          <a className="ghost-button" href="/compare-runs" rel="noreferrer" target="_blank">
            Compare Runs
          </a>
          <button className="primary-button" onClick={() => void handleRefresh()} type="button">
            Refresh
          </button>
          <div className="status-chip">{statusText}</div>
        </div>
      </header>

      <main className="grid">
        <section className="panel run-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Runs</p>
              <h2>Benchmark Rounds</h2>
            </div>
            <p className="panel-note">
              Search by round name, run id, or keywords like <code>pc7 cache</code>; keep your comparison set pinned while
              you browse older rounds.
            </p>
          </div>
          <div className="run-toolbar">
            <input
              className="text-input"
              onChange={(event) => setRunSearch(event.target.value)}
              placeholder="Search name, run id, model, or keyword"
              type="search"
              value={runSearch}
            />
            <select className="select-input" onChange={(event) => setRunStatusFilter(event.target.value)} value={runStatusFilter}>
              {RUN_STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="run-filter-row">
            <button
              className={`run-filter-chip ${showComparedOnly ? "active" : ""}`.trim()}
              onClick={() => setShowComparedOnly((previous) => !previous)}
              type="button"
            >
              {showComparedOnly ? "Showing compare tray only" : "Focus compare tray"}
            </button>
            {runTags.map((tag) => (
              <button
                className={`run-filter-chip ${runTagFilter === tag ? "active" : ""}`.trim()}
                key={tag}
                onClick={() => setRunTagFilter((previous) => (previous === tag ? "all" : tag))}
                type="button"
              >
                {tag}
              </button>
            ))}
          </div>
          <div className="run-meta-row">
            <p className="run-result-note">
              Showing {displayedRuns.length} of {runs.length} rounds. {selectedRuns.length} selected for comparison.
              {hiddenSelectedCount > 0 ? ` ${hiddenSelectedCount} selected rounds are hidden by the current filters.` : ""}
            </p>
            <div className="run-filter-actions">
              {selectedRuns.length > 1 ? (
                <button className="ghost-button" onClick={keepCurrentRunOnly} type="button">
                  Keep current only
                </button>
              ) : null}
              {hasRunFilters ? (
                <button className="ghost-button" onClick={resetRunFilters} type="button">
                  Reset filters
                </button>
              ) : null}
            </div>
          </div>
          {selectedRuns.length ? (
            <section className="run-selection-tray">
              <div className="run-selection-top">
                <div className="run-selection-copy">
                  <p className="panel-kicker">Compare Tray</p>
                  <h3>{selectedRuns.length} rounds ready to compare</h3>
                </div>
                <div className="status-chip">{selectedRuns.length} selected</div>
              </div>
              <div className="selected-run-pills">
                {selectedRuns.map((run) => (
                  <button
                    className={`selected-run-pill ${run.run_id === selectedRunId ? "active" : ""}`.trim()}
                    key={`selected-${run.run_id}`}
                    onClick={() => void handleRunSelect(run.run_id)}
                    type="button"
                  >
                    <span className="selected-run-pill-name">{runDisplayName(run)}</span>
                    <span className="selected-run-pill-meta">
                      {statusLabel(run.status)} · {numberish(run.resolved_true_cases)} resolved · {percent(run.cache_hit_rate)} cache
                    </span>
                  </button>
                ))}
              </div>
            </section>
          ) : null}
          <div className="run-list">
            {displayedRuns.length ? displayedRuns.map((run) => {
              const checked = compareRunIds.has(run.run_id);
              return (
                <article
                  className={`run-card ${run.run_id === selectedRunId ? "selected" : ""}`.trim()}
                  key={run.run_id}
                  onClick={() => void handleRunSelect(run.run_id)}
                >
                  <div className="run-card-top">
                    <div>
                      <p className="run-id">{runDisplayName(run)}</p>
                      <div className="run-updated">
                        {run.display_name ? run.run_id : safeText(run.updated_at)}
                      </div>
                      {run.display_name ? (
                        <div className="run-updated">{safeText(run.updated_at)}</div>
                      ) : null}
                      {runActivityText(run) ? (
                        <div className="run-activity">{runActivityText(run)}</div>
                      ) : null}
                    </div>
                    <span className={`status-badge ${statusClass(run.status)}`.trim()}>{statusLabel(run.status)}</span>
                  </div>
                  <div className="mini-stats">
                    <div className="mini-stat">
                      <div className="mini-stat-label">Inference</div>
                      <div className="mini-stat-value">
                        {run.inference_done}/{run.total_cases}
                      </div>
                    </div>
                    <div className="mini-stat">
                      <div className="mini-stat-label">Eval</div>
                      <div className="mini-stat-value">
                        {run.eval_reports}/{run.total_cases}
                      </div>
                    </div>
                    <div className="mini-stat">
                      <div className="mini-stat-label">Resolved</div>
                      <div className="mini-stat-value">{numberish(run.resolved_true_cases)}</div>
                    </div>
                    <div className="mini-stat">
                      <div className="mini-stat-label">Failed</div>
                      <div className="mini-stat-value">{numberish(run.failed_count)}</div>
                    </div>
                  </div>
                  <label
                    className="compare-toggle"
                    onClick={(event) => {
                      event.stopPropagation();
                    }}
                  >
                    <input
                      checked={checked}
                      onChange={(event) => toggleCompare(run.run_id, event.target.checked)}
                      type="checkbox"
                    />
                    Compare this run
                  </label>
                </article>
              );
            }) : (
              <div className="empty-state run-list-empty">
                No rounds match the current filters. Broaden the search or clear the compare-only focus.
              </div>
            )}
          </div>
        </section>

        <section className="panel compare-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Compare</p>
              <h2>Run Comparison</h2>
            </div>
            <p className="panel-note">Focus on completion, resolution, fix/pass retention, and efficiency at a glance.</p>
          </div>
          {selectedRuns.length ? (
            <div className="table-wrap">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>metric</th>
                    {selectedRuns.map((run) => (
                      <th key={run.run_id}>{runDisplayName(run)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    return COMPARISON_METRICS.map(([key, label]) => {
                      const bestRunIds = metricBestRunIds(selectedRuns, key);
                      return (
                    <tr key={key}>
                      <th>{label}</th>
                        {selectedRuns.map((run) => (
                          <td
                            className={bestRunIds.has(run.run_id) ? "metric-best" : ""}
                            key={`${run.run_id}-${key}`}
                          >
                            {formatRunMetric(run, key)}
                          </td>
                        ))}
                    </tr>
                    );
                    });
                  })()}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">Select at least one run to compare.</div>
          )}
        </section>

        <section className="panel summary-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Selected Run</p>
              <h2>{selectedRunDetail?.run ? runDisplayName(selectedRunDetail.run) : "No run selected"}</h2>
            </div>
            <p className="panel-note">
              {selectedRunDetail?.run
                ? `${selectedRunDetail.run.run_id} · ${statusLabel(selectedRunDetail.run.status)} · ${safeText(selectedRunDetail.run.updated_at)} · ${selectedRunDetail.run.eval_reports}/${selectedRunDetail.run.total_cases} reports${selectedRunDetail.run.active_count ? ` · ${selectedRunDetail.run.active_count} infer active` : ""}${selectedRunDetail.run.eval_active_count ? ` · ${selectedRunDetail.run.eval_active_count} eval active` : ""}${selectedRunDetail.run.failed_count ? ` · ${selectedRunDetail.run.failed_count} failed` : ""}`
                : "Choose a run card to inspect its summary and cases."}
            </p>
          </div>
          {selectedRunDetail?.run ? (
            <div className="display-name-editor">
              <input
                className="text-input"
                disabled={isSavingDisplayName}
                onChange={(event) => setDisplayNameDraft(event.target.value)}
                placeholder="Optional display name for this round"
                type="text"
                value={displayNameDraft}
              />
              <button
                className="primary-button"
                disabled={isSavingDisplayName}
                onClick={() => void handleDisplayNameSave(displayNameDraft)}
                type="button"
              >
                {isSavingDisplayName ? "Saving..." : "Save Name"}
              </button>
              <button
                className="ghost-button"
                disabled={isSavingDisplayName || !selectedRunDetail.run.display_name}
                onClick={() => void handleDisplayNameSave("")}
                type="button"
              >
                Clear
              </button>
              <button
                className="danger-button"
                disabled={isSavingDisplayName || isDeletingRun || selectedRunDetail.run.status === "running"}
                onClick={() => void handleDeleteRun()}
                type="button"
              >
                {isDeletingRun ? "Deleting..." : "Delete Run"}
              </button>
            </div>
          ) : null}
          {selectedRunDetail?.run && runActivityText(selectedRunDetail.run) ? (
            <p className="live-activity-note">
              {runActivityText(selectedRunDetail.run)}
            </p>
          ) : null}
          <div className="summary-cards">
            {selectedRunDetail ? (
              [
                ["Resolved", `${numberish(selectedRunDetail.summary?.resolved_true_cases)}/${numberish(selectedRunDetail.summary?.total_cases)}`, percent(selectedRunDetail.summary?.resolution_rate_known_only)],
                ["F2P Micro", percent(selectedRunDetail.summary?.f2p_micro_rate_known_only), "targeted failing tests repaired"],
                ["P2P Micro", percent(selectedRunDetail.summary?.p2p_micro_pass_rate_known_only), "previously passing tests retained"],
                ["Total Cost", money(selectedRunDetail.summary?.total_cli_cost_usd), "USD"],
                ["Avg Duration", duration(selectedRunDetail.summary?.avg_cli_duration_ms), "mean per case"],
                ["Total Turns", `${numberish(selectedRunDetail.summary?.total_cli_turns)} turns`, "aggregate CLI rounds"],
                ["Input Tokens", tokenK(selectedRunDetail.summary?.total_cli_model_input_tokens), "model input"],
                ["Output Tokens", tokenK(selectedRunDetail.summary?.total_cli_model_output_tokens), "model output"],
                ["Total Tokens", tokenK(selectedRunDetail.summary?.total_cli_tokens), "input + output"],
                ["Cache Hit", percent(selectedRunDetail.summary?.cache_hit_rate), "cache_read / (input + cache_read)"],
              ].map(([title, value, foot]) => (
                <article className="summary-card" key={title}>
                  <h3>{title}</h3>
                  <div className="summary-card-value">{value}</div>
                  <div className="summary-card-foot">{foot}</div>
                </article>
              ))
            ) : (
              <div className="empty-state">No summary available.</div>
            )}
          </div>
          <div className="tool-layout">
            <div>
              <h3>Tool Mix</h3>
              <div className="tool-mix">
                {selectedRunDetail && Object.entries(selectedRunDetail.summary?.aggregate_tool_names || {}).length ? (
                  (() => {
                    const entries = Object.entries(selectedRunDetail.summary.aggregate_tool_names || {});
                    const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
                    return entries.map(([name, count]) => (
                      <div className="tool-bar" key={name}>
                        <div>{name}</div>
                        <div className="tool-track">
                          <div className="tool-fill" style={{ width: `${(count / total) * 100}%` }} />
                        </div>
                        <div>{numberish(count)}</div>
                      </div>
                    ));
                  })()
                ) : (
                  <div className="empty-state">No tool data.</div>
                )}
              </div>
            </div>
            <div>
              <h3>Anomalies</h3>
              <div className="anomaly-list">
                {selectedRunDetail && Object.entries(selectedRunDetail.summary?.anomaly_counts || {}).length ? (
                  Object.entries(selectedRunDetail.summary.anomaly_counts || {}).map(([name, count]) => (
                    <span className="anomaly-pill" key={name}>
                      {name}: {count}
                    </span>
                  ))
                ) : (
                  <div className="empty-state">No anomalies recorded.</div>
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="panel analysis-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Analysis</p>
              <h2>Bad Case Analysis</h2>
            </div>
            <p className="panel-note">
              Surface the manually written case reports, track coverage, and spot recurring failure modes
              without leaving the dashboard.
            </p>
          </div>
          {analysisOverview ? (
            <>
              <div className="summary-cards">
                {[
                  ["Analyzed", `${numberish(analysisOverview.total_docs)}/${numberish(analysisOverview.total_cases)}`, percent(analysisOverview.coverage_rate)],
                  ["Remaining", numberish(analysisOverview.remaining_cases), "cases not yet written up"],
                  ["Reviewed", `${numberish(analysisOverview.reviewed_docs)}/${numberish(analysisOverview.total_docs)}`, percent(analysisOverview.review_rate)],
                  ["Top Issue", safeText(analysisOverview.tag_counts?.[0]?.tag), `${numberish(analysisOverview.tag_counts?.[0]?.count)} docs`],
                  ["Top Family", analysisFamilyLabel(analysisOverview.family_counts?.[0]?.family), `${numberish(analysisOverview.family_counts?.[0]?.count)} docs`],
                  ["Top Repo", safeText(analysisOverview.repo_counts?.[0]?.repo), `${numberish(analysisOverview.repo_counts?.[0]?.count)} docs`],
                ].map(([title, value, foot]) => (
                  <article className="summary-card" key={title}>
                    <h3>{title}</h3>
                    <div className="summary-card-value">{value}</div>
                    <div className="summary-card-foot">{foot}</div>
                  </article>
                ))}
              </div>

              <div className="analysis-layout">
                <div className="analysis-stack">
                  <div className="analysis-section">
                    <h3>Common Issues</h3>
                    <div className="analysis-chip-list">
                      {(analysisOverview.tag_counts || []).slice(0, 10).map((item) => (
                        <span className="analysis-chip" key={item.tag}>
                          {item.tag}: {item.count}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="analysis-section">
                    <h3>Outcome Families</h3>
                    <div className="analysis-chip-list">
                      {(analysisOverview.family_counts || []).map((item) => (
                        <span className="analysis-chip subtle" key={item.family}>
                          {analysisFamilyLabel(item.family)}: {item.count}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="analysis-section">
                    <h3>Repo Spread</h3>
                    <div className="analysis-chip-list">
                      {(analysisOverview.repo_counts || []).map((item) => (
                        <span className="analysis-chip subtle" key={item.repo}>
                          {item.repo}: {item.count}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="analysis-links">
                    {analysisOverview.final_report_url ? (
                      <a className="ghost-button" href={artifactViewerUrl(analysisOverview.final_report_url)} rel="noreferrer" target="_blank">
                        Open Full Report
                      </a>
                    ) : null}
                    {analysisOverview.common_summary_url ? (
                      <a className="ghost-button" href={artifactViewerUrl(analysisOverview.common_summary_url)} rel="noreferrer" target="_blank">
                        Open Summary
                      </a>
                    ) : null}
                    {analysisOverview.synthesis_url ? (
                      <a className="ghost-button" href={artifactViewerUrl(analysisOverview.synthesis_url)} rel="noreferrer" target="_blank">
                        Open Synthesis
                      </a>
                    ) : null}
                    {analysisOverview.synthesis_methodology_url ? (
                      <a className="ghost-button" href={artifactViewerUrl(analysisOverview.synthesis_methodology_url)} rel="noreferrer" target="_blank">
                        Open Synthesis Method
                      </a>
                    ) : null}
                    {analysisOverview.design_url ? (
                      <a className="ghost-button" href={artifactViewerUrl(analysisOverview.design_url)} rel="noreferrer" target="_blank">
                        Open Case Design
                      </a>
                    ) : null}
                    {analysisOverview.playbook_url ? (
                      <a className="ghost-button" href={artifactViewerUrl(analysisOverview.playbook_url)} rel="noreferrer" target="_blank">
                        Open Playbook
                      </a>
                    ) : null}
                    {analysisOverview.template_url ? (
                      <a className="ghost-button" href={artifactViewerUrl(analysisOverview.template_url)} rel="noreferrer" target="_blank">
                        Open Template
                      </a>
                    ) : null}
                    {analysisOverview.backlog_url ? (
                      <a className="ghost-button" href={artifactViewerUrl(analysisOverview.backlog_url)} rel="noreferrer" target="_blank">
                        Open Backlog
                      </a>
                    ) : null}
                  </div>
                </div>

                <div>
                  <h3>Reports</h3>
                  <div className="analysis-doc-list">
                    {(analysisOverview.docs || []).map((doc) => (
                      <article className={`analysis-doc ${selectedCaseId === doc.instance_id ? "selected" : ""}`.trim()} key={doc.instance_id}>
                        <div className="analysis-doc-top">
                          <div>
                            <div className="analysis-doc-id">{doc.instance_id}</div>
                            <div className="analysis-doc-meta">
                              {safeText(doc.repo)} · {safeText(doc.comparison_category)}
                            </div>
                          </div>
                          <div className="analysis-doc-actions">
                            <span className={`review-pill ${doc.reviewed ? "reviewed" : "pending"}`.trim()}>
                              {reviewLabel(doc.reviewed)}
                            </span>
                            <button
                              className="ghost-button review-toggle"
                              disabled={reviewPendingId === doc.instance_id}
                              onClick={() => void handleAnalysisReview(doc.instance_id, !doc.reviewed)}
                              type="button"
                            >
                              {reviewPendingId === doc.instance_id
                                ? "Saving..."
                                : doc.reviewed
                                  ? "Mark Unreviewed"
                                  : "Mark Reviewed"}
                            </button>
                            {doc.url ? (
                              <a className="detail-chip" href={artifactViewerUrl(doc.url)} rel="noreferrer" target="_blank">
                                <strong>open</strong>
                              </a>
                            ) : null}
                          </div>
                        </div>
                        {doc.conclusion ? <p className="analysis-doc-copy">{doc.conclusion}</p> : null}
                        {doc.reviewed_at ? (
                          <div className="analysis-doc-meta review-meta">
                            reviewed at {formatIsoTimestamp(doc.reviewed_at)}
                          </div>
                        ) : null}
                        <div className="analysis-chip-list">
                          {(doc.tags || []).map((tag) => (
                            <span className="analysis-chip subtle" key={`${doc.instance_id}-${tag}`}>
                              {tag}
                            </span>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="empty-state">No analysis overview available.</div>
          )}
        </section>

        <section className="panel case-panel">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Cases</p>
              <h2>Case Drill-Down</h2>
            </div>
            <p className="panel-note">Filter by status, anomaly, or substring; sort by outcome or cost/duration.</p>
          </div>

          <div className="case-toolbar">
            <input
              className="text-input"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search case_id or repo"
              type="search"
              value={search}
            />
            <select className="select-input" onChange={(event) => setResolvedFilter(event.target.value)} value={resolvedFilter}>
              <option value="all">All cases</option>
              <option value="resolved">Resolved only</option>
              <option value="unresolved">Unresolved only</option>
            </select>
            <select className="select-input" onChange={(event) => setAnomalyFilter(event.target.value)} value={anomalyFilter}>
              <option value="all">All anomaly states</option>
              <option value="with">With anomalies</option>
              <option value="without">Without anomalies</option>
            </select>
            <div className="toolbar-note">
              Sorting by {caseSortKey} ({caseSortDirection}). Click a header to toggle order.
            </div>
          </div>

          <div className="table-wrap">
            <table className="case-table">
              <thead>
                <tr>
                  {CASE_COLUMNS.map((column) => (
                    column.key ? (
                      <th
                        aria-sort={
                          caseSortKey === column.key
                            ? caseSortDirection === "asc"
                              ? "ascending"
                              : "descending"
                            : "none"
                        }
                        className="sortable"
                        key={column.key}
                      >
                        <button className="sort-button" onClick={() => toggleCaseSort(column.key)} type="button">
                          <span>{column.label}</span>
                          <span aria-hidden="true" className="sort-arrows">
                            <span className={`sort-arrow ${caseSortKey === column.key && caseSortDirection === "asc" ? "active" : ""}`.trim()}>
                              ▲
                            </span>
                            <span className={`sort-arrow ${caseSortKey === column.key && caseSortDirection === "desc" ? "active" : ""}`.trim()}>
                              ▼
                            </span>
                          </span>
                        </button>
                      </th>
                    ) : (
                      <th key={column.label}>{column.label}</th>
                    )
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredCases.length ? (
                  filteredCases.map((row) => (
                    <tr
                      className={`case-row ${row.instance_id === selectedCaseId ? "selected" : ""}`.trim()}
                      key={row.instance_id}
                      onClick={() => void handleCaseSelect(row.instance_id)}
                    >
                      <td className="case-id">{row.instance_id}</td>
                      <td>
                        {row.resolved === true ? <span className="bool-true">true</span> : null}
                        {row.resolved === false ? <span className="bool-false">false</span> : null}
                        {row.resolved !== true && row.resolved !== false ? "n/a" : null}
                      </td>
                      <td>
                        {numberish(row.f2p_success)}/{numberish(row.f2p_total)}
                        <br />
                        <span className="run-updated">{percent(row.f2p_rate)}</span>
                      </td>
                      <td>
                        {numberish(row.p2p_success)}/{numberish(row.p2p_total)}
                        <br />
                        <span className="run-updated">{percent(row.p2p_rate)}</span>
                      </td>
                      <td>{money(row.cli_total_cost_usd)}</td>
                      <td>{duration(row.cli_duration_ms)}</td>
                      <td>
                        <ArtifactLinks artifacts={row.artifacts} />
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="empty-state" colSpan={7}>
                      No cases match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {!selectedCase ? (
            <div className="empty-state">Click a case row to inspect its full reasoning trace.</div>
          ) : (
            <section className="case-detail">
              <div className="case-detail-top">
                <div>
                  <p className="panel-kicker">Selected Case</p>
                  <h3>{selectedCase.instance_id}</h3>
                  <p className="panel-note">
                    {safeText(selectedCase.repo)} · resolved {safeText(selectedCase.resolved)} · {numberish(selectedCase.cli_num_turns)} CLI turns
                  </p>
                </div>
                <button
                  className="ghost-button"
                  onClick={() => {
                    setSelectedCaseId(null);
                    setSelectedCaseTrace(null);
                    setSelectedCaseTraceStatus("idle");
                    setSelectedCaseTraceError(null);
                  }}
                  type="button"
                >
                  Close
                </button>
              </div>

              <div className="case-detail-metrics">
                <DetailChip label="f2p" value={`${numberish(selectedCase.f2p_success)}/${numberish(selectedCase.f2p_total)} (${percent(selectedCase.f2p_rate)})`} />
                <DetailChip label="p2p" value={`${numberish(selectedCase.p2p_success)}/${numberish(selectedCase.p2p_total)} (${percent(selectedCase.p2p_rate)})`} />
                <DetailChip label="cost" value={money(selectedCase.cli_total_cost_usd)} />
                <DetailChip label="duration" value={duration(selectedCase.cli_duration_ms)} />
              </div>

              <div className="case-detail-block">
                <h4>Artifacts</h4>
                <ArtifactLinks artifacts={selectedCase.artifacts} />
              </div>

              <div className="case-detail-block">
                <h4>Analysis</h4>
                {selectedCase.analysis ? (
                  <>
                    <div className="trace-summary">
                      <DetailChip label="category" value={safeText(selectedCase.analysis.comparison_category)} />
                      <DetailChip label="review" value={reviewLabel(selectedCase.analysis.reviewed)} />
                      {selectedCase.analysis.reviewed_at ? (
                        <DetailChip label="reviewed at" value={formatIsoTimestamp(selectedCase.analysis.reviewed_at)} />
                      ) : null}
                      <button
                        className="ghost-button review-toggle"
                        disabled={reviewPendingId === selectedCase.analysis.instance_id}
                        onClick={() => void handleAnalysisReview(selectedCase.analysis.instance_id, !selectedCase.analysis.reviewed)}
                        type="button"
                      >
                        {reviewPendingId === selectedCase.analysis.instance_id
                          ? "Saving..."
                          : selectedCase.analysis.reviewed
                            ? "Mark Unreviewed"
                            : "Mark Reviewed"}
                      </button>
                      {selectedCase.analysis.url ? (
                        <a className="detail-chip" href={artifactViewerUrl(selectedCase.analysis.url)} rel="noreferrer" target="_blank">
                          <strong>analysis report</strong>
                        </a>
                      ) : null}
                    </div>
                    {selectedCase.analysis.conclusion ? (
                      <p className="analysis-doc-copy case-analysis-copy">{selectedCase.analysis.conclusion}</p>
                    ) : null}
                    <div className="analysis-chip-list">
                      {(selectedCase.analysis.tags || []).map((tag) => (
                        <span className="analysis-chip subtle" key={`${selectedCase.instance_id}-${tag}`}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="empty-state">No case analysis document exists yet for this instance.</div>
                )}
              </div>

              <div className="case-detail-block">
                <h4>Trace Summary</h4>
                <div className="trace-summary">
                  {selectedCaseTraceStatus === "loading" ? (
                    <DetailChip label="trace" value="loading..." />
                  ) : null}
                  {selectedCaseTraceStatus === "error" ? (
                    <DetailChip label="trace" value="load failed" />
                  ) : null}
                  {selectedCaseTrace ? (
                    <>
                      <DetailChip label="requests" value={numberish(selectedCaseTrace.trace_count)} />
                      <DetailChip label="tool calls" value={numberish(selectedCaseTrace.total_tool_calls)} />
                      <DetailChip label="input toks" value={numberish(selectedCaseTrace.total_input_tokens)} />
                      <DetailChip label="output toks" value={numberish(selectedCaseTrace.total_output_tokens)} />
                      <DetailChip label="duration" value={duration(selectedCaseTrace.total_duration_ms)} />
                      <DetailChip label="protocols" value={safeText((selectedCaseTrace.protocols || []).join(", "))} />
                      <DetailChip label="models" value={safeText((selectedCaseTrace.models || []).join(", "))} />
                      {selectedCaseTrace.trace_artifact_url ? (
                        <a className="detail-chip" href={artifactViewerUrl(selectedCaseTrace.trace_artifact_url)} rel="noreferrer" target="_blank">
                          <strong>raw trace</strong>
                        </a>
                      ) : null}
                    </>
                  ) : null}
                </div>
              </div>

              <div className="case-detail-block">
                <h4>Trace Timeline</h4>
                {selectedCaseTraceStatus === "loading" ? (
                  <div className="trace-empty">Loading parsed trace...</div>
                ) : null}
                {selectedCaseTraceStatus === "error" ? (
                  <div className="trace-empty">{selectedCaseTraceError || "Trace request failed."}</div>
                ) : null}
                {selectedCaseTrace && selectedCaseTrace.turns?.length ? (
                  <div className="trace-timeline">
                    {selectedCaseTrace.turns.map((turn) => (
                      <TraceTurn key={turn.index} turn={turn} />
                    ))}
                  </div>
                ) : null}
                {selectedCaseTrace && !selectedCaseTrace.turns?.length ? (
                  <div className="trace-empty">No trace turns were parsed from this case.</div>
                ) : null}
                {!selectedCaseTrace && selectedCaseTraceStatus === "idle" ? (
                  <div className="trace-empty">Select the case again to load trace data.</div>
                ) : null}
              </div>
            </section>
          )}
        </section>
      </main>
    </div>
  );
}
