#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/wt/sss_repos/sss_auto/SWE-EVO"
cd "$REPO_ROOT"

RUN_STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_ROOT="$REPO_ROOT/official48_runs/$RUN_STAMP"
BACKUP_ROOT="$REPO_ROOT/official48_runs/backups/$RUN_STAMP"
SRC_ROOT="$REPO_ROOT/official48_source"

mkdir -p "$RUN_ROOT" "$BACKUP_ROOT"

curl -s --max-time 30 -X DELETE http://127.0.0.1:18783/api/data/all >/dev/null

if [ -d "$REPO_ROOT/output_final" ]; then
  mv "$REPO_ROOT/output_final" "$BACKUP_ROOT/output_final"
fi
if [ -d "$REPO_ROOT/hf_out" ]; then
  mv "$REPO_ROOT/hf_out" "$BACKUP_ROOT/hf_out"
fi

cp -a "$SRC_ROOT/output_final" "$REPO_ROOT/output_final"
cp -a "$SRC_ROOT/hf_out" "$REPO_ROOT/hf_out"

PYTHONPATH="$REPO_ROOT/.deps" python3 -u "$REPO_ROOT/run_innercc_infer_official48.py" \
  --output-dir "$RUN_ROOT/infer" \
  --instances-dir "$REPO_ROOT/output_final" \
  --cli-bin "/home/wt/repo/innerCC/cli" \
  --settings-file "/home/wt/.claude/settings.json" \
  --env-file "/home/wt/.config/swe-evo/minimax.env" \
  --force-workspace

PYTHONPATH="$REPO_ROOT/.deps" python3 -u "$REPO_ROOT/SWE-bench/evaluate_instance.py" \
  --trajectories_path "$RUN_ROOT/infer" \
  --max_workers 1 \
  --scaffold CustomCLI

cp -a /home/wt/sss_repos/sss_auto/llm_router/proxy/data "$RUN_ROOT/router_data_snapshot"
