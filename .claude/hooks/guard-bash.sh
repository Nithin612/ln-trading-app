#!/usr/bin/env bash
# PreToolUse hook (Bash): block destructive commands before they run.
# Reads the hook JSON from stdin; the command string is at .tool_input.command.
# Exit 2 = BLOCK (message on stderr is shown to Claude). Exit 0 = allow.

set -uo pipefail

INPUT="$(cat)"
CMD="$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)"
[ -z "$CMD" ] && exit 0

block() {
  echo "BLOCKED by .claude/hooks/guard-bash.sh: $1" >&2
  echo "If this is genuinely intended, the user can run it manually with ! <cmd>." >&2
  exit 2
}

# Recursive force-remove outside /tmp (rm -rf, rm -fr, rm -r -f ...)
if printf '%s' "$CMD" | grep -qE '(^|[;&|]\s*)rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r|-r\s+-f|-f\s+-r)\b'; then
  printf '%s' "$CMD" | grep -qE 'rm\s+(-[a-zA-Z]+\s+)+(/tmp|"?\$\{?TMPDIR)' || \
    block "recursive force delete"
fi

# Destructive SQL through any client
printf '%s' "$CMD" | grep -qiE '\b(DROP\s+(TABLE|DATABASE|SCHEMA)|TRUNCATE\s+TABLE|TRUNCATE\s+[a-z_"]+\s*(CASCADE|RESTART|;|$))' && \
  block "destructive SQL (DROP/TRUNCATE) — use an alembic migration instead"

# Wiping docker volumes (the DB lives there)
printf '%s' "$CMD" | grep -qE 'docker\s+(volume\s+(rm|prune)|compose\s+down\s+(.*\s)?(-v|--volumes))' && \
  block "docker volume removal would destroy the database"

# Git history rewrites / force pushes
printf '%s' "$CMD" | grep -qE 'git\s+push\s+(.*\s)?(--force|-f)\b' && \
  block "git force-push"
printf '%s' "$CMD" | grep -qE 'git\s+reset\s+--hard\b' && \
  block "git reset --hard discards uncommitted work — stash or commit first"

# Editing the protected spec via shell redirection
printf '%s' "$CMD" | grep -qE '>\s*docs/SIGNAL_ENGINE\.md' && \
  block "docs/SIGNAL_ENGINE.md is the protected edge spec"

exit 0
