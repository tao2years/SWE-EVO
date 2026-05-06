#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REPO_ROOT/requirements.swe-evo.txt"

if command -v npm >/dev/null 2>&1; then
  (cd "$REPO_ROOT" && npm ci)
else
  printf 'npm not found, skipped frontend install.\n'
fi

cat <<EOF
Bootstrap complete.

Next steps:
1. cp config/claude.settings.example.json config/claude.settings.json
2. cp config/swe-evo.example.env config/swe-evo.env
3. Edit the copied files with your real router URL, model, and credentials.
4. Activate the venv: source "$VENV_DIR/bin/activate"
EOF
