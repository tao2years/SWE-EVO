#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLI_CANDIDATES = [
    Path(os.environ["INNERCC_CLI_BIN"]) if os.environ.get("INNERCC_CLI_BIN") else None,
    Path("/home/wt/repo/innerCC/cli"),
    Path("/home/wt/sss_repos/innerCC/cli"),
]
DEFAULT_SETTINGS_PATH = Path(os.environ.get("INNERCC_SETTINGS_PATH", "/home/wt/.claude/settings.json"))
DEFAULT_ENV_PATH = Path(os.environ.get("INNERCC_ENV_FILE", "/home/wt/.config/swe-evo/minimax.env"))
DEFAULT_MODEL = os.environ.get("INNERCC_MODEL", "MiniMax-M2.5-highspeed")
DEFAULT_AGENT_NAME = os.environ.get("INNERCC_AGENT_NAME", "innercc-cli")
DEFAULT_MAX_WORKERS = int(os.environ.get("INNERCC_MAX_WORKERS", "1"))


def run(cmd, *, cwd=None, env=None, check=True, capture_output=False, text=True):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=check,
        capture_output=capture_output,
        text=text,
    )


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'").strip('"')
        env[key.strip()] = value
    return env


def load_settings_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    env = payload.get("env")
    if not isinstance(env, dict):
        return {}
    return {str(key): str(value) for key, value in env.items()}


def commit_exists(repo_dir: Path, commit: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", f"{commit}^{{commit}}"],
        cwd=repo_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def resolve_first_existing(paths: list[Path | None]) -> Path:
    for path in paths:
        if path and path.is_file():
            return path
    checked = ", ".join(str(path) for path in paths if path)
    raise FileNotFoundError(f"Unable to find required file from candidates: {checked}")


def extract_last_json_line(stdout: str) -> dict | None:
    for line in reversed(stdout.splitlines()):
        payload = line.strip()
        if not payload:
            continue
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            continue
    return None


def extract_cli_json(stdout: str) -> dict | None:
    payload = stdout.strip()
    if payload:
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return extract_last_json_line(stdout)


def coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def is_claude_cli(cli_bin: Path) -> bool:
    return cli_bin.name == "claude"


def prepare_workspace(instance: dict, workspace_dir: Path, force: bool) -> None:
    repo_name = instance["repo"]
    base_commit = instance["base_commit"]
    repo_url = f"https://github.com/{repo_name}.git"
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
        run(["git", "remote", "set-url", "origin", repo_url], cwd=workspace_dir)
        run(["git", "config", "user.email", "benchmark@example.com"], cwd=workspace_dir)
        run(["git", "config", "user.name", "benchmark"], cwd=workspace_dir)
        return

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
    run(["git", "config", "user.email", "benchmark@example.com"], cwd=workspace_dir)
    run(["git", "config", "user.name", "benchmark"], cwd=workspace_dir)


def build_prompt(instance: dict) -> str:
    f2p = instance["FAIL_TO_PASS"]
    test_list = "\n".join(f"- {t}" for t in f2p)
    return f"""You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: {instance["instance_id"]}

Release note / requirement:
{instance["problem_statement"]}

Expected failing tests that should pass after your fix:
{test_list}

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
"""


def run_cli(
    instance: dict,
    workspace_dir: Path,
    run_dir: Path,
    cli_bin: Path,
    settings_path: Path,
    env_path: Path,
    model_name: str,
    max_turns: int,
    timeout_seconds: int | None = None,
) -> tuple[Path, int]:
    env = os.environ.copy()
    env.update(load_env_file(env_path))
    env.update(load_settings_env(settings_path))
    if env.get("OPENAI_API_KEY") and not env.get("ANTHROPIC_API_KEY"):
        env["ANTHROPIC_API_KEY"] = env["OPENAI_API_KEY"]

    prompt = build_prompt(instance)
    raw_stdout_path = run_dir / "cli_stdout.log"
    result_path = run_dir / "cli_result.json"
    if is_claude_cli(cli_bin):
        cmd = [
            str(cli_bin),
            "-p",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
            "--settings",
            str(settings_path),
            "--model",
            model_name,
            prompt,
        ]
        use_stdin_prompt = False
    else:
        cmd = [
            str(cli_bin),
            "--bare",
            "-p",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
            "--settings",
            str(settings_path),
            "--model",
            model_name,
        ]
        if max_turns is not None:
            cmd.extend(["--max-turns", str(max_turns)])
        use_stdin_prompt = True

    proc = subprocess.Popen(
        cmd,
        cwd=workspace_dir,
        env=env,
        stdin=subprocess.PIPE if use_stdin_prompt else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(prompt if use_stdin_prompt else None, timeout=timeout_seconds)
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
        timeout_note = f"\n[timeout] innerCC CLI exceeded {timeout_seconds} seconds and was terminated.\n"
        stdout = coerce_text(exc.stdout) + coerce_text(stdout)
        stderr = coerce_text(exc.stderr) + coerce_text(stderr) + timeout_note
        returncode = 124

    raw_stdout_path.write_text(stdout, encoding="utf-8")
    parsed_payload = extract_cli_json(stdout)
    if parsed_payload is None:
        result_path.write_text(stdout, encoding="utf-8")
    else:
        result_path.write_text(json.dumps(parsed_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "cli_stderr.log").write_text(stderr, encoding="utf-8")
    (run_dir / "cli_exit_code.txt").write_text(str(returncode), encoding="utf-8")
    return result_path, returncode


def write_patch_outputs(instance_id: str, workspace_dir: Path, run_dir: Path, agent_name: str) -> Path:
    diff = run(
        ["git", "-c", "core.fileMode=false", "diff"],
        cwd=workspace_dir,
        capture_output=True,
    ).stdout

    patch_path = run_dir / "patch.diff"
    patch_path.write_text(diff, encoding="utf-8")

    preds = {
        instance_id: {
            "model_name_or_path": agent_name,
            "instance_id": instance_id,
            "model_patch": diff,
        }
    }
    preds_path = run_dir / "preds.json"
    preds_path.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")
    return preds_path


def merge_patches(code_patch: str, test_patch: str) -> str:
    def clean(text: str) -> str:
        if not text:
            return ""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not text.endswith("\n"):
            text += "\n"
        return text

    cp = clean(code_patch)
    tp = clean(test_patch)
    parts = []
    if tp:
        parts.append(tp)
    if cp:
        parts.append(cp)
    return ("\n".join(p.rstrip("\n") for p in parts if p) + "\n") if parts else ""


def build_local_instance_image(instance: dict, workspace_dir: Path, case_root: Path, client) -> None:
    from swebench.harness.constants import INSTANCE_IMAGE_BUILD_DIR
    from swebench.harness.docker_build import build_image
    from swebench.harness.test_spec.test_spec import make_test_spec

    test_spec = make_test_spec(instance, namespace=None, instance_image_tag="latest")
    build_dir = case_root / INSTANCE_IMAGE_BUILD_DIR / test_spec.instance_image_key.replace(":", "__")
    repo_bundle_dir = build_dir / "repo"
    dockerfile = test_spec.instance_dockerfile
    marker = "COPY ./setup_repo.sh /root/\n"
    if marker not in dockerfile:
        raise RuntimeError("Unsupported instance dockerfile layout for local repo injection")
    dockerfile = dockerfile.replace(marker, "COPY ./repo /testbed\nCOPY ./setup_repo.sh /root/\n", 1)

    local_repo_source = workspace_dir.parent / instance["repo"].split("/")[-1]
    if not (local_repo_source / ".git").exists():
        local_repo_source = workspace_dir

    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", str(local_repo_source), repo_bundle_dir.name], cwd=build_dir)

    setup_lines = [
        line
        for line in test_spec.repo_script_list
        if not line.startswith("git clone -o origin ")
    ]
    setup_repo_script = "\n".join(["#!/bin/bash", "set -euxo pipefail", *setup_lines]) + "\n"

    build_image(
        image_name=test_spec.instance_image_key,
        setup_scripts={"setup_repo.sh": setup_repo_script},
        dockerfile=dockerfile,
        platform=test_spec.platform,
        client=client,
        build_dir=build_dir,
        nocache=False,
    )


def run_local_evaluation(
    instance: dict,
    workspace_dir: Path,
    run_dir: Path,
    case_root: Path,
    eval_run_id: str,
    agent_name: str,
    max_workers: int,
) -> Path:
    os.chdir(case_root)
    sys.path.insert(0, str(REPO_ROOT / ".deps"))
    sys.path.insert(0, str(REPO_ROOT / "SWE-bench"))

    import docker
    from swebench.harness.constants import KEY_INSTANCE_ID, KEY_MODEL, KEY_PREDICTION, MAP_REPO_VERSION_TO_SPECS
    from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
    from swebench.harness.run_evaluation import build_env_images, run_instances

    current_version = instance.get("end_version") or instance.get("version")
    true_version = current_version
    specs_by_ver = MAP_REPO_VERSION_TO_SPECS.get(instance["repo"], {})
    for ver_harness in specs_by_ver.keys():
        if ver_harness in current_version:
            true_version = ver_harness
            break
    else:
        raise RuntimeError(f"Cannot map version {current_version} for repo {instance['repo']}")

    preds = json.loads((run_dir / "preds.json").read_text(encoding="utf-8"))
    model_patch = preds[instance["instance_id"]]["model_patch"]

    eval_instance = dict(instance)
    eval_instance["version"] = true_version
    eval_instance["test_cmds"] = MAP_REPO_VERSION_TO_SPECS[instance["repo"]][true_version]["test_cmd"]
    eval_instance["log_parser"] = MAP_REPO_TO_PARSER[instance["repo"]].__name__
    eval_instance["all_patch"] = merge_patches(model_patch, instance["test_patch"])

    predictions = {
        eval_instance["instance_id"]: {
            KEY_MODEL: agent_name,
            KEY_PREDICTION: eval_instance["all_patch"],
            KEY_INSTANCE_ID: eval_instance["instance_id"],
        }
    }

    client = docker.from_env()
    build_env_images(client, [eval_instance], force_rebuild=False, max_workers=max_workers)
    build_local_instance_image(eval_instance, workspace_dir, case_root, client)
    run_instances(
        predictions=predictions,
        instances=[eval_instance],
        cache_level="env",
        clean=True,
        force_rebuild=False,
        max_workers=max_workers,
        run_id=eval_run_id,
        timeout=1800,
        namespace=None,
        instance_image_tag="latest",
        rewrite_reports=False,
    )

    return (
        case_root
        / "logs"
        / "run_evaluation"
        / eval_run_id
        / agent_name
        / eval_instance["instance_id"]
        / "report.json"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--case-root", default=str(REPO_ROOT / "custom_cli_case"))
    parser.add_argument("--cli-bin", default=None)
    parser.add_argument("--settings-file", default=str(DEFAULT_SETTINGS_PATH))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--agent-name", default=DEFAULT_AGENT_NAME)
    parser.add_argument("--eval-run-id", default=None)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--force-workspace", action="store_true")
    args = parser.parse_args()

    case_root = Path(args.case_root)
    cli_bin = Path(args.cli_bin) if args.cli_bin else resolve_first_existing(DEFAULT_CLI_CANDIDATES)
    settings_path = Path(args.settings_file)
    env_path = Path(args.env_file)
    eval_run_id = args.eval_run_id or args.instance_id

    if not cli_bin.exists():
        raise FileNotFoundError(cli_bin)
    if not settings_path.exists():
        raise FileNotFoundError(settings_path)
    if not env_path.exists():
        raise FileNotFoundError(env_path)

    instance_path = case_root / "output_final" / f"{args.instance_id}.json"
    if not instance_path.exists():
        raise FileNotFoundError(instance_path)

    instance = json.loads(instance_path.read_text(encoding="utf-8"))
    workspace_dir = case_root / "workspace" / args.instance_id
    run_dir = case_root / "run" / args.instance_id
    run_dir.mkdir(parents=True, exist_ok=True)

    prepare_workspace(instance, workspace_dir, args.force_workspace)
    cli_result, cli_returncode = run_cli(
        instance,
        workspace_dir,
        run_dir,
        cli_bin,
        settings_path,
        env_path,
        args.model,
        args.max_turns,
    )
    preds_path = write_patch_outputs(args.instance_id, workspace_dir, run_dir, args.agent_name)
    report_path = run_local_evaluation(
        instance,
        workspace_dir,
        run_dir,
        case_root,
        eval_run_id,
        args.agent_name,
        args.max_workers,
    )

    summary = {
        "instance_id": args.instance_id,
        "agent_name": args.agent_name,
        "eval_run_id": eval_run_id,
        "cli_bin": str(cli_bin),
        "max_turns": args.max_turns,
        "max_workers": args.max_workers,
        "workspace_dir": str(workspace_dir),
        "cli_result": str(cli_result),
        "cli_returncode": cli_returncode,
        "preds_json": str(preds_path),
        "report_json": str(report_path),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
