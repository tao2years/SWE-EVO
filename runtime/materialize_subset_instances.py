#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path

from swe_evo_env import default_official48_source_root


def read_manifest(path: Path) -> list[str]:
    instance_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        instance_ids.append(stripped)
    return instance_ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--source-dir",
        default=str(default_official48_source_root() / "output_final"),
    )
    parser.add_argument("--dest-dir", required=True)
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    source_dir = Path(args.source_dir).expanduser().resolve()
    dest_dir = Path(args.dest_dir).expanduser().resolve()

    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    if not source_dir.exists():
        raise FileNotFoundError(source_dir)

    instance_ids = read_manifest(manifest_path)
    if args.limit > 0:
        instance_ids = instance_ids[: args.limit]

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    materialized: list[dict] = []
    for instance_id in instance_ids:
        src = source_dir / f"{instance_id}.json"
        if not src.exists():
            raise FileNotFoundError(src)
        dst = dest_dir / src.name
        if args.mode == "copy":
            shutil.copy2(src, dst)
        else:
            dst.symlink_to(src)
        payload = json.loads(src.read_text(encoding="utf-8"))
        materialized.append(
            {
                "instance_id": instance_id,
                "repo": payload.get("repo"),
                "source": str(src),
                "dest": str(dst),
            }
        )

    metadata = {
        "manifest": str(manifest_path),
        "source_dir": str(source_dir),
        "dest_dir": str(dest_dir),
        "mode": args.mode,
        "count": len(materialized),
        "instances": materialized,
    }
    metadata_path = dest_dir.parent / "subset_metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"dest_dir": str(dest_dir), "count": len(materialized)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
