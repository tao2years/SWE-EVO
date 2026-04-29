import "server-only";

import { spawnSync } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";

const REPO_ROOT = process.cwd();
const RUNS_ROOT = path.join(REPO_ROOT, "official48_runs");
const STATIC_ROOT = path.join(REPO_ROOT, "dashboard");
const LOGS_ROOT = path.join(REPO_ROOT, "logs", "run_evaluation");
const SUMMARY_SCRIPT = path.join(REPO_ROOT, "summarize_official48_run.py");
const RUN_ID_RE = /^\d{8}-\d{6}$/;
const SYSTEM_REMINDER_RE = /<system-reminder>[\s\S]*?<\/system-reminder>\s*/g;
const BENCHMARK_ID_RE = /\n*\[id:[^\]]+\]\s*$/;
const TRACE_CACHE = new Map();

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
  if (await pathExists(summaryPath)) {
    return;
  }

  const monitor = await loadJson(path.join(runDir, "monitor_status.json"), {});
  if (!monitor?.done) {
    return;
  }

  spawnSync("python3", [SUMMARY_SCRIPT, "--run-root", runDir], {
    cwd: REPO_ROOT,
    encoding: "utf-8",
    stdio: "pipe",
    timeout: 120_000,
  });
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

function expectedTotalCases(summaryData, monitor, progress) {
  if (summaryData?.summary?.total_cases) {
    return Number(summaryData.summary.total_cases);
  }
  if (progress?.total_instances) {
    return Number(progress.total_instances);
  }
  if ((monitor?.inference_done ?? 0) > 0 && monitor?.done) {
    return Number(monitor.inference_done);
  }
  return 48;
}

export async function buildRunOverview(runDir) {
  await ensureSummary(runDir);

  const runId = path.basename(runDir);
  const metadata = await loadRunMetadata(runDir);
  const summaryData = await loadJson(path.join(runDir, "analysis", "summary.json"), {});
  const monitor = await loadJson(path.join(runDir, "monitor_status.json"), {});
  const progress = await loadJson(path.join(runDir, "progress_state.json"), {});
  const summary = summaryData?.summary ?? {};

  const totalCases = expectedTotalCases(summaryData, monitor, progress);
  const reportCount = (await actualReportPaths(runId)).length;
  const inferenceDone = Number(monitor?.inference_done ?? 0);
  const evalReports = Math.max(reportCount, Number(monitor?.eval_reports ?? reportCount));
  const evalCompletedTasks = Number(monitor?.eval_completed_tasks ?? reportCount);
  const done = Boolean(monitor?.done);
  const status = done ? "completed" : inferenceDone || evalCompletedTasks ? "running" : "idle";

  return {
    run_id: runId,
    display_name: normalizeDisplayName(metadata?.display_name),
    run_root: toRepoRelative(runDir),
    status,
    updated_at: monitor?.timestamp ?? progress?.timestamp ?? null,
    inference_done: inferenceDone,
    eval_reports: evalReports,
    eval_completed_tasks: evalCompletedTasks,
    total_cases: totalCases,
    summary_available: Boolean(summaryData?.summary),
    resolved_true_cases: summary?.resolved_true_cases ?? null,
    resolution_rate: summary?.resolution_rate_known_only ?? null,
    f2p_micro_rate: summary?.f2p_micro_rate_known_only ?? null,
    p2p_micro_pass_rate: summary?.p2p_micro_pass_rate_known_only ?? null,
    total_cli_cost_usd: summary?.total_cli_cost_usd ?? null,
    avg_cli_duration_ms: summary?.avg_cli_duration_ms ?? null,
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

async function buildCaseDetail(runId, runDir, rawCase) {
  const instanceId = rawCase.instance_id;
  const inferRunDir = path.join(runDir, "infer", "runs", instanceId);
  const evalLogPath = path.join(runDir, "eval_worker_logs", `${instanceId}.log`);
  const reportPath = await findReportPath(runId, instanceId);
  const reportDir = reportPath ? path.dirname(reportPath) : null;

  return {
    ...rawCase,
    tool_counts_by_name: safeParseEmbeddedJson(rawCase.tool_counts_by_name, {}),
    anomaly_flags: safeParseEmbeddedJson(rawCase.anomaly_flags, []),
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
  const cases = [];
  for (const item of summaryData?.cases ?? []) {
    if (item && typeof item === "object") {
      cases.push(await buildCaseDetail(runId, runDir, item));
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
  return {
    runs,
    selectedRunId,
    selectedRunDetail,
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

export async function readArtifact(relativePath) {
  if (!relativePath) {
    return null;
  }
  const absolutePath = path.resolve(REPO_ROOT, relativePath);
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

export { REPO_ROOT, RUNS_ROOT, STATIC_ROOT };
