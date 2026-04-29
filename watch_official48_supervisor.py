#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path("/home/wt/sss_repos/sss_auto/SWE-EVO")
LLM_ROUTER_ROOT = Path("/home/wt/sss_repos/sss_auto/llm_router")
ROUTER_SESSION = "swe-evo-official48-router"
EVAL_SESSION = "swe-evo-official48-eval"
MONITOR_SESSION = "swe-evo-official48-monitor"
PROGRESS_SESSION = "swe-evo-official48-progress"
SUPERVISOR_SESSION = "swe-evo-official48-supervisor"
ROUTER_TMUX_PREFIX = "sss-auto-llm-router"


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def tmux_has_session(name: str) -> bool:
    result = subprocess.run(["tmux", "has-session", "-t", name], text=True, capture_output=True)
    return result.returncode == 0


def start_tmux_session(name: str, shell_command: str) -> None:
    subprocess.run(["tmux", "new-session", "-d", "-s", name, shell_command], check=True, text=True)


def append_log(path: Path, message: str) -> None:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{timestamp}] {message}\n")


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def actual_report_count(run_root: Path) -> int:
    eval_run_root = REPO_ROOT / "logs" / "run_evaluation" / f"eval_input_{run_root.name}"
    return len(list(eval_run_root.glob("**/report.json")))


def router_api_healthy() -> bool:
    try:
        with urlopen("http://127.0.0.1:18783/api/sessions", timeout=5) as response:
            response.read(1)
        return True
    except URLError:
        return False
    except Exception:
        return False


def ensure_llm_router(log_path: Path) -> None:
    proxy_ok = tmux_has_session(f"{ROUTER_TMUX_PREFIX}-proxy")
    web_ok = tmux_has_session(f"{ROUTER_TMUX_PREFIX}-web")
    api_ok = router_api_healthy()
    if proxy_ok and web_ok and api_ok:
        return

    append_log(
        log_path,
        f"llm_router unhealthy (proxy={proxy_ok}, web={web_ok}, api={api_ok}); restarting stack",
    )
    subprocess.run(
        [
            "bash",
            "-lc",
            (
                "SESSION_PREFIX=sss-auto-llm-router "
                "ANTHROPIC_UPSTREAM_URL=https://api.minimaxi.com/anthropic "
                "OPENAI_UPSTREAM_URL=https://api.minimaxi.com/v1 "
                "bash /home/wt/sss_repos/sss_auto/llm_router/scripts/start-prod.sh"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
    )


def monitor_done(run_root: Path) -> bool:
    state = read_json(run_root / "monitor_status.json", {})
    total_instances = int(state.get("total_instances", 48) or 48)
    return bool(state.get("done")) and actual_report_count(run_root) >= total_instances


def ensure_eval(run_root: Path, log_path: Path, max_concurrency: int) -> None:
    if tmux_has_session(EVAL_SESSION):
        return
    report_count = actual_report_count(run_root)
    append_log(log_path, f"eval session missing; restarting (report_count={report_count})")
    start_tmux_session(
        EVAL_SESSION,
        (
            "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && "
            f"python3 -u run_official48_eval_worker.py {run_root} {max_concurrency} --retry-missing-report"
            f" 2>&1 | tee -a {run_root}/eval_worker.log'"
        ),
    )


def ensure_monitor(run_root: Path, log_path: Path) -> None:
    if tmux_has_session(MONITOR_SESSION):
        return
    append_log(log_path, "monitor session missing; restarting")
    start_tmux_session(
        MONITOR_SESSION,
        (
            "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && "
            f"python3 -u monitor_official48_run.py {run_root}"
            f" 2>&1 | tee -a {run_root}/monitor.log'"
        ),
    )


def ensure_progress(run_root: Path, progress_md: Path, log_path: Path) -> None:
    if tmux_has_session(PROGRESS_SESSION):
        return
    append_log(log_path, "progress session missing; restarting")
    start_tmux_session(
        PROGRESS_SESSION,
        (
            "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && "
            f"python3 -u record_official48_progress.py {run_root} {progress_md} --interval-seconds 1800'"
        ),
    )


def ensure_router_worker(
    run_root: Path,
    log_path: Path,
    inference_concurrency: int,
    cli_timeout_seconds: int,
    router_ready_timeout_seconds: int,
    cli_bin: str,
    settings_file: str,
    env_file: str,
    model_name: str,
    agent_name: str,
) -> None:
    if tmux_has_session(ROUTER_SESSION):
        return
    monitor_state = read_json(run_root / "monitor_status.json", {})
    total_instances = int(monitor_state.get("total_instances", 48) or 48)
    if int(monitor_state.get("inference_done", 0)) >= total_instances:
        return
    append_log(log_path, "router inference session missing; restarting with --resume")
    start_tmux_session(
        ROUTER_SESSION,
        (
            "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && "
            "PYTHONPATH=/home/wt/sss_repos/sss_auto/SWE-EVO/.deps "
            "python3 -u run_innercc_infer_official48.py "
            f"--output-dir {run_root}/infer "
            "--instances-dir /home/wt/sss_repos/sss_auto/SWE-EVO/output_final "
            f"--cli-bin {cli_bin} "
            f"--settings-file {settings_file} "
            f"--env-file {env_file} "
            f"--model {model_name} "
            f"--agent-name {agent_name} "
            f"--resume --max-concurrency {inference_concurrency} "
            f"--cli-timeout-seconds {cli_timeout_seconds} "
            f"--router-ready-timeout-seconds {router_ready_timeout_seconds} "
            "2>&1 | tee -a /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/current_router.log'"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root")
    parser.add_argument("--progress-md", default=str(REPO_ROOT / "progress.md"))
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--inference-concurrency", type=int, default=2)
    parser.add_argument("--eval-max-concurrency", type=int, default=3)
    parser.add_argument("--cli-timeout-seconds", type=int, default=5400)
    parser.add_argument("--router-ready-timeout-seconds", type=int, default=120)
    parser.add_argument("--cli-bin", default="/home/wt/repo/innerCC/cli")
    parser.add_argument("--settings-file", default="/home/wt/.claude/settings.json")
    parser.add_argument("--env-file", default="/home/wt/.config/swe-evo/minimax.env")
    parser.add_argument("--model", default="MiniMax-M2.5-highspeed")
    parser.add_argument("--agent-name", default="innercc-cli")
    args = parser.parse_args()

    run_root = Path(args.run_root).resolve()
    progress_md = Path(args.progress_md).resolve()
    supervisor_log = run_root / "supervisor.log"
    append_log(supervisor_log, f"supervisor started for {run_root}")

    while True:
        ensure_llm_router(supervisor_log)
        ensure_eval(run_root, supervisor_log, args.eval_max_concurrency)
        ensure_monitor(run_root, supervisor_log)
        ensure_progress(run_root, progress_md, supervisor_log)

        if monitor_done(run_root):
            append_log(supervisor_log, "monitor reports done=true; supervisor exiting")
            break

        ensure_router_worker(
            run_root,
            supervisor_log,
            args.inference_concurrency,
            args.cli_timeout_seconds,
            args.router_ready_timeout_seconds,
            args.cli_bin,
            args.settings_file,
            args.env_file,
            args.model,
            args.agent_name,
        )
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
