#!/usr/bin/env bash
# PostToolUse hook (Edit|Write): auto-format + lint the files Claude just touched.
# Receives hook JSON on stdin; file paths also arrive via $CLAUDE_FILE_PATHS.
# Non-blocking by design: formatting failures print but never abort the edit
# (exit 0 always) — correctness gates live in `make check`, not here.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FILES="${CLAUDE_FILE_PATHS:-}"
[ -z "$FILES" ] && exit 0

py_files=()
ts_files=()
rs_files=()

for f in $FILES; do
  [ -f "$f" ] || continue
  case "$f" in
    *.py) py_files+=("$f") ;;
    *.ts|*.tsx|*.css|*.json) case "$f" in */node_modules/*) ;; *) ts_files+=("$f") ;; esac ;;
    *.rs) rs_files+=("$f") ;;
  esac
done

if [ ${#py_files[@]} -gt 0 ] && [ -x "$REPO_ROOT/backend/.venv/bin/ruff" ]; then
  "$REPO_ROOT/backend/.venv/bin/ruff" format --quiet "${py_files[@]}" 2>/dev/null
  "$REPO_ROOT/backend/.venv/bin/ruff" check --fix --quiet "${py_files[@]}" 2>/dev/null
fi

if [ ${#ts_files[@]} -gt 0 ] && [ -d "$REPO_ROOT/frontend/node_modules" ]; then
  (cd "$REPO_ROOT/frontend" && npx --no-install prettier --write --log-level=silent "${ts_files[@]}" 2>/dev/null)
fi

if [ ${#rs_files[@]} -gt 0 ] && command -v rustfmt >/dev/null 2>&1; then
  rustfmt --edition 2021 "${rs_files[@]}" 2>/dev/null
fi

exit 0
