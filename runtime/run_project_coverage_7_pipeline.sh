#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
RUNTIME_ROOT="$SCRIPT_DIR"
cd "$REPO_ROOT"

usage() {
  cat <<'EOF'
Usage:
  ./run_project_coverage_7_pipeline.sh [--cli innercc|claude] [options]

Options:
  --cli <name>                   CLI flavor: innercc or claude. Default: innercc
  --manifest <path>              Subset manifest. Default: config/subsets/project-coverage-7.txt
  --limit <n>                    Materialize only the first n instances from the manifest
  --cli-bin <path>               Override CLI binary
  --env-file <path>              Override credential env file
  --model <name>                 Override model name
  --max-turns <n>                Cap agent turns for smoke runs
  --infer-max-concurrency <n>    Inference concurrency. Default: 2
  --eval-max-concurrency <n>     Evaluation concurrency. Default: 3
  --cli-timeout-seconds <n>      CLI timeout per case. Default: 5400
  --copy-mode <copy|symlink>     Materialization mode. Default: copy
  --resume                       Resume an existing run directory
  --no-force-workspace           Reuse existing workspaces when present
  --help                         Show this help
EOF
}

venv_ready() {
  local python_bin="$REPO_ROOT/.venv/bin/python"
  if [ ! -x "$python_bin" ]; then
    return 1
  fi
  "$python_bin" - <<'PY' >/dev/null 2>&1
for mod in ("tqdm", "docker", "numpy", "swebench"):
    __import__(mod)
PY
}

pick_first_file() {
  local candidate
  for candidate in "$@"; do
    if [ -f "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  return 1
}

resolve_cli_bin() {
  local candidate="$1"
  if command -v "$candidate" >/dev/null 2>&1; then
    command -v "$candidate"
    return
  fi
  python3 - "$candidate" <<'PY'
import os
import sys
from pathlib import Path

print(Path(os.path.expanduser(sys.argv[1])).resolve())
PY
}

pick_cli_bin() {
  local cli_kind="$1"
  local candidate

  if [ "$cli_kind" = "claude" ]; then
    if command -v claude >/dev/null 2>&1; then
      command -v claude
      return
    fi
    return 1
  fi

  for candidate in \
    "$REPO_ROOT/dist/innercc_0509_dcp" \
    "$REPO_ROOT/../innerCC/cli" \
    "$REPO_ROOT/../../innerCC/cli" \
    "$HOME/repo/innerCC/cli" \
    "$HOME/sss_repos/innerCC/cli"
  do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return
    fi
  done
  if command -v innercc >/dev/null 2>&1; then
    command -v innercc
    return
  fi
  return 1
}

CLI_KIND="${CLI_KIND:-innercc}"
MANIFEST_PATH="$REPO_ROOT/config/subsets/project-coverage-7.txt"
LIMIT="${LIMIT:-0}"
INFER_MAX_CONCURRENCY="${INFER_MAX_CONCURRENCY:-2}"
EVAL_MAX_CONCURRENCY="${EVAL_MAX_CONCURRENCY:-3}"
CLI_TIMEOUT_SECONDS="${CLI_TIMEOUT_SECONDS:-5400}"
MODEL_NAME="${MODEL_NAME:-${INNERCC_MODEL:-MiniMax-M2.5-highspeed}}"
CLI_BIN="${CLI_BIN:-}"
ENV_FILE="${ENV_FILE:-}"
MAX_TURNS="${MAX_TURNS:-}"
COPY_MODE="${COPY_MODE:-copy}"
RUN_DISPLAY_NAME="${RUN_DISPLAY_NAME:-}"
RESUME=0
FORCE_WORKSPACE=1

while [ $# -gt 0 ]; do
  case "$1" in
    --cli)
      CLI_KIND="$2"
      shift 2
      ;;
    --manifest)
      MANIFEST_PATH="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --cli-bin)
      CLI_BIN="$2"
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
    --max-turns)
      MAX_TURNS="$2"
      shift 2
      ;;
    --infer-max-concurrency)
      INFER_MAX_CONCURRENCY="$2"
      shift 2
      ;;
    --eval-max-concurrency)
      EVAL_MAX_CONCURRENCY="$2"
      shift 2
      ;;
    --cli-timeout-seconds)
      CLI_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --copy-mode)
      COPY_MODE="$2"
      shift 2
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --no-force-workspace)
      FORCE_WORKSPACE=0
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$CLI_KIND" in
  innercc|claude)
    ;;
  *)
    printf 'Unsupported --cli: %s\n' "$CLI_KIND" >&2
    exit 2
    ;;
esac

if ! venv_ready; then
  bash "$RUNTIME_ROOT/bootstrap_env.sh"
fi

PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

if [ -z "$ENV_FILE" ]; then
  ENV_FILE="$(pick_first_file \
    "$REPO_ROOT/config/swe-evo.env" \
    "$HOME/.config/swe-evo/minimax.env" \
    "/home/wt/sss_repos/sss_auto/SWE-EVO/config/swe-evo.env" \
  )"
fi

if [ ! -f "$ENV_FILE" ]; then
  printf 'Missing env file: %s\n' "$ENV_FILE" >&2
  exit 1
fi

if [ -z "$CLI_BIN" ]; then
  CLI_BIN="$(pick_cli_bin "$CLI_KIND")"
fi

if [ ! -x "$CLI_BIN" ] && ! command -v "$CLI_BIN" >/dev/null 2>&1; then
  printf 'Missing CLI binary: %s\n' "$CLI_BIN" >&2
  exit 1
fi
CLI_BIN="$(resolve_cli_bin "$CLI_BIN")"

MANIFEST_NAME="$(basename "$MANIFEST_PATH" .txt)"
RUN_STAMP="${RUN_STAMP:-$(date +%Y%m%d-%H%M%S)-${MANIFEST_NAME}-${CLI_KIND}}"
RUN_ROOT="$REPO_ROOT/official48_runs/$RUN_STAMP"
INPUT_ROOT="$RUN_ROOT/input"
INSTANCE_DIR="$INPUT_ROOT/output_final"
SETTINGS_FILE="$RUN_ROOT/config/claude.direct.settings.json"
AGENT_NAME="innercc-cli"

if [ "$CLI_KIND" = "claude" ]; then
  AGENT_NAME="claude-code"
fi

mkdir -p "$RUN_ROOT" "$INPUT_ROOT" "$RUN_ROOT/config"

"$PYTHON_BIN" "$RUNTIME_ROOT/build_claude_direct_settings.py" \
  --env-file "$ENV_FILE" \
  --output "$SETTINGS_FILE" \
  --model "$MODEL_NAME" \
  --overwrite

MATERIALIZE_CMD=(
  "$PYTHON_BIN" "$RUNTIME_ROOT/materialize_subset_instances.py"
  --manifest "$MANIFEST_PATH"
  --source-dir "$REPO_ROOT/official48_source/output_final"
  --dest-dir "$INSTANCE_DIR"
  --mode "$COPY_MODE"
)
if [ "$LIMIT" != "0" ]; then
  MATERIALIZE_CMD+=(--limit "$LIMIT")
fi
"${MATERIALIZE_CMD[@]}"

cat >"$RUN_ROOT/metadata.json" <<EOF
{
  "display_name": "$(printf '%s' "$RUN_DISPLAY_NAME")",
  "cli_kind": "$(printf '%s' "$CLI_KIND")",
  "cli_bin": "$(printf '%s' "$CLI_BIN")",
  "agent_name": "$(printf '%s' "$AGENT_NAME")",
  "model": "$(printf '%s' "$MODEL_NAME")",
  "manifest": "$(printf '%s' "$MANIFEST_PATH")",
  "instances_dir": "$(printf '%s' "$INSTANCE_DIR")",
  "settings_file": "$(printf '%s' "$SETTINGS_FILE")",
  "env_file": "$(printf '%s' "$ENV_FILE")"
}
EOF

printf '[pipeline] run_root=%s\n' "$RUN_ROOT"
printf '[pipeline] cli=%s bin=%s\n' "$CLI_KIND" "$CLI_BIN"
printf '[pipeline] manifest=%s\n' "$MANIFEST_PATH"

"$PYTHON_BIN" "$RUNTIME_ROOT/run_official48_eval_worker.py" \
  "$RUN_ROOT" "$EVAL_MAX_CONCURRENCY" \
  --retry-missing-report \
  --instances-dir "$INSTANCE_DIR" \
  > >(tee -a "$RUN_ROOT/eval_worker.log") 2>&1 &
EVAL_PID=$!

cleanup() {
  if [ -n "${EVAL_PID:-}" ]; then
    kill "$EVAL_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

INFER_CMD=(
  "$PYTHON_BIN" "$RUNTIME_ROOT/run_official48_subset_infer.py"
  --output-dir "$RUN_ROOT/infer"
  --instances-dir "$INSTANCE_DIR"
  --cli-bin "$CLI_BIN"
  --settings-file "$SETTINGS_FILE"
  --env-file "$ENV_FILE"
  --model "$MODEL_NAME"
  --agent-name "$AGENT_NAME"
  --max-concurrency "$INFER_MAX_CONCURRENCY"
  --cli-timeout-seconds "$CLI_TIMEOUT_SECONDS"
)
if [ "$FORCE_WORKSPACE" -eq 1 ]; then
  INFER_CMD+=(--force-workspace)
fi
if [ "$RESUME" -eq 1 ]; then
  INFER_CMD+=(--resume)
fi
if [ -n "$MAX_TURNS" ]; then
  INFER_CMD+=(--max-turns "$MAX_TURNS")
fi

"${INFER_CMD[@]}"

wait "$EVAL_PID"
trap - EXIT

"$PYTHON_BIN" "$RUNTIME_ROOT/summarize_official48_run.py" \
  --run-root "$RUN_ROOT" \
  --instances-dir "$INSTANCE_DIR"

LATEST_LINK="$REPO_ROOT/official48_runs/latest-${MANIFEST_NAME}-${CLI_KIND}"
rm -f "$LATEST_LINK"
ln -s "$RUN_ROOT" "$LATEST_LINK"

printf '[pipeline] completed run_root=%s\n' "$RUN_ROOT"
printf '[pipeline] summary=%s\n' "$RUN_ROOT/analysis/summary.json"
