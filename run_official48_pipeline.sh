#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$SCRIPT_DIR}"
cd "$REPO_ROOT"

pick_first_file() {
  local first="$1"
  shift
  if [ -f "$first" ]; then
    printf '%s\n' "$first"
    return
  fi
  local candidate
  for candidate in "$@"; do
    if [ -f "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  printf '%s\n' "$first"
}

pick_cli_bin() {
  local candidate
  for candidate in \
    "$REPO_ROOT/../innerCC/cli" \
    "$HOME/repo/innerCC/cli" \
    "$HOME/sss_repos/innerCC/cli"
  do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  if command -v innercc >/dev/null 2>&1; then
    printf 'innercc\n'
    return
  fi
  if command -v claude >/dev/null 2>&1; then
    printf 'claude\n'
    return
  fi
  printf 'innercc\n'
}

run_python() {
  if [ -n "${SWE_EVO_DEPS_PATH:-}" ] || [ -d "$PYTHON_DEPS_PATH" ]; then
    PYTHONPATH="$PYTHON_DEPS_PATH${PYTHONPATH:+:$PYTHONPATH}" python3 -u "$@"
    return
  fi
  python3 -u "$@"
}

INFER_MAX_CONCURRENCY="${INFER_MAX_CONCURRENCY:-2}"
EVAL_MAX_CONCURRENCY="${EVAL_MAX_CONCURRENCY:-3}"
CLI_TIMEOUT_SECONDS="${CLI_TIMEOUT_SECONDS:-5400}"
ROUTER_READY_TIMEOUT_SECONDS="${ROUTER_READY_TIMEOUT_SECONDS:-120}"
MODEL_NAME="${MODEL_NAME:-${INNERCC_MODEL:-MiniMax-M2.5-highspeed}}"
CLI_BIN="${CLI_BIN:-${INNERCC_CLI_BIN:-$(pick_cli_bin)}}"
SETTINGS_FILE="${SETTINGS_FILE:-${INNERCC_SETTINGS_PATH:-$(pick_first_file "$REPO_ROOT/config/claude.settings.json" "$HOME/.claude/settings.json")}}"
ENV_FILE="${ENV_FILE:-${INNERCC_ENV_FILE:-$(pick_first_file "$REPO_ROOT/config/swe-evo.env" "$HOME/.config/swe-evo/minimax.env")}}"
AGENT_NAME="${AGENT_NAME:-${INNERCC_AGENT_NAME:-innercc-cli}}"
PYTHON_DEPS_PATH="${SWE_EVO_DEPS_PATH:-$REPO_ROOT/.deps}"
ROUTER_API_BASE="${SWE_EVO_ROUTER_API_BASE:-http://127.0.0.1:18783}"
LLM_ROUTER_ROOT="${LLM_ROUTER_ROOT:-$REPO_ROOT/../llm_router}"

RUN_STAMP="$(date +%Y%m%d-%H%M%S)"
RUN_ROOT="$REPO_ROOT/official48_runs/$RUN_STAMP"
BACKUP_ROOT="$REPO_ROOT/official48_runs/backups/$RUN_STAMP"
SRC_ROOT="${OFFICIAL48_SOURCE_ROOT:-$REPO_ROOT/official48_source}"

mkdir -p "$RUN_ROOT" "$BACKUP_ROOT"

curl -fsS --max-time 30 -X DELETE "$ROUTER_API_BASE/api/data/all" >/dev/null || true

if [ -d "$REPO_ROOT/output_final" ]; then
  mv "$REPO_ROOT/output_final" "$BACKUP_ROOT/output_final"
fi
if [ -d "$REPO_ROOT/hf_out" ]; then
  mv "$REPO_ROOT/hf_out" "$BACKUP_ROOT/hf_out"
fi

cp -a "$SRC_ROOT/output_final" "$REPO_ROOT/output_final"
cp -a "$SRC_ROOT/hf_out" "$REPO_ROOT/hf_out"

run_python "$REPO_ROOT/run_official48_eval_worker.py" \
  "$RUN_ROOT" "$EVAL_MAX_CONCURRENCY" --retry-missing-report \
  > >(tee -a "$RUN_ROOT/eval_worker.log") 2>&1 &
EVAL_PID=$!

cleanup() {
  if [[ -n "${EVAL_PID:-}" ]]; then
    kill "$EVAL_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

run_python "$REPO_ROOT/run_innercc_infer_official48.py" \
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

if [ -d "$LLM_ROUTER_ROOT/proxy/data" ]; then
  cp -a "$LLM_ROUTER_ROOT/proxy/data" "$RUN_ROOT/router_data_snapshot"
fi
