#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/wt/sss_repos/sss_auto/SWE-EVO"
cd "$REPO_ROOT"

INFER_MAX_CONCURRENCY="${INFER_MAX_CONCURRENCY:-2}"
EVAL_MAX_CONCURRENCY="${EVAL_MAX_CONCURRENCY:-3}"
CLI_TIMEOUT_SECONDS="${CLI_TIMEOUT_SECONDS:-5400}"
ROUTER_READY_TIMEOUT_SECONDS="${ROUTER_READY_TIMEOUT_SECONDS:-120}"
MODEL_NAME="${MODEL_NAME:-MiniMax-M2.5-highspeed}"
CLI_BIN="${CLI_BIN:-/home/wt/repo/innerCC/cli}"
SETTINGS_FILE="${SETTINGS_FILE:-/home/wt/.claude/settings.json}"
ENV_FILE="${ENV_FILE:-/home/wt/.config/swe-evo/minimax.env}"
AGENT_NAME="${AGENT_NAME:-innercc-cli}"

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

PYTHONPATH="$REPO_ROOT/.deps" python3 -u "$REPO_ROOT/run_official48_eval_worker.py" \
  "$RUN_ROOT" "$EVAL_MAX_CONCURRENCY" --retry-missing-report \
  > >(tee -a "$RUN_ROOT/eval_worker.log") 2>&1 &
EVAL_PID=$!

cleanup() {
  if [[ -n "${EVAL_PID:-}" ]]; then
    kill "$EVAL_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

PYTHONPATH="$REPO_ROOT/.deps" python3 -u "$REPO_ROOT/run_innercc_infer_official48.py" \
  --output-dir "$RUN_ROOT/infer" \
  --instances-dir "$REPO_ROOT/output_final" \
  --cli-bin "$CLI_BIN" \
  --settings-file "$SETTINGS_FILE" \
  --env-file "$ENV_FILE" \
  --model "$MODEL_NAME" \
  --agent-name "$AGENT_NAME" \
  --max-concurrency "$INFER_MAX_CONCURRENCY" \
  --cli-timeout-seconds "$CLI_TIMEOUT_SECONDS" \
  --router-ready-timeout-seconds "$ROUTER_READY_TIMEOUT_SECONDS" \
  --force-workspace

wait "$EVAL_PID"
trap - EXIT

cp -a /home/wt/sss_repos/sss_auto/llm_router/proxy/data "$RUN_ROOT/router_data_snapshot"
