from pathlib import Path
from tqdm import tqdm
import json
import docker, json, pathlib
import argparse
import numpy as np

from docker.errors import ImageNotFound, APIError
from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
from swebench.harness.constants import KEY_INSTANCE_ID, KEY_MODEL, KEY_PREDICTION, LOG_INSTANCE, RUN_EVALUATION_LOG_DIR
from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
from swebench.harness.grading import get_logs_eval, TestStatus, get_eval_report
from swebench.harness.test_spec.test_spec import make_test_spec, TestSpec, get_test_specs_from_dataset
from swebench.harness.run_evaluation import build_env_images, run_instances

parser = argparse.ArgumentParser(description="Read CLI input")
parser.add_argument("--instance", type=str, default='...', help="xxx")
parser.add_argument("--scaffold", type=str, default='OpenHands', help='Your Scaffold: Please choose scaffold in ["OpenHands", "SWE-agent"]')
parser.add_argument("--max_workers", type=int, default='4', help="xxx")
parser.add_argument("--run_name", type=str, default='kimi-k2-instruct_maxiter_100_N_v0.58.0-no-hint-run_1', help="xxx")

args = parser.parse_args()

def merge_patches(code_patch: str, test_patch: str, order: str = "test_then_code") -> str:
    """
    return an only unified-diff which are merged from test_patch and code_patch.
    order: "test_then_code" (default) or "code_then_test".
    """
    def clean(x: str) -> str:
        if not x:
            return ""
        x = x.replace("\r\n", "\n").replace("\r", "\n")
        if not x.endswith("\n"):
            x += "\n"
        return x

    cp = clean(code_patch)
    tp = clean(test_patch)

    parts = []
    if order == "test_then_code":
        if tp: parts.append(tp)
        if cp: parts.append(cp)
    else:
        if cp: parts.append(cp)
        if tp: parts.append(tp)

    return ("\n".join(p.rstrip("\n") for p in parts if p) + "\n") if parts else ""

def pull_and_retag_instance_images(client, instances, target_tag="latest"):
    test_specs = get_test_specs_from_dataset(instances)
    for id, ins in enumerate(instances):
        src_ref = ins["image"]               
        iid     = ins["instance_id"]         
        dst_repo = f"sweb.eval.x86_64.{iid}" 
        dst_ref  = f"{dst_repo}:{target_tag}"
        dst_repo_2 = test_specs[id].env_image_key
        dst_ref_2 = f"{dst_repo_2}"
        try:
            client.images.get(dst_ref)
            client.images.get(dst_ref_2)
            print(f"[skip] already present: {dst_ref} and {dst_ref_2}")
            continue
        except:
            pass
        print(f"[pull] {src_ref}")
        img = client.images.pull(src_ref)    
        print(f"[tag p1] {src_ref}  ->  {dst_ref}")
        client.api.tag(image=img.id, repository=dst_repo, tag=target_tag)
        print(f"[tag p2] {src_ref}  ->  {dst_ref_2}")
        client.api.tag(image=img.id, repository=dst_repo_2)
    print("[ok] retag all instance images done.")

if __name__ =="__main__":
    if args.scaffold == 'OpenHands':
        in_path  = f"/mnt/data/swe_world_2/OpenHands/evaluation/evaluation_outputs/outputs/__mnt__data__swe_world_2__SWE-EVO-dev__hf_out__hf_jsonl-test/CodeActAgent/{args.run_name}/output.jsonl" 
    elif args.scaffold == 'SWE-agent':
        in_path = f"/mnt/data/swe_world_2/SWE-agent/trajectories/{args.run_name}/preds.json"
    else:
        print(f'Our current code do not support for your {args.scaffold}, please use scaffold in ["OpenHands", "SWE-agent"]')
        exit()
    root_path = "/mnt/data/swe_world_2/SWE-EVO-dev/output_v9"
    root = Path(root_path)
    files = list(root.glob("*.json"))
    print(f'[Len] = {len(files)}')
    instances = []
    count = 0
    for p in tqdm(files, desc='Loading data ...', total=len(files)):
        if args.instance != '...':
            if p != Path(f"/mnt/data/swe_world_2/SWE-EVO-dev/output_v9/{args.instance}.json"): 
                continue
        d = json.loads(p.read_text())
        current_version = d.get("end_version") or d.get("version")
        true_version = current_version
        specs_by_ver = MAP_REPO_VERSION_TO_SPECS.get(d["repo"], {}) 
        found = False
        for ver_harness in specs_by_ver.keys(): 
            if ver_harness in current_version: 
                true_version = ver_harness
                found = True
        if found == False:
            print(f'Cannot find true version in current rule based !!! Exit with current_version = {current_version} and total_keys = {specs_by_ver.keys()}')
            exit()

        test_cmd = MAP_REPO_VERSION_TO_SPECS[d["repo"]][true_version]["test_cmd"]
        log_parser = MAP_REPO_TO_PARSER[d["repo"]]
        # print(f'[log_parser.__name__] = {log_parser.__name__} with repo = {d["repo"]} and [test_cmd] = {test_cmd} and [version] = {true_version}')
        flag = False
        if args.scaffold == 'OpenHands':
            with open(in_path, "r", encoding="utf-8") as fi:
                for id, line in enumerate(fi):
                    if not line.strip(): 
                        continue
                    obj = json.loads(line)
                    # print(f'[obj["instance_id"]] = {obj["instance_id"]} and d["instance_id"] = {d["instance_id"]:}')
                    if obj["instance_id"] == d["instance_id"]:
                        # print(f'with instance_id = {obj["instance_id"]}: [Key = {obj['test_result'].keys()}]')
                        if obj['test_result'] == {}:
                            continue
                        d["patch"] = obj["test_result"]["git_patch"]
                        flag = True
        elif args.scaffold == 'SWE-agent':
            with open(in_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if d["instance_id"] in data.keys():
                    d["patch"] = data[d["instance_id"]]["model_patch"]
                    flag = True

        if flag == False:
            print(f'Cannot find trajectories for instance {d["instance_id"]}!!!')
            continue
            # exit()
        instances.append(d)    
        instances[count]["version"] = true_version
        instances[count]["test_cmds"] = test_cmd
        # print(f'[test_cmd] = {instances[count]["test_cmds"]}')
        instances[count]["log_parser"] = log_parser.__name__

        instances[count]["all_patch"] = merge_patches(
            instances[count]["patch"],
            instances[count]["test_patch"],
            order="test_then_code",  # or "code_then_test"
        )
        instances[count]["code_patch"] = instances[count]["patch"]
        count += 1


    #########################################################################
    # Run instance for gold_patch

    # print(f'[KEY_MODEL] = {KEY_MODEL}')
    # print(f'[KEY_PREDICTION] = {KEY_PREDICTION}')
    # print(f'[KEY_INSTANCE_ID] = {KEY_INSTANCE_ID}')

    predictions = {}
    for inst in instances:
        # print(f'inst["instance_id"] = {inst["instance_id"]}')
        predictions[inst["instance_id"]] = {
            KEY_MODEL: args.run_name,        
            KEY_PREDICTION: inst["all_patch"],   # before: inst["patch"]
            KEY_INSTANCE_ID: inst["instance_id"]
        }

    run_id = args.run_name
    cache_level = "env"      # none|base|env|instance
    clean = True
    force_rebuild = False
    max_workers = args.max_workers
    timeout = 1800
    namespace = None
    instance_image_tag = "latest"
    rewrite_reports = False
    client = docker.from_env()

    pull_and_retag_instance_images(client, instances, target_tag=instance_image_tag)

    if namespace is None and not rewrite_reports:
        build_env_images(client, instances, force_rebuild, max_workers)

    run_instances(
        predictions,
        instances,
        cache_level,
        clean,
        force_rebuild,
        max_workers,
        run_id,
        timeout,
        namespace=namespace,
        instance_image_tag=instance_image_tag,
        rewrite_reports=rewrite_reports,
    )

    print(f"Logs & reports in: {RUN_EVALUATION_LOG_DIR}")

    # #########################################################################

    log_root = Path(RUN_EVALUATION_LOG_DIR) / run_id
    success = failure = total = 0
    resolved = applied = submitted = 0
    true_success_rate = []
    for id, inst in enumerate(instances):  
        inst_id = inst["instance_id"]
        spec = make_test_spec(inst, namespace=None)
        log_fp = log_root / run_id / inst_id / "test_output.txt"  

        pred = {
            KEY_INSTANCE_ID: inst_id,
            KEY_MODEL: args.run_name,
            KEY_PREDICTION: predictions[inst_id][KEY_PREDICTION], 
        }

        report = get_eval_report(spec, pred, str(log_fp), include_tests_status=True)
        r = report[inst_id]
        if r["patch_exists"]:
            submitted += 1
            if r["patch_successfully_applied"]:
                applied += 1
            if r["resolved"]:
                resolved += 1
            if "tests_status" in r.keys():
                bonus_success = len(r["tests_status"]["FAIL_TO_PASS"]["success"])
                bonus_failure = len(r["tests_status"]["FAIL_TO_PASS"]["failure"])
                total += bonus_success + bonus_failure
                print(f'[id] {id} bonus_success = {bonus_success} and bonus_failure = {bonus_failure}')
                print(f'[bonus_success] = {bonus_success} and [bonus_failure] = {bonus_failure}')
                if len(r["tests_status"]["PASS_TO_PASS"]["failure"]) == 0:
                    success += bonus_success
                    true_success_rate.append(bonus_success / (bonus_success+bonus_failure))
                else:
                    true_success_rate.append(0)
                failure += bonus_failure

    print(f'[Success] = {success} and [total] = {total} => [Pass rate] = {success/(failure+success):.3%}  [{success}/{(failure+success)}]')
    print(f'[True success rate] = {np.mean(np.array(true_success_rate)):.2%}')
    print(f"[Resolved rate] = {resolved/submitted:.3%}  [{resolved}/{submitted}]")
    print(f"[Applied rate] = {applied/submitted:.3%}  [{applied}/{submitted}]")
