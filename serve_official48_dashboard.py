#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import subprocess
import threading
import urllib.parse
from functools import lru_cache
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
RUNS_ROOT = REPO_ROOT / "official48_runs"
STATIC_ROOT = REPO_ROOT / "dashboard"
LOGS_ROOT = REPO_ROOT / "logs" / "run_evaluation"
SUMMARY_SCRIPT = REPO_ROOT / "summarize_official48_run.py"
RUN_ID_RE = re.compile(r"^\d{8}-\d{6}$")
_SUMMARY_LOCK = threading.Lock()
_SYSTEM_REMINDER_RE = re.compile(r"(?s)<system-reminder>.*?</system-reminder>\s*")
_BENCHMARK_ID_RE = re.compile(r"\n*\[id:[^\]]+\]\s*$")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def run_log_root(run_id: str) -> Path:
    return LOGS_ROOT / f"eval_input_{run_id}"


def actual_report_paths(run_id: str) -> list[Path]:
    return sorted(run_log_root(run_id).glob("**/report.json"))


def find_report_path(run_id: str, instance_id: str) -> Path | None:
    for path in actual_report_paths(run_id):
        if path.parent.name == instance_id:
            return path
    return None


def to_rel(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return str(path.resolve().relative_to(REPO_ROOT))


def artifact_url(path: Path | None) -> str | None:
    rel = to_rel(path)
    if rel is None:
        return None
    return f"/artifact?path={urllib.parse.quote(rel)}"


def parse_json_blob(blob: Any, default: Any) -> Any:
    if isinstance(blob, (dict, list)):
        return blob
    if blob is None or blob == "":
        return default
    try:
        return json.loads(blob)
    except Exception:
        return default


def strip_transient_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_transient_fields(item)
            for key, item in value.items()
            if key != "cache_control"
        }
    if isinstance(value, list):
        return [strip_transient_fields(item) for item in value]
    return value


def canonical_message(message: Any) -> str:
    return json.dumps(strip_transient_fields(message), ensure_ascii=False, sort_keys=True)


def common_prefix_len(left: list[Any], right: list[Any]) -> int:
    limit = min(len(left), len(right))
    for index in range(limit):
        if canonical_message(left[index]) != canonical_message(right[index]):
            return index
    return limit


def clean_prompt_text(text: Any) -> str | None:
    cleaned = render_block_text(text)
    if not cleaned:
        return None
    cleaned = _SYSTEM_REMINDER_RE.sub("", cleaned).strip()
    cleaned = _BENCHMARK_ID_RE.sub("", cleaned).strip()
    return cleaned or None


def render_block_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.replace("\r\n", "\n").strip()
        return text or None
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            rendered = render_block_text(item)
            if rendered:
                parts.append(rendered)
        joined = "\n\n".join(parts).strip()
        return joined or None
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return render_block_text(value["text"])
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def summarize_tool_input(name: str, tool_input: Any) -> str | None:
    if not isinstance(tool_input, dict):
        return render_block_text(tool_input)
    if name == "Bash":
        return tool_input.get("command")
    if name == "Read":
        file_path = tool_input.get("file_path") or tool_input.get("path")
        offset = tool_input.get("offset")
        limit = tool_input.get("limit")
        if file_path and (offset is not None or limit is not None):
            return f"{file_path} (offset={offset or 0}, limit={limit if limit is not None else 'all'})"
        return file_path
    if name == "Edit":
        file_path = tool_input.get("file_path") or tool_input.get("path")
        old_string = tool_input.get("old_string")
        new_string = tool_input.get("new_string")
        bits = [bit for bit in [file_path, "replace" if old_string is not None else None, "write" if new_string is not None else None] if bit]
        return " | ".join(bits) if bits else None
    if name == "Write":
        return tool_input.get("file_path") or tool_input.get("path")
    if name == "Glob":
        return tool_input.get("pattern")
    if name == "Grep":
        pattern = tool_input.get("pattern")
        include = tool_input.get("include")
        if pattern and include:
            return f"{pattern} @ {include}"
        return pattern or include
    return render_block_text(tool_input)


def transform_tool_call(block: dict[str, Any]) -> dict[str, Any]:
    name = str(block.get("name") or "tool")
    tool_input = block.get("input", {})
    return {
        "tool_use_id": block.get("id"),
        "tool_name": name,
        "summary": summarize_tool_input(name, tool_input),
        "input_json": json.dumps(tool_input, ensure_ascii=False, indent=2) if isinstance(tool_input, dict) else render_block_text(tool_input),
    }


def transform_tool_result(block: dict[str, Any], tool_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    tool_use_id = block.get("tool_use_id")
    tool_meta = tool_index.get(str(tool_use_id), {})
    return {
        "tool_use_id": tool_use_id,
        "tool_name": tool_meta.get("tool_name"),
        "tool_summary": tool_meta.get("summary"),
        "is_error": bool(block.get("is_error")),
        "content": render_block_text(block.get("content")) or "",
    }


def transform_request_message(message: Any, tool_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(message, dict) or message.get("role") != "user":
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []

    text_parts: list[str] = []
    tool_results: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            cleaned = clean_prompt_text(block.get("text"))
            if cleaned:
                text_parts.append(cleaned)
        elif block_type == "tool_result":
            tool_results.append(transform_tool_result(block, tool_index))

    rendered: list[dict[str, Any]] = []
    if text_parts:
        rendered.append({"kind": "user_text", "text": "\n\n".join(text_parts)})
    if tool_results:
        rendered.append({"kind": "tool_results", "results": tool_results})
    return rendered


def transform_assistant_response(response: Any, trace: dict[str, Any], tool_index: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not isinstance(response, dict):
        fallback_text = render_block_text(trace.get("response_body"))
        assistant = {
            "text": fallback_text or "",
            "tool_calls": [],
            "stop_reason": None,
            "model": trace.get("model"),
            "usage": {},
        }
        return assistant, None

    content = response.get("content")
    if not isinstance(content, list):
        content = []

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "thinking":
            continue
        if block_type == "text":
            cleaned = render_block_text(block.get("text"))
            if cleaned:
                text_parts.append(cleaned)
            continue
        if block_type == "tool_use":
            tool_call = transform_tool_call(block)
            tool_calls.append(tool_call)
            tool_use_id = tool_call.get("tool_use_id")
            if tool_use_id:
                tool_index[str(tool_use_id)] = {
                    "tool_name": tool_call["tool_name"],
                    "summary": tool_call.get("summary"),
                }

    assistant = {
        "text": "\n\n".join(text_parts).strip(),
        "tool_calls": tool_calls,
        "stop_reason": response.get("stop_reason"),
        "model": response.get("model") or trace.get("model"),
        "usage": response.get("usage") if isinstance(response.get("usage"), dict) else {},
    }
    assistant_message = {"role": response.get("role") or "assistant", "content": content} if content else None
    return assistant, assistant_message


def trace_bundle_path(run_id: str, instance_id: str) -> Path:
    return RUNS_ROOT / run_id / "infer" / "runs" / instance_id / "router_trace_bundle.json"


@lru_cache(maxsize=64)
def load_case_trace_view(path_str: str, mtime_ns: int, run_id: str, instance_id: str) -> dict[str, Any]:
    del mtime_ns
    path = Path(path_str)
    payload = load_json(path, {})
    traces = payload.get("traces", []) if isinstance(payload, dict) else []
    ordered_traces = [trace for trace in traces if isinstance(trace, dict)]
    ordered_traces.sort(key=lambda trace: int(trace.get("timestamp") or 0))

    prev_messages: list[Any] = []
    tool_index: dict[str, dict[str, Any]] = {}
    turns: list[dict[str, Any]] = []
    protocols: set[str] = set()
    models: set[str] = set()
    total_duration_ms = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_http_errors = 0
    total_tool_calls = 0

    for index, trace in enumerate(ordered_traces, start=1):
        protocol = trace.get("protocol")
        model = trace.get("model")
        if isinstance(protocol, str) and protocol:
            protocols.add(protocol)
        if isinstance(model, str) and model:
            models.add(model)

        request = parse_json_blob(trace.get("request_body"), {})
        response = parse_json_blob(trace.get("response_body"), {})
        current_messages = request.get("messages") if isinstance(request, dict) and isinstance(request.get("messages"), list) else []
        prefix_len = common_prefix_len(prev_messages, current_messages)
        new_request_messages = current_messages[prefix_len:]

        request_messages: list[dict[str, Any]] = []
        for message in new_request_messages:
            request_messages.extend(transform_request_message(message, tool_index))

        assistant, assistant_message = transform_assistant_response(response, trace, tool_index)
        total_tool_calls += len(assistant["tool_calls"])

        turns.append(
            {
                "index": index,
                "timestamp": trace.get("timestamp"),
                "duration_ms": trace.get("duration_ms"),
                "response_status": trace.get("response_status"),
                "request_messages": request_messages,
                "assistant": assistant,
            }
        )

        prev_messages = list(current_messages)
        if assistant_message is not None:
            prev_messages.append(assistant_message)

        total_duration_ms += int(trace.get("duration_ms") or 0)
        total_input_tokens += int(trace.get("tokens_input") or 0)
        total_output_tokens += int(trace.get("tokens_output") or 0)
        if int(trace.get("response_status") or 200) >= 400:
            total_http_errors += 1

    return {
        "run_id": run_id,
        "instance_id": instance_id,
        "trace_artifact_url": artifact_url(path),
        "trace_count": len(ordered_traces),
        "turns": turns,
        "protocols": sorted(protocols),
        "models": sorted(models),
        "total_duration_ms": total_duration_ms,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_http_errors": total_http_errors,
        "total_tool_calls": total_tool_calls,
    }


def ensure_summary(run_dir: Path) -> None:
    summary_path = run_dir / "analysis" / "summary.json"
    if summary_path.exists():
        return
    monitor = load_json(run_dir / "monitor_status.json", {})
    if not monitor.get("done"):
        return
    with _SUMMARY_LOCK:
        if summary_path.exists():
            return
        subprocess.run(
            ["python3", str(SUMMARY_SCRIPT), "--run-root", str(run_dir)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )


def detect_runs() -> list[Path]:
    return sorted(
        [path for path in RUNS_ROOT.iterdir() if path.is_dir() and RUN_ID_RE.match(path.name)],
        reverse=True,
    )


def expected_total_cases(run_dir: Path, summary: dict, monitor: dict, progress: dict) -> int:
    if summary.get("summary", {}).get("total_cases"):
        return int(summary["summary"]["total_cases"])
    if progress.get("total_instances"):
        return int(progress["total_instances"])
    if monitor.get("inference_done", 0) > 0 and monitor.get("done"):
        return int(monitor["inference_done"])
    return 48


def build_run_overview(run_dir: Path) -> dict[str, Any]:
    ensure_summary(run_dir)
    summary_data = load_json(run_dir / "analysis" / "summary.json", {})
    monitor = load_json(run_dir / "monitor_status.json", {})
    progress = load_json(run_dir / "progress_state.json", {})
    total_cases = expected_total_cases(run_dir, summary_data, monitor, progress)
    report_count = len(actual_report_paths(run_dir.name))
    inference_done = int(monitor.get("inference_done", 0))
    eval_reports = int(monitor.get("eval_reports", report_count))
    eval_completed_tasks = int(monitor.get("eval_completed_tasks", report_count))
    done = bool(monitor.get("done"))
    status = "completed" if done else ("running" if inference_done or eval_completed_tasks else "idle")
    summary = summary_data.get("summary", {})

    return {
        "run_id": run_dir.name,
        "run_root": to_rel(run_dir),
        "status": status,
        "updated_at": monitor.get("timestamp") or progress.get("timestamp"),
        "inference_done": inference_done,
        "eval_reports": report_count if report_count >= eval_reports else eval_reports,
        "eval_completed_tasks": eval_completed_tasks,
        "total_cases": total_cases,
        "summary_available": bool(summary_data),
        "resolved_true_cases": summary.get("resolved_true_cases"),
        "resolution_rate": summary.get("resolution_rate_known_only"),
        "f2p_micro_rate": summary.get("f2p_micro_rate_known_only"),
        "p2p_micro_pass_rate": summary.get("p2p_micro_pass_rate_known_only"),
        "total_cli_cost_usd": summary.get("total_cli_cost_usd"),
        "avg_cli_duration_ms": summary.get("avg_cli_duration_ms"),
    }


def build_case_detail(run_id: str, run_dir: Path, case: dict[str, Any]) -> dict[str, Any]:
    instance_id = case["instance_id"]
    infer_run_dir = run_dir / "infer" / "runs" / instance_id
    eval_log_path = run_dir / "eval_worker_logs" / f"{instance_id}.log"
    report_path = find_report_path(run_id, instance_id)

    enriched = dict(case)
    enriched["tool_counts_by_name"] = json.loads(case["tool_counts_by_name"]) if case.get("tool_counts_by_name") else {}
    enriched["anomaly_flags"] = json.loads(case["anomaly_flags"]) if case.get("anomaly_flags") else []
    enriched["artifacts"] = {
        "report_json": artifact_url(report_path),
        "run_instance_log": artifact_url(report_path.parent / "run_instance.log") if report_path else None,
        "test_output": artifact_url(report_path.parent / "test_output.txt") if report_path else None,
        "patch_diff": artifact_url(infer_run_dir / "patch.diff"),
        "cli_result": artifact_url(infer_run_dir / "cli_result.json"),
        "cli_stdout": artifact_url(infer_run_dir / "cli_stdout.log"),
        "cli_stderr": artifact_url(infer_run_dir / "cli_stderr.log"),
        "router_trace_bundle": artifact_url(infer_run_dir / "router_trace_bundle.json"),
        "eval_worker_log": artifact_url(eval_log_path),
    }
    return enriched


def build_run_detail(run_id: str) -> dict[str, Any] | None:
    run_dir = RUNS_ROOT / run_id
    if not run_dir.exists():
        return None
    overview = build_run_overview(run_dir)
    summary_data = load_json(run_dir / "analysis" / "summary.json", {"summary": {}, "cases": []})
    cases = [build_case_detail(run_id, run_dir, case) for case in summary_data.get("cases", []) if isinstance(case, dict)]
    return {
        "run": overview,
        "summary": summary_data.get("summary", {}),
        "cases": cases,
    }


def build_case_trace_detail(run_id: str, instance_id: str) -> dict[str, Any] | None:
    path = trace_bundle_path(run_id, instance_id)
    if not path.exists():
        return None
    stat = path.stat()
    return load_case_trace_view(str(path), stat.st_mtime_ns, run_id, instance_id)


def scan_runs() -> dict[str, Any]:
    runs = [build_run_overview(run_dir) for run_dir in detect_runs()]
    return {"runs": runs}


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_artifact(self, rel_path: str) -> None:
        target = (REPO_ROOT / rel_path).resolve()
        try:
            target.relative_to(REPO_ROOT)
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN, "Path escapes repository root")
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Artifact not found")
            return

        content = target.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(target))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path

        if route == "/api/health":
            self.send_json({"ok": True})
            return

        if route == "/api/runs":
            self.send_json(scan_runs())
            return

        case_trace_match = re.match(r"^/api/run/([^/]+)/case/([^/]+)/trace$", route)
        if case_trace_match:
            run_id, instance_id = case_trace_match.groups()
            detail = build_case_trace_detail(run_id, instance_id)
            if detail is None:
                self.send_json({"error": "trace not found"}, status=404)
                return
            self.send_json(detail)
            return

        if route.startswith("/api/run/"):
            run_id = route.split("/api/run/", 1)[1]
            detail = build_run_detail(run_id)
            if detail is None:
                self.send_json({"error": "run not found"}, status=404)
                return
            self.send_json(detail)
            return

        if route == "/artifact":
            query = urllib.parse.parse_qs(parsed.query)
            rel_path = query.get("path", [None])[0]
            if rel_path is None:
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing artifact path")
                return
            self.serve_artifact(rel_path)
            return

        if route in {"/", "/dashboard", "/dashboard/"}:
            self.path = "/index.html"
        elif route.startswith("/dashboard/"):
            self.path = route[len("/dashboard") :]
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18881)
    args = parser.parse_args()

    STATIC_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"official48 dashboard: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
