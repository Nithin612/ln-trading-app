#!/usr/bin/env bash
# PreToolUse hook (Edit|Write): protect load-bearing files from silent edits.
# Exit 2 = BLOCK. The block message tells Claude why and what to do instead.

set -uo pipefail

INPUT="$(cat)"
FILE="$(printf '%s' "$INPUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)"
[ -z "$FILE" ] && exit 0

case "$FILE" in
  */docs/SIGNAL_ENGINE.md)
    echo "BLOCKED: docs/SIGNAL_ENGINE.md is the user's trading edge (protected spec)." >&2
    echo "Spec changes require an explicit user instruction in THIS session +" >&2
    echo "a backtest regression run (SIGNAL_ENGINE.md §8). Ask the user first;" >&2
    echo "they can edit it manually or temporarily lift this guard." >&2
    exit 2 ;;
  */backend/alembic/versions/*.py)
    if [ -f "$FILE" ]; then
      echo "BLOCKED: $FILE is an existing migration — applied migrations are immutable." >&2
      echo "Create a NEW alembic revision instead of editing history." >&2
      exit 2
    fi ;;  # new migration files are fine
  */.env|*/.env.*)
    case "$FILE" in
      *.env.example) ;;  # the template is editable
      *)
        echo "BLOCKED: .env files hold secrets and are user-managed." >&2
        echo "Document the new variable in .env.example and ask the user to set it." >&2
        exit 2 ;;
    esac ;;
esac

exit 0
