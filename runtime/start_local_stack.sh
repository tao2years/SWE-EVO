#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash runtime/start_local_stack.sh [--config config/local.launch.env] [all|dashboard|run]

Targets:
  all        Start dashboard and run pipeline
  dashboard  Start dashboard only
  run        Start run pipeline only
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/config/local.launch.env"
TARGET="all"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG_FILE="$2"
      shift 2
      ;;
    all|dashboard|run)
      TARGET="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Config file not found: $CONFIG_FILE" >&2
  echo "Copy config/local.launch.env.example to config/local.launch.env first." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$REPO_ROOT/.venv/bin/python3" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi

DASHBOARD_MODE="${DASHBOARD_MODE:-start}"
DASHBOARD_BACKGROUND="${DASHBOARD_BACKGROUND:-1}"
DASHBOARD_SESSION_NAME="${DASHBOARD_SESSION_NAME:-subset-run-dashboard}"

RUN_BACKGROUND="${RUN_BACKGROUND:-1}"
RUN_SESSION_NAME="${RUN_SESSION_NAME:-subset-innercc-run}"
RUN_CLI="${RUN_CLI:-innercc}"
RUN_MODE="${RUN_MODE:-direct}"
RUN_MANIFEST="${RUN_MANIFEST:-config/subsets/project-coverage-7.txt}"
RUN_MODEL="${RUN_MODEL:-}"
RUN_LIMIT="${RUN_LIMIT:-}"
RUN_MAX_TURNS="${RUN_MAX_TURNS:-}"
RUN_INFER_MAX_CONCURRENCY="${RUN_INFER_MAX_CONCURRENCY:-3}"
RUN_EVAL_MAX_CONCURRENCY="${RUN_EVAL_MAX_CONCURRENCY:-3}"
RUN_CLI_TIMEOUT_SECONDS="${RUN_CLI_TIMEOUT_SECONDS:-5400}"
RUN_CLI_BIN="${RUN_CLI_BIN:-}"
RUN_ENV_FILE="${RUN_ENV_FILE:-}"
RUN_SETTINGS_FILE="${RUN_SETTINGS_FILE:-}"
RUN_ROUTER_ROOT="${RUN_ROUTER_ROOT:-}"
RUN_ROUTER_API_BASE="${RUN_ROUTER_API_BASE:-}"
RUN_RESUME="${RUN_RESUME:-0}"
RUN_NO_FORCE_WORKSPACE="${RUN_NO_FORCE_WORKSPACE:-0}"

print_cmd() {
  printf '+'
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
}

start_dashboard() {
  local cmd=("$PYTHON_BIN" "$REPO_ROOT/run_evaluation.py" dashboard "$DASHBOARD_MODE")
  if [[ "$DASHBOARD_BACKGROUND" == "1" ]]; then
    cmd+=("--background" "--session-name" "$DASHBOARD_SESSION_NAME")
  fi
  print_cmd "${cmd[@]}"
  (
    cd "$REPO_ROOT"
    "${cmd[@]}"
  )
}

start_run() {
  local cmd=(
    "$PYTHON_BIN" "$REPO_ROOT/run_evaluation.py" run
    "--cli" "$RUN_CLI"
    "--mode" "$RUN_MODE"
    "--manifest" "$RUN_MANIFEST"
    "--infer-max-concurrency" "$RUN_INFER_MAX_CONCURRENCY"
    "--eval-max-concurrency" "$RUN_EVAL_MAX_CONCURRENCY"
    "--cli-timeout-seconds" "$RUN_CLI_TIMEOUT_SECONDS"
  )

  if [[ -n "$RUN_MODEL" ]]; then
    cmd+=("--model" "$RUN_MODEL")
  fi
  if [[ -n "$RUN_LIMIT" ]]; then
    cmd+=("--limit" "$RUN_LIMIT")
  fi
  if [[ -n "$RUN_MAX_TURNS" ]]; then
    cmd+=("--max-turns" "$RUN_MAX_TURNS")
  fi
  if [[ -n "$RUN_CLI_BIN" ]]; then
    cmd+=("--cli-bin" "$RUN_CLI_BIN")
  fi
  if [[ -n "$RUN_ENV_FILE" ]]; then
    cmd+=("--env-file" "$RUN_ENV_FILE")
  fi
  if [[ -n "$RUN_SETTINGS_FILE" ]]; then
    cmd+=("--settings-file" "$RUN_SETTINGS_FILE")
  fi
  if [[ -n "$RUN_ROUTER_ROOT" ]]; then
    cmd+=("--router-root" "$RUN_ROUTER_ROOT")
  fi
  if [[ -n "$RUN_ROUTER_API_BASE" ]]; then
    cmd+=("--router-api-base" "$RUN_ROUTER_API_BASE")
  fi
  if [[ "$RUN_RESUME" == "1" ]]; then
    cmd+=("--resume")
  fi
  if [[ "$RUN_NO_FORCE_WORKSPACE" == "1" ]]; then
    cmd+=("--no-force-workspace")
  fi
  if [[ "$RUN_BACKGROUND" == "1" ]]; then
    cmd+=("--background" "--session-name" "$RUN_SESSION_NAME")
  fi

  print_cmd "${cmd[@]}"
  (
    cd "$REPO_ROOT"
    "${cmd[@]}"
  )
}

case "$TARGET" in
  all)
    start_dashboard
    start_run
    ;;
  dashboard)
    start_dashboard
    ;;
  run)
    start_run
    ;;
esac

if [[ "$DASHBOARD_BACKGROUND" == "1" && "$TARGET" != "run" ]]; then
  echo "Dashboard tmux session: $DASHBOARD_SESSION_NAME"
fi
if [[ "$RUN_BACKGROUND" == "1" && "$TARGET" != "dashboard" ]]; then
  echo "Run tmux session: $RUN_SESSION_NAME"
fi
