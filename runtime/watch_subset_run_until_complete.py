#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def infer_process_active(run_root: Path) -> bool:
    result = subprocess.run(
        ["pgrep", "-af", "run_official48_subset_infer.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    needle = str((run_root / "infer").resolve())
    for line in result.stdout.splitlines():
        if needle in line:
            return True
    return False


def summarize(repo_root: Path, run_root: Path, instances_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_ROOT / "summarize_official48_run.py"),
            "--run-root",
            str(run_root),
            "--repo-root",
            str(repo_root),
            "--instances-dir",
            str(instances_dir),
        ],
        check=False,
    )


def resume_once(repo_root: Path, run_root: Path, metadata: dict, instances_dir: Path) -> int:
    cmd = [
        sys.executable,
        str(SCRIPT_ROOT / "run_official48_subset_infer.py"),
        "--output-dir",
        str(run_root / "infer"),
        "--instances-dir",
        str(instances_dir),
        "--cli-bin",
        metadata["cli_bin"],
        "--settings-file",
        metadata["settings_file"],
        "--env-file",
        metadata["env_file"],
        "--model",
        metadata["model"],
        "--agent-name",
        metadata["agent_name"],
        "--max-concurrency",
        "1",
        "--cli-timeout-seconds",
        "5400",
        "--resume",
        "--force-workspace",
    ]
    print(f"[watch] resume run_root={run_root}", flush=True)
    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-resume-attempts", type=int, default=4)
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else SCRIPT_ROOT.parent
    instances_dir = run_root / "input" / "output_final"
    metadata = load_json(run_root / "metadata.json", {})
    if not metadata:
        raise SystemExit(f"missing metadata.json under {run_root}")

    attempts = 0
    while True:
        infer_status = load_json(run_root / "infer" / "inference_status.json", {})
        total = int(infer_status.get("total_instances") or 0)
        completed = int(infer_status.get("completed_count") or 0)
        failed = int(infer_status.get("failed_count") or 0)
        active = int(infer_status.get("active_count") or 0)
        infer_active = infer_process_active(run_root)

        if total and completed >= total and failed == 0 and active == 0 and not infer_active:
            summarize(repo_root, run_root, instances_dir)
            print(f"[watch] complete run_root={run_root}", flush=True)
            return

        needs_resume = (
            total > 0
            and active == 0
            and not infer_active
            and (
                failed > 0
                or completed + failed < total
            )
        )

        if needs_resume:
            if attempts >= args.max_resume_attempts:
                summarize(repo_root, run_root, instances_dir)
                raise SystemExit(
                    f"resume attempts exhausted for {run_root}: completed={completed} failed={failed} total={total}"
                )
            attempts += 1
            rc = resume_once(repo_root, run_root, metadata, instances_dir)
            summarize(repo_root, run_root, instances_dir)
            if rc == 0:
                attempts = 0
            time.sleep(max(args.poll_seconds // 3, 10))
            continue

        summarize(repo_root, run_root, instances_dir)
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
