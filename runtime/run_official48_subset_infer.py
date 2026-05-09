#!/usr/bin/env python3
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import importlib.util
import json
import os
import threading
from pathlib import Path

from swe_evo_env import (
    REPO_ROOT,
    default_cli_bin_path,
    default_env_file,
    default_model_name,
    default_settings_path,
)


CUSTOM_RUNNER_PATH = REPO_ROOT / "custom_cli_case" / "run_custom_cli_case.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_custom_cli_case", CUSTOM_RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.{threading.get_ident()}.tmp"
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


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


def build_trace_placeholder(instance_id: str, agent_name: str, run_dir: Path) -> Path:
    payload = {
        "mode": "router_disabled",
        "instance_id": instance_id,
        "agent_name": agent_name,
        "traces": [],
    }
    bundle_path = run_dir / "router_trace_bundle.json"
    bundle_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle_path


def load_cli_metrics(cli_result_path: Path) -> dict:
    try:
        payload = json.loads(cli_result_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return payload


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
    max_turns: int | None,
    cli_timeout_seconds: int,
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

    runner.prepare_workspace(instance, workspace_dir, force_workspace)
    cli_result, cli_returncode = runner.run_cli(
        instance,
        workspace_dir,
        run_dir,
        cli_bin,
        settings_file,
        env_file,
        model_name,
        max_turns,
        cli_timeout_seconds,
    )

    instance_preds_path = runner.write_patch_outputs(instance_id, workspace_dir, run_dir, agent_name)
    preds = json.loads(instance_preds_path.read_text(encoding="utf-8"))
    cli_metrics = load_cli_metrics(Path(cli_result))
    bundle_path = build_trace_placeholder(instance_id, agent_name, run_dir)

    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary_entry = {
        "instance_id": instance_id,
        "cli_returncode": cli_returncode,
        "cli_result": str(cli_result),
        "preds_json": str(instance_preds_path),
        "router_trace_bundle": str(bundle_path),
        "router_session_id": None,
        "router_run_id": None,
        "router_note": "router_disabled",
        "router_export_error": None,
        "max_turns": max_turns,
        "started_at": started_at,
        "finished_at": finished_at,
        "cli_type": cli_metrics.get("type"),
        "cli_subtype": cli_metrics.get("subtype"),
        "cli_is_error": cli_metrics.get("is_error"),
        "cli_duration_ms": cli_metrics.get("duration_ms"),
        "cli_duration_api_ms": cli_metrics.get("duration_api_ms"),
        "cli_num_turns": cli_metrics.get("num_turns"),
        "cli_total_cost_usd": cli_metrics.get("total_cost_usd"),
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
                max_turns=args.max_turns,
                cli_timeout_seconds=args.cli_timeout_seconds,
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


def main() -> None:
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
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--cli-timeout-seconds", type=int, default=5400)
    args = parser.parse_args()

    if args.max_concurrency < 1:
        raise SystemExit("--max-concurrency must be >= 1")
    if args.max_turns is not None and args.max_turns < 1:
        raise SystemExit("--max-turns must be >= 1")

    runner = load_runner()
    run_batch(args, runner)


if __name__ == "__main__":
    main()
