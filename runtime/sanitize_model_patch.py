#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


FORBIDDEN_PARTS = {
    "test",
    "tests",
    "testing",
    "fixture",
    "fixtures",
    "docs",
    "doc",
    "changes",
    "newsfragments",
}
FORBIDDEN_BASENAMES = {
    "CHANGELOG",
    "CHANGELOG.md",
    "CHANGELOG.rst",
    "NEWS.md",
    "NEWS.rst",
}


def is_forbidden_path(path: str) -> bool:
    normalized = path.strip().lstrip("ab/").strip("/")
    parts = [part for part in normalized.split("/") if part]
    if any(part in FORBIDDEN_PARTS for part in parts):
        return True
    basename = parts[-1] if parts else normalized
    if basename in FORBIDDEN_BASENAMES:
        return True
    return False


def split_diff_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current:
                blocks.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("".join(current))
    return blocks


def block_paths(block: str) -> tuple[str | None, str | None]:
    old_path = None
    new_path = None
    for line in block.splitlines():
        if line.startswith("--- "):
            old_path = line[4:].strip()
        elif line.startswith("+++ "):
            new_path = line[4:].strip()
        if old_path is not None and new_path is not None:
            break
    return old_path, new_path


def sanitize_patch_text(text: str) -> tuple[str, list[str]]:
    kept: list[str] = []
    removed: list[str] = []
    for block in split_diff_blocks(text):
        if not block.startswith("diff --git "):
            kept.append(block)
            continue
        old_path, new_path = block_paths(block)
        candidates = [p for p in (old_path, new_path) if p and p not in {"/dev/null"}]
        if any(is_forbidden_path(path) for path in candidates):
            removed.extend(candidates)
            continue
        kept.append(block)
    sanitized = "".join(kept)
    if sanitized and not sanitized.endswith("\n"):
        sanitized += "\n"
    return sanitized, removed


def update_aggregate_preds(run_case_dir: Path, sanitized_patch: str) -> None:
    aggregate_preds_path = run_case_dir.parents[1] / "preds.json"
    if not aggregate_preds_path.exists():
        return
    try:
        aggregate = json.loads(aggregate_preds_path.read_text(encoding="utf-8"))
    except Exception:
        return
    instance_id = run_case_dir.name
    payload = aggregate.get(instance_id)
    if isinstance(payload, dict):
        payload["model_patch"] = sanitized_patch
        aggregate_preds_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2), encoding="utf-8")


def sanitize_run_case(run_case_dir: Path) -> dict:
    patch_path = run_case_dir / "patch.diff"
    preds_path = run_case_dir / "preds.json"
    if not patch_path.exists() or not preds_path.exists():
        return {"changed": False, "removed_paths": []}

    original_patch = patch_path.read_text(encoding="utf-8", errors="replace")
    sanitized_patch, removed_paths = sanitize_patch_text(original_patch)
    changed = sanitized_patch != original_patch
    if changed:
        patch_path.write_text(sanitized_patch, encoding="utf-8")
    preds = json.loads(preds_path.read_text(encoding="utf-8"))
    for payload in preds.values():
        if isinstance(payload, dict):
            payload["model_patch"] = sanitized_patch
    preds_path.write_text(json.dumps(preds, ensure_ascii=False, indent=2), encoding="utf-8")
    update_aggregate_preds(run_case_dir, sanitized_patch)
    if changed:
        marker = {
            "changed": True,
            "removed_paths": sorted(set(removed_paths)),
        }
        (run_case_dir / "patch_sanitization.json").write_text(
            json.dumps(marker, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return marker
    return {"changed": False, "removed_paths": []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-case-dir", default="")
    parser.add_argument("--runs-root", default="")
    args = parser.parse_args()

    results = {}
    if args.run_case_dir:
        run_case_dir = Path(args.run_case_dir).resolve()
        results[str(run_case_dir)] = sanitize_run_case(run_case_dir)
    elif args.runs_root:
        runs_root = Path(args.runs_root).resolve()
        for patch_path in sorted(runs_root.glob("*/patch.diff")):
            run_case_dir = patch_path.parent
            results[str(run_case_dir)] = sanitize_run_case(run_case_dir)
    else:
        raise SystemExit("provide --run-case-dir or --runs-root")

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
