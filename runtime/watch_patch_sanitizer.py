#!/usr/bin/env python3
import argparse
import time
from pathlib import Path

from sanitize_model_patch import sanitize_run_case


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", required=True)
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()

    runs_root = Path(args.runs_root).resolve()
    while True:
        for patch_path in runs_root.glob("*/patch.diff"):
            run_case_dir = patch_path.parent
            sanitize_run_case(run_case_dir)
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
