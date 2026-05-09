#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


RUN_ID_RE = re.compile(r"run_id=(\d{8}-\d{6})")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def discover_run_ids(launcher_log: Path) -> list[str]:
    if not launcher_log.exists():
        return []
    text = launcher_log.read_text(encoding="utf-8", errors="replace")
    run_ids: list[str] = []
    for run_id in RUN_ID_RE.findall(text):
        if run_id not in run_ids:
            run_ids.append(run_id)
    return run_ids


def collect_snapshot(repo_root: Path, run_id: str) -> dict:
    run_root = repo_root / "official48_runs" / run_id
    metadata = load_json(run_root / "metadata.json", {})
    infer_status = load_json(run_root / "infer" / "inference_status.json", {})
    eval_status = load_json(run_root / "eval_worker_status.json", {})
    summary = load_json(run_root / "analysis" / "summary.json", {}).get("summary", {})
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": run_id,
        "display_name": metadata.get("display_name"),
        "infer_completed": infer_status.get("completed_count"),
        "infer_total": infer_status.get("total_instances"),
        "infer_active": infer_status.get("active", []),
        "infer_failed": infer_status.get("failed", []),
        "infer_done": infer_status.get("done"),
        "eval_completed": len((eval_status.get("completed") or {})),
        "eval_active": eval_status.get("active", []),
        "eval_done": eval_status.get("done"),
        "resolved_true_cases": summary.get("resolved_true_cases"),
        "resolution_rate": summary.get("resolution_rate"),
        "total_cli_cost_usd": summary.get("total_cli_cost_usd"),
    }


def session_exists(session_name: str) -> bool:
    completed = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--launcher-log", required=True)
    parser.add_argument("--tmux-session", required=True)
    parser.add_argument("--output-log", required=True)
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    launcher_log = Path(args.launcher_log).resolve()
    output_log = Path(args.output_log).resolve()

    while True:
        append_line(output_log, f"[watch] {datetime.now().isoformat(timespec='seconds')}")
        run_ids = discover_run_ids(launcher_log)
        if not run_ids:
            append_line(output_log, json.dumps({"run_ids": []}, ensure_ascii=False))
        for run_id in run_ids:
            snapshot = collect_snapshot(repo_root, run_id)
            append_line(output_log, json.dumps(snapshot, ensure_ascii=False))
        append_line(output_log, "")

        if not session_exists(args.tmux_session):
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
