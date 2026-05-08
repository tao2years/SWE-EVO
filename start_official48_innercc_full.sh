#!/bin/sh
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$SCRIPT_DIR}"
cd "$REPO_ROOT"

usage() {
  cat <<'EOF'
Usage:
  bash ./start_official48_innercc_full.sh [options]

Starts a fresh official48 innercc full run in the background.
The launcher will:
  1. Stop stale SWE-EVO official48 tmux sessions.
  2. Restart llm_router in background tmux sessions.
  3. Re-stage official48_source/{output_final,hf_out}.
  4. Create a new official48_runs/<run_stamp> directory.
  5. Start the full run in tmux and leave monitor/eval/progress under supervisor control.

Options:
  --cli-bin PATH
  --settings-file PATH
  --env-file PATH
  --model NAME
  --agent-name NAME
  --source-root PATH
  --router-root PATH
  --router-api-base URL
  --run-stamp YYYYMMDD-HHMMSS
  --run-display-name NAME
  --inference-concurrency N
  --eval-concurrency N
  --max-turns N
  --cli-timeout-seconds N
  --router-ready-timeout-seconds N
  --router-stall-timeout-seconds N
  --dry-run
  --no-stop
  -h, --help

Environment overrides:
  CLI_BIN
  SETTINGS_FILE
  ENV_FILE
  MODEL_NAME
  AGENT_NAME
  OFFICIAL48_SOURCE_ROOT
  LLM_ROUTER_ROOT
  ROUTER_API_BASE
  RUN_STAMP
  RUN_DISPLAY_NAME
  INFER_MAX_CONCURRENCY
  EVAL_MAX_CONCURRENCY
  MAX_TURNS
  CLI_TIMEOUT_SECONDS
  ROUTER_READY_TIMEOUT_SECONDS
  ROUTER_STALL_TIMEOUT_SECONDS
  SWE_EVO_DEPS_PATH
  INNERCC_CLI_BIN
  INNERCC_SETTINGS_PATH
  INNERCC_ENV_FILE
  INNERCC_MODEL
EOF
}

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
    "${INNERCC_CLI_BIN:-}" \
    "$REPO_ROOT/../innerCC/cli" \
    "$REPO_ROOT/../../innerCC/cli" \
    "$HOME/repo/innerCC/cli" \
    "$HOME/sss_repos/innerCC/cli"
  do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
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

json_escape() {
  printf '%s' "$1" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

shell_quote() {
  printf '%q' "$1"
}

abs_path() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

print(Path(sys.argv[1]).expanduser().resolve())
PY
}

command_exists_or_executable() {
  local candidate="$1"
  if [[ "$candidate" == */* ]]; then
    [ -x "$candidate" ]
    return
  fi
  command -v "$candidate" >/dev/null 2>&1
}

assert_positive_int() {
  local label="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]] || [ "$value" -lt 1 ]; then
    printf '[error] %s must be a positive integer: %s\n' "$label" "$value" >&2
    exit 1
  fi
}

stop_tmux_session_if_exists() {
  local session_name="$1"
  if tmux has-session -t "$session_name" 2>/dev/null; then
    printf '[stop] %s\n' "$session_name"
    tmux kill-session -t "$session_name"
  fi
}

tmux_session_exists() {
  tmux has-session -t "$1" 2>/dev/null
}

reset_router_runtime_data() {
  local router_root="$1"
  local backup_root="$2"
  local data_dir="$router_root/proxy/data"
  local backup_dir="$backup_root/router_proxy_data"
  if [ ! -d "$data_dir" ]; then
    return 0
  fi
  printf '[router] moving stale router data to %s\n' "$backup_dir"
  mv "$data_dir" "$backup_dir"
}

start_dashboard_if_needed() {
  local session_name="$1"
  local log_path="$2"
  if tmux_session_exists "$session_name"; then
    printf '[dashboard] reusing tmux session %s\n' "$session_name"
    return 0
  fi

  mkdir -p "$(dirname "$log_path")"
  printf '[dashboard] starting tmux session %s\n' "$session_name"
  tmux new-session -d -s "$session_name" \
    "bash -lc 'cd $(shell_quote "$REPO_ROOT") && if [ ! -f .next/BUILD_ID ]; then npm run build; fi && npm run dashboard:start >> $(shell_quote "$log_path") 2>&1'"
}

stop_stale_official48_sessions() {
  local fixed_session
  for fixed_session in \
    swe-evo-official48-router \
    swe-evo-official48-eval \
    swe-evo-official48-monitor \
    swe-evo-official48-progress \
    swe-evo-official48-supervisor
  do
    stop_tmux_session_if_exists "$fixed_session"
  done

  local tmux_line session_name
  while IFS= read -r tmux_line; do
    session_name="${tmux_line%%:*}"
    case "$session_name" in
      swe-evo-official48-innercc-*|swe-evo-official48-progress-local-*|swe-evo-official48-milestones-*)
        stop_tmux_session_if_exists "$session_name"
        ;;
    esac
  done < <(tmux ls 2>/dev/null || true)
}

CLI_BIN="${CLI_BIN:-$(pick_cli_bin)}"
SETTINGS_FILE="${SETTINGS_FILE:-${INNERCC_SETTINGS_PATH:-$(pick_first_file "$REPO_ROOT/config/claude.settings.json" "$HOME/.claude/settings.json")}}"
ENV_FILE="${ENV_FILE:-${INNERCC_ENV_FILE:-$(pick_first_file "$REPO_ROOT/config/swe-evo.env" "$HOME/.config/swe-evo/minimax.env")}}"
MODEL_NAME="${MODEL_NAME:-${INNERCC_MODEL:-MiniMax-M2.5-highspeed}}"
AGENT_NAME="${AGENT_NAME:-innercc-cli}"
SOURCE_ROOT="${OFFICIAL48_SOURCE_ROOT:-$REPO_ROOT/official48_source}"
LLM_ROUTER_ROOT="${LLM_ROUTER_ROOT:-$REPO_ROOT/../llm_router}"
ROUTER_API_BASE="${ROUTER_API_BASE:-http://127.0.0.1:18783}"
INFER_MAX_CONCURRENCY="${INFER_MAX_CONCURRENCY:-3}"
EVAL_MAX_CONCURRENCY="${EVAL_MAX_CONCURRENCY:-3}"
MAX_TURNS="${MAX_TURNS:-}"
CLI_TIMEOUT_SECONDS="${CLI_TIMEOUT_SECONDS:-5400}"
ROUTER_READY_TIMEOUT_SECONDS="${ROUTER_READY_TIMEOUT_SECONDS:-120}"
ROUTER_STALL_TIMEOUT_SECONDS="${ROUTER_STALL_TIMEOUT_SECONDS:-1800}"
RUN_STAMP="${RUN_STAMP:-$(date +%Y%m%d-%H%M%S)}"
RUN_DISPLAY_NAME="${RUN_DISPLAY_NAME:-full-innercc-$RUN_STAMP}"
PYTHON_DEPS_PATH="${SWE_EVO_DEPS_PATH:-$REPO_ROOT/.deps}"
ROUTER_SESSION_PREFIX="${ROUTER_SESSION_PREFIX:-sss-auto-llm-router}"
ROUTER_PROXY_PORT="${ROUTER_PROXY_PORT:-18782}"
ROUTER_API_PORT="${ROUTER_API_PORT:-18783}"
ROUTER_WEB_PORT="${ROUTER_WEB_PORT:-18781}"
DASHBOARD_SESSION="${DASHBOARD_SESSION:-swe-evo-dashboard}"
DASHBOARD_LOG_PATH="${DASHBOARD_LOG_PATH:-$REPO_ROOT/logs/official48_dashboard.log}"
ANTHROPIC_UPSTREAM_URL="${ANTHROPIC_UPSTREAM_URL:-https://api.minimaxi.com/anthropic}"
OPENAI_UPSTREAM_URL="${OPENAI_UPSTREAM_URL:-https://api.minimaxi.com/v1}"
DRY_RUN=0
NO_STOP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cli-bin)
      CLI_BIN="$2"
      shift 2
      ;;
    --settings-file)
      SETTINGS_FILE="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --model)
      MODEL_NAME="$2"
      shift 2
      ;;
    --agent-name)
      AGENT_NAME="$2"
      shift 2
      ;;
    --source-root)
      SOURCE_ROOT="$2"
      shift 2
      ;;
    --router-root)
      LLM_ROUTER_ROOT="$2"
      shift 2
      ;;
    --router-api-base)
      ROUTER_API_BASE="$2"
      shift 2
      ;;
    --run-stamp)
      RUN_STAMP="$2"
      shift 2
      ;;
    --run-display-name)
      RUN_DISPLAY_NAME="$2"
      shift 2
      ;;
    --inference-concurrency)
      INFER_MAX_CONCURRENCY="$2"
      shift 2
      ;;
    --eval-concurrency)
      EVAL_MAX_CONCURRENCY="$2"
      shift 2
      ;;
    --max-turns)
      MAX_TURNS="$2"
      shift 2
      ;;
    --cli-timeout-seconds)
      CLI_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --router-ready-timeout-seconds)
      ROUTER_READY_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --router-stall-timeout-seconds)
      ROUTER_STALL_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-stop)
      NO_STOP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf '[error] unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SOURCE_ROOT="$(abs_path "$SOURCE_ROOT")"
LLM_ROUTER_ROOT="$(abs_path "$LLM_ROUTER_ROOT")"
if [[ "$CLI_BIN" == */* ]]; then
  CLI_BIN="$(abs_path "$CLI_BIN")"
fi
SETTINGS_FILE="$(abs_path "$SETTINGS_FILE")"
ENV_FILE="$(abs_path "$ENV_FILE")"

RUN_ROOT="$REPO_ROOT/official48_runs/$RUN_STAMP"
BACKUP_ROOT="$REPO_ROOT/official48_runs/backups/$RUN_STAMP"
LAUNCH_SCRIPT_PATH="$RUN_ROOT/launch_innercc_full.sh"
MAIN_TMUX_SESSION="swe-evo-official48-innercc-$RUN_STAMP"
LATEST_LINK="$REPO_ROOT/official48_runs/latest"

if ! command_exists_or_executable "$CLI_BIN"; then
  printf '[error] CLI_BIN is not executable or resolvable: %s\n' "$CLI_BIN" >&2
  exit 1
fi
if [ ! -f "$SETTINGS_FILE" ]; then
  printf '[error] settings file not found: %s\n' "$SETTINGS_FILE" >&2
  exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
  printf '[error] env file not found: %s\n' "$ENV_FILE" >&2
  exit 1
fi
if [ ! -d "$SOURCE_ROOT/output_final" ]; then
  printf '[error] missing source output_final: %s\n' "$SOURCE_ROOT/output_final" >&2
  exit 1
fi
if [ ! -d "$SOURCE_ROOT/hf_out" ]; then
  printf '[error] missing source hf_out: %s\n' "$SOURCE_ROOT/hf_out" >&2
  exit 1
fi
if [ ! -f "$LLM_ROUTER_ROOT/scripts/start-prod.sh" ]; then
  printf '[error] missing llm_router start script: %s\n' "$LLM_ROUTER_ROOT/scripts/start-prod.sh" >&2
  exit 1
fi
if [ -e "$RUN_ROOT" ]; then
  printf '[error] run root already exists: %s\n' "$RUN_ROOT" >&2
  exit 1
fi
assert_positive_int INFER_MAX_CONCURRENCY "$INFER_MAX_CONCURRENCY"
assert_positive_int EVAL_MAX_CONCURRENCY "$EVAL_MAX_CONCURRENCY"
assert_positive_int CLI_TIMEOUT_SECONDS "$CLI_TIMEOUT_SECONDS"
assert_positive_int ROUTER_READY_TIMEOUT_SECONDS "$ROUTER_READY_TIMEOUT_SECONDS"
assert_positive_int ROUTER_STALL_TIMEOUT_SECONDS "$ROUTER_STALL_TIMEOUT_SECONDS"
if [ -n "$MAX_TURNS" ]; then
  assert_positive_int MAX_TURNS "$MAX_TURNS"
fi

printf '[config] repo_root=%s\n' "$REPO_ROOT"
printf '[config] run_root=%s\n' "$RUN_ROOT"
printf '[config] cli_bin=%s\n' "$CLI_BIN"
printf '[config] settings_file=%s\n' "$SETTINGS_FILE"
printf '[config] env_file=%s\n' "$ENV_FILE"
printf '[config] model=%s\n' "$MODEL_NAME"
printf '[config] agent_name=%s\n' "$AGENT_NAME"
printf '[config] source_root=%s\n' "$SOURCE_ROOT"
printf '[config] router_root=%s\n' "$LLM_ROUTER_ROOT"
printf '[config] router_api_base=%s\n' "$ROUTER_API_BASE"
printf '[config] inference_concurrency=%s\n' "$INFER_MAX_CONCURRENCY"
printf '[config] eval_concurrency=%s\n' "$EVAL_MAX_CONCURRENCY"
printf '[config] max_turns=%s\n' "${MAX_TURNS:-<unset>}"
printf '[config] cli_timeout_seconds=%s\n' "$CLI_TIMEOUT_SECONDS"
printf '[config] router_ready_timeout_seconds=%s\n' "$ROUTER_READY_TIMEOUT_SECONDS"
printf '[config] router_stall_timeout_seconds=%s\n' "$ROUTER_STALL_TIMEOUT_SECONDS"
printf '[config] main_tmux_session=%s\n' "$MAIN_TMUX_SESSION"
printf '[config] dashboard_session=%s\n' "$DASHBOARD_SESSION"

if [ "$DRY_RUN" -eq 1 ]; then
  printf '[dry-run] validation passed; nothing started\n'
  exit 0
fi

mkdir -p "$RUN_ROOT" "$BACKUP_ROOT"

if [ "$NO_STOP" -eq 0 ]; then
  stop_stale_official48_sessions
fi

if [ -e "$LATEST_LINK" ] || [ -L "$LATEST_LINK" ]; then
  rm -rf "$LATEST_LINK"
fi
ln -s "$RUN_ROOT" "$LATEST_LINK"

cat >"$RUN_ROOT/metadata.json" <<EOF
{
  "display_name": $(json_escape "$RUN_DISPLAY_NAME"),
  "model": $(json_escape "$MODEL_NAME"),
  "cli_bin": $(json_escape "$CLI_BIN"),
  "settings_file": $(json_escape "$SETTINGS_FILE"),
  "env_file": $(json_escape "$ENV_FILE"),
  "agent_name": $(json_escape "$AGENT_NAME"),
  "source_root": $(json_escape "$SOURCE_ROOT"),
  "router_root": $(json_escape "$LLM_ROUTER_ROOT"),
  "router_api_base": $(json_escape "$ROUTER_API_BASE"),
  "inference_concurrency": $INFER_MAX_CONCURRENCY,
  "eval_concurrency": $EVAL_MAX_CONCURRENCY,
  "max_turns": ${MAX_TURNS:-null},
  "cli_timeout_seconds": $CLI_TIMEOUT_SECONDS,
  "router_ready_timeout_seconds": $ROUTER_READY_TIMEOUT_SECONDS,
  "router_stall_timeout_seconds": $ROUTER_STALL_TIMEOUT_SECONDS,
  "created_at": $(date --iso-8601=seconds | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))')
}
EOF

if [ -d "$REPO_ROOT/output_final" ]; then
  mv "$REPO_ROOT/output_final" "$BACKUP_ROOT/output_final"
fi
if [ -d "$REPO_ROOT/hf_out" ]; then
  mv "$REPO_ROOT/hf_out" "$BACKUP_ROOT/hf_out"
fi

cp -a "$SOURCE_ROOT/output_final" "$REPO_ROOT/output_final"
cp -a "$SOURCE_ROOT/hf_out" "$REPO_ROOT/hf_out"

MAX_TURNS_ARGS=()
if [ -n "$MAX_TURNS" ]; then
  MAX_TURNS_ARGS=(
    --max-turns
    "$MAX_TURNS"
  )
fi

cat >"$LAUNCH_SCRIPT_PATH" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd $(shell_quote "$REPO_ROOT")
if [ -d $(shell_quote "$PYTHON_DEPS_PATH") ]; then
  export PYTHONPATH=$(shell_quote "$PYTHON_DEPS_PATH")\${PYTHONPATH:+:\$PYTHONPATH}
fi
RUN_ROOT="\$1"
python3 -u watch_official48_supervisor.py "\$RUN_ROOT" \\
  --progress-md $(shell_quote "$REPO_ROOT/progress.md") \\
  --interval-seconds 30 \\
  --inference-concurrency $(shell_quote "$INFER_MAX_CONCURRENCY") \\
  --eval-max-concurrency $(shell_quote "$EVAL_MAX_CONCURRENCY") \\
  ${MAX_TURNS_ARGS:+$(shell_quote "${MAX_TURNS_ARGS[0]}") $(shell_quote "${MAX_TURNS_ARGS[1]}") \\}
  --cli-timeout-seconds $(shell_quote "$CLI_TIMEOUT_SECONDS") \\
  --router-ready-timeout-seconds $(shell_quote "$ROUTER_READY_TIMEOUT_SECONDS") \\
  --router-stall-timeout-seconds $(shell_quote "$ROUTER_STALL_TIMEOUT_SECONDS") \\
  --cli-bin $(shell_quote "$CLI_BIN") \\
  --settings-file $(shell_quote "$SETTINGS_FILE") \\
  --env-file $(shell_quote "$ENV_FILE") \\
  --model $(shell_quote "$MODEL_NAME") \\
  --agent-name $(shell_quote "$AGENT_NAME") \\
  2>&1 | tee -a "\$RUN_ROOT/supervisor_console.log"
python3 -u monitor_official48_run.py "\$RUN_ROOT"
python3 -u summarize_official48_run.py --run-root "\$RUN_ROOT"
EOF
chmod +x "$LAUNCH_SCRIPT_PATH"

printf '[router] starting background llm_router sessions\n'
stop_tmux_session_if_exists "${ROUTER_SESSION_PREFIX}-proxy"
stop_tmux_session_if_exists "${ROUTER_SESSION_PREFIX}-web"
reset_router_runtime_data "$LLM_ROUTER_ROOT" "$BACKUP_ROOT"
(
  cd "$LLM_ROUTER_ROOT"
  SESSION_PREFIX="$ROUTER_SESSION_PREFIX" \
  PROXY_PORT="$ROUTER_PROXY_PORT" \
  API_SERVER_PORT="$ROUTER_API_PORT" \
  WEB_PORT="$ROUTER_WEB_PORT" \
  ANTHROPIC_UPSTREAM_URL="$ANTHROPIC_UPSTREAM_URL" \
  OPENAI_UPSTREAM_URL="$OPENAI_UPSTREAM_URL" \
  bash "$LLM_ROUTER_ROOT/scripts/start-prod.sh"
)

start_dashboard_if_needed "$DASHBOARD_SESSION" "$DASHBOARD_LOG_PATH"

tmux new-session -d -s "$MAIN_TMUX_SESSION" \
  "bash $(shell_quote "$LAUNCH_SCRIPT_PATH") $(shell_quote "$RUN_ROOT")"

cat <<EOF
[started] run_root=$RUN_ROOT
[started] main_tmux_session=$MAIN_TMUX_SESSION
[started] router_sessions=${ROUTER_SESSION_PREFIX}-proxy,${ROUTER_SESSION_PREFIX}-web
[started] dashboard_session=$DASHBOARD_SESSION
[started] latest_link=$LATEST_LINK
[hint] attach: tmux attach -t $MAIN_TMUX_SESSION
[hint] dashboard: http://127.0.0.1:18881
[hint] monitor: python3 ./monitor_official48_run.py $RUN_ROOT
[hint] summary: python3 ./summarize_official48_run.py --run-root $RUN_ROOT
EOF
