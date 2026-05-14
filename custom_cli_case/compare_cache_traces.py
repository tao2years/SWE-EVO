#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = REPO_ROOT / "runtime"
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from swe_evo_env import (  # noqa: E402
    REPO_ROOT as SWE_EVO_REPO_ROOT,
    default_cli_bin_path,
    default_env_file,
    default_model_name,
    default_router_api_base,
    default_router_db_path,
    default_settings_path,
)


CUSTOM_RUNNER_PATH = REPO_ROOT / "custom_cli_case" / "run_custom_cli_case.py"
DEFAULT_COMPARE_ROOT = REPO_ROOT / "custom_cli_case" / "compare_runs"
DEFAULT_INSTANCE_SOURCE_ROOT = REPO_ROOT / "official48_source" / "output_final"
DEFAULT_CLAUDE_RUN_ROOT = (
    REPO_ROOT / "official48_runs" / "20260511-clean-router-project-coverage-7-claude-2.1.138"
)
DEFAULT_INNERCC_RUN_ROOT = (
    REPO_ROOT / "official48_runs" / "20260511-194955-project-coverage-7-innercc-context-router-rerun"
)
DEFAULT_INNERCC_CONTEXT_BIN = REPO_ROOT.parents[1] / "innerCC" / "innercc_0509_context"
DEFAULT_CLAUDE_BIN = Path(shutil.which("claude") or "claude")


@dataclass
class VariantConfig:
    name: str
    cli_kind: str
    cli_bin: Path
    agent_name: str
    workspace_dir: Path
    run_dir: Path


def load_runner():
    spec = importlib.util.spec_from_file_location("run_custom_cli_case", CUSTOM_RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def sanitize_preview(text: str | None, limit: int = 160) -> str:
    if not text:
        return ""
    compact = " ".join(text.replace("\r", "\n").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def pick_instance_from_historical_runs(
    claude_run_root: Path,
    innercc_run_root: Path,
) -> dict:
    claude_cases = claude_run_root / "analysis" / "cases.csv"
    innercc_cases = innercc_run_root / "analysis" / "cases.csv"
    if not claude_cases.exists() or not innercc_cases.exists():
        return {
            "instance_id": "dask__dask_2024.3.1_2024.4.0",
            "reason": "historical cases.csv missing; fallback to known high-gap dask case",
            "claude_cache_hit_rate": None,
            "innercc_cache_hit_rate": None,
            "gap": None,
        }

    def load_case_map(path: Path) -> dict[str, dict]:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return {row["instance_id"]: row for row in reader if row.get("instance_id")}

    def cache_hit_rate(row: dict) -> float:
        input_tokens = safe_float(row.get("cli_model_input_tokens"))
        cache_read = safe_float(row.get("cli_model_cache_read_tokens"))
        denom = input_tokens + cache_read
        return (cache_read / denom) if denom > 0 else 0.0

    claude_map = load_case_map(claude_cases)
    innercc_map = load_case_map(innercc_cases)

    best: dict | None = None
    for instance_id in sorted(set(claude_map) & set(innercc_map)):
        c_rate = cache_hit_rate(claude_map[instance_id])
        i_rate = cache_hit_rate(innercc_map[instance_id])
        gap = c_rate - i_rate
        if best is None or gap > best["gap"]:
            best = {
                "instance_id": instance_id,
                "reason": "picked by max historical cache-hit gap between Claude Code and innercc context rerun",
                "claude_cache_hit_rate": c_rate,
                "innercc_cache_hit_rate": i_rate,
                "gap": gap,
            }

    if best is None:
        return {
            "instance_id": "dask__dask_2024.3.1_2024.4.0",
            "reason": "no overlapping historical cases found; fallback to known high-gap dask case",
            "claude_cache_hit_rate": None,
            "innercc_cache_hit_rate": None,
            "gap": None,
        }
    return best


def resolve_instance_path(instance_id: str | None, instance_file: str | None) -> tuple[Path, dict]:
    if instance_file:
        path = Path(instance_file).expanduser().resolve()
    else:
        assert instance_id is not None
        path = (DEFAULT_INSTANCE_SOURCE_ROOT / f"{instance_id}.json").resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return path, payload


def resolve_innercc_bin(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    if DEFAULT_INNERCC_CONTEXT_BIN.exists():
        return DEFAULT_INNERCC_CONTEXT_BIN.resolve()
    fallback = default_cli_bin_path()
    return fallback.resolve()


def resolve_claude_bin(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    return DEFAULT_CLAUDE_BIN


def find_local_repo_sources(instance_id: str) -> list[Path]:
    candidates: list[Path] = []
    direct_candidates = [
        REPO_ROOT / "custom_cli_case" / "workspace" / instance_id,
    ]
    for path in direct_candidates:
        if (path / ".git").exists():
            candidates.append(path)

    official48_root = REPO_ROOT / "official48_runs"
    if official48_root.exists():
        for path in sorted(official48_root.glob(f"*/infer/workspaces/{instance_id}")):
            if (path / ".git").exists():
                candidates.append(path)

    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path.resolve())
    return unique


def try_seed_workspace_from_local_cache(runner, instance: dict, workspace_dir: Path, force_workspace: bool) -> bool:
    if force_workspace and workspace_dir.exists():
        shutil.rmtree(workspace_dir)
    if (workspace_dir / ".git").exists():
        return True

    repo_name = instance["repo"]
    repo_url = f"https://github.com/{repo_name}.git"
    base_commit = instance["base_commit"]

    for source_repo in find_local_repo_sources(instance["instance_id"]):
        if not runner.commit_exists(source_repo, base_commit):
            continue
        workspace_dir.parent.mkdir(parents=True, exist_ok=True)
        runner.run(["git", "clone", str(source_repo), workspace_dir.name], cwd=workspace_dir.parent)
        runner.run(["git", "checkout", base_commit], cwd=workspace_dir)
        runner.run(["git", "remote", "set-url", "origin", repo_url], cwd=workspace_dir)
        runner.run(["git", "config", "user.email", "benchmark@example.com"], cwd=workspace_dir)
        runner.run(["git", "config", "user.name", "benchmark"], cwd=workspace_dir)
        return True
    return False


def parse_proxy_base_url(settings_file: Path, env_file: Path) -> str | None:
    for source in (settings_file, env_file):
        if not source.exists():
            continue
        text = source.read_text(encoding="utf-8", errors="replace")
        for needle in (
            "http://127.0.0.1:18782",
            "http://localhost:18782",
        ):
            if needle in text:
                return needle
    return None


def router_api_healthy(router_api_base: str, timeout_seconds: int = 5) -> bool:
    try:
        with urllib.request.urlopen(f"{router_api_base.rstrip('/')}/api/sessions", timeout=timeout_seconds) as response:
            return response.status == 200
    except Exception:
        return False


def proxy_base_healthy(proxy_base_url: str, timeout_seconds: int = 5) -> bool:
    try:
        with urllib.request.urlopen(f"{proxy_base_url.rstrip('/')}/v1/models", timeout=timeout_seconds) as response:
            return response.status == 200
    except Exception:
        return False


def wait_for_router(router_db_path: Path, router_api_base: str, proxy_base_url: str | None, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        db_ready = router_db_path.exists()
        api_ready = router_api_healthy(router_api_base)
        proxy_ready = proxy_base_healthy(proxy_base_url) if proxy_base_url else True
        if db_ready and api_ready and proxy_ready:
            return
        time.sleep(2.0)
    raise TimeoutError(
        "router not ready: "
        f"db={router_db_path.exists()} api={router_api_healthy(router_api_base)} "
        f"proxy={proxy_base_healthy(proxy_base_url) if proxy_base_url else 'n/a'}"
    )


def rows_as_dicts(cur: sqlite3.Cursor, query: str, params: tuple) -> list[dict]:
    cur.execute(query, params)
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def extract_claude_code_session_id(trace_row: dict) -> str | None:
    try:
        headers = json.loads(trace_row.get("request_headers") or "{}")
    except Exception:
        return None
    value = headers.get("x-claude-code-session-id")
    return str(value) if value else None


def find_router_traces_for_workspace(
    con: sqlite3.Connection,
    workspace_dir: Path,
    instance_id: str,
    started_at_ms: int,
    finished_at_ms: int,
) -> list[dict]:
    cur = con.cursor()
    window_start = started_at_ms - 5_000
    window_end = finished_at_ms + 30_000

    def query_traces(pattern: str) -> list[dict]:
        return rows_as_dicts(
            cur,
            """
            SELECT *
            FROM traces
            WHERE timestamp BETWEEN ? AND ?
              AND request_body LIKE ?
            ORDER BY timestamp ASC
            """,
            (window_start, window_end, pattern),
        )

    def group_candidates(pattern: str) -> list[dict]:
        return rows_as_dicts(
            cur,
            """
            SELECT
              COALESCE(run_id, '') AS run_id,
              COALESCE(session_id, '') AS session_id,
              COUNT(*) AS matched_trace_count,
              MIN(timestamp) AS first_timestamp,
              MAX(timestamp) AS last_timestamp
            FROM traces
            WHERE timestamp BETWEEN ? AND ?
              AND request_body LIKE ?
            GROUP BY COALESCE(run_id, ''), COALESCE(session_id, '')
            ORDER BY matched_trace_count DESC, last_timestamp DESC
            """,
            (window_start, window_end, pattern),
        )

    patterns = [
        f"%{workspace_dir.as_posix()}%",
        f"%{workspace_dir}%",
        f"%{instance_id}%",
    ]
    for pattern in patterns:
        candidates = group_candidates(pattern)
        if not candidates:
            continue
        top = candidates[0]
        run_id = top.get("run_id") or ""
        session_id = top.get("session_id") or ""

        traces = query_traces(pattern)
        if pattern == f"%{instance_id}%":
            traces = [
                row
                for row in traces
                if (row.get("run_id") or "") == run_id
                and (row.get("session_id") or "") == session_id
            ]
        if traces:
            by_cc_session: dict[str, list[dict]] = {}
            for row in traces:
                cc_session_id = extract_claude_code_session_id(row)
                if not cc_session_id:
                    continue
                by_cc_session.setdefault(cc_session_id, []).append(row)

            if len(by_cc_session) > 1:
                eligible = [
                    (cc_session_id, rows)
                    for cc_session_id, rows in by_cc_session.items()
                    if min(int(r["timestamp"]) for r in rows) >= started_at_ms
                ]
                if eligible:
                    eligible.sort(key=lambda item: min(int(r["timestamp"]) for r in item[1]))
                    traces = eligible[0][1]
                else:
                    # If all observed x-session ids started before this run's
                    # start timestamp, keep the most recently-started one.
                    traces = max(
                        by_cc_session.items(),
                        key=lambda item: min(int(r["timestamp"]) for r in item[1]),
                    )[1]
        if traces:
            return traces
    return []


def export_router_bundle_from_db(
    instance_id: str,
    workspace_dir: Path,
    run_dir: Path,
    router_db_path: Path,
    started_at_ms: int,
    finished_at_ms: int,
) -> tuple[Path, str | None, str | None]:
    if not router_db_path.exists():
        raise FileNotFoundError(router_db_path)

    con = sqlite3.connect(str(router_db_path))
    try:
        traces = find_router_traces_for_workspace(
            con,
            workspace_dir,
            instance_id,
            started_at_ms,
            finished_at_ms,
        )
        if not traces:
            raise RuntimeError(
                f"unable to locate router traces by workspace/time window for {instance_id}: {workspace_dir}"
            )

        session_ids = sorted({str(row["session_id"]) for row in traces if row.get("session_id")})
        run_ids = sorted({str(row["run_id"]) for row in traces if row.get("run_id")})
        cur = con.cursor()
        sessions: list[dict] = []
        runs: list[dict] = []
        if session_ids:
            placeholders = ",".join("?" for _ in session_ids)
            sessions = rows_as_dicts(cur, f"SELECT * FROM sessions WHERE id IN ({placeholders})", tuple(session_ids))
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            runs = rows_as_dicts(cur, f"SELECT * FROM runs WHERE id IN ({placeholders})", tuple(run_ids))
    finally:
        con.close()

    session_id = session_ids[0] if len(session_ids) == 1 else None
    run_id = run_ids[0] if len(run_ids) == 1 else None

    bundle = {
        "version": 1,
        "exported_at": int(time.time() * 1000),
        "scope": {
            "session_ids": session_ids,
            "run_ids": run_ids,
            "trace_ids": [row["id"] for row in traces if row.get("id")],
        },
        "counts": {
            "sessions": len(sessions),
            "runs": len(runs),
            "traces": len(traces),
        },
        "sessions": sessions,
        "runs": runs,
        "traces": traces,
    }
    bundle_path = run_dir / "router_trace_bundle.json"
    write_json(bundle_path, bundle)
    return bundle_path, session_id, run_id


def extract_first_text_block(content: list[dict] | None) -> str:
    if not isinstance(content, list):
        return ""
    texts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            texts.append(block["text"])
    return "\n".join(texts)


def summarize_request_messages(messages: list[dict]) -> dict:
    role_counts: dict[str, int] = {}
    block_counts: dict[str, int] = {}
    tool_result_blocks = 0
    tool_use_blocks = 0
    text_blocks = 0
    text_chars = 0
    for message in messages:
        role = str(message.get("role", "unknown"))
        role_counts[role] = role_counts.get(role, 0) + 1
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type", "unknown"))
            block_counts[block_type] = block_counts.get(block_type, 0) + 1
            if block_type == "tool_result":
                tool_result_blocks += 1
            elif block_type == "tool_use":
                tool_use_blocks += 1
            elif block_type == "text":
                text_blocks += 1
                if isinstance(block.get("text"), str):
                    text_chars += len(block["text"])
    return {
        "role_counts": role_counts,
        "block_counts": block_counts,
        "tool_result_blocks": tool_result_blocks,
        "tool_use_blocks": tool_use_blocks,
        "text_blocks": text_blocks,
        "text_chars": text_chars,
    }


def summarize_trace_rows(bundle: dict) -> list[dict]:
    traces = bundle.get("traces", [])
    rows: list[dict] = []
    prev_body_len: int | None = None
    prev_msg_count: int | None = None
    prev_cache_read: int | None = None

    for turn_index, trace in enumerate(traces):
        request_body_text = trace.get("request_body") or "{}"
        response_body_text = trace.get("response_body") or "{}"
        try:
            request_body = json.loads(request_body_text)
        except Exception:
            request_body = {}
        try:
            response_body = json.loads(response_body_text)
        except Exception:
            response_body = {}

        messages = request_body.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        request_summary = summarize_request_messages(messages)
        response_content = response_body.get("content", [])
        if not isinstance(response_content, list):
            response_content = []
        tool_use_names = [
            str(block.get("name"))
            for block in response_content
            if isinstance(block, dict) and block.get("type") == "tool_use"
        ]
        assistant_text_preview = sanitize_preview(extract_first_text_block(response_content), limit=180)
        usage = response_body.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}

        msg_count = len(messages)
        body_len = len(request_body_text)
        input_tokens = safe_int(usage.get("input_tokens"))
        output_tokens = safe_int(usage.get("output_tokens"))
        cache_read = safe_int(usage.get("cache_read_input_tokens"))
        cache_create = safe_int(usage.get("cache_creation_input_tokens"))
        cache_hit_rate = (cache_read / (cache_read + input_tokens)) if (cache_read + input_tokens) > 0 else 0.0

        events: list[str] = []
        if cache_create > 0:
            events.append(f"cache_create={cache_create}")
        if prev_body_len is not None and body_len < prev_body_len:
            events.append(f"request_shrink={body_len - prev_body_len}")
        if prev_msg_count is not None and msg_count < prev_msg_count:
            events.append(f"msg_reset={msg_count - prev_msg_count}")
        if prev_cache_read is not None and prev_cache_read > 0 and cache_read < prev_cache_read:
            events.append(f"cache_read_drop={cache_read - prev_cache_read}")

        rows.append(
            {
                "turn_index": turn_index,
                "trace_id": trace.get("id"),
                "timestamp": trace.get("timestamp"),
                "duration_ms": trace.get("duration_ms"),
                "request_method": trace.get("request_method"),
                "request_path": trace.get("request_path"),
                "response_status": trace.get("response_status"),
                "model": trace.get("model"),
                "msg_count": msg_count,
                "request_body_bytes": body_len,
                "request_body_delta": None if prev_body_len is None else body_len - prev_body_len,
                "msg_count_delta": None if prev_msg_count is None else msg_count - prev_msg_count,
                "request_role_counts": request_summary["role_counts"],
                "request_block_counts": request_summary["block_counts"],
                "request_tool_result_blocks": request_summary["tool_result_blocks"],
                "request_tool_use_blocks": request_summary["tool_use_blocks"],
                "request_text_blocks": request_summary["text_blocks"],
                "request_text_chars": request_summary["text_chars"],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
                "cache_hit_rate": cache_hit_rate,
                "stop_reason": response_body.get("stop_reason"),
                "assistant_tool_use_names": tool_use_names,
                "assistant_tool_use_count": len(tool_use_names),
                "assistant_text_preview": assistant_text_preview,
                "events": events,
                "request_body_sha256": hashlib.sha256(request_body_text.encode("utf-8")).hexdigest(),
                "response_body_sha256": hashlib.sha256(response_body_text.encode("utf-8")).hexdigest(),
                "request_body": request_body_text,
                "response_body": response_body_text,
            }
        )

        prev_body_len = body_len
        prev_msg_count = msg_count
        prev_cache_read = cache_read

    return rows


def summarize_variant_rows(rows: list[dict]) -> dict:
    if not rows:
        return {
            "trace_count": 0,
            "first_reset_turn": None,
            "max_msg_count": 0,
            "max_request_body_bytes": 0,
            "max_input_tokens": 0,
            "final_cache_hit_rate": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cache_read_input_tokens": 0,
            "total_cache_creation_input_tokens": 0,
        }

    first_reset_turn = None
    for row in rows:
        if any(event.startswith("request_shrink") or event.startswith("msg_reset") for event in row["events"]):
            first_reset_turn = row["turn_index"]
            break

    total_input = sum(row["input_tokens"] for row in rows)
    total_output = sum(row["output_tokens"] for row in rows)
    total_cache_read = sum(row["cache_read_input_tokens"] for row in rows)
    total_cache_create = sum(row["cache_creation_input_tokens"] for row in rows)

    return {
        "trace_count": len(rows),
        "first_reset_turn": first_reset_turn,
        "max_msg_count": max(row["msg_count"] for row in rows),
        "max_request_body_bytes": max(row["request_body_bytes"] for row in rows),
        "max_input_tokens": max(row["input_tokens"] for row in rows),
        "final_cache_hit_rate": rows[-1]["cache_hit_rate"],
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_read_input_tokens": total_cache_read,
        "total_cache_creation_input_tokens": total_cache_create,
    }


def build_variant_timeline_md(variant_name: str, rows: list[dict], summary: dict) -> str:
    lines = [f"# {variant_name} 逐轮 Router Trace 摘要", ""]
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- trace 数: {summary['trace_count']}")
    lines.append(f"- 首次 reset turn: {summary['first_reset_turn']}")
    lines.append(f"- 最大 msg_count: {summary['max_msg_count']}")
    lines.append(f"- 最大 request body: {summary['max_request_body_bytes']}")
    lines.append(f"- 最大 input_tokens: {summary['max_input_tokens']}")
    lines.append(f"- 总 cache_read_input_tokens: {summary['total_cache_read_input_tokens']}")
    lines.append("")
    lines.append("## 时间线")
    lines.append("")
    lines.append("| turn | msg_count | body_bytes | input | cache_read | cache_create | output | tool_results | stop_reason | assistant tools / text | events |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |")
    for row in rows:
        tool_summary = ", ".join(row["assistant_tool_use_names"]) or row["assistant_text_preview"] or "-"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["turn_index"]),
                    str(row["msg_count"]),
                    str(row["request_body_bytes"]),
                    str(row["input_tokens"]),
                    str(row["cache_read_input_tokens"]),
                    str(row["cache_creation_input_tokens"]),
                    str(row["output_tokens"]),
                    str(row["request_tool_result_blocks"]),
                    str(row["stop_reason"] or "-"),
                    tool_summary.replace("|", "/"),
                    ", ".join(row["events"]) or "-",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def build_shared_prefix_summary(claude_rows: list[dict], innercc_rows: list[dict]) -> dict:
    shared = 0
    for claude_row, innercc_row in zip(claude_rows, innercc_rows):
        if claude_row["request_body"] != innercc_row["request_body"]:
            break
        shared += 1

    divergence = shared if shared < min(len(claude_rows), len(innercc_rows)) else None
    return {
        "shared_prefix_trace_count": shared,
        "first_divergence_turn": divergence,
    }


def strip_raw_bodies(rows: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for row in rows:
        clone = dict(row)
        clone.pop("request_body", None)
        clone.pop("response_body", None)
        sanitized.append(clone)
    return sanitized


def build_comparison_md(
    instance_id: str,
    historical_pick: dict,
    claude_summary: dict,
    innercc_summary: dict,
    shared_prefix: dict,
    claude_rows: list[dict],
    innercc_rows: list[dict],
) -> str:
    lines = [f"# cache trace 对照：{instance_id}", ""]
    lines.append("## 选 case 依据")
    lines.append("")
    lines.append(f"- 选择原因: {historical_pick.get('reason')}")
    if historical_pick.get("claude_cache_hit_rate") is not None:
        lines.append(
            f"- 历史命中率: Claude={historical_pick['claude_cache_hit_rate']:.4f}, "
            f"innercc={historical_pick['innercc_cache_hit_rate']:.4f}, gap={historical_pick['gap']:.4f}"
        )
    lines.append("")
    lines.append("## 关键结论")
    lines.append("")
    lines.append(
        f"- 两边共享完全相同的请求前缀 trace 数: {shared_prefix['shared_prefix_trace_count']}。"
    )
    lines.append(
        f"- Claude 总 trace 数: {claude_summary['trace_count']}，innercc 总 trace 数: {innercc_summary['trace_count']}。"
    )
    lines.append(
        f"- Claude 首次 request shrink / msg reset: {claude_summary['first_reset_turn']}；"
        f"innercc 首次 request shrink / msg reset: {innercc_summary['first_reset_turn']}。"
    )
    lines.append(
        f"- Claude 最大 input_tokens: {claude_summary['max_input_tokens']}；"
        f"innercc 最大 input_tokens: {innercc_summary['max_input_tokens']}。"
    )
    lines.append(
        f"- Claude 最大 request body: {claude_summary['max_request_body_bytes']}；"
        f"innercc 最大 request body: {innercc_summary['max_request_body_bytes']}。"
    )
    if claude_rows and innercc_rows:
        lines.append(
            f"- 首轮 cache_create 对比: Claude={claude_rows[0]['cache_creation_input_tokens']}；"
            f"innercc={innercc_rows[0]['cache_creation_input_tokens']}。"
        )
        lines.append(
            f"- 首轮 cache_read 对比: Claude={claude_rows[0]['cache_read_input_tokens']}；"
            f"innercc={innercc_rows[0]['cache_read_input_tokens']}。"
        )
    lines.append("")

    innercc_reset_row = None
    if innercc_summary["first_reset_turn"] is not None:
        innercc_reset_row = innercc_rows[innercc_summary["first_reset_turn"]]
        lines.append("## innercc 关键转折点")
        lines.append("")
        lines.append(
            f"- innercc 在 turn {innercc_reset_row['turn_index']} 出现 request shrink，"
            f"body bytes 变为 {innercc_reset_row['request_body_bytes']}，"
            f"msg_count 变为 {innercc_reset_row['msg_count']}，"
            f"cache_read_input_tokens 变为 {innercc_reset_row['cache_read_input_tokens']}。"
        )
        if innercc_reset_row["request_body_delta"] is not None:
            lines.append(f"- 该 turn 相对上一轮 body bytes 变化: {innercc_reset_row['request_body_delta']}")
        if innercc_reset_row["msg_count_delta"] is not None:
            lines.append(f"- 该 turn 相对上一轮 msg_count 变化: {innercc_reset_row['msg_count_delta']}")
        lines.append("")

    lines.append("## 对比判断")
    lines.append("")
    if shared_prefix["shared_prefix_trace_count"] > 0:
        lines.append(
            "- 前半段共享长前缀，说明不是首轮 prompt 大小差异导致命中率差。"
        )
    elif claude_rows and innercc_rows:
        lines.append(
            "- 两边从第 0 轮开始就不是同一个精确前缀，说明 live run 下还存在 prompt 构造层面的前缀不一致。"
        )
    if innercc_summary["first_reset_turn"] is not None and claude_summary["first_reset_turn"] is None:
        lines.append(
            "- innercc 中途发生 history rewrite / compact 风格的 request shrink，而 Claude 没有，这通常会打断已建立的 cache 前缀。"
        )
    elif claude_rows and innercc_rows:
        if innercc_rows[0]["cache_creation_input_tokens"] < claude_rows[0]["cache_creation_input_tokens"]:
            lines.append(
                "- live run 下更明显的现象是 innercc 首轮可缓存前缀更小，后续每轮 cache_read 也显著低于 Claude。"
            )
    if innercc_summary["trace_count"] > claude_summary["trace_count"]:
        lines.append(
            "- innercc 后续又继续跑了更多轮，使新增输入 token 持续累积，进一步摊薄 cache_read 的贡献。"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def run_variant(
    runner,
    instance: dict,
    variant: VariantConfig,
    settings_file: Path,
    env_file: Path,
    model_name: str,
    max_turns: int | None,
    skill_name: str | None,
    skill_hint: str | None,
    timeout_seconds: int,
    force_workspace: bool,
    router_db_path: Path,
) -> dict:
    variant.workspace_dir.parent.mkdir(parents=True, exist_ok=True)
    variant.run_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"[compare] start variant={variant.name} instance={instance['instance_id']} workspace={variant.workspace_dir}",
        flush=True,
    )
    started_at_ms = int(time.time() * 1000)
    if not try_seed_workspace_from_local_cache(runner, instance, variant.workspace_dir, force_workspace):
        runner.prepare_workspace(instance, variant.workspace_dir, force_workspace)
    cli_result_path, cli_returncode = runner.run_cli(
        instance,
        variant.workspace_dir,
        variant.run_dir,
        variant.cli_bin,
        settings_file,
        env_file,
        model_name,
        max_turns,
        skill_name,
        skill_hint,
        timeout_seconds,
    )
    finished_at_ms = int(time.time() * 1000)

    preds_json = runner.write_patch_outputs(
        instance["instance_id"],
        variant.workspace_dir,
        variant.run_dir,
        variant.agent_name,
    )

    router_bundle_path = variant.run_dir / "router_trace_bundle.json"
    router_session_id = None
    router_run_id = None
    router_export_error = None
    try:
        router_bundle_path, router_session_id, router_run_id = export_router_bundle_from_db(
            instance["instance_id"],
            variant.workspace_dir,
            variant.run_dir,
            router_db_path,
            started_at_ms,
            finished_at_ms,
        )
    except Exception as exc:
        router_export_error = str(exc)
        (variant.run_dir / "router_trace_bundle_error.txt").write_text(f"{exc}\n", encoding="utf-8")

    summary = {
        "variant": variant.name,
        "cli_kind": variant.cli_kind,
        "cli_bin": str(variant.cli_bin),
        "agent_name": variant.agent_name,
        "workspace_dir": str(variant.workspace_dir),
        "run_dir": str(variant.run_dir),
        "started_at_ms": started_at_ms,
        "finished_at_ms": finished_at_ms,
        "cli_result": str(cli_result_path),
        "cli_returncode": cli_returncode,
        "preds_json": str(preds_json),
        "router_trace_bundle": str(router_bundle_path),
        "router_session_id": router_session_id,
        "router_run_id": router_run_id,
        "router_export_error": router_export_error,
    }
    write_json(variant.run_dir / "run_summary.json", summary)
    print(
        f"[compare] done variant={variant.name} rc={cli_returncode} bundle={router_bundle_path}",
        flush=True,
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Claude Code and innercc_0509_context on the same SWE-EVO case and summarize per-turn router traces."
    )
    parser.add_argument("--instance-id", default=None)
    parser.add_argument("--instance-file", default=None)
    parser.add_argument("--compare-root", default=None)
    parser.add_argument("--innercc-cli-bin", default=None)
    parser.add_argument("--claude-cli-bin", default=None)
    parser.add_argument("--settings-file", default=str(default_settings_path()))
    parser.add_argument("--env-file", default=str(default_env_file()))
    parser.add_argument("--model", default=default_model_name())
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--timeout-seconds", type=int, default=5400)
    parser.add_argument("--skill-name", default=None)
    parser.add_argument("--skill-hint", default=None)
    parser.add_argument("--router-db-path", default=str(default_router_db_path()))
    parser.add_argument("--router-api-base", default=default_router_api_base())
    parser.add_argument("--router-ready-timeout-seconds", type=int, default=120)
    parser.add_argument("--force-workspace", action="store_true")
    parser.add_argument("--skip-run", action="store_true")
    parser.add_argument("--reuse-existing-variants", action="store_true")
    parser.add_argument("--claude-bundle", default=None)
    parser.add_argument("--innercc-bundle", default=None)
    parser.add_argument("--historical-claude-run-root", default=str(DEFAULT_CLAUDE_RUN_ROOT))
    parser.add_argument("--historical-innercc-run-root", default=str(DEFAULT_INNERCC_RUN_ROOT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runner = load_runner()
    settings_file = Path(args.settings_file).expanduser().resolve()
    env_file = Path(args.env_file).expanduser().resolve()
    router_db_path = Path(args.router_db_path).expanduser().resolve()
    router_api_base = args.router_api_base.rstrip("/")

    if not settings_file.exists():
        raise FileNotFoundError(settings_file)
    if not env_file.exists():
        raise FileNotFoundError(env_file)

    historical_pick = pick_instance_from_historical_runs(
        Path(args.historical_claude_run_root).expanduser().resolve(),
        Path(args.historical_innercc_run_root).expanduser().resolve(),
    )
    instance_id = args.instance_id or historical_pick["instance_id"]
    instance_path, instance = resolve_instance_path(instance_id, args.instance_file)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    compare_root = Path(args.compare_root).expanduser().resolve() if args.compare_root else (
        DEFAULT_COMPARE_ROOT / f"{stamp}-{instance['instance_id']}"
    )
    compare_root.mkdir(parents=True, exist_ok=True)

    metadata = {
        "instance_id": instance["instance_id"],
        "instance_file": str(instance_path),
        "repo": instance.get("repo"),
        "base_commit": instance.get("base_commit"),
        "execution_mode": "serial",
        "variant_order": ["claude_code", "innercc_0509_context"],
        "selected_by": historical_pick,
        "model": args.model,
        "settings_file": str(settings_file),
        "env_file": str(env_file),
        "router_db_path": str(router_db_path),
        "router_api_base": router_api_base,
    }
    write_json(compare_root / "metadata.json", metadata)
    write_json(compare_root / "instance.json", instance)

    proxy_base_url = parse_proxy_base_url(settings_file, env_file)
    if not args.skip_run:
        wait_for_router(
            router_db_path,
            router_api_base,
            proxy_base_url,
            timeout_seconds=args.router_ready_timeout_seconds,
        )

        variants = [
            VariantConfig(
                name="claude_code",
                cli_kind="claude",
                cli_bin=resolve_claude_bin(args.claude_cli_bin),
                agent_name="claude-code",
                workspace_dir=compare_root / "workspaces" / "claude_code" / instance["instance_id"],
                run_dir=compare_root / "variants" / "claude_code",
            ),
            VariantConfig(
                name="innercc_0509_context",
                cli_kind="innercc",
                cli_bin=resolve_innercc_bin(args.innercc_cli_bin),
                agent_name="innercc_0509_context",
                workspace_dir=compare_root / "workspaces" / "innercc_0509_context" / instance["instance_id"],
                run_dir=compare_root / "variants" / "innercc_0509_context",
            ),
        ]

        run_summaries = {}
        for variant in variants:
            existing_summary_path = variant.run_dir / "run_summary.json"
            existing_bundle_path = variant.run_dir / "router_trace_bundle.json"
            if (
                args.reuse_existing_variants
                and existing_summary_path.exists()
                and existing_bundle_path.exists()
            ):
                print(
                    f"[compare] reuse variant={variant.name} summary={existing_summary_path}",
                    flush=True,
                )
                run_summaries[variant.name] = load_json(existing_summary_path, {})
                continue

            run_summaries[variant.name] = run_variant(
                runner,
                instance,
                variant,
                settings_file,
                env_file,
                args.model,
                args.max_turns,
                args.skill_name,
                args.skill_hint,
                args.timeout_seconds,
                args.force_workspace,
                router_db_path,
            )
        write_json(compare_root / "run_summaries.json", run_summaries)

    claude_bundle_path = Path(args.claude_bundle).expanduser().resolve() if args.claude_bundle else (
        compare_root / "variants" / "claude_code" / "router_trace_bundle.json"
    )
    innercc_bundle_path = Path(args.innercc_bundle).expanduser().resolve() if args.innercc_bundle else (
        compare_root / "variants" / "innercc_0509_context" / "router_trace_bundle.json"
    )
    if not claude_bundle_path.exists():
        raise FileNotFoundError(claude_bundle_path)
    if not innercc_bundle_path.exists():
        raise FileNotFoundError(innercc_bundle_path)

    claude_bundle = load_json(claude_bundle_path, {})
    innercc_bundle = load_json(innercc_bundle_path, {})
    claude_rows = summarize_trace_rows(claude_bundle)
    innercc_rows = summarize_trace_rows(innercc_bundle)
    claude_summary = summarize_variant_rows(claude_rows)
    innercc_summary = summarize_variant_rows(innercc_rows)
    shared_prefix = build_shared_prefix_summary(claude_rows, innercc_rows)

    variants_root = compare_root / "variants"
    write_json(variants_root / "claude_code" / "router_trace_summary.json", {
        "summary": claude_summary,
        "rows": strip_raw_bodies(claude_rows),
    })
    write_json(variants_root / "innercc_0509_context" / "router_trace_summary.json", {
        "summary": innercc_summary,
        "rows": strip_raw_bodies(innercc_rows),
    })
    (variants_root / "claude_code" / "router_trace_timeline.md").write_text(
        build_variant_timeline_md("claude_code", claude_rows, claude_summary),
        encoding="utf-8",
    )
    (variants_root / "innercc_0509_context" / "router_trace_timeline.md").write_text(
        build_variant_timeline_md("innercc_0509_context", innercc_rows, innercc_summary),
        encoding="utf-8",
    )

    comparison = {
        "instance_id": instance["instance_id"],
        "selected_by": historical_pick,
        "shared_prefix": shared_prefix,
        "claude_code": claude_summary,
        "innercc_0509_context": innercc_summary,
        "claude_bundle": str(claude_bundle_path),
        "innercc_bundle": str(innercc_bundle_path),
    }
    write_json(compare_root / "comparison.json", comparison)
    (compare_root / "comparison.md").write_text(
        build_comparison_md(
            instance["instance_id"],
            historical_pick,
            claude_summary,
            innercc_summary,
            shared_prefix,
            claude_rows,
            innercc_rows,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "compare_root": str(compare_root),
                "instance_id": instance["instance_id"],
                "claude_bundle": str(claude_bundle_path),
                "innercc_bundle": str(innercc_bundle_path),
                "shared_prefix_trace_count": shared_prefix["shared_prefix_trace_count"],
                "claude_trace_count": claude_summary["trace_count"],
                "innercc_trace_count": innercc_summary["trace_count"],
                "innercc_first_reset_turn": innercc_summary["first_reset_turn"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
