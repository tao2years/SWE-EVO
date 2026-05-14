#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
RUNTIME_ROOT="$SCRIPT_DIR"
cd "$REPO_ROOT"

usage() {
  cat <<'EOF'
Usage:
  ./run_project_coverage_7_pipeline_router.sh [--cli innercc|claude] [options]
EOF
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

ensure_router() {
  local router_root="$1"
  local router_api_base="$2"
  local sessions
  sessions="$(tmux ls 2>/dev/null || true)"
  if printf '%s\n' "$sessions" | grep -q 'sss-auto-llm-router-proxy:' && printf '%s\n' "$sessions" | grep -q 'sss-auto-llm-router-web:'; then
    if curl -fsS -m 5 "$router_api_base/api/sessions" >/dev/null 2>&1; then
      return
    fi
  fi
  (
    cd "$router_root"
    SESSION_PREFIX=sss-auto-llm-router \
    ANTHROPIC_UPSTREAM_URL=https://api.minimaxi.com/anthropic \
    OPENAI_UPSTREAM_URL=https://api.minimaxi.com/v1 \
    bash "$router_root/scripts/start-prod.sh"
  )
}

CLI_KIND="${CLI_KIND:-innercc}"
MANIFEST_PATH="$REPO_ROOT/config/subsets/project-coverage-7.txt"
LIMIT="${LIMIT:-0}"
INFER_MAX_CONCURRENCY="${INFER_MAX_CONCURRENCY:-3}"
EVAL_MAX_CONCURRENCY="${EVAL_MAX_CONCURRENCY:-3}"
CLI_TIMEOUT_SECONDS="${CLI_TIMEOUT_SECONDS:-5400}"
ROUTER_READY_TIMEOUT_SECONDS="${ROUTER_READY_TIMEOUT_SECONDS:-120}"
RUN_HEARTBEAT_TIMEOUT_SECONDS="${RUN_HEARTBEAT_TIMEOUT_SECONDS:-3600}"
RUN_HEARTBEAT_POLL_SECONDS="${RUN_HEARTBEAT_POLL_SECONDS:-60}"
RUN_HEARTBEAT_KILL_GRACE_SECONDS="${RUN_HEARTBEAT_KILL_GRACE_SECONDS:-30}"
MODEL_NAME="${MODEL_NAME:-${INNERCC_MODEL:-MiniMax-M2.5-highspeed}}"
CLI_BIN="${CLI_BIN:-}"
ENV_FILE="${ENV_FILE:-}"
SETTINGS_FILE="${SETTINGS_FILE:-}"
MAX_TURNS="${MAX_TURNS:-}"
SKILL_NAME="${SKILL_NAME:-}"
SKILL_HINT="${SKILL_HINT:-}"
DISABLE_SLASH_COMMANDS="${DISABLE_SLASH_COMMANDS:-0}"
COPY_MODE="${COPY_MODE:-copy}"
RUN_DISPLAY_NAME="${RUN_DISPLAY_NAME:-}"
ROUTER_ROOT="${ROUTER_ROOT:-$REPO_ROOT/../llm_router}"
ROUTER_API_BASE="${ROUTER_API_BASE:-http://127.0.0.1:18783}"
RESUME=0
FORCE_WORKSPACE=1

while [ $# -gt 0 ]; do
  case "$1" in
    --cli) CLI_KIND="$2"; shift 2 ;;
    --manifest) MANIFEST_PATH="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --cli-bin) CLI_BIN="$2"; shift 2 ;;
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --settings-file) SETTINGS_FILE="$2"; shift 2 ;;
    --model) MODEL_NAME="$2"; shift 2 ;;
    --max-turns) MAX_TURNS="$2"; shift 2 ;;
    --skill-name) SKILL_NAME="$2"; shift 2 ;;
    --skill-hint) SKILL_HINT="$2"; shift 2 ;;
    --disable-slash-commands) DISABLE_SLASH_COMMANDS=1; shift ;;
    --infer-max-concurrency) INFER_MAX_CONCURRENCY="$2"; shift 2 ;;
    --eval-max-concurrency) EVAL_MAX_CONCURRENCY="$2"; shift 2 ;;
    --cli-timeout-seconds) CLI_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --heartbeat-timeout-seconds) RUN_HEARTBEAT_TIMEOUT_SECONDS="$2"; shift 2 ;;
    --heartbeat-poll-seconds) RUN_HEARTBEAT_POLL_SECONDS="$2"; shift 2 ;;
    --heartbeat-kill-grace-seconds) RUN_HEARTBEAT_KILL_GRACE_SECONDS="$2"; shift 2 ;;
    --copy-mode) COPY_MODE="$2"; shift 2 ;;
    --router-root) ROUTER_ROOT="$2"; shift 2 ;;
    --router-api-base) ROUTER_API_BASE="$2"; shift 2 ;;
    --resume) RESUME=1; shift ;;
    --no-force-workspace) FORCE_WORKSPACE=0; shift ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

if ! venv_ready; then
  bash "$RUNTIME_ROOT/bootstrap_env.sh"
fi

PYTHON_BIN="$REPO_ROOT/.venv/bin/python"

write_lifecycle() {
  local state="$1"
  shift || true
  "$PYTHON_BIN" - "$RUN_ROOT" "$state" "$@" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

run_root = Path(sys.argv[1])
state = sys.argv[2]
path = run_root / "run_lifecycle.json"
payload = {}
if path.exists():
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}

for raw in sys.argv[3:]:
    if "=" not in raw:
        continue
    key, value = raw.split("=", 1)
    if value == "__DELETE__":
        payload.pop(key, None)
        continue
    if value.startswith("json:"):
        try:
            payload[key] = json.loads(value[5:])
            continue
        except Exception:
            pass
    payload[key] = value

payload["state"] = state
payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
path.write_text(f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n", encoding="utf-8")
PY
}

lifecycle_state() {
  "$PYTHON_BIN" - "$RUN_ROOT" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) / "run_lifecycle.json"
if not path.exists():
    print("")
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("")
    raise SystemExit(0)
print(payload.get("state", ""))
PY
}

lifecycle_is_terminal() {
  local state
  state="$(lifecycle_state)"
  case "$state" in
    completed|timed_out|terminated|failed|interrupted)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

kill_process_group() {
  local signal_name="$1"
  local pid="${2:-}"
  if [ -z "$pid" ] || [ "$pid" -le 0 ] 2>/dev/null; then
    return
  fi
  kill "-$signal_name" -- "-$pid" >/dev/null 2>&1 || kill "-$signal_name" "$pid" >/dev/null 2>&1 || true
}

if [ -z "$ENV_FILE" ]; then
  ENV_FILE="$(pick_first_file "$REPO_ROOT/config/swe-evo.env" "$HOME/.config/swe-evo/minimax.env")"
fi
if [ -z "$SETTINGS_FILE" ]; then
  SETTINGS_FILE="$(pick_first_file "$REPO_ROOT/config/claude.settings.json" "$HOME/.claude/settings.json")"
fi
if [ -z "$CLI_BIN" ]; then
  CLI_BIN="$(pick_cli_bin "$CLI_KIND")"
fi
if [ ! -x "$CLI_BIN" ] && ! command -v "$CLI_BIN" >/dev/null 2>&1; then
  printf 'Missing CLI binary: %s\n' "$CLI_BIN" >&2
  exit 1
fi
CLI_BIN="$(resolve_cli_bin "$CLI_BIN")"

ensure_router "$ROUTER_ROOT" "$ROUTER_API_BASE"

MANIFEST_NAME="$(basename "$MANIFEST_PATH" .txt)"
RUN_STAMP="${RUN_STAMP:-$(date +%Y%m%d-%H%M%S)-${MANIFEST_NAME}-${CLI_KIND}-router}"
RUN_ROOT="$REPO_ROOT/official48_runs/$RUN_STAMP"
INPUT_ROOT="$RUN_ROOT/input"
INSTANCE_DIR="$INPUT_ROOT/output_final"
AGENT_NAME="innercc-cli"
if [ "$CLI_KIND" = "claude" ]; then
  AGENT_NAME="claude-code"
fi

mkdir -p "$RUN_ROOT" "$INPUT_ROOT"

"$PYTHON_BIN" "$RUNTIME_ROOT/materialize_subset_instances.py" \
  --manifest "$MANIFEST_PATH" \
  --source-dir "$REPO_ROOT/official48_source/output_final" \
  --dest-dir "$INSTANCE_DIR" \
  --mode "$COPY_MODE" \
  ${LIMIT:+--limit "$LIMIT"}

cat >"$RUN_ROOT/metadata.json" <<EOF
{
  "display_name": "$(printf '%s' "$RUN_DISPLAY_NAME")",
  "mode": "router",
  "cli_kind": "$(printf '%s' "$CLI_KIND")",
  "cli_bin": "$(printf '%s' "$CLI_BIN")",
  "agent_name": "$(printf '%s' "$AGENT_NAME")",
  "model": "$(printf '%s' "$MODEL_NAME")",
  "skill_name": "$(printf '%s' "$SKILL_NAME")",
  "disable_slash_commands": $DISABLE_SLASH_COMMANDS,
  "manifest": "$(printf '%s' "$MANIFEST_PATH")",
  "instances_dir": "$(printf '%s' "$INSTANCE_DIR")",
  "settings_file": "$(printf '%s' "$SETTINGS_FILE")",
  "env_file": "$(printf '%s' "$ENV_FILE")",
  "router_root": "$(printf '%s' "$ROUTER_ROOT")",
  "router_api_base": "$(printf '%s' "$ROUTER_API_BASE")"
}
EOF

STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
write_lifecycle running \
  "started_at=$STARTED_AT" \
  "heartbeat_timeout_seconds=json:$RUN_HEARTBEAT_TIMEOUT_SECONDS"

setsid "$PYTHON_BIN" "$RUNTIME_ROOT/run_official48_eval_worker.py" \
  "$RUN_ROOT" "$EVAL_MAX_CONCURRENCY" \
  --retry-missing-report \
  --instances-dir "$INSTANCE_DIR" \
  > >(tee -a "$RUN_ROOT/eval_worker.log") 2>&1 &
EVAL_PID=$!
INFER_PID=""
WATCHDOG_PID=""
INFER_RC=""
EVAL_RC=""

cleanup() {
  local exit_code=$?
  if [ -n "${WATCHDOG_PID:-}" ]; then
    kill "$WATCHDOG_PID" >/dev/null 2>&1 || true
    wait "$WATCHDOG_PID" >/dev/null 2>&1 || true
  fi
  kill_process_group TERM "${INFER_PID:-}"
  if [ -n "${EVAL_PID:-}" ]; then
    kill_process_group TERM "$EVAL_PID"
  fi
  if [ "$exit_code" -ne 0 ] && ! lifecycle_is_terminal; then
    write_lifecycle interrupted \
      "reason=nonzero_exit" \
      "infer_exit_code=json:${INFER_RC:-null}" \
      "eval_exit_code=json:${EVAL_RC:-null}"
  fi
}
trap cleanup EXIT INT TERM

INFER_CMD=(
  "$PYTHON_BIN"
  "$RUNTIME_ROOT/legacy/run_innercc_infer_official48.py"
  "--output-dir" "$RUN_ROOT/infer"
  "--instances-dir" "$INSTANCE_DIR"
  "--cli-bin" "$CLI_BIN"
  "--settings-file" "$SETTINGS_FILE"
  "--env-file" "$ENV_FILE"
  "--model" "$MODEL_NAME"
  "--agent-name" "$AGENT_NAME"
  "--max-concurrency" "$INFER_MAX_CONCURRENCY"
  "--cli-timeout-seconds" "$CLI_TIMEOUT_SECONDS"
  "--router-api-base" "$ROUTER_API_BASE"
  "--router-ready-timeout-seconds" "$ROUTER_READY_TIMEOUT_SECONDS"
)
if [ "$FORCE_WORKSPACE" -eq 1 ]; then
  INFER_CMD+=("--force-workspace")
fi
if [ "$RESUME" -eq 1 ]; then
  INFER_CMD+=("--resume")
fi
if [ -n "$MAX_TURNS" ]; then
  INFER_CMD+=("--max-turns" "$MAX_TURNS")
fi
if [ -n "$SKILL_NAME" ]; then
  INFER_CMD+=("--skill-name" "$SKILL_NAME")
fi
if [ -n "$SKILL_HINT" ]; then
  INFER_CMD+=("--skill-hint" "$SKILL_HINT")
fi
if [ "$DISABLE_SLASH_COMMANDS" -eq 1 ]; then
  INFER_CMD+=("--disable-slash-commands")
fi

PYTHONPATH="$RUNTIME_ROOT${PYTHONPATH:+:$PYTHONPATH}" setsid "${INFER_CMD[@]}" &
INFER_PID=$!

"$PYTHON_BIN" "$RUNTIME_ROOT/watch_run_heartbeat.py" \
  --run-root "$RUN_ROOT" \
  --infer-pid "$INFER_PID" \
  --eval-pid "$EVAL_PID" \
  --heartbeat-timeout-seconds "$RUN_HEARTBEAT_TIMEOUT_SECONDS" \
  --poll-interval-seconds "$RUN_HEARTBEAT_POLL_SECONDS" \
  --kill-grace-seconds "$RUN_HEARTBEAT_KILL_GRACE_SECONDS" &
WATCHDOG_PID=$!

set +e
wait "$INFER_PID"
INFER_RC=$?
wait "$EVAL_PID"
EVAL_RC=$?
set -e

if [ -n "${WATCHDOG_PID:-}" ]; then
  kill "$WATCHDOG_PID" >/dev/null 2>&1 || true
  wait "$WATCHDOG_PID" >/dev/null 2>&1 || true
  WATCHDOG_PID=""
fi

trap - EXIT

"$PYTHON_BIN" "$RUNTIME_ROOT/summarize_official48_run.py" \
  --run-root "$RUN_ROOT" \
  --instances-dir "$INSTANCE_DIR"

if lifecycle_is_terminal; then
  exit 1
fi

if [ "$INFER_RC" -ne 0 ] || [ "$EVAL_RC" -ne 0 ]; then
  write_lifecycle interrupted \
    "reason=nonzero_exit" \
    "infer_exit_code=json:$INFER_RC" \
    "eval_exit_code=json:$EVAL_RC"
  exit 1
fi

FINISHED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
write_lifecycle completed \
  "finished_at=$FINISHED_AT" \
  "infer_exit_code=json:$INFER_RC" \
  "eval_exit_code=json:$EVAL_RC"
