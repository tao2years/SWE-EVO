# Requires: pip install datasets tqdm
import os, re, subprocess, json, sys
from collections import defaultdict
from datasets import load_dataset
from tqdm import tqdm

# ========= CONFIG =========
LOCAL_BASE_DIR = "/mnt/data/swe_world_2/swe_bench"  
TIMEOUT = 60

TAG_FILTER_REGEX = None  # r"^(?:v)?\d+(?:\.\d+){1,3}[A-Za-z0-9\-\._]*$"

# ========= UTILS =========
def run(cmd, cwd=None, timeout=TIMEOUT):
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    ).stdout

def owner_repo_to_local_path(repo: str) -> str:
    # "owner/repo" -> ".../owner__repo"
    return os.path.join(LOCAL_BASE_DIR, repo.replace("/", "__"))

def list_tag_commits_remote(repo: str):
    url = f"https://github.com/{repo}.git"
    out = run(["git", "ls-remote", "--tags", url])
    commit_to_tags = defaultdict(list)

    for line in out.strip().splitlines():
        sha, ref = line.split("\t")
        if not ref.startswith("refs/tags/"):
            continue
        tag_name = ref[len("refs/tags/"):]
        if tag_name.endswith("^{}"):
            # Peeled line: commit that the tag ultimately points to
            tag_name = tag_name[:-3]
            if TAG_FILTER_REGEX and not re.match(TAG_FILTER_REGEX, tag_name):
                continue
            commit_to_tags[sha].append(tag_name)
        else:
            # Might be a lightweight tag (points directly to commit)
            # We'll tentatively record it; if there's also a peeled line,
            # that peeled line will add same tag against the true commit.
            if TAG_FILTER_REGEX and not re.match(TAG_FILTER_REGEX, tag_name):
                continue
            commit_to_tags[sha].append(tag_name)

    # Deduplicate tag lists
    for k in list(commit_to_tags.keys()):
        commit_to_tags[k] = sorted(set(commit_to_tags[k]))
    return dict(commit_to_tags)

def list_tag_commits_local(repo: str):
    path = owner_repo_to_local_path(repo)
    git_dir = os.path.join(path, ".git")
    if not (LOCAL_BASE_DIR and os.path.isdir(git_dir)):
        return None

    out = run(["git", "show-ref", "--tags", "-d"], cwd=path)
    commit_to_tags = defaultdict(list)
    temp_map = defaultdict(list)  # tag_name -> [sha candidates]

    for line in out.strip().splitlines():
        sha, ref = line.split(" ", 1)
        if not ref.startswith("refs/tags/"):
            continue
        tag_name = ref[len("refs/tags/"):].strip()
        if tag_name.endswith("^{}"):
            # Peeled -> real commit
            tag_name = tag_name[:-3]
            if TAG_FILTER_REGEX and not re.match(TAG_FILTER_REGEX, tag_name):
                continue
            commit_to_tags[sha].append(tag_name)
        else:
            # Lightweight or tag object (for annotated)
            if TAG_FILTER_REGEX and not re.match(TAG_FILTER_REGEX, tag_name):
                continue
            temp_map[tag_name].append(sha)

    for tag_name, shas in temp_map.items():
        if not any(tag_name in tags for tags in commit_to_tags.values()):
            for sha in shas:
                commit_to_tags[sha].append(tag_name)

    for k in list(commit_to_tags.keys()):
        commit_to_tags[k] = sorted(set(commit_to_tags[k]))
    return dict(commit_to_tags)

def build_tag_commit_index(repos):
    """
    repos: iterable 
    return: dict repo -> (dict commit_sha -> list[tag_names])
    """
    idx = {}
    for repo in tqdm(sorted(set(repos)), desc="Indexing tags"):
        local_map = list_tag_commits_local(repo)
        if local_map is not None and len(local_map) > 0:
            idx[repo] = local_map
        else:
            idx[repo] = list_tag_commits_remote(repo)
    return idx

def match_base_commit_to_tags(commit_map, base_sha):
    """
    commit_map: dict commit_sha -> list[tag_names]
    base_sha: 40-hex 
    Return: list tag_names
    """
    if base_sha in commit_map:
        return commit_map[base_sha]

    for sha, tags in commit_map.items():
        if sha.startswith(base_sha) or base_sha.startswith(sha):
            return tags
    return []

# ========= MAIN =========
def main():
    # ds = load_dataset("princeton-nlp/SWE-bench", split="test")
    # out_path = "swebench_test_base_is_release_tag.jsonl"
    ds = load_dataset('SWE-gym/SWE-gym', split="train")
    out_path = "swegym_train_base_is_release_tag.jsonl"
    repos = [ex["repo"] for ex in ds if ex.get("repo")]
    tag_index = build_tag_commit_index(repos)

    rows = []
    for ex in tqdm(ds, desc="Filtering instances"):
        repo = ex["repo"]
        base = ex["base_commit"]
        iid  = ex["instance_id"]
        commit_map = tag_index.get(repo, {})
        tags = match_base_commit_to_tags(commit_map, base)
        if tags:
            rows.append({
                "instance_id": iid,
                "repo": repo,
                "base_commit": base,
                "matching_tags": tags,
            })

    print(f"Matched {len(rows)} instances where base_commit == a tag commit.")
    for r in rows[:55555]:
        print(json.dumps(r, ensure_ascii=False))

    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("Saved:", out_path)

if __name__ == "__main__":
    main()
