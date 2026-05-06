#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from swe_evo_env import REPO_ROOT, prepend_pythonpath


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def find_report_dir(eval_run_root: Path, instance_id: str) -> Path | None:
    direct = eval_run_root / "innercc-cli" / instance_id
    if (direct / "report.json").exists():
        return direct
    for report_json in sorted(eval_run_root.glob(f"**/{instance_id}/report.json")):
        return report_json.parent
    return None


def ensure_eval_input_link(run_root: Path) -> Path:
    link = run_root / f"eval_input_{run_root.name}"
    target = run_root / "infer"
    if link.exists() or link.is_symlink():
        return link
    link.symlink_to(target)
    return link


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: run_official48_eval_worker.py <run_root> [max_concurrency] [--retry-missing-report] [--poll-interval-seconds N]"
        )

    run_root = Path(sys.argv[1]).resolve()
    retry_missing_report = "--retry-missing-report" in sys.argv[2:]
    poll_interval_seconds = 15
    raw_args = sys.argv[2:]
    if "--poll-interval-seconds" in raw_args:
        idx = raw_args.index("--poll-interval-seconds")
        try:
            poll_interval_seconds = int(raw_args[idx + 1])
        except Exception as exc:
            raise SystemExit("--poll-interval-seconds requires an integer value") from exc
        raw_args = raw_args[:idx] + raw_args[idx + 2 :]

    positional = [arg for arg in raw_args if not arg.startswith("--")]
    max_concurrency = int(positional[0]) if positional else 3
    infer_summary_path = run_root / "infer" / "inference_summary.json"
    infer_status_path = run_root / "infer" / "inference_status.json"
    eval_input_link = ensure_eval_input_link(run_root)
    eval_run_root = REPO_ROOT / "logs" / "run_evaluation" / eval_input_link.name
    eval_logs_dir = run_root / "eval_worker_logs"
    eval_logs_dir.mkdir(parents=True, exist_ok=True)
    eval_state_path = run_root / "eval_worker_status.json"
    eval_state_log = run_root / "eval_worker.log"
    eval_result_links = run_root / "evaluation"
    eval_result_links.mkdir(parents=True, exist_ok=True)

    active: dict[str, tuple[subprocess.Popen[str], Path, str]] = {}
    completed: dict[str, dict] = {}
    existing_state = {}
    if eval_state_path.exists():
        try:
            existing_state = json.loads(eval_state_path.read_text(encoding="utf-8"))
        except Exception:
            existing_state = {}
    for instance_id, payload in existing_state.get("completed", {}).items():
        report_json = payload.get("report_json")
        report_dir = find_report_dir(eval_run_root, instance_id)
        report_exists = bool((report_json and Path(report_json).exists()) or report_dir is not None)
        if report_dir is not None:
            payload = dict(payload)
            payload["report_dir"] = str(report_dir)
            payload["report_json"] = str(report_dir / "report.json")
        if retry_missing_report and not report_exists:
            continue
        completed[instance_id] = payload

    def persist_state() -> None:
        payload = {
            "run_root": str(run_root),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "max_concurrency": max_concurrency,
            "active": sorted(active.keys()),
            "completed": completed,
            "done": False,
        }
        write_json(eval_state_path, payload)
        with eval_state_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    while True:
        inference_rows = []
        if infer_summary_path.exists():
            try:
                inference_rows = json.loads(infer_summary_path.read_text(encoding="utf-8"))
            except Exception:
                inference_rows = []
        inference_state = {}
        if infer_status_path.exists():
            try:
                inference_state = json.loads(infer_status_path.read_text(encoding="utf-8"))
            except Exception:
                inference_state = {}

        for instance_id, (proc, log_path, eval_run_name) in list(active.items()):
            rc = proc.poll()
            if rc is None:
                continue
            report_dir = find_report_dir(REPO_ROOT / "logs" / "run_evaluation" / eval_run_name, instance_id)
            link_path = eval_result_links / instance_id
            if report_dir is not None and report_dir.exists() and not link_path.exists():
                link_path.symlink_to(report_dir)
            completed[instance_id] = {
                "returncode": rc,
                "log_path": str(log_path),
                "report_dir": str(report_dir) if report_dir is not None else None,
                "report_json": str(report_dir / "report.json") if report_dir is not None else None,
                "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            active.pop(instance_id, None)

        ready_rows = [row for row in inference_rows if row.get("preds_json")]
        for row in ready_rows:
            instance_id = row["instance_id"]
            if instance_id in completed or instance_id in active:
                continue
            if len(active) >= max_concurrency:
                break
            log_path = eval_logs_dir / f"{instance_id}.log"
            eval_run_name = eval_input_link.name
            cmd = [
                "python3",
                str(REPO_ROOT / "SWE-bench" / "evaluate_instance.py"),
                "--trajectories_path",
                str(eval_input_link),
                "--instance",
                instance_id,
                "--max_workers",
                "1",
                "--scaffold",
                "CustomCLI",
            ]
            env = prepend_pythonpath(os.environ.copy())
            env["PYTHONNOUSERSITE"] = "1"
            log_fh = log_path.open("w", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                cwd=REPO_ROOT,
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                text=True,
            )
            active[instance_id] = (proc, log_path, eval_run_name)

        total_instances = int(inference_state.get("total_instances") or len(inference_rows) or 48)
        all_inference_done = bool(inference_state.get("done")) or len(inference_rows) >= total_instances
        all_eval_done = all_inference_done and len(completed) >= total_instances and not active

        persist_state()

        if all_eval_done:
            payload = json.loads(eval_state_path.read_text(encoding="utf-8"))
            payload["done"] = True
            write_json(eval_state_path, payload)
            with eval_state_log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
            break

        time.sleep(poll_interval_seconds)


if __name__ == "__main__":
    main()
