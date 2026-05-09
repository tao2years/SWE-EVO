#!/usr/bin/env python3
import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
import socket
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from swe_evo_env import (
    REPO_ROOT,
    default_cli_bin_path,
    default_env_file,
    default_model_name,
    default_router_api_base,
    default_router_root,
    default_settings_path,
    shell_join,
    shell_python_env_prefix,
    shell_quote,
)


LLM_ROUTER_ROOT = default_router_root()
ROUTER_API_BASE = default_router_api_base()
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


def kill_tmux_session(name: str) -> None:
    subprocess.run(["tmux", "kill-session", "-t", name], check=False, text=True, capture_output=True)


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


def repo_shell(command: str) -> str:
    inner = f"cd {shell_quote(REPO_ROOT)} && {command}"
    return f"bash -lc {shell_quote(inner)}"


def router_api_healthy(timeout_seconds: int = 5, attempts: int = 3, attempt_delay_seconds: float = 1.0) -> bool:
    for attempt in range(max(attempts, 1)):
        try:
            with urlopen(f"{ROUTER_API_BASE}/api/sessions", timeout=timeout_seconds) as response:
                response.read(1)
            return True
        except URLError:
            pass
        except Exception:
            pass
        if attempt + 1 < max(attempts, 1):
            time.sleep(attempt_delay_seconds)
    return False


def parse_base_url_from_settings(settings_file: Path) -> str | None:
    try:
        payload = json.loads(settings_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    env = payload.get("env", {})
    if not isinstance(env, dict):
        return None
    for key in ("ANTHROPIC_BASE_URL", "OPENAI_BASE_URL"):
        value = env.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def parse_base_url_from_env_file(env_file: Path) -> str | None:
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for key in ("ANTHROPIC_BASE_URL", "OPENAI_BASE_URL"):
            prefixes = (f"{key}=", f"export {key}=")
            if not stripped.startswith(prefixes):
                continue
            _, value = stripped.split("=", 1)
            value = value.strip().strip("'\"")
            if value:
                return value
    return None


def load_router_proxy_base_url(settings_file: Path, env_file: Path) -> str | None:
    return parse_base_url_from_settings(settings_file) or parse_base_url_from_env_file(env_file)


def proxy_base_healthy(
    proxy_base_url: str,
    timeout_seconds: int = 5,
    attempts: int = 3,
    attempt_delay_seconds: float = 1.0,
) -> bool:
    parsed = urlparse(proxy_base_url)
    host = parsed.hostname
    if host is None:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for attempt in range(max(attempts, 1)):
        try:
            with socket.create_connection((host, port), timeout=timeout_seconds):
                return True
        except Exception:
            pass
        if attempt + 1 < max(attempts, 1):
            time.sleep(attempt_delay_seconds)
    return False


def ensure_llm_router(log_path: Path, health_state: dict[str, int | float], proxy_base_url: str) -> None:
    proxy_ok = tmux_has_session(f"{ROUTER_TMUX_PREFIX}-proxy")
    web_ok = tmux_has_session(f"{ROUTER_TMUX_PREFIX}-web")
    api_ok = router_api_healthy()
    proxy_base_ok = proxy_base_healthy(proxy_base_url)
    if proxy_ok and web_ok and proxy_base_ok:
        health_state["consecutive_unhealthy"] = 0
        return

    consecutive_unhealthy = int(health_state.get("consecutive_unhealthy", 0)) + 1
    health_state["consecutive_unhealthy"] = consecutive_unhealthy
    restart_threshold = 3
    cooldown_seconds = 180
    last_restart_monotonic = float(health_state.get("last_restart_monotonic", 0.0))
    now_monotonic = time.monotonic()

    if consecutive_unhealthy < restart_threshold:
        append_log(
            log_path,
            (
                "llm_router unhealthy "
                f"(proxy={proxy_ok}, web={web_ok}, proxy_base={proxy_base_ok}, api={api_ok}); "
                f"waiting for threshold {consecutive_unhealthy}/{restart_threshold}"
            ),
        )
        return
    if now_monotonic - last_restart_monotonic < cooldown_seconds:
        append_log(
            log_path,
            (
                "llm_router still unhealthy but restart is cooling down "
                f"(proxy={proxy_ok}, web={web_ok}, proxy_base={proxy_base_ok}, api={api_ok})"
            ),
        )
        return

    append_log(
        log_path,
        f"llm_router unhealthy (proxy={proxy_ok}, web={web_ok}, proxy_base={proxy_base_ok}, api={api_ok}); restarting stack",
    )
    subprocess.run(
        [
            "bash",
            "-lc",
            (
                "SESSION_PREFIX=sss-auto-llm-router "
                "ANTHROPIC_UPSTREAM_URL=https://api.minimaxi.com/anthropic "
                "OPENAI_UPSTREAM_URL=https://api.minimaxi.com/v1 "
                f"bash {shell_quote(LLM_ROUTER_ROOT / 'scripts' / 'start-prod.sh')}"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
    )
    health_state["last_restart_monotonic"] = now_monotonic
    health_state["consecutive_unhealthy"] = 0


def monitor_done(run_root: Path) -> bool:
    state = read_json(run_root / "monitor_status.json", {})
    total_instances = int(state.get("total_instances", 48) or 48)
    return bool(state.get("done")) and actual_report_count(run_root) >= total_instances


def router_worker_stalled(run_root: Path, stall_timeout_seconds: int) -> tuple[bool, str | None]:
    state = read_json(run_root / "monitor_status.json", {})
    active_count = int(state.get("active_count", 0) or 0)
    latest_router_activity_ms = state.get("latest_router_activity_ms")
    latest_global_router_activity_ms = state.get("latest_global_router_activity_ms")
    if active_count <= 0:
        return False, None

    candidate_ms = []
    for value in (latest_router_activity_ms, latest_global_router_activity_ms):
        try:
            if value:
                candidate_ms.append(int(value))
        except Exception:
            continue
    if not candidate_ms:
        return False, None

    effective_activity_ms = max(candidate_ms)
    effective_activity_label = state.get("latest_router_activity")
    if latest_global_router_activity_ms and effective_activity_ms == int(latest_global_router_activity_ms):
        effective_activity_label = state.get("latest_global_router_activity")
    age_seconds = max(0, int(time.time() - (effective_activity_ms / 1000)))
    if age_seconds < stall_timeout_seconds:
        return False, None

    return True, (
        f"active_count={active_count} "
        f"latest_router_activity={effective_activity_label} "
        f"age_seconds={age_seconds}"
    )


def ensure_eval(run_root: Path, log_path: Path, max_concurrency: int) -> None:
    if tmux_has_session(EVAL_SESSION):
        return
    report_count = actual_report_count(run_root)
    append_log(log_path, f"eval session missing; restarting (report_count={report_count})")
    command = (
        f"{shell_python_env_prefix()}"
        f"{shell_join(['python3', '-u', 'run_official48_eval_worker.py', run_root, max_concurrency, '--retry-missing-report'])} "
        f"2>&1 | tee -a {shell_quote(run_root / 'eval_worker.log')}"
    )
    start_tmux_session(
        EVAL_SESSION,
        repo_shell(command),
    )


def ensure_monitor(run_root: Path, log_path: Path) -> None:
    if tmux_has_session(MONITOR_SESSION):
        return
    append_log(log_path, "monitor session missing; restarting")
    command = (
        f"{shell_join(['python3', '-u', 'monitor_official48_run.py', run_root])} "
        f"2>&1 | tee -a {shell_quote(run_root / 'monitor.log')}"
    )
    start_tmux_session(
        MONITOR_SESSION,
        repo_shell(command),
    )


def ensure_progress(run_root: Path, progress_md: Path, log_path: Path) -> None:
    if tmux_has_session(PROGRESS_SESSION):
        return
    append_log(log_path, "progress session missing; restarting")
    command = shell_join(
        [
            "python3",
            "-u",
            "record_official48_progress.py",
            run_root,
            progress_md,
            "--interval-seconds",
            1800,
        ]
    )
    start_tmux_session(
        PROGRESS_SESSION,
        repo_shell(command),
    )


def ensure_router_worker(
    run_root: Path,
    log_path: Path,
    inference_concurrency: int,
    max_turns: int | None,
    cli_timeout_seconds: int,
    router_ready_timeout_seconds: int,
    router_stall_timeout_seconds: int,
    cli_bin: str,
    settings_file: str,
    env_file: str,
    model_name: str,
    agent_name: str,
) -> None:
    if tmux_has_session(ROUTER_SESSION):
        stalled, reason = router_worker_stalled(run_root, router_stall_timeout_seconds)
        if not stalled:
            return
        append_log(log_path, f"router inference session appears stalled; restarting ({reason})")
        kill_tmux_session(ROUTER_SESSION)
    monitor_state = read_json(run_root / "monitor_status.json", {})
    total_instances = int(monitor_state.get("total_instances", 48) or 48)
    if int(monitor_state.get("inference_done", 0)) >= total_instances:
        return
    append_log(log_path, "router inference session missing; restarting with --resume")
    max_turns_args = shell_join(["--max-turns", max_turns]) + " " if max_turns is not None else ""
    command = (
        f"{shell_python_env_prefix()}"
        f"{shell_join(['python3', '-u', 'run_innercc_infer_official48.py'])} "
        f"{shell_join(['--output-dir', run_root / 'infer'])} "
        f"{shell_join(['--instances-dir', REPO_ROOT / 'output_final'])} "
        f"{shell_join(['--cli-bin', cli_bin])} "
        f"{shell_join(['--settings-file', settings_file])} "
        f"{shell_join(['--env-file', env_file])} "
        f"{shell_join(['--model', model_name])} "
        f"{shell_join(['--agent-name', agent_name])} "
        f"{shell_join(['--resume', '--max-concurrency', inference_concurrency])} "
        f"{max_turns_args}"
        f"{shell_join(['--cli-timeout-seconds', cli_timeout_seconds])} "
        f"{shell_join(['--router-ready-timeout-seconds', router_ready_timeout_seconds])} "
        f"2>&1 | tee -a {shell_quote(REPO_ROOT / 'official48_runs' / 'current_router.log')}"
    )
    start_tmux_session(
        ROUTER_SESSION,
        repo_shell(command),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root")
    parser.add_argument("--progress-md", default=str(REPO_ROOT / "progress.md"))
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--inference-concurrency", type=int, default=2)
    parser.add_argument("--eval-max-concurrency", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--cli-timeout-seconds", type=int, default=5400)
    parser.add_argument("--router-ready-timeout-seconds", type=int, default=120)
    parser.add_argument("--router-stall-timeout-seconds", type=int, default=1800)
    parser.add_argument("--cli-bin", default=str(default_cli_bin_path()))
    parser.add_argument("--settings-file", default=str(default_settings_path()))
    parser.add_argument("--env-file", default=str(default_env_file()))
    parser.add_argument("--model", default=default_model_name())
    parser.add_argument("--agent-name", default="innercc-cli")
    args = parser.parse_args()
    if args.inference_concurrency < 1:
        raise SystemExit("--inference-concurrency must be >= 1")
    if args.eval_max_concurrency < 1:
        raise SystemExit("--eval-max-concurrency must be >= 1")
    if args.max_turns is not None and args.max_turns < 1:
        raise SystemExit("--max-turns must be >= 1")

    run_root = Path(args.run_root).resolve()
    progress_md = Path(args.progress_md).resolve()
    settings_file = Path(args.settings_file).resolve()
    env_file = Path(args.env_file).resolve()
    proxy_base_url = load_router_proxy_base_url(settings_file, env_file)
    if not proxy_base_url:
        raise RuntimeError("router proxy base url is missing")
    supervisor_log = run_root / "supervisor.log"
    append_log(supervisor_log, f"supervisor started for {run_root}")
    router_health_state = {
        "consecutive_unhealthy": 0,
        "last_restart_monotonic": 0.0,
    }

    while True:
        ensure_llm_router(supervisor_log, router_health_state, proxy_base_url)
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
            args.max_turns,
            args.cli_timeout_seconds,
            args.router_ready_timeout_seconds,
            args.router_stall_timeout_seconds,
            args.cli_bin,
            args.settings_file,
            args.env_file,
            args.model,
            args.agent_name,
        )
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
