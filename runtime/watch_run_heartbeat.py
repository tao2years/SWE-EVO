#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import time
from datetime import datetime
from pathlib import Path


TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
TERMINAL_STATES = {"completed", "timed_out", "terminated", "failed", "interrupted"}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.{os.getpid()}.tmp"
    tmp_path.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")
    os.replace(tmp_path, path)


def parse_timestamp(value: str | None) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("T", " ")
    try:
        return datetime.strptime(normalized, TIMESTAMP_FORMAT).timestamp()
    except ValueError:
        return None


def lifecycle_path(run_root: Path) -> Path:
    return run_root / "run_lifecycle.json"


def update_lifecycle(run_root: Path, **updates) -> dict:
    path = lifecycle_path(run_root)
    payload = load_json(path, {})
    payload.update({key: value for key, value in updates.items() if value is not None})
    payload["updated_at"] = datetime.now().strftime(TIMESTAMP_FORMAT)
    write_json_atomic(path, payload)
    return payload


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def signal_process_group(pid: int, sig: signal.Signals) -> None:
    if pid <= 0:
        return
    try:
        os.killpg(pid, sig)
        return
    except OSError:
        pass
    try:
        os.kill(pid, sig)
    except OSError:
        pass


def latest_heartbeat(run_root: Path) -> tuple[float | None, str | None]:
    candidates = [
        run_root / "monitor_status.json",
        run_root / "progress_state.json",
        run_root / "infer" / "inference_status.json",
        run_root / "eval_worker_status.json",
    ]
    best_timestamp = None
    best_source = None

    for path in candidates:
        if not path.exists():
            continue
        file_timestamp = path.stat().st_mtime
        payload = load_json(path, None)
        embedded_timestamp = None
        if isinstance(payload, dict):
            embedded_timestamp = parse_timestamp(payload.get("timestamp")) or parse_timestamp(payload.get("updated_at"))
        candidate_timestamp = max(
            value for value in (file_timestamp, embedded_timestamp) if value is not None
        )
        if best_timestamp is None or candidate_timestamp > best_timestamp:
            best_timestamp = candidate_timestamp
            best_source = str(path)

    return best_timestamp, best_source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--infer-pid", type=int, default=0)
    parser.add_argument("--eval-pid", type=int, default=0)
    parser.add_argument("--heartbeat-timeout-seconds", type=int, default=3600)
    parser.add_argument("--poll-interval-seconds", type=int, default=60)
    parser.add_argument("--kill-grace-seconds", type=int, default=30)
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    managed_pids = [pid for pid in (args.infer_pid, args.eval_pid) if pid > 0]
    started_at = datetime.now().strftime(TIMESTAMP_FORMAT)
    update_lifecycle(
        run_root,
        state="running",
        started_at=started_at,
        heartbeat_timeout_seconds=args.heartbeat_timeout_seconds,
        watchdog_started_at=started_at,
        infer_pid=args.infer_pid or None,
        eval_pid=args.eval_pid or None,
    )

    while True:
        payload = load_json(lifecycle_path(run_root), {})
        current_state = payload.get("state")
        if current_state in TERMINAL_STATES and current_state != "running":
            return

        if not any(pid_alive(pid) for pid in managed_pids):
            return

        heartbeat_timestamp, heartbeat_source = latest_heartbeat(run_root)
        if heartbeat_timestamp is None:
            baseline = parse_timestamp(payload.get("started_at")) or time.time()
        else:
            baseline = heartbeat_timestamp
        heartbeat_age_seconds = max(0, int(time.time() - baseline))

        if heartbeat_age_seconds < args.heartbeat_timeout_seconds:
            time.sleep(max(args.poll_interval_seconds, 1))
            continue

        timed_out_at = datetime.now().strftime(TIMESTAMP_FORMAT)
        update_lifecycle(
            run_root,
            state="timed_out",
            reason="heartbeat_timeout",
            timed_out_at=timed_out_at,
            heartbeat_age_seconds=heartbeat_age_seconds,
            heartbeat_source=heartbeat_source,
        )

        for pid in managed_pids:
            signal_process_group(pid, signal.SIGTERM)
        deadline = time.time() + max(args.kill_grace_seconds, 1)
        while time.time() < deadline and any(pid_alive(pid) for pid in managed_pids):
            time.sleep(1)
        for pid in managed_pids:
            signal_process_group(pid, signal.SIGKILL)
        return


if __name__ == "__main__":
    main()
