#!/usr/bin/env python3
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from swe_evo_env import REPO_ROOT, default_cli_bin_path, pythonpath_entries

SOURCE_OUTPUT_DIR = REPO_ROOT / "output_final"
BATCH_CASE_ROOT = REPO_ROOT / "innercc_batch_case"
CUSTOM_RUNNER_PATH = REPO_ROOT / "custom_cli_case" / "run_custom_cli_case.py"
DEFAULT_CLI_BIN = default_cli_bin_path()
DEFAULT_MAX_WORKERS = int(os.environ.get("INNERCC_MAX_WORKERS", "1"))


def load_custom_runner():
    spec = importlib.util.spec_from_file_location("run_custom_cli_case", CUSTOM_RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def prepare_batch_root():
    if BATCH_CASE_ROOT.exists():
        shutil.rmtree(BATCH_CASE_ROOT)
    (BATCH_CASE_ROOT / "output_final").mkdir(parents=True, exist_ok=True)
    for src in sorted(SOURCE_OUTPUT_DIR.glob("*.json")):
        shutil.copy2(src, BATCH_CASE_ROOT / "output_final" / src.name)


def compare_url_for_instance(instance: dict) -> str:
    owner, repo = instance["repo"].split("/", 1)
    return f"https://api.github.com/repos/{owner}/{repo}/compare/{instance['start_version']}...{instance['end_version']}"


def render_compare_file_diff(file_info: dict) -> str:
    status = file_info["status"]
    filename = file_info["filename"]
    prev = file_info.get("previous_filename", filename)
    patch = file_info.get("patch", "")
    lines = [f"diff --git a/{prev} b/{filename}"]
    if status == "added":
        lines.extend(["new file mode 100644", "--- /dev/null", f"+++ b/{filename}"])
    elif status == "removed":
        lines.extend(["deleted file mode 100644", f"--- a/{prev}", "+++ /dev/null"])
    elif status == "renamed":
        lines.extend([f"rename from {prev}", f"rename to {filename}", f"--- a/{prev}", f"+++ b/{filename}"])
    else:
        lines.extend([f"--- a/{prev}", f"+++ b/{filename}"])
    if patch:
        lines.append(patch)
    return "\n".join(lines) + "\n"


def rebuild_top_level_patches(instance_path: Path):
    instance = json.loads(instance_path.read_text(encoding="utf-8"))
    with urllib.request.urlopen(compare_url_for_instance(instance), timeout=60) as response:
        compare_data = json.load(response)

    code_parts: list[str] = []
    test_parts: list[str] = []
    for file_info in compare_data.get("files", []):
        rendered = render_compare_file_diff(file_info)
        if "test" in file_info["filename"].lower():
            test_parts.append(rendered)
        else:
            code_parts.append(rendered)

    instance["patch"] = "".join(code_parts)
    instance["test_patch"] = "".join(test_parts)
    instance_path.write_text(json.dumps(instance, ensure_ascii=False, indent=4), encoding="utf-8")


def import_harness():
    for extra_path in reversed(pythonpath_entries(REPO_ROOT / "SWE-bench")):
        if extra_path not in sys.path:
            sys.path.insert(0, extra_path)
    from swebench.harness.constants import KEY_INSTANCE_ID, KEY_MODEL, KEY_PREDICTION, MAP_REPO_VERSION_TO_SPECS
    from swebench.harness.grading import TestStatus, get_logs_eval
    from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
    from swebench.harness.run_evaluation import build_env_images, run_instances
    from swebench.harness.test_spec.test_spec import make_test_spec

    return {
        "KEY_INSTANCE_ID": KEY_INSTANCE_ID,
        "KEY_MODEL": KEY_MODEL,
        "KEY_PREDICTION": KEY_PREDICTION,
        "MAP_REPO_VERSION_TO_SPECS": MAP_REPO_VERSION_TO_SPECS,
        "TestStatus": TestStatus,
        "get_logs_eval": get_logs_eval,
        "MAP_REPO_TO_PARSER": MAP_REPO_TO_PARSER,
        "build_env_images": build_env_images,
        "run_instances": run_instances,
        "make_test_spec": make_test_spec,
    }


def map_true_version(instance: dict, specs_map: dict) -> str:
    current_version = instance.get("end_version") or instance.get("version")
    for ver_harness in specs_map[instance["repo"]].keys():
        if ver_harness in current_version:
            return ver_harness
    raise RuntimeError(f"Cannot map version {current_version} for repo {instance['repo']}")


def fill_f2p_p2p_locally(instance_path: Path, runner_module):
    import docker

    harness = import_harness()
    instance = json.loads(instance_path.read_text(encoding="utf-8"))
    instance_id = instance["instance_id"]
    workspace_dir = BATCH_CASE_ROOT / "workspace" / instance_id

    runner_module.prepare_workspace(instance, workspace_dir, force=True)

    true_version = map_true_version(instance, harness["MAP_REPO_VERSION_TO_SPECS"])
    eval_instance = dict(instance)
    eval_instance["version"] = true_version
    eval_instance["test_cmds"] = harness["MAP_REPO_VERSION_TO_SPECS"][instance["repo"]][true_version]["test_cmd"]
    eval_instance["log_parser"] = harness["MAP_REPO_TO_PARSER"][instance["repo"]].__name__

    post_patch = runner_module.merge_patches(instance["patch"], instance["test_patch"])
    pre_patch = instance["test_patch"]

    client = docker.from_env()
    os.chdir(BATCH_CASE_ROOT)
    harness["build_env_images"](client, [eval_instance], force_rebuild=False, max_workers=1)
    runner_module.build_local_instance_image(eval_instance, workspace_dir, BATCH_CASE_ROOT, client)

    post_run_id = f"metadata-{instance_id}-gold"
    pre_run_id = f"metadata-{instance_id}-pre"

    harness["run_instances"](
        predictions={
            instance_id: {
                harness["KEY_MODEL"]: "gold",
                harness["KEY_PREDICTION"]: post_patch,
                harness["KEY_INSTANCE_ID"]: instance_id,
            }
        },
        instances=[eval_instance],
        cache_level="instance",
        clean=True,
        force_rebuild=False,
        max_workers=1,
        run_id=post_run_id,
        timeout=1800,
        namespace=None,
        instance_image_tag="latest",
        rewrite_reports=False,
    )

    harness["run_instances"](
        predictions={
            instance_id: {
                harness["KEY_MODEL"]: "pre-empty-patch",
                harness["KEY_PREDICTION"]: pre_patch,
                harness["KEY_INSTANCE_ID"]: instance_id,
            }
        },
        instances=[eval_instance],
        cache_level="instance",
        clean=True,
        force_rebuild=False,
        max_workers=1,
        run_id=pre_run_id,
        timeout=1800,
        namespace=None,
        instance_image_tag="latest",
        rewrite_reports=False,
    )

    spec = harness["make_test_spec"](eval_instance, namespace=None)
    post_log = BATCH_CASE_ROOT / "logs" / "run_evaluation" / post_run_id / "gold" / instance_id / "test_output.txt"
    pre_log = BATCH_CASE_ROOT / "logs" / "run_evaluation" / pre_run_id / "pre-empty-patch" / instance_id / "test_output.txt"
    post_map, found_post = harness["get_logs_eval"](spec, str(post_log))
    pre_map, found_pre = harness["get_logs_eval"](spec, str(pre_log))
    if not (found_post and found_pre):
        raise RuntimeError(f"Missing F2P/P2P logs for {instance_id}")

    failed = harness["TestStatus"].FAILED.value
    errored = harness["TestStatus"].ERROR.value
    passed = harness["TestStatus"].PASSED.value
    instance["FAIL_TO_PASS"] = sorted(
        test_name for test_name, post_status in post_map.items() if post_status == passed and (pre_map.get(test_name) in (failed, errored, None))
    )
    instance["PASS_TO_PASS"] = sorted(
        test_name for test_name, pre_status in pre_map.items() if pre_status == passed and post_map.get(test_name) == passed
    )
    instance_path.write_text(json.dumps(instance, ensure_ascii=False, indent=4), encoding="utf-8")
    (SOURCE_OUTPUT_DIR / instance_path.name).write_text(json.dumps(instance, ensure_ascii=False, indent=4), encoding="utf-8")


def instance_needs_repair(instance: dict) -> bool:
    return (
        not instance.get("patch")
        or not instance.get("test_patch")
        or not isinstance(instance.get("FAIL_TO_PASS"), list)
        or not isinstance(instance.get("PASS_TO_PASS"), list)
    )


def repair_instances(runner_module):
    for instance_path in sorted((BATCH_CASE_ROOT / "output_final").glob("*.json")):
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        if not instance_needs_repair(instance):
            continue
        print(f"[repair] rebuilding metadata for {instance['instance_id']}", flush=True)
        rebuild_top_level_patches(instance_path)
        fill_f2p_p2p_locally(instance_path, runner_module)
        fixed = json.loads(instance_path.read_text(encoding="utf-8"))
        print(
            f"[repair] {fixed['instance_id']} F2P={len(fixed['FAIL_TO_PASS'])} P2P={len(fixed['PASS_TO_PASS'])}",
            flush=True,
        )


def run_batch(runner_module):
    results = []
    for instance_path in sorted((BATCH_CASE_ROOT / "output_final").glob("*.json")):
        instance_id = instance_path.stem
        run_id = f"{instance_id}-innercc-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        cmd = [
            "python3",
            str(CUSTOM_RUNNER_PATH),
            "--instance-id",
            instance_id,
            "--case-root",
            str(BATCH_CASE_ROOT),
            "--cli-bin",
            str(DEFAULT_CLI_BIN),
            "--eval-run-id",
            run_id,
            "--force-workspace",
            "--max-workers",
            str(DEFAULT_MAX_WORKERS),
        ]
        print(f"[batch] start {instance_id}", flush=True)
        completed = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
        result = {
            "instance_id": instance_id,
            "run_id": run_id,
            "returncode": completed.returncode,
            "summary_path": str(BATCH_CASE_ROOT / "run" / instance_id / "summary.json"),
        }
        results.append(result)
        print(f"[batch] done {instance_id} rc={completed.returncode}", flush=True)
    summary_path = BATCH_CASE_ROOT / "batch_summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[batch] summary written to {summary_path}", flush=True)


def main():
    if not DEFAULT_CLI_BIN.exists():
        raise FileNotFoundError(DEFAULT_CLI_BIN)
    runner_module = load_custom_runner()
    prepare_batch_root()
    repair_instances(runner_module)
    run_batch(runner_module)


if __name__ == "__main__":
    main()
