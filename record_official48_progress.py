#!/usr/bin/env python3
import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_instance_order(repo_root: Path) -> list[str]:
    instances_dir = repo_root / "output_final"
    instance_ids: list[str] = []
    for path in sorted(instances_dir.glob("*.json")):
        payload = read_json(path, {})
        instance_id = payload.get("instance_id") if isinstance(payload, dict) else None
        instance_ids.append(instance_id or path.stem)
    return instance_ids


def parse_last_started_instance(router_log_path: Path) -> tuple[int, int, str] | None:
    if not router_log_path.exists():
        return None
    pattern = re.compile(r"^\[infer (\d+)/(\d+)\] (.+)$")
    last_match = None
    for line in router_log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line.strip())
        if match:
            last_match = (int(match.group(1)), int(match.group(2)), match.group(3))
    return last_match


def detect_active_instance(
    instance_ids: list[str],
    inference_done: int,
    last_started: tuple[int, int, str] | None,
) -> tuple[int | None, str | None]:
    if last_started is not None:
        started_index, _, started_instance = last_started
        if inference_done < started_index:
            return started_index, started_instance
    if 0 <= inference_done < len(instance_ids):
        return inference_done + 1, instance_ids[inference_done]
    return None, None


def last_completed_eval(eval_state: dict) -> tuple[str | None, str | None]:
    completed = eval_state.get("completed", {})
    if not isinstance(completed, dict) or not completed:
        return None, None
    ordered = sorted(
        completed.items(),
        key=lambda item: item[1].get("finished_at", ""),
    )
    instance_id, payload = ordered[-1]
    return instance_id, payload.get("finished_at")


def format_pct(done: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{done / total * 100:.1f}%"


def build_snapshot(run_root: Path) -> dict:
    repo_root = run_root.parents[1]
    instance_ids = load_instance_order(repo_root)
    total_instances = len(instance_ids) or 48
    infer_summary = read_json(run_root / "infer" / "inference_summary.json", [])
    infer_state = read_json(run_root / "infer" / "inference_status.json", {})
    eval_state = read_json(run_root / "eval_worker_status.json", {})
    monitor_state = read_json(run_root / "monitor_status.json", {})
    last_started = parse_last_started_instance(repo_root / "official48_runs" / "current_router.log")

    if infer_state.get("total_instances"):
        total_instances = int(infer_state["total_instances"])
    inference_done = int(infer_state.get("completed_count", monitor_state.get("inference_done", len(infer_summary))))
    eval_done = int(monitor_state.get("eval_reports", len(eval_state.get("completed", {}))))
    active_instances = list(infer_state.get("active", []))
    active_index, active_instance = detect_active_instance(instance_ids, inference_done, last_started)
    if active_instances:
        active_index = None
        active_instance = ", ".join(active_instances)
    last_inference_instance = infer_summary[-1]["instance_id"] if infer_summary else None
    last_eval_instance, last_eval_time = last_completed_eval(eval_state)

    now = datetime.now().astimezone()
    return {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "run_root": str(run_root),
        "total_instances": total_instances,
        "inference_done": inference_done,
        "eval_done": eval_done,
        "remaining": max(total_instances - inference_done, 0),
        "active_count": len(active_instances),
        "active_instances": active_instances,
        "active_index": active_index,
        "active_instance": active_instance,
        "last_inference_instance": last_inference_instance,
        "last_eval_instance": last_eval_instance,
        "last_eval_time": last_eval_time,
        "done": bool(monitor_state.get("done", False)),
    }


def build_delta(snapshot: dict, previous: dict | None) -> str:
    if not previous:
        return "Initial snapshot."

    parts: list[str] = []
    inf_delta = snapshot["inference_done"] - previous.get("inference_done", 0)
    eval_delta = snapshot["eval_done"] - previous.get("eval_done", 0)

    if inf_delta > 0:
        parts.append(
            f"Inference advanced by {inf_delta} to {snapshot['inference_done']}/{snapshot['total_instances']}."
        )
    else:
        parts.append(f"Inference unchanged at {snapshot['inference_done']}/{snapshot['total_instances']}.")

    if eval_delta > 0:
        parts.append(f"Evaluation advanced by {eval_delta} to {snapshot['eval_done']}/{snapshot['total_instances']}.")
    else:
        parts.append(f"Evaluation unchanged at {snapshot['eval_done']}/{snapshot['total_instances']}.")

    previous_active = previous.get("active_instance")
    current_active = snapshot.get("active_instance")
    if current_active and current_active != previous_active:
        parts.append(f"Current in-flight instance changed to {current_active}.")
    elif current_active:
        parts.append(f"Current in-flight instance is still {current_active}.")
    elif previous_active and not current_active:
        parts.append("No active inference instance is visible from the current status files.")

    if snapshot.get("done") and not previous.get("done"):
        parts.append("Run is marked done.")

    return " ".join(parts)


def ensure_header(path: Path, run_root: Path) -> None:
    if path.exists():
        return
    header = [
        "# official48 Progress",
        "",
        f"- Run root: `{run_root}`",
        "- Source of truth: `monitor_status.json`, `eval_worker_status.json`, `infer/inference_summary.json`, and `official48_runs/current_router.log`.",
        "- This file records observed state only. It does not invent missing progress or ETA.",
        "",
    ]
    path.write_text("\n".join(header), encoding="utf-8")


def append_snapshot(path: Path, snapshot: dict, delta: str) -> None:
    lines = [
        f"## {snapshot['timestamp']}",
        "",
        f"- Inference: `{snapshot['inference_done']}/{snapshot['total_instances']}` ({format_pct(snapshot['inference_done'], snapshot['total_instances'])})",
        f"- Evaluation: `{snapshot['eval_done']}/{snapshot['total_instances']}` ({format_pct(snapshot['eval_done'], snapshot['total_instances'])})",
        f"- Remaining instances: `{snapshot['remaining']}`",
        f"- Active inference slots: `{snapshot['active_count']}`",
        f"- Current in-flight instance(s): `{snapshot['active_instance'] or 'unknown'}`"
        + (f" (`{snapshot['active_index']}/{snapshot['total_instances']}`)" if snapshot["active_index"] else ""),
        f"- Last completed inference: `{snapshot['last_inference_instance'] or 'none'}`",
        f"- Last completed evaluation: `{snapshot['last_eval_instance'] or 'none'}`"
        + (f" at `{snapshot['last_eval_time']}`" if snapshot["last_eval_time"] else ""),
        f"- Delta since previous snapshot: {delta}",
        "",
    ]
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root")
    parser.add_argument("output_md")
    parser.add_argument("--interval-seconds", type=int, default=1800)
    parser.add_argument("--state-file", default="")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    output_md = Path(args.output_md).resolve()
    state_file = Path(args.state_file).resolve() if args.state_file else run_root / "progress_state.json"

    ensure_header(output_md, run_root)
    previous = read_json(state_file, None)
    next_write_at = 0.0

    while True:
        snapshot = build_snapshot(run_root)
        now = time.time()
        should_write = now >= next_write_at or (snapshot["done"] and not (previous or {}).get("done"))

        if should_write:
            delta = build_delta(snapshot, previous)
            append_snapshot(output_md, snapshot, delta)
            state_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            previous = snapshot
            next_write_at = now + args.interval_seconds

        if snapshot["done"]:
            break

        time.sleep(30)


if __name__ == "__main__":
    main()
