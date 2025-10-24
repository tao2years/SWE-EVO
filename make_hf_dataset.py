#!/usr/bin/env python3
# make_hf_dataset.py
import os, json, glob, argparse
from pathlib import Path

# optional: pip install datasets
from datasets import Dataset, DatasetDict

try:
    import numpy as np
except Exception:
    np = None

SRC_DIR = "/mnt/data/swe_world_2/SWE-EVO-dev/output_final"
OUT_DIR = "/mnt/data/swe_world_2/SWE-EVO-dev/hf_out"        # sẽ tạo 2 thư mục con: hf_dataset/ và hf_jsonl/

def to_py(x):
    if np is not None:
        if isinstance(x, np.ndarray):
            return [to_py(v) for v in x.tolist()]
        if isinstance(x, np.generic):
            return x.item()
    if isinstance(x, dict):
        return {str(k): to_py(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [to_py(v) for v in x]
    return x

def ensure_list_str(x):
    if x is None:
        return []
    if isinstance(x, str):
        # Có khả năng là JSON string -> parse
        try:
            j = json.loads(x)
            if isinstance(j, list):
                return [str(v) for v in j]
        except Exception:
            return [x]
        return [x]
    if isinstance(x, (list, tuple, set)):
        return [str(v) for v in x if v is not None]
    return []

def sanitize_instance(obj: dict) -> dict:
    obj = to_py(obj)

    # Các field tối thiểu cần có
    must_be_str = [
        "repo", "instance_id", "base_commit", "patch", "test_patch",
        "problem_statement", "environment_setup_commit", "image",
        "start_version", "end_version", "end_version_commit"
    ]
    for k in must_be_str:
        if k in obj and obj[k] is not None:
            obj[k] = str(obj[k])

    # Chuẩn hoá tests
    obj["FAIL_TO_PASS"] = ensure_list_str(obj.get("FAIL_TO_PASS"))
    obj["PASS_TO_PASS"] = ensure_list_str(obj.get("PASS_TO_PASS"))

    # PRs: list[dict]
    prs = obj.get("PRs")
    if isinstance(prs, list):
        obj["PRs"] = [to_py(p) for p in prs if isinstance(p, dict)]
    else:
        obj["PRs"] = []

    return obj

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC_DIR)
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--split", default="test")  # run_infer.sh thường dùng "test"
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out_ds = out / "hf_dataset"
    out_jsonl = out / "hf_jsonl"
    out_ds.mkdir(parents=True, exist_ok=True)
    out_jsonl.mkdir(parents=True, exist_ok=True)

    rows = []
    for fp in sorted(glob.glob(str(src / "*.json"))):
        if True:
        # if fp == "/mnt/data/swe_world_2/SWE-EVO-dev/output_final/scikit-learn__scikit-learn_0.21.1_0.21.2.json":
            print(f'[fp] = {fp}')
            with open(fp, "r", encoding="utf-8") as f:
                inst = json.load(f)
            rows.append(sanitize_instance(inst))

    # 1) Lưu Hugging Face dataset (local)
    dd = DatasetDict({args.split: Dataset.from_list(rows)})
    dd.save_to_disk(str(out_ds))  # load lại bằng datasets.load_from_disk(...)

    # 2) Gộp thành JSONL (đơn giản nhất cho OpenHands run_infer)
    jsonl_fp = out_jsonl / f"{args.split}.jsonl"
    with open(jsonl_fp, "w", encoding="utf-8") as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("[OK] Saved local HF dataset to:", out_ds)
    print("[OK] Wrote JSONL:", jsonl_fp)

if __name__ == "__main__":
    main()


# python make_hf_dataset.py \
#   --src /mnt/data/swe_world_2/SWE-EVO-dev/output_final \
#   --out /mnt/data/swe_world_2/SWE-EVO-dev/hf_out \
#   --split test
