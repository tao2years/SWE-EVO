#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_ID="psf__requests_v2.27.0_v2.27.1-innercc-$(date +%Y%m%d-%H%M%S)"

cd "$REPO_ROOT"

python3 custom_cli_case/run_custom_cli_case.py \
  --instance-id psf__requests_v2.27.0_v2.27.1 \
  --case-root "$REPO_ROOT/custom_cli_case" \
  --eval-run-id "$RUN_ID" \
  --force-workspace \
  --max-workers "${INNERCC_MAX_WORKERS:-1}"
