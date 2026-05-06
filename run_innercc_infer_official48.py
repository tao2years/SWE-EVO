#!/usr/bin/env python3
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from urllib.error import URLError

from swe_evo_env import (
    REPO_ROOT,
    default_cli_bin_path,
    default_env_file,
    default_model_name,
    default_router_api_base,
    default_router_db_path,
    default_settings_path,
)

CUSTOM_RUNNER_PATH = REPO_ROOT / "custom_cli_case" / "run_custom_cli_case.py"
ROUTER_DB_PATH = default_router_db_path()
ROUTER_API_BASE = default_router_api_base()


def load_runner():
    spec = importlib.util.spec_from_file_location("run_custom_cli_case", CUSTOM_RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run(cmd, *, cwd=None, env=None, check=True, capture_output=False, text=True):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=capture_output,
        text=text,
    )


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.{threading.get_ident()}.tmp"
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def commit_exists(repo_dir: Path, commit: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"],
        cwd=repo_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def prepare_workspace_ssh(instance: dict, workspace_dir: Path, force: bool) -> None:
    repo_name = instance["repo"]
    base_commit = instance["base_commit"]
    repo_url = f"git@github.com:{repo_name}.git"
    cache_repo_dir = workspace_dir.parent / repo_name.split("/")[-1]

    if force and workspace_dir.exists():
        shutil.rmtree(workspace_dir)

    if (workspace_dir / ".git").exists():
        return

    workspace_dir.parent.mkdir(parents=True, exist_ok=True)
    if (
        cache_repo_dir != workspace_dir
        and (cache_repo_dir / ".git").exists()
        and commit_exists(cache_repo_dir, base_commit)
    ):
        run(["git", "clone", str(cache_repo_dir), workspace_dir.name], cwd=workspace_dir.parent)
        run(["git", "checkout", base_commit], cwd=workspace_dir)
    else:
        run(["git", "init", workspace_dir.name], cwd=workspace_dir.parent)
        run(["git", "remote", "add", "origin", repo_url], cwd=workspace_dir)
        fetch_cmd = ["git", "fetch", "--depth", "1", "origin", base_commit]
        last_error = None
        for _ in range(3):
            try:
                run(fetch_cmd, cwd=workspace_dir)
                last_error = None
                break
            except subprocess.CalledProcessError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        run(["git", "checkout", "FETCH_HEAD"], cwd=workspace_dir)

    run(["git", "remote", "set-url", "origin", repo_url], cwd=workspace_dir)
    run(["git", "config", "user.email", "benchmark@example.com"], cwd=workspace_dir)
    run(["git", "config", "user.name", "benchmark"], cwd=workspace_dir)


def load_instances(instances_dir: Path) -> list[dict]:
    return [
        json.loads(instance_path.read_text(encoding="utf-8"))
        for instance_path in sorted(instances_dir.glob("*.json"))
    ]


def load_resume_state(
    aggregate_preds_path: Path,
    summary_path: Path,
) -> tuple[dict, list[dict], dict[str, dict], set[str]]:
    all_preds: dict = {}
    summaries: list[dict] = []
    summary_by_id: dict[str, dict] = {}
    completed_ids: set[str] = set()

    if aggregate_preds_path.exists():
        try:
            all_preds = json.loads(aggregate_preds_path.read_text(encoding="utf-8"))
        except Exception:
            all_preds = {}

    if summary_path.exists():
        try:
            summaries = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            summaries = []

    for row in summaries:
        instance_id = row.get("instance_id")
        if not instance_id:
            continue
        summary_by_id[instance_id] = row
        preds_json = row.get("preds_json")
        if preds_json and Path(preds_json).exists():
            completed_ids.add(instance_id)
            if instance_id not in all_preds:
                try:
                    all_preds.update(json.loads(Path(preds_json).read_text(encoding="utf-8")))
                except Exception:
                    pass

    return all_preds, summaries, summary_by_id, completed_ids


def router_api_healthy(router_api_base: str, timeout_seconds: int = 5) -> bool:
    try:
        with urllib.request.urlopen(f"{router_api_base}/api/sessions", timeout=timeout_seconds) as response:
            response.read(1)
        return True
    except URLError:
        return False
    except Exception:
        return False


def wait_for_router(
    router_db_path: Path,
    router_api_base: str,
    timeout_seconds: int,
    poll_seconds: float,
    instance_id: str,
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if router_db_path.exists() and router_api_healthy(router_api_base):
            return
        time.sleep(poll_seconds)
    raise TimeoutError(
        f"router not ready for {instance_id}: db={router_db_path.exists()} api={router_api_healthy(router_api_base)}"
    )


def patch_router_note(
    kind: str,
    resource_id: str,
    note_text: str,
    router_api_base: str,
    timeout_seconds: int = 30,
    poll_seconds: float = 2.0,
) -> bool:
    deadline = time.time() + timeout_seconds
    payload = json.dumps({"notes": note_text}).encode("utf-8")

    while time.time() < deadline:
        try:
            request = urllib.request.Request(
                f"{router_api_base}/api/{kind}/{resource_id}/notes",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="PATCH",
            )
            with urllib.request.urlopen(request, timeout=10):
                return True
        except Exception:
            time.sleep(poll_seconds)
    return False


def export_router_bundle(
    instance_id: str,
    run_dir: Path,
    router_db_path: Path,
    router_api_base: str,
    timeout_seconds: int,
    poll_seconds: float,
) -> tuple[Path, str | None, str | None]:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        if not router_db_path.exists() or not router_api_healthy(router_api_base):
            time.sleep(poll_seconds)
            continue

        con = sqlite3.connect(router_db_path)
        try:
            row = con.execute(
                "SELECT id FROM sessions WHERE external_id = ? ORDER BY updated_at DESC LIMIT 1",
                (f"benchmark:innercc:{instance_id}",),
            ).fetchone()
            if row is None:
                row = con.execute(
                    "SELECT id FROM sessions WHERE external_id = ? ORDER BY updated_at DESC LIMIT 1",
                    (f"benchmark:cc:{instance_id}",),
                ).fetchone()
            if row is None:
                time.sleep(poll_seconds)
                continue

            session_id = row[0]
            run_row = con.execute(
                "SELECT id FROM runs WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            run_id = run_row[0] if run_row is not None else None
        finally:
            con.close()

        try:
            payload = json.dumps({"session_ids": [session_id], "run_ids": [], "trace_ids": []}).encode("utf-8")
            request = urllib.request.Request(
                f"{router_api_base}/api/export",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                bundle = json.load(response)
            bundle_path = run_dir / "router_trace_bundle.json"
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            return bundle_path, session_id, run_id
        except Exception:
            time.sleep(poll_seconds)

    raise TimeoutError(f"failed to export router bundle for {instance_id} within {timeout_seconds} seconds")


def start_router_note_watcher(
    instance_id: str,
    note_text: str,
    router_db_path: Path,
    router_api_base: str,
    timeout_seconds: int,
    poll_seconds: float,
) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()

    def worker():
        deadline = time.time() + timeout_seconds
        while not stop_event.is_set() and time.time() < deadline:
            if not router_db_path.exists():
                stop_event.wait(poll_seconds)
                continue

            con = sqlite3.connect(router_db_path)
            try:
                row = con.execute(
                    "SELECT id FROM sessions WHERE external_id IN (?, ?) ORDER BY updated_at DESC LIMIT 1",
                    (f"benchmark:innercc:{instance_id}", f"benchmark:cc:{instance_id}"),
                ).fetchone()
                if row is None:
                    stop_event.wait(poll_seconds)
                    continue
                session_id = row[0]
                run_row = con.execute(
                    "SELECT id FROM runs WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
            finally:
                con.close()

            patch_router_note("sessions", session_id, note_text, router_api_base)
            if run_row is not None:
                patch_router_note("runs", run_row[0], note_text, router_api_base)
            return

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return stop_event, thread


def write_inference_status(
    status_path: Path,
    run_root: Path,
    instances: list[dict],
    max_concurrency: int,
    active_ids: set[str],
    completed_ids: set[str],
    failed_ids: set[str],
) -> None:
    ordered_completed = [item["instance_id"] for item in instances if item["instance_id"] in completed_ids]
    ordered_failed = [item["instance_id"] for item in instances if item["instance_id"] in failed_ids]
    payload = {
        "run_root": str(run_root),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_instances": len(instances),
        "max_concurrency": max_concurrency,
        "active": sorted(active_ids),
        "active_count": len(active_ids),
        "completed": ordered_completed,
        "completed_count": len(completed_ids),
        "failed": ordered_failed,
        "failed_count": len(failed_ids),
        "pending_count": max(len(instances) - len(active_ids) - len(completed_ids), 0),
        "done": len(completed_ids) >= len(instances),
    }
    write_json_atomic(status_path, payload)


def process_instance(
    instance: dict,
    idx: int,
    total_instances: int,
    *,
    runner,
    workspaces_root: Path,
    runs_root: Path,
    cli_bin: Path,
    settings_file: Path,
    env_file: Path,
    model_name: str,
    agent_name: str,
    force_workspace: bool,
    cli_timeout_seconds: int,
    router_db_path: Path,
    router_api_base: str,
    router_ready_timeout_seconds: int,
    router_export_timeout_seconds: int,
    router_poll_seconds: float,
    on_start=None,
) -> tuple[dict, dict]:
    instance_id = instance["instance_id"]
    if on_start is not None:
        on_start(instance_id)
    print(f"[infer {idx}/{total_instances}] start {instance_id}", flush=True)

    workspace_dir = workspaces_root / instance_id
    run_dir = runs_root / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_text = f"innercc | {instance_id} | {started_at}"

    prepare_workspace_ssh(instance, workspace_dir, force_workspace)
    wait_for_router(
        router_db_path,
        router_api_base,
        timeout_seconds=router_ready_timeout_seconds,
        poll_seconds=router_poll_seconds,
        instance_id=instance_id,
    )

    watcher_stop, watcher_thread = start_router_note_watcher(
        instance_id,
        note_text,
        router_db_path,
        router_api_base,
        timeout_seconds=router_ready_timeout_seconds,
        poll_seconds=router_poll_seconds,
    )
    try:
        cli_result, cli_returncode = runner.run_cli(
            instance,
            workspace_dir,
            run_dir,
            cli_bin,
            settings_file,
            env_file,
            model_name,
            None,
            cli_timeout_seconds,
        )
    finally:
        watcher_stop.set()
        watcher_thread.join(timeout=1)

    instance_preds_path = runner.write_patch_outputs(instance_id, workspace_dir, run_dir, agent_name)
    preds = json.loads(instance_preds_path.read_text(encoding="utf-8"))
    bundle_path, session_id, router_run_id = export_router_bundle(
        instance_id,
        run_dir,
        router_db_path,
        router_api_base,
        timeout_seconds=router_export_timeout_seconds,
        poll_seconds=router_poll_seconds,
    )

    if session_id:
        patch_router_note("sessions", session_id, note_text, router_api_base)
    if router_run_id:
        patch_router_note("runs", router_run_id, note_text, router_api_base)

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_entry = {
        "instance_id": instance_id,
        "cli_returncode": cli_returncode,
        "cli_result": str(cli_result),
        "preds_json": str(instance_preds_path),
        "router_trace_bundle": str(bundle_path),
        "router_session_id": session_id,
        "router_run_id": router_run_id,
        "router_note": note_text,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    print(f"[infer {idx}/{total_instances}] done {instance_id} rc={cli_returncode}", flush=True)
    return summary_entry, preds


def run_batch(args, runner) -> None:
    instances_dir = Path(args.instances_dir)
    output_dir = Path(args.output_dir)
    workspaces_root = output_dir / "workspaces"
    runs_root = output_dir / "runs"
    aggregate_preds_path = output_dir / "preds.json"
    summary_path = output_dir / "inference_summary.json"
    status_path = output_dir / "inference_status.json"

    output_dir.mkdir(parents=True, exist_ok=True)
    workspaces_root.mkdir(parents=True, exist_ok=True)
    runs_root.mkdir(parents=True, exist_ok=True)

    instances = load_instances(instances_dir)
    all_preds = {}
    summaries = []
    summary_by_id: dict[str, dict] = {}
    completed_ids: set[str] = set()
    if args.resume:
        all_preds, summaries, summary_by_id, completed_ids = load_resume_state(aggregate_preds_path, summary_path)

    active_ids: set[str] = set()
    failed_ids: set[str] = set()
    state_lock = threading.Lock()

    if all_preds:
        write_json_atomic(aggregate_preds_path, all_preds)
    if summaries:
        write_json_atomic(summary_path, summaries)
    write_inference_status(
        status_path,
        output_dir.parent,
        instances,
        args.max_concurrency,
        active_ids,
        completed_ids,
        failed_ids,
    )

    pending: list[tuple[int, dict]] = []
    for idx, instance in enumerate(instances, start=1):
        instance_id = instance["instance_id"]
        if instance_id in completed_ids:
            print(f"[infer {idx}/{len(instances)}] skip completed {instance_id}", flush=True)
            continue
        pending.append((idx, instance))

    if not pending:
        print(f"[infer] nothing to do, already completed {len(completed_ids)}/{len(instances)} instances", flush=True)
        write_inference_status(
            status_path,
            output_dir.parent,
            instances,
            args.max_concurrency,
            active_ids,
            completed_ids,
            failed_ids,
        )
        return

    router_db_path = Path(args.router_db_path)
    router_api_base = args.router_api_base.rstrip("/")
    errors: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=args.max_concurrency) as executor:
        future_to_meta = {}

        def mark_active(instance_id: str) -> None:
            with state_lock:
                active_ids.add(instance_id)
                write_inference_status(
                    status_path,
                    output_dir.parent,
                    instances,
                    args.max_concurrency,
                    active_ids,
                    completed_ids,
                    failed_ids,
                )

        for idx, instance in pending:
            instance_id = instance["instance_id"]
            future = executor.submit(
                process_instance,
                instance,
                idx,
                len(instances),
                runner=runner,
                workspaces_root=workspaces_root,
                runs_root=runs_root,
                cli_bin=Path(args.cli_bin),
                settings_file=Path(args.settings_file),
                env_file=Path(args.env_file),
                model_name=args.model,
                agent_name=args.agent_name,
                force_workspace=args.force_workspace,
                cli_timeout_seconds=args.cli_timeout_seconds,
                router_db_path=router_db_path,
                router_api_base=router_api_base,
                router_ready_timeout_seconds=args.router_ready_timeout_seconds,
                router_export_timeout_seconds=args.router_export_timeout_seconds,
                router_poll_seconds=args.router_poll_seconds,
                on_start=mark_active,
            )
            future_to_meta[future] = (idx, instance_id)

        for future in as_completed(future_to_meta):
            idx, instance_id = future_to_meta[future]
            try:
                summary_entry, preds = future.result()
            except Exception as exc:
                errors.append((instance_id, str(exc)))
                print(f"[infer {idx}/{len(instances)}] failed {instance_id}: {exc}", flush=True)
                with state_lock:
                    active_ids.discard(instance_id)
                    failed_ids.add(instance_id)
                    write_inference_status(
                        status_path,
                        output_dir.parent,
                        instances,
                        args.max_concurrency,
                        active_ids,
                        completed_ids,
                        failed_ids,
                    )
                continue

            with state_lock:
                active_ids.discard(instance_id)
                failed_ids.discard(instance_id)
                completed_ids.add(instance_id)
                all_preds.update(preds)
                summary_by_id[instance_id] = summary_entry
                ordered_ids = [item["instance_id"] for item in instances if item["instance_id"] in summary_by_id]
                summaries = [summary_by_id[item_id] for item_id in ordered_ids]
                write_json_atomic(aggregate_preds_path, all_preds)
                write_json_atomic(summary_path, summaries)
                write_inference_status(
                    status_path,
                    output_dir.parent,
                    instances,
                    args.max_concurrency,
                    active_ids,
                    completed_ids,
                    failed_ids,
                )

    print(f"[infer] completed {len(completed_ids)}/{len(instances)} instances", flush=True)
    if errors:
        error_text = "; ".join(f"{instance_id}: {message}" for instance_id, message in errors)
        raise RuntimeError(f"inference finished with failures: {error_text}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--instances-dir", default=str(REPO_ROOT / "output_final"))
    parser.add_argument("--cli-bin", default=str(default_cli_bin_path()))
    parser.add_argument("--settings-file", default=str(default_settings_path()))
    parser.add_argument("--env-file", default=str(default_env_file()))
    parser.add_argument("--model", default=default_model_name())
    parser.add_argument("--agent-name", default="innercc-cli")
    parser.add_argument("--force-workspace", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-concurrency", type=int, default=2)
    parser.add_argument("--cli-timeout-seconds", type=int, default=5400)
    parser.add_argument("--router-db-path", default=str(ROUTER_DB_PATH))
    parser.add_argument("--router-api-base", default=ROUTER_API_BASE)
    parser.add_argument("--router-ready-timeout-seconds", type=int, default=120)
    parser.add_argument("--router-export-timeout-seconds", type=int, default=120)
    parser.add_argument("--router-poll-seconds", type=float, default=2.0)
    args = parser.parse_args()

    if args.max_concurrency < 1:
        raise SystemExit("--max-concurrency must be >= 1")

    runner = load_runner()
    run_batch(args, runner)


if __name__ == "__main__":
    main()
