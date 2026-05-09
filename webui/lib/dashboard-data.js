import "server-only";

import { spawnSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";

const WEBUI_ROOT = process.cwd();
const REPO_ROOT = path.resolve(/* turbopackIgnore: true */ WEBUI_ROOT, "..");

function joinRepoPath(...segments) {
  return path.join(/* turbopackIgnore: true */ REPO_ROOT, ...segments);
}

function resolveRepoPath(relativePath) {
  return path.resolve(/* turbopackIgnore: true */ REPO_ROOT, relativePath);
}

const RUNS_ROOT = joinRepoPath("official48_runs");
const STATIC_ROOT = path.join(/* turbopackIgnore: true */ WEBUI_ROOT, "dashboard");
const LOGS_ROOT = joinRepoPath("logs", "run_evaluation");
const SUMMARY_SCRIPT = joinRepoPath("runtime", "summarize_official48_run.py");
const BAD_CASE_ROOT = joinRepoPath("docs", "bad_case_analysis");
const BAD_CASE_REVIEW_PATH = path.join(BAD_CASE_ROOT, "review_status.json");
const RUN_ID_RE = /^\d{8}-\d{6}(?:-.+)?$/;
const SYSTEM_REMINDER_RE = /<system-reminder>[\s\S]*?<\/system-reminder>\s*/g;
const BENCHMARK_ID_RE = /\n*\[id:[^\]]+\]\s*$/;
const TRACE_CACHE = new Map();
const SUMMARY_REFRESH_PROMISES = new Map();
const BAD_CASE_IGNORE = new Set([
  "analysis_framework.md",
  "bad_case_analysis_design.md",
  "candidate_cases.md",
  "common_issues_summary.md",
]);

function isInsideRoot(targetPath) {
  const relative = path.relative(REPO_ROOT, targetPath);
  return relative && !relative.startsWith("..") && !path.isAbsolute(relative);
}

function toRepoRelative(targetPath) {
  const absolute = path.resolve(targetPath);
  const relative = path.relative(REPO_ROOT, absolute);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    return null;
  }
  return relative || null;
}

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function statSafe(targetPath) {
  try {
    return await fs.stat(targetPath);
  } catch {
    return null;
  }
}

async function loadJson(filePath, fallback) {
  try {
    const content = await fs.readFile(filePath, "utf-8");
    return JSON.parse(content);
  } catch {
    return fallback;
  }
}

function parseJsonBlob(blob, fallback) {
  if (blob && typeof blob === "object") {
    return blob;
  }
  if (blob === null || blob === undefined || blob === "") {
    return fallback;
  }
  try {
    return JSON.parse(blob);
  } catch {
    return fallback;
  }
}

function safeParseEmbeddedJson(blob, fallback) {
  if (typeof blob !== "string" || blob === "") {
    return fallback;
  }
  try {
    return JSON.parse(blob);
  } catch {
    return fallback;
  }
}

async function ensureSummary(runDir) {
  const summaryPath = path.join(runDir, "analysis", "summary.json");
  const runId = path.basename(runDir);
  const monitor = await loadJson(path.join(runDir, "monitor_status.json"), {});
  const inferSummaryPath = path.join(runDir, "infer", "inference_summary.json");
  const evalStatusPath = path.join(runDir, "eval_worker_status.json");
  const reportPaths = await actualReportPaths(runId);

  const summaryStat = await statSafe(summaryPath);
  const inferSummaryStat = await statSafe(inferSummaryPath);
  const evalStatusStat = await statSafe(evalStatusPath);
  let latestSourceMtime = Math.max(
    inferSummaryStat?.mtimeMs ?? 0,
    evalStatusStat?.mtimeMs ?? 0,
  );
  for (const reportPath of reportPaths) {
    const reportStat = await statSafe(reportPath);
    latestSourceMtime = Math.max(latestSourceMtime, reportStat?.mtimeMs ?? 0);
  }

  const hasLiveInputs = Boolean(inferSummaryStat || evalStatusStat || reportPaths.length);
  if (!summaryStat && !monitor?.done && !hasLiveInputs) {
    return;
  }

  const needsRefresh = !summaryStat || latestSourceMtime > (summaryStat.mtimeMs + 500);
  if (!needsRefresh) {
    return;
  }

  const refreshKey = runDir;
  if (SUMMARY_REFRESH_PROMISES.has(refreshKey)) {
    await SUMMARY_REFRESH_PROMISES.get(refreshKey);
    return;
  }

  const refreshPromise = (async () => {
    spawnSync("python3", [SUMMARY_SCRIPT, "--run-root", runDir], {
      cwd: REPO_ROOT,
      encoding: "utf-8",
      stdio: "pipe",
      timeout: 120_000,
    });
  })();

  SUMMARY_REFRESH_PROMISES.set(refreshKey, refreshPromise);
  try {
    await refreshPromise;
  } finally {
    SUMMARY_REFRESH_PROMISES.delete(refreshKey);
  }
}

function metadataPath(runDir) {
  return path.join(runDir, "metadata.json");
}

function normalizeDisplayName(value) {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized || null;
}

async function loadRunMetadata(runDir) {
  const metadata = await loadJson(metadataPath(runDir), {});
  return metadata && typeof metadata === "object" ? metadata : {};
}

async function writeRunMetadata(runDir, metadata) {
  await fs.writeFile(metadataPath(runDir), `${JSON.stringify(metadata, null, 2)}\n`, "utf-8");
}

async function detectRuns() {
  const entries = await fs.readdir(RUNS_ROOT, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory() && RUN_ID_RE.test(entry.name))
    .map((entry) => path.join(RUNS_ROOT, entry.name))
    .sort((left, right) => path.basename(right).localeCompare(path.basename(left)));
}

async function collectFiles(rootDir, targetName, results = []) {
  let entries = [];
  try {
    entries = await fs.readdir(rootDir, { withFileTypes: true });
  } catch {
    return results;
  }

  for (const entry of entries) {
    const entryPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      await collectFiles(entryPath, targetName, results);
      continue;
    }
    if (entry.isFile() && entry.name === targetName) {
      results.push(entryPath);
    }
  }

  return results;
}

async function actualReportPaths(runId) {
  const reportRoot = path.join(LOGS_ROOT, `eval_input_${runId}`);
  const results = await collectFiles(reportRoot, "report.json");
  return results.sort();
}

async function findReportPath(runId, instanceId) {
  const reportPaths = await actualReportPaths(runId);
  return reportPaths.find((reportPath) => path.basename(path.dirname(reportPath)) === instanceId) ?? null;
}

async function artifactUrl(targetPath) {
  if (!targetPath || !(await pathExists(targetPath))) {
    return null;
  }
  const relative = toRepoRelative(targetPath);
  if (!relative) {
    return null;
  }
  return `/artifact?path=${encodeURIComponent(relative)}`;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractBacktickField(markdown, fieldName) {
  const pattern = new RegExp(`- \`${escapeRegExp(fieldName)}\`: \`([^\\n\`]+)\``);
  const match = markdown.match(pattern);
  return match?.[1]?.trim() ?? null;
}

function extractIndentedBullet(markdown, label) {
  const lines = markdown.split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trimEnd();
    if (!line.startsWith(`- ${label}`)) {
      continue;
    }
    const inline = line.slice(`- ${label}`.length).trim().replace(/^[:：]\s*/, "");
    if (inline) {
      return inline;
    }
    const collected = [];
    for (let inner = index + 1; inner < lines.length; inner += 1) {
      const next = lines[inner];
      if (/^- /.test(next.trimStart()) || /^## /.test(next)) {
        break;
      }
      if (next.trim()) {
        collected.push(next.trim());
      }
    }
    return collected.join(" ").trim() || null;
  }
  return null;
}

function extractTagList(markdown) {
  const lines = markdown.split("\n");
  const tags = [];
  let capture = false;
  for (const line of lines) {
    if (line.trim() === "- 根因标签：") {
      capture = true;
      continue;
    }
    if (!capture) {
      continue;
    }
    const match = line.match(/^\s*-\s+`([^`]+)`/);
    if (match) {
      tags.push(match[1]);
      continue;
    }
    if (line.trim() === "") {
      continue;
    }
    break;
  }
  return tags;
}

function analysisInstanceIdForPath(docPathOrRelative) {
  const basename = path.basename(String(docPathOrRelative));
  if (!basename.endsWith("_analysis.md") || BAD_CASE_IGNORE.has(basename)) {
    return null;
  }
  return basename.replace(/_analysis\.md$/, "");
}

function normalizeAnalysisReviewState(rawState) {
  const reports = rawState?.reports && typeof rawState.reports === "object"
    ? rawState.reports
    : {};
  return {
    version: 1,
    reports,
  };
}

async function loadAnalysisReviewState() {
  return normalizeAnalysisReviewState(
    await loadJson(BAD_CASE_REVIEW_PATH, { version: 1, reports: {} }),
  );
}

async function writeAnalysisReviewState(state) {
  await fs.writeFile(
    BAD_CASE_REVIEW_PATH,
    `${JSON.stringify(normalizeAnalysisReviewState(state), null, 2)}\n`,
    "utf-8",
  );
}

function reviewInfoForInstance(reviewState, instanceId) {
  const entry = reviewState?.reports?.[instanceId];
  return {
    reviewed: Boolean(entry?.reviewed),
    reviewed_at: typeof entry?.reviewed_at === "string" ? entry.reviewed_at : null,
  };
}

async function parseBadCaseDoc(docPath, reviewState) {
  const markdown = await fs.readFile(docPath, "utf-8");
  const instanceId = analysisInstanceIdForPath(docPath);
  const reviewInfo = reviewInfoForInstance(reviewState, instanceId);
  return {
    instance_id: instanceId,
    title: markdown.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? instanceId,
    repo: extractBacktickField(markdown, "repo"),
    comparison_category: extractBacktickField(markdown, "comparison_category") ?? "unknown",
    conclusion: extractIndentedBullet(markdown, "一句话结论："),
    tags: extractTagList(markdown),
    reviewed: reviewInfo.reviewed,
    reviewed_at: reviewInfo.reviewed_at,
    relative_path: toRepoRelative(docPath),
    url: await artifactUrl(docPath),
  };
}

async function loadBadCaseDocs() {
  if (!(await pathExists(BAD_CASE_ROOT))) {
    return [];
  }
  const reviewState = await loadAnalysisReviewState();
  const entries = await fs.readdir(BAD_CASE_ROOT, { withFileTypes: true });
  const docs = [];
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith("_analysis.md") || BAD_CASE_IGNORE.has(entry.name)) {
      continue;
    }
    docs.push(await parseBadCaseDoc(path.join(BAD_CASE_ROOT, entry.name), reviewState));
  }
  docs.sort(
    (left, right) =>
      Number(left.reviewed) - Number(right.reviewed)
      || left.instance_id.localeCompare(right.instance_id),
  );
  return docs;
}

function countBy(items, valueFn, keyName) {
  const counts = new Map();
  for (const item of items) {
    const value = valueFn(item);
    if (!value) {
      continue;
    }
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || String(left[0]).localeCompare(String(right[0])))
    .map(([name, count]) => ({ [keyName]: name, count }));
}

function countTags(docs) {
  const counts = new Map();
  for (const doc of docs) {
    for (const tag of doc.tags || []) {
      counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([tag, count]) => ({ tag, count }));
}

function analysisFamilyForCategory(category) {
  const value = String(category || "unknown");
  if (value === "both_resolved_reference_success") {
    return "both_resolved";
  }
  if (value === "both_fixed_f2p_but_regressed_p2p" || value.startsWith("both_partial")) {
    return "both_partial";
  }
  if (value === "claude_only" || value.includes("claude_closer")) {
    return "claude_advantage";
  }
  if (value === "inner_only" || value.startsWith("inner_") || value.includes("inner_closer")) {
    return "inner_advantage";
  }
  if (value.startsWith("both_failed")) {
    return "both_failed";
  }
  return "other";
}

export async function buildBadCaseAnalysisOverview() {
  const docs = await loadBadCaseDocs();
  const reviewedDocs = docs.filter((doc) => doc.reviewed).length;
  return {
    total_docs: docs.length,
    total_cases: 48,
    remaining_cases: Math.max(0, 48 - docs.length),
    coverage_rate: docs.length / 48,
    reviewed_docs: reviewedDocs,
    review_rate: docs.length ? reviewedDocs / docs.length : 0,
    unreviewed_docs: Math.max(0, docs.length - reviewedDocs),
    docs,
    category_counts: countBy(docs, (doc) => doc.comparison_category, "category"),
    family_counts: countBy(docs, (doc) => analysisFamilyForCategory(doc.comparison_category), "family"),
    tag_counts: countTags(docs),
    repo_counts: countBy(docs, (doc) => doc.repo, "repo"),
    common_summary_url: await artifactUrl(path.join(BAD_CASE_ROOT, "common_issues_summary.md")),
    synthesis_url: await artifactUrl(path.join(BAD_CASE_ROOT, "cross_case_synthesis.md")),
    final_report_url: await artifactUrl(path.join(BAD_CASE_ROOT, "final_conference_report.md")),
    synthesis_methodology_url: await artifactUrl(path.join(BAD_CASE_ROOT, "synthesis_methodology.md")),
    design_url: await artifactUrl(path.join(BAD_CASE_ROOT, "bad_case_analysis_design.md")),
    framework_url: await artifactUrl(path.join(BAD_CASE_ROOT, "analysis_framework.md")),
    playbook_url: await artifactUrl(path.join(BAD_CASE_ROOT, "reusable_analysis_playbook.md")),
    template_url: await artifactUrl(path.join(BAD_CASE_ROOT, "case_report_template.md")),
    backlog_url: await artifactUrl(path.join(BAD_CASE_ROOT, "candidate_cases.md")),
  };
}

function expectedTotalCases(summaryData, monitor, progress, inferState) {
  if (summaryData?.summary?.total_cases) {
    return Number(summaryData.summary.total_cases);
  }
  if (inferState?.total_instances) {
    return Number(inferState.total_instances);
  }
  if (progress?.total_instances) {
    return Number(progress.total_instances);
  }
  if ((monitor?.inference_done ?? 0) > 0 && monitor?.done) {
    return Number(monitor.inference_done);
  }
  return 48;
}

const ACTIVE_STALL_MINUTES = 10;

function minutesSinceTimestamp(value) {
  if (typeof value !== "string" || !value) {
    return null;
  }
  const parsed = new Date(value.replace(" ", "T"));
  if (Number.isNaN(parsed.valueOf())) {
    return null;
  }
  return Math.max(0, Math.floor((Date.now() - parsed.valueOf()) / 60000));
}

function timestampMsFromString(value) {
  if (typeof value !== "string" || !value) {
    return null;
  }
  const parsed = new Date(value.replace(" ", "T"));
  return Number.isNaN(parsed.valueOf()) ? null : parsed.valueOf();
}

export async function buildRunOverview(runDir) {
  await ensureSummary(runDir);

  const runId = path.basename(runDir);
  const metadata = await loadRunMetadata(runDir);
  const summaryData = await loadJson(path.join(runDir, "analysis", "summary.json"), {});
  const monitor = await loadJson(path.join(runDir, "monitor_status.json"), {});
  const progress = await loadJson(path.join(runDir, "progress_state.json"), {});
  const inferState = await loadJson(path.join(runDir, "infer", "inference_status.json"), {});
  const evalState = await loadJson(path.join(runDir, "eval_worker_status.json"), {});
  const summary = summaryData?.summary ?? {};

  const totalCases = expectedTotalCases(summaryData, monitor, progress, inferState);
  const reportCount = (await actualReportPaths(runId)).length;
  const inferenceDone = Number(monitor?.inference_done ?? inferState?.completed_count ?? 0);
  const evalReports = Math.max(reportCount, Number(monitor?.eval_reports ?? reportCount));
  const evalCompletedTasks = Number(
    monitor?.eval_completed_tasks
      ?? Object.keys(evalState?.completed ?? {}).length
      ?? reportCount
  );
  const evalActiveCount = Number(monitor?.eval_active_count ?? evalState?.active?.length ?? 0);
  const evalActiveInstances = Array.isArray(monitor?.eval_active_instances)
    ? monitor.eval_active_instances
    : Array.isArray(evalState?.active)
      ? evalState.active
      : [];
  const failedCount = Number(inferState?.failed_count ?? 0);
  const failedInstances = Array.isArray(inferState?.failed) ? inferState.failed : [];
  const activeCount = Number(monitor?.active_count ?? progress?.active_count ?? inferState?.active_count ?? 0);
  const activeInstances = Array.isArray(monitor?.active_instances)
    ? monitor.active_instances
    : Array.isArray(progress?.active_instances)
      ? progress.active_instances
      : Array.isArray(inferState?.active)
        ? inferState.active
        : [];
  const lastRouterActivity = typeof monitor?.latest_router_activity === "string" ? monitor.latest_router_activity : null;
  const lastGlobalRouterActivity = typeof monitor?.latest_global_router_activity === "string" ? monitor.latest_global_router_activity : null;
  const effectiveRouterActivity = (() => {
    const activeMs = timestampMsFromString(lastRouterActivity);
    const globalMs = timestampMsFromString(lastGlobalRouterActivity);
    if (globalMs !== null && (activeMs === null || globalMs > activeMs)) {
      return lastGlobalRouterActivity;
    }
    return lastRouterActivity;
  })();
  const routerQuietMinutes = minutesSinceTimestamp(effectiveRouterActivity);
  const done = Boolean(monitor?.done || (inferState?.done && evalState?.done));
  const status = done
    ? "completed"
    : activeCount
      ? (routerQuietMinutes !== null && routerQuietMinutes >= ACTIVE_STALL_MINUTES && !evalActiveCount ? "stalled" : "running")
      : evalActiveCount
        ? "running"
        : inferenceDone || evalCompletedTasks || evalReports
          ? "stalled"
          : "idle";

  return {
    run_id: runId,
    display_name: normalizeDisplayName(metadata?.display_name),
    run_root: toRepoRelative(runDir),
    status,
    updated_at: monitor?.timestamp ?? progress?.timestamp ?? inferState?.timestamp ?? evalState?.timestamp ?? null,
    inference_done: inferenceDone,
    eval_reports: evalReports,
    eval_completed_tasks: evalCompletedTasks,
    eval_active_count: evalActiveCount,
    eval_active_instances: evalActiveInstances,
    failed_count: failedCount,
    failed_instances: failedInstances,
    attempted_count: inferenceDone + failedCount,
    active_count: activeCount,
    active_instances: activeInstances,
    last_router_activity: effectiveRouterActivity,
    router_quiet_minutes: routerQuietMinutes,
    total_cases: totalCases,
    summary_available: Boolean(summaryData?.summary),
    resolved_true_cases: summary?.resolved_true_cases ?? null,
    resolution_rate: summary?.resolution_rate_known_only ?? null,
    f2p_micro_rate: summary?.f2p_micro_rate_known_only ?? null,
    p2p_micro_pass_rate: summary?.p2p_micro_pass_rate_known_only ?? null,
    total_cli_cost_usd: summary?.total_cli_cost_usd ?? null,
    avg_cli_duration_ms: summary?.avg_cli_duration_ms ?? null,
    total_cli_turns: summary?.total_cli_turns ?? null,
    total_cli_model_input_tokens: summary?.total_cli_model_input_tokens ?? null,
    total_cli_model_output_tokens: summary?.total_cli_model_output_tokens ?? null,
    total_cli_tokens: summary?.total_cli_tokens ?? null,
    cache_hit_rate: summary?.cache_hit_rate ?? null,
    total_tool_use_count: summary?.total_tool_use_count ?? null,
    total_tool_error_count: summary?.total_tool_error_count ?? null,
  };
}

export async function scanRuns() {
  const runDirs = await detectRuns();
  const runs = [];
  for (const runDir of runDirs) {
    runs.push(await buildRunOverview(runDir));
  }
  return { runs };
}

async function buildCaseDetail(runId, runDir, rawCase, analysisMap = new Map()) {
  const instanceId = rawCase.instance_id;
  const inferRunDir = path.join(runDir, "infer", "runs", instanceId);
  const evalLogPath = path.join(runDir, "eval_worker_logs", `${instanceId}.log`);
  const reportPath = await findReportPath(runId, instanceId);
  const reportDir = reportPath ? path.dirname(reportPath) : null;
  const analysis = analysisMap.get(instanceId) ?? null;

  return {
    ...rawCase,
    tool_counts_by_name: safeParseEmbeddedJson(rawCase.tool_counts_by_name, {}),
    anomaly_flags: safeParseEmbeddedJson(rawCase.anomaly_flags, []),
    analysis,
    artifacts: {
      report_json: await artifactUrl(reportPath),
      run_instance_log: await artifactUrl(reportDir ? path.join(reportDir, "run_instance.log") : null),
      test_output: await artifactUrl(reportDir ? path.join(reportDir, "test_output.txt") : null),
      patch_diff: await artifactUrl(path.join(inferRunDir, "patch.diff")),
      cli_result: await artifactUrl(path.join(inferRunDir, "cli_result.json")),
      cli_stdout: await artifactUrl(path.join(inferRunDir, "cli_stdout.log")),
      cli_stderr: await artifactUrl(path.join(inferRunDir, "cli_stderr.log")),
      router_trace_bundle: await artifactUrl(path.join(inferRunDir, "router_trace_bundle.json")),
      eval_worker_log: await artifactUrl(evalLogPath),
      analysis_report: analysis?.url ?? null,
    },
  };
}

export async function buildRunDetail(runId) {
  const runDir = path.join(RUNS_ROOT, runId);
  if (!(await pathExists(runDir))) {
    return null;
  }

  const run = await buildRunOverview(runDir);
  const summaryData = await loadJson(path.join(runDir, "analysis", "summary.json"), {
    summary: {},
    cases: [],
  });
  const badCaseDocs = await loadBadCaseDocs();
  const analysisMap = new Map(badCaseDocs.map((doc) => [doc.instance_id, doc]));
  const cases = [];
  for (const item of summaryData?.cases ?? []) {
    if (item && typeof item === "object") {
      cases.push(await buildCaseDetail(runId, runDir, item, analysisMap));
    }
  }

  return {
    run,
    summary: summaryData?.summary ?? {},
    cases,
  };
}

export async function updateRunDisplayName(runId, displayName) {
  const runDir = path.join(RUNS_ROOT, runId);
  if (!(await pathExists(runDir))) {
    return null;
  }

  const metadata = await loadRunMetadata(runDir);
  const normalized = normalizeDisplayName(displayName);
  if (normalized === null) {
    delete metadata.display_name;
  } else {
    metadata.display_name = normalized;
  }
  if (Object.keys(metadata).length === 0) {
    try {
      await fs.unlink(metadataPath(runDir));
    } catch {}
  } else {
    await writeRunMetadata(runDir, metadata);
  }
  return buildRunDetail(runId);
}

export async function deleteRun(runId) {
  const runDir = path.join(RUNS_ROOT, runId);
  if (!(await pathExists(runDir))) {
    return { deleted: false, reason: "not_found" };
  }

  const run = await buildRunOverview(runDir);
  if (run?.status === "running") {
    return { deleted: false, reason: "running" };
  }

  await fs.rm(runDir, { recursive: true, force: true });
  await fs.rm(path.join(LOGS_ROOT, `eval_input_${runId}`), { recursive: true, force: true });

  for (const key of TRACE_CACHE.keys()) {
    if (key.includes(`${path.sep}official48_runs${path.sep}${runId}${path.sep}`)) {
      TRACE_CACHE.delete(key);
    }
  }

  return { deleted: true, reason: null };
}

function stripTransientFields(value) {
  if (Array.isArray(value)) {
    return value.map(stripTransientFields);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => key !== "cache_control")
        .map(([key, inner]) => [key, stripTransientFields(inner)]),
    );
  }
  return value;
}

function canonicalMessage(message) {
  return JSON.stringify(stripTransientFields(message));
}

function commonPrefixLength(left, right) {
  const limit = Math.min(left.length, right.length);
  for (let index = 0; index < limit; index += 1) {
    if (canonicalMessage(left[index]) !== canonicalMessage(right[index])) {
      return index;
    }
  }
  return limit;
}

function renderBlockText(value) {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    const text = value.replace(/\r\n/g, "\n").trim();
    return text || null;
  }
  if (Array.isArray(value)) {
    const parts = value.map(renderBlockText).filter(Boolean);
    return parts.length ? parts.join("\n\n") : null;
  }
  if (typeof value === "object") {
    if (typeof value.text === "string") {
      return renderBlockText(value.text);
    }
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

function cleanPromptText(value) {
  const rendered = renderBlockText(value);
  if (!rendered) {
    return null;
  }
  const withoutReminder = rendered.replace(SYSTEM_REMINDER_RE, "").trim();
  const withoutBenchmarkId = withoutReminder.replace(BENCHMARK_ID_RE, "").trim();
  return withoutBenchmarkId || null;
}

function summarizeToolInput(name, toolInput) {
  if (!toolInput || typeof toolInput !== "object") {
    return renderBlockText(toolInput);
  }
  if (name === "Bash") {
    return toolInput.command ?? null;
  }
  if (name === "Read") {
    const filePath = toolInput.file_path ?? toolInput.path ?? null;
    if (!filePath) {
      return null;
    }
    const bits = [filePath];
    if (toolInput.offset !== undefined || toolInput.limit !== undefined) {
      bits.push(`offset=${toolInput.offset ?? 0}`);
      bits.push(`limit=${toolInput.limit ?? "all"}`);
    }
    return bits.join(" | ");
  }
  if (name === "Edit") {
    return toolInput.file_path ?? toolInput.path ?? null;
  }
  if (name === "Write") {
    return toolInput.file_path ?? toolInput.path ?? null;
  }
  if (name === "Glob") {
    return toolInput.pattern ?? null;
  }
  if (name === "Grep") {
    if (toolInput.pattern && toolInput.include) {
      return `${toolInput.pattern} @ ${toolInput.include}`;
    }
    return toolInput.pattern ?? toolInput.include ?? null;
  }
  return renderBlockText(toolInput);
}

function transformToolCall(block) {
  const toolName = String(block?.name ?? "tool");
  const toolInput = block?.input ?? {};
  return {
    tool_use_id: block?.id ?? null,
    tool_name: toolName,
    summary: summarizeToolInput(toolName, toolInput),
    input_json: typeof toolInput === "object"
      ? JSON.stringify(toolInput, null, 2)
      : renderBlockText(toolInput),
  };
}

function transformToolResult(block, toolIndex) {
  const toolUseId = block?.tool_use_id ?? null;
  const toolMeta = toolIndex.get(String(toolUseId)) ?? {};
  return {
    tool_use_id: toolUseId,
    tool_name: toolMeta.tool_name ?? null,
    tool_summary: toolMeta.summary ?? null,
    is_error: Boolean(block?.is_error),
    content: renderBlockText(block?.content) ?? "",
  };
}

function transformRequestMessage(message, toolIndex) {
  if (!message || typeof message !== "object" || message.role !== "user" || !Array.isArray(message.content)) {
    return [];
  }

  const textParts = [];
  const toolResults = [];
  for (const block of message.content) {
    if (!block || typeof block !== "object") {
      continue;
    }
    if (block.type === "text") {
      const cleaned = cleanPromptText(block.text);
      if (cleaned) {
        textParts.push(cleaned);
      }
    }
    if (block.type === "tool_result") {
      toolResults.push(transformToolResult(block, toolIndex));
    }
  }

  const rendered = [];
  if (textParts.length) {
    rendered.push({ kind: "user_text", text: textParts.join("\n\n") });
  }
  if (toolResults.length) {
    rendered.push({ kind: "tool_results", results: toolResults });
  }
  return rendered;
}

function transformAssistantResponse(response, trace, toolIndex) {
  if (!response || typeof response !== "object") {
    return {
      assistant: {
        text: renderBlockText(trace?.response_body) ?? "",
        tool_calls: [],
        stop_reason: null,
        model: trace?.model ?? null,
        usage: {},
      },
      assistantMessage: null,
    };
  }

  const content = Array.isArray(response.content) ? response.content : [];
  const textParts = [];
  const toolCalls = [];

  for (const block of content) {
    if (!block || typeof block !== "object") {
      continue;
    }
    if (block.type === "thinking") {
      continue;
    }
    if (block.type === "text") {
      const cleaned = renderBlockText(block.text);
      if (cleaned) {
        textParts.push(cleaned);
      }
      continue;
    }
    if (block.type === "tool_use") {
      const toolCall = transformToolCall(block);
      toolCalls.push(toolCall);
      if (toolCall.tool_use_id) {
        toolIndex.set(String(toolCall.tool_use_id), {
          tool_name: toolCall.tool_name,
          summary: toolCall.summary,
        });
      }
    }
  }

  return {
    assistant: {
      text: textParts.join("\n\n").trim(),
      tool_calls: toolCalls,
      stop_reason: response.stop_reason ?? null,
      model: response.model ?? trace?.model ?? null,
      usage: response.usage && typeof response.usage === "object" ? response.usage : {},
    },
    assistantMessage: content.length
      ? { role: response.role ?? "assistant", content }
      : null,
  };
}

function traceBundlePath(runId, instanceId) {
  return path.join(RUNS_ROOT, runId, "infer", "runs", instanceId, "router_trace_bundle.json");
}

export async function buildCaseTraceDetail(runId, instanceId) {
  const bundlePath = traceBundlePath(runId, instanceId);
  if (!(await pathExists(bundlePath))) {
    return null;
  }

  const stat = await fs.stat(bundlePath);
  const cacheKey = `${bundlePath}:${stat.mtimeMs}`;
  if (TRACE_CACHE.has(cacheKey)) {
    return TRACE_CACHE.get(cacheKey);
  }

  const payload = await loadJson(bundlePath, {});
  const traces = Array.isArray(payload?.traces) ? [...payload.traces] : [];
  traces.sort((left, right) => Number(left?.timestamp ?? 0) - Number(right?.timestamp ?? 0));

  const toolIndex = new Map();
  let previousMessages = [];
  const turns = [];
  const protocols = new Set();
  const models = new Set();
  let totalDurationMs = 0;
  let totalInputTokens = 0;
  let totalOutputTokens = 0;
  let totalHttpErrors = 0;
  let totalToolCalls = 0;

  for (let index = 0; index < traces.length; index += 1) {
    const trace = traces[index];
    if (trace?.protocol) {
      protocols.add(trace.protocol);
    }
    if (trace?.model) {
      models.add(trace.model);
    }

    const request = parseJsonBlob(trace?.request_body, {});
    const response = parseJsonBlob(trace?.response_body, {});
    const currentMessages = Array.isArray(request?.messages) ? request.messages : [];
    const prefixLength = commonPrefixLength(previousMessages, currentMessages);
    const requestMessages = currentMessages.slice(prefixLength).flatMap((message) => transformRequestMessage(message, toolIndex));
    const { assistant, assistantMessage } = transformAssistantResponse(response, trace, toolIndex);

    totalToolCalls += assistant.tool_calls.length;
    turns.push({
      index: index + 1,
      timestamp: trace?.timestamp ?? null,
      duration_ms: trace?.duration_ms ?? null,
      response_status: trace?.response_status ?? null,
      request_messages: requestMessages,
      assistant,
    });

    previousMessages = [...currentMessages];
    if (assistantMessage) {
      previousMessages.push(assistantMessage);
    }

    totalDurationMs += Number(trace?.duration_ms ?? 0);
    totalInputTokens += Number(trace?.tokens_input ?? 0);
    totalOutputTokens += Number(trace?.tokens_output ?? 0);
    if (Number(trace?.response_status ?? 200) >= 400) {
      totalHttpErrors += 1;
    }
  }

  const result = {
    run_id: runId,
    instance_id: instanceId,
    trace_artifact_url: await artifactUrl(bundlePath),
    trace_count: traces.length,
    turns,
    protocols: [...protocols].sort(),
    models: [...models].sort(),
    total_duration_ms: totalDurationMs,
    total_input_tokens: totalInputTokens,
    total_output_tokens: totalOutputTokens,
    total_http_errors: totalHttpErrors,
    total_tool_calls: totalToolCalls,
  };
  TRACE_CACHE.set(cacheKey, result);
  return result;
}

export async function buildInitialDashboardData() {
  const { runs } = await scanRuns();
  const selectedRunId = runs[0]?.run_id ?? null;
  const selectedRunDetail = selectedRunId ? await buildRunDetail(selectedRunId) : null;
  const analysisOverview = await buildBadCaseAnalysisOverview();
  return {
    runs,
    selectedRunId,
    selectedRunDetail,
    analysisOverview,
  };
}

function contentTypeForFile(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  switch (extension) {
    case ".json":
      return "application/json; charset=utf-8";
    case ".js":
      return "text/javascript; charset=utf-8";
    case ".css":
      return "text/css; charset=utf-8";
    case ".html":
      return "text/html; charset=utf-8";
    case ".svg":
      return "image/svg+xml";
    case ".png":
      return "image/png";
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".pdf":
      return "application/pdf";
    default:
      return "text/plain; charset=utf-8";
  }
}

function isInlineTextContentType(contentType) {
  return contentType.startsWith("text/") || contentType.startsWith("application/json");
}

export async function readArtifact(relativePath) {
  if (!relativePath) {
    return null;
  }
  const absolutePath = resolveRepoPath(relativePath);
  if (!isInsideRoot(absolutePath)) {
    return null;
  }
  if (!(await pathExists(absolutePath))) {
    return null;
  }

  return {
    content: await fs.readFile(absolutePath),
    contentType: contentTypeForFile(absolutePath),
    filename: path.basename(absolutePath),
  };
}

export async function readArtifactForView(relativePath, maxInlineBytes = 5 * 1024 * 1024) {
  if (!relativePath) {
    return null;
  }
  const absolutePath = resolveRepoPath(relativePath);
  if (!isInsideRoot(absolutePath)) {
    return null;
  }
  if (!(await pathExists(absolutePath))) {
    return null;
  }

  const stat = await fs.stat(absolutePath);
  const contentType = contentTypeForFile(absolutePath);
  const rawUrl = `/artifact?path=${encodeURIComponent(relativePath)}`;
  const textLike = isInlineTextContentType(contentType);
  const tooLarge = stat.size > maxInlineBytes;

  let content = null;
  let parsedJson = null;
  if (textLike && !tooLarge) {
    content = await fs.readFile(absolutePath, "utf-8");
    if (contentType.startsWith("application/json")) {
      try {
        parsedJson = JSON.parse(content);
      } catch {
        parsedJson = null;
      }
    }
  }

  const analysisInstanceId = analysisInstanceIdForPath(relativePath);
  let analysisDoc = null;
  if (analysisInstanceId) {
    const reviewState = await loadAnalysisReviewState();
    const reviewInfo = reviewInfoForInstance(reviewState, analysisInstanceId);
    analysisDoc = {
      instance_id: analysisInstanceId,
      reviewed: reviewInfo.reviewed,
      reviewed_at: reviewInfo.reviewed_at,
    };
  }

  return {
    relativePath,
    filename: path.basename(absolutePath),
    contentType,
    sizeBytes: stat.size,
    textLike,
    tooLarge,
    rawUrl,
    content,
    parsedJson,
    analysisDoc,
  };
}

export async function updateAnalysisReview(instanceId, reviewed) {
  const docPath = path.join(BAD_CASE_ROOT, `${instanceId}_analysis.md`);
  if (!(await pathExists(docPath))) {
    return null;
  }

  const reviewState = await loadAnalysisReviewState();
  if (reviewed) {
    reviewState.reports[instanceId] = {
      reviewed: true,
      reviewed_at: new Date().toISOString(),
    };
  } else {
    delete reviewState.reports[instanceId];
  }
  await writeAnalysisReviewState(reviewState);
  return {
    instance_id: instanceId,
    ...reviewInfoForInstance(reviewState, instanceId),
  };
}

export { REPO_ROOT, RUNS_ROOT, STATIC_ROOT };
