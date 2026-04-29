#!/usr/bin/env python3
import json
import sys
import time
from datetime import datetime
from pathlib import Path


def count_files(base: Path, pattern: str) -> int:
    return len(list(base.glob(pattern)))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: monitor_official48_run.py <run_root>")

    run_root = Path(sys.argv[1]).resolve()
    repo_root = run_root.parents[1]
    infer_root = run_root / "infer"
    run_dir = infer_root / "runs"
    infer_summary = infer_root / "inference_summary.json"
    eval_status_path = run_root / "eval_worker_status.json"
    monitor_json = run_root / "monitor_status.json"
    monitor_log = run_root / "monitor.log"
    eval_run_root = repo_root / "logs" / "run_evaluation" / f"eval_input_{run_root.name}"

    while True:
        inference_done = 0
        if infer_summary.exists():
            try:
                inference_done = len(json.loads(infer_summary.read_text(encoding="utf-8")))
            except Exception:
                inference_done = 0

        cli_results = count_files(run_dir, "*/cli_result.json")
        trace_bundles = count_files(run_dir, "*/router_trace_bundle.json")
        eval_reports = count_files(eval_run_root, "**/report.json")
        eval_completed_tasks = 0
        if eval_status_path.exists():
            try:
                eval_state = json.loads(eval_status_path.read_text(encoding="utf-8"))
                eval_completed_tasks = len(eval_state.get("completed", {}))
            except Exception:
                eval_completed_tasks = 0

        done = infer_summary.exists() and inference_done == 48 and eval_reports >= 48
        payload = {
            "run_root": str(run_root),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "inference_done": inference_done,
            "cli_results": cli_results,
            "trace_bundles": trace_bundles,
            "eval_reports": eval_reports,
            "eval_completed_tasks": eval_completed_tasks,
            "done": done,
        }
        monitor_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        with monitor_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

        if done:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
