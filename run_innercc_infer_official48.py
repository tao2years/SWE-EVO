#!/usr/bin/env python3
import argparse
from datetime import datetime
import importlib.util
import json
import shutil
import subprocess
import sqlite3
import threading
import time
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
CUSTOM_RUNNER_PATH = REPO_ROOT / "custom_cli_case" / "run_custom_cli_case.py"
ROUTER_DB_PATH = Path("/home/wt/sss_repos/sss_auto/llm_router/proxy/data/traces.db")
ROUTER_API_BASE = "http://127.0.0.1:18783"


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--instances-dir", default=str(REPO_ROOT / "output_final"))
    parser.add_argument("--cli-bin", default="/home/wt/repo/innerCC/cli")
    parser.add_argument("--settings-file", default="/home/wt/.claude/settings.json")
    parser.add_argument("--env-file", default="/home/wt/.config/swe-evo/minimax.env")
    parser.add_argument("--model", default="MiniMax-M2.5-highspeed")
    parser.add_argument("--agent-name", default="innercc-cli")
    parser.add_argument("--force-workspace", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--cli-timeout-seconds", type=int, default=5400)
    parser.add_argument("--router-db-path", default=str(ROUTER_DB_PATH))
    parser.add_argument("--router-api-base", default=ROUTER_API_BASE)
    args = parser.parse_args()

    runner = load_runner()
    instances_dir = Path(args.instances_dir)
    output_dir = Path(args.output_dir)
    workspaces_root = output_dir / "workspaces"
    runs_root = output_dir / "runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    workspaces_root.mkdir(parents=True, exist_ok=True)
    runs_root.mkdir(parents=True, exist_ok=True)

    instances = []
    for instance_path in sorted(instances_dir.glob("*.json")):
        instances.append(json.loads(instance_path.read_text(encoding="utf-8")))

    aggregate_preds_path = output_dir / "preds.json"
    summary_path = output_dir / "inference_summary.json"
    all_preds = {}
    summaries = []
    summary_by_id = {}
    completed_ids = set()
    if args.resume:
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
            if row.get("preds_json") and Path(row["preds_json"]).exists():
                completed_ids.add(instance_id)
    router_db_path = Path(args.router_db_path)
    router_api_base = args.router_api_base.rstrip("/")

    def export_router_bundle(instance_id: str, run_dir: Path) -> tuple[Path | None, str | None, str | None]:
        if not router_db_path.exists():
            return None, None, None
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
                return None, None, None
            session_id = row[0]
            run_row = con.execute(
                "SELECT id FROM runs WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            run_id = run_row[0] if run_row is not None else None
        finally:
            con.close()
        payload = json.dumps({"session_ids": [row[0]], "run_ids": [], "trace_ids": []}).encode("utf-8")
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

    def patch_router_note(kind: str, resource_id: str, note_text: str) -> None:
        payload = json.dumps({"notes": note_text}).encode("utf-8")
        request = urllib.request.Request(
            f"{router_api_base}/api/{kind}/{resource_id}/notes",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(request, timeout=30):
            pass

    def start_router_note_watcher(instance_id: str, note_text: str) -> tuple[threading.Event, threading.Thread]:
        stop_event = threading.Event()

        def worker():
            while not stop_event.is_set():
                if not router_db_path.exists():
                    stop_event.wait(2)
                    continue
                con = sqlite3.connect(router_db_path)
                try:
                    row = con.execute(
                        "SELECT id FROM sessions WHERE external_id IN (?, ?) ORDER BY updated_at DESC LIMIT 1",
                        (f"benchmark:innercc:{instance_id}", f"benchmark:cc:{instance_id}"),
                    ).fetchone()
                    if row is None:
                        stop_event.wait(2)
                        continue
                    session_id = row[0]
                    run_row = con.execute(
                        "SELECT id FROM runs WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1",
                        (session_id,),
                    ).fetchone()
                finally:
                    con.close()
                patch_router_note("sessions", session_id, note_text)
                if run_row is not None:
                    patch_router_note("runs", run_row[0], note_text)
                return

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return stop_event, thread

    for idx, instance in enumerate(instances, start=1):
        instance_id = instance["instance_id"]
        if instance_id in completed_ids:
            print(f"[infer {idx}/{len(instances)}] skip completed {instance_id}", flush=True)
            continue
        print(f"[infer {idx}/{len(instances)}] {instance_id}", flush=True)
        workspace_dir = workspaces_root / instance_id
        run_dir = runs_root / instance_id
        run_dir.mkdir(parents=True, exist_ok=True)
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        note_text = f"innercc | {instance_id} | {started_at}"

        prepare_workspace_ssh(instance, workspace_dir, args.force_workspace)
        watcher_stop, watcher_thread = start_router_note_watcher(instance_id, note_text)
        cli_result, cli_returncode = runner.run_cli(
            instance,
            workspace_dir,
            run_dir,
            Path(args.cli_bin),
            Path(args.settings_file),
            Path(args.env_file),
            args.model,
            None,
            args.cli_timeout_seconds,
        )
        watcher_stop.set()
        watcher_thread.join(timeout=1)
        instance_preds_path = runner.write_patch_outputs(instance_id, workspace_dir, run_dir, args.agent_name)
        preds = json.loads(instance_preds_path.read_text(encoding="utf-8"))
        all_preds.update(preds)
        bundle_path, session_id, router_run_id = export_router_bundle(instance_id, run_dir)
        if session_id:
            patch_router_note("sessions", session_id, note_text)
        if router_run_id:
            patch_router_note("runs", router_run_id, note_text)
        summary_by_id[instance_id] = {
            "instance_id": instance_id,
            "cli_returncode": cli_returncode,
            "cli_result": str(cli_result),
            "preds_json": str(instance_preds_path),
            "router_trace_bundle": str(bundle_path) if bundle_path else None,
            "router_session_id": session_id,
            "router_run_id": router_run_id,
            "router_note": note_text,
        }
        ordered_ids = [item["instance_id"] for item in instances if item["instance_id"] in summary_by_id]
        summaries = [summary_by_id[item_id] for item_id in ordered_ids]
        aggregate_preds_path.write_text(json.dumps(all_preds, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[infer] completed {len(instances)} instances", flush=True)


if __name__ == "__main__":
    main()
