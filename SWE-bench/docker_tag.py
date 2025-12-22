from pathlib import Path
import json
import docker, json, pathlib
import argparse

from docker.errors import ImageNotFound, APIError
from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
from swebench.harness.constants import KEY_INSTANCE_ID, KEY_MODEL, KEY_PREDICTION, LOG_INSTANCE, RUN_EVALUATION_LOG_DIR
from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
from swebench.harness.grading import get_logs_eval, TestStatus, get_eval_report
from swebench.harness.test_spec.test_spec import make_test_spec, TestSpec, get_test_specs_from_dataset
from swebench.harness.run_evaluation import build_env_images, run_instances

parser = argparse.ArgumentParser(description="Read CLI input")
parser.add_argument("--instance", type=str, default='...', help="xxx")
parser.add_argument("--max_workers", type=int, default='4', help="xxx")
parser.add_argument("--run_name", type=str, default='kimi-k2-instruct_maxiter_100_N_v0.58.0-no-hint-run_1', help="xxx")

args = parser.parse_args()

def merge_patches(code_patch: str, test_patch: str, order: str = "test_then_code") -> str:
    """
    return an only unified-diff which are merged from test_patch and code_patch.
    order: "test_then_code" (mặc định) hoặc "code_then_test".
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

in_path  = f"../OpenHands/evaluation/evaluation_outputs/outputs/__mnt__data__swe_world_2__SWE-EVO-dev__hf_out__hf_jsonl-test/CodeActAgent/{args.run_name}/output.jsonl" 
root_path = "../output_final"
root = Path(root_path)
instances = []
count = 0
for p in root.glob("*.json"):
    if args.instance != '...':
        if p != Path(f"../output_final/{args.instance}.json"): 
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
    print(f'[log_parser.__name__] = {log_parser.__name__} with repo = {d["repo"]} and [test_cmd] = {test_cmd} and [version] = {true_version}')
    instances.append(d)    
    flag = False
    with open(in_path, "r", encoding="utf-8") as fi:
        for id, line in enumerate(fi):
            if not line.strip(): 
                continue
            obj = json.loads(line)
            # print(f'[obj["instance_id"]] = {obj["instance_id"]} and instances[count]["instance_id"] = {instances[count]["instance_id"]:}')
            if obj["instance_id"] == instances[count]["instance_id"]:
                instances[count]["patch"] = obj["test_result"]["git_patch"]
                flag = True
    if flag == False:
        print(f'Cannot find trajectories for instance {instances[count]["instance_id"]}!!!')
        exit()

    instances[count]["version"] = true_version
    instances[count]["test_cmds"] = test_cmd
    print(f'[test_cmd] = {instances[count]["test_cmds"]}')
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

print(f'[KEY_MODEL] = {KEY_MODEL}')
print(f'[KEY_PREDICTION] = {KEY_PREDICTION}')
print(f'[KEY_INSTANCE_ID] = {KEY_INSTANCE_ID}')

predictions = {}
for inst in instances:
    print(f'inst["instance_id"] = {inst["instance_id"]}')
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

