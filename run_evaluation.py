#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "configs.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def runtime_path(*parts: str) -> Path:
    cfg = load_config()
    return REPO_ROOT / cfg["paths"]["runtime_dir"] / Path(*parts)


def webui_path(*parts: str) -> Path:
    cfg = load_config()
    return REPO_ROOT / cfg["paths"]["webui_dir"] / Path(*parts)


def resolve_cli_bin_path(value: str) -> str:
    candidate = Path(os.path.expanduser(value))
    if candidate.is_absolute():
        return str(candidate)
    return str((REPO_ROOT / candidate).resolve())


def run_cmd(cmd: list[str], *, cwd: Path | None = None) -> int:
    completed = subprocess.run(cmd, cwd=cwd or REPO_ROOT)
    return completed.returncode


def background_cmd(command: str, session_name: str) -> int:
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, command], check=True)
    print(json.dumps({"background": True, "session_name": session_name}, ensure_ascii=False))
    return 0


def cmd_bootstrap(_: argparse.Namespace) -> int:
    return run_cmd(["bash", str(runtime_path("bootstrap_env.sh"))])


def cmd_dashboard(args: argparse.Namespace) -> int:
    script = "dashboard:dev" if args.mode == "dev" else "dashboard:start"
    if args.background:
        session_name = args.session_name or f"dashboard-{args.mode}-{int(time.time())}"
        command = f"cd {webui_path()} && npm run {script}"
        return background_cmd(command, session_name)
    return run_cmd(["npm", "run", script], cwd=webui_path())


def cmd_show_config(_: argparse.Namespace) -> int:
    print(json.dumps(load_config(), ensure_ascii=False, indent=2))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config()
    defaults = cfg["defaults"]
    agent_cfg = cfg["agents"].get(args.cli or defaults["cli"], {})
    mode_name = args.mode or defaults.get("mode", "direct")
    mode_cfg = cfg["modes"][mode_name]
    cmd = [
        "bash",
        str(REPO_ROOT / mode_cfg["pipeline_script"]),
        "--cli",
        args.cli or defaults["cli"],
        "--manifest",
        args.manifest or cfg["paths"]["subset_manifest"],
        "--infer-max-concurrency",
        str(args.infer_max_concurrency or defaults["infer_max_concurrency"]),
        "--eval-max-concurrency",
        str(args.eval_max_concurrency or defaults["eval_max_concurrency"]),
        "--cli-timeout-seconds",
        str(args.cli_timeout_seconds or defaults["cli_timeout_seconds"]),
    ]
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if args.max_turns:
        cmd.extend(["--max-turns", str(args.max_turns)])
    model = args.model or agent_cfg.get("model") or defaults["model"]
    if model:
        cmd.extend(["--model", model])
    cli_bin = args.cli_bin or agent_cfg.get("cli_bin", "")
    if cli_bin:
        cmd.extend(["--cli-bin", resolve_cli_bin_path(cli_bin)])
    env_file = args.env_file or agent_cfg.get("env_file", "")
    if env_file:
        cmd.extend(["--env-file", str(Path(os.path.expanduser(env_file)))])
    settings_file = args.settings_file or mode_cfg.get("settings_file", "")
    if settings_file:
        cmd.extend(["--settings-file", str(Path(os.path.expanduser(settings_file)))])
    router_root = args.router_root or mode_cfg.get("router_root", "")
    if router_root:
        cmd.extend(["--router-root", str(Path(os.path.expanduser(router_root)))])
    router_api_base = args.router_api_base or mode_cfg.get("router_api_base", "")
    if router_api_base:
        cmd.extend(["--router-api-base", router_api_base])
    if args.resume:
        cmd.append("--resume")
    if args.no_force_workspace:
        cmd.append("--no-force-workspace")
    if args.dry_run:
        print(json.dumps({"command": cmd, "mode": mode_name}, ensure_ascii=False, indent=2))
        return 0
    if args.background:
        session_name = args.session_name or f"{mode_name}-{args.cli or defaults['cli']}-{int(time.time())}"
        command = " ".join(subprocess.list2cmdline([part]) for part in cmd)
        command = f"cd {REPO_ROOT} && {command}"
        return background_cmd(command, session_name)
    return run_cmd(cmd)


def cmd_summarize(args: argparse.Namespace) -> int:
    return run_cmd(
        [
            sys.executable,
            str(runtime_path("summarize_official48_run.py")),
            "--run-root",
            args.run_root,
            "--repo-root",
            str(REPO_ROOT),
            "--instances-dir",
            args.instances_dir,
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified entrypoint for SWE-EVO subset runs")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap")
    bootstrap.set_defaults(func=cmd_bootstrap)

    dashboard = subparsers.add_parser("dashboard")
    dashboard.add_argument("mode", choices=["dev", "start"])
    dashboard.add_argument("--background", action="store_true")
    dashboard.add_argument("--session-name", default="")
    dashboard.set_defaults(func=cmd_dashboard)

    show_config = subparsers.add_parser("show-config")
    show_config.set_defaults(func=cmd_show_config)

    run = subparsers.add_parser("run")
    run.add_argument("--cli", choices=["innercc", "claude"], default="")
    run.add_argument("--mode", choices=["direct", "router"], default="")
    run.add_argument("--manifest", default="")
    run.add_argument("--limit", type=int, default=0)
    run.add_argument("--max-turns", type=int, default=0)
    run.add_argument("--infer-max-concurrency", type=int, default=0)
    run.add_argument("--eval-max-concurrency", type=int, default=0)
    run.add_argument("--cli-timeout-seconds", type=int, default=0)
    run.add_argument("--model", default="")
    run.add_argument("--cli-bin", default="")
    run.add_argument("--env-file", default="")
    run.add_argument("--settings-file", default="")
    run.add_argument("--router-root", default="")
    run.add_argument("--router-api-base", default="")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--no-force-workspace", action="store_true")
    run.add_argument("--background", action="store_true")
    run.add_argument("--session-name", default="")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=cmd_run)

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--run-root", required=True)
    summarize.add_argument("--instances-dir", required=True)
    summarize.set_defaults(func=cmd_summarize)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
