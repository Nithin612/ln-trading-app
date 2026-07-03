# Working with Claude Code on this project

Guide for the human — how to steer Claude Code through the v2 upgrade.
Updated for the Phase-0 workbench (2026-07-03): most of the discipline that
used to live in this file is now *enforced by the repo itself* (hooks,
agents, rules, skills under `.claude/`), so this guide is short.

## Session start

Nothing special to paste anymore: `CLAUDE.md` carries current truth and is
loaded automatically. For a work session, name the phase or task —
Claude reads `docs/PHASES.md` for status and `docs/UPGRADE_PLAN.md` for the
why. Useful commands: `make up` (infra), `make check` (full gate).

## What the workbench does for you

- **Hooks** (`.claude/settings.json` + `.claude/hooks/`):
  - auto-format+lint every file Claude edits (ruff / prettier / rustfmt);
  - block destructive commands (recursive rm outside /tmp, DROP/TRUNCATE,
    `docker compose down -v`, volume rm, force-push, `git reset --hard`);
  - protect `docs/SIGNAL_ENGINE.md` (your edge), applied alembic
    migrations, and `.env` from edits. If Claude reports "the hook blocked
    me", that's the system working — you can always run a command yourself
    with `!` or edit a protected file manually.
- **Review agents** (`.claude/agents/`) — ask for them by name, or expect
  Claude to run them before calling work done:
  - `quant-verifier` — any change to analysis/signals/backtest/engine is
    checked formula-by-formula against SIGNAL_ENGINE.md;
  - `bug-hunter` — pipeline/async/broker changes (this one found 9 real
    defects in its first run, 3 confirmed with reproductions);
  - `ui-reviewer` · `perf-auditor` · `test-guardian`.
  Every agent must cite file:line + how it verified — reject vague reports.
- **Skills**: `/vertical-slice` (how features get built), `/phase-gate`
  (phase exit ritual — run before declaring a phase done), `/signal-audit`
  ("why did/didn't X fire?" gets a recomputed, evidence-backed answer),
  `/perf-bench` (numbers into docs/PERFORMANCE.md).

## Steering tips that still matter

- One phase at a time; inside a phase, vertical slices. If Claude proposes
  jumping ahead, say no.
- When you question a signal, ask for `/signal-audit SYMBOL` — you'll get
  the hand-recomputed factor table, not a story.
- Any change that moves backtest win-rate/Sharpe/drawdown by >5% stops and
  asks you (SIGNAL_ENGINE.md §8). Expect that question; don't let it be
  skipped.
- Prototype salvage (antigravity): analysis first, then explicit approval
  to port, always rewritten with tests — never silent copies.
- End of every phase: check `docs/phases/phase-NN-*.md` exists and tells
  the truth. That file is for future-you.

## Anti-patterns (unchanged, still reject on sight)

Code without tests · implicit changes not in the diff summary · TODO
comments instead of issues · float for money · look-ahead in backtests ·
"works on my machine" without exact commands · big-bang commits.

## Phase-specific reminders

- **Phase 1 (Rust core):** the adjudication checkpoint (volume-direction,
  RSI bands, SL canon, window canon, fill realism) needs YOUR decisions —
  each option comes with its backtest impact. Golden fixtures are generated
  only after you decide.
- **Phase 3 (realtime):** purchase the Kite Connect subscription before
  this phase starts; daily token refresh (~6 AM IST expiry) becomes part of
  the routine. The soak week runs during live market hours.
- **Phase 4 (F&O):** bring your masterclass option-selling rules to the
  calibration session; conservative defaults trade until then.
- **Phase 7 (live):** static IP, kill-switch test, and the 30-day paper
  gate (restarted 2026-07-03) are all hard blockers. No exceptions.
