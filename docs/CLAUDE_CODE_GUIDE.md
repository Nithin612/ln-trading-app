# Working with Claude Code on this project

This guide is for the human (you) — how to set up VS Code + Claude Code and steer it effectively through the 12-phase build.

---

## One-time setup

1. **Install Claude Code in VS Code**
   - Open VS Code → Extensions → search "Claude Code" → install
   - Sign in with your Anthropic account
   - Verify by opening the Claude Code panel — you should see a chat input

2. **Clone / unzip this project skeleton** into a folder, e.g. `~/dev/trading-platform/`

3. **Open the project in VS Code**: `code ~/dev/trading-platform`

4. **Start the infrastructure** (in VS Code's terminal):
   ```bash
   cp .env.example .env
   # Edit .env: replace JWT_SECRET_KEY with `openssl rand -hex 32`
   make up
   make db-extensions   # verify TimescaleDB loaded
   ```

5. **Open Claude Code panel** and paste this first message:

   > Read `CLAUDE.md` and all files under `docs/`. Confirm you understand the project, the tech stack, and the 12-phase plan. Then summarize Phase 1 in your own words and propose the first 3 file changes you'd make to start it. Wait for my approval before writing any code.

   This forces Claude Code to load context fully before touching code, and gives you a checkpoint before work starts.

---

## Pointing Claude Code at your existing rough code

If you have prior work on local that might have useful pieces:

1. Tell Claude Code the absolute path explicitly:
   > My rough prototype lives at `/home/nithin/code/agent/antigravity/trading/`. Before starting Phase 1, list the files there, identify anything related to authentication or user management or setup, and tell me which pieces (if any) are worth salvaging. Do not copy code yet — just analyze and report.

2. Claude Code will use `find`, `grep`, and read the files. It produces a salvage report.

3. You decide what to lift. Then:
   > OK, port the password-hashing utility from the prototype but rewrite it to use bcrypt instead of MD5. Then add tests. Match our coding conventions in `CLAUDE.md`.

This separates *analysis* from *copying*, which prevents silent ports of broken code.

---

## The phase workflow (every phase, same dance)

Each phase follows the same 6 steps. Phase 1 is the template.

### Step 1: spec acknowledgement
> Read `docs/PHASES.md` Phase 1 and `docs/DATABASE_SCHEMA.sql` for the users + user_sessions tables. Summarize what you understand. List any ambiguities.

### Step 2: design proposal
> Propose:
> - File structure for Phase 1 (backend + frontend)
> - Order of work (model → migration → service → API → tests → frontend)
> - Which third-party libs you'll add (pin versions)
> Wait for my approval.

### Step 3: model + migration + tests
> Implement the User model in `backend/app/db/models/user.py`, generate the Alembic migration, write tests for the model. Run tests and confirm green before moving on.

### Step 4: API layer + tests
> Implement `/auth/login`, `/auth/refresh`, `/auth/logout`, and `/users/` CRUD. Write integration tests using FastAPI TestClient. Run them. Show me failing tests if any.

### Step 5: frontend
> Build the login page and the admin user-management page. Use shadcn/ui components. Add unit tests for the auth hook and integration tests for the pages.

### Step 6: end-to-end smoke test + commit
> Bring up the full stack. Walk me through testing the login flow manually. After I confirm it works, write a CHANGELOG.md entry and commit with message `feat(auth): phase 1 complete - login, JWT, user CRUD`.

---

## Anti-patterns — call Claude Code out on these

- **Code without tests.** Anytime Claude Code says "I'll write tests next" but then moves to the next feature, stop it: "Tests now, before next feature."
- **Implicit changes.** If a refactor touches 8 files but the description says 3, ask: "List all files you modified, and why."
- **`# TODO` comments.** Reject these. Either implement now or leave a real GitHub issue.
- **Big bang commits.** Each commit should be one logical change. If Claude Code wants to commit "Phase 1 done" with 80 files changed, ask it to break the commit into 4-6 logical pieces.
- **Float for prices.** Anywhere you see `float` for money, reject. Must be `Decimal` in Python, `Numeric` in DB.
- **Look-ahead bias in backtests.** Watch like a hawk for any indicator computed using *future* candles. Test for this explicitly in Phase 5.
- **"Works on my machine"** — every PR must include the exact commands to reproduce. Push back if not.

---

## When stuck or unsure

Three patterns that unstick most problems:

1. **"Show me before doing"** — ask Claude Code to write the proposed code in a comment block first, before writing the file. You review, then green-light.

2. **"Make it fail first"** — for any new feature, write the test that *will* fail first. Watch it fail. Then make it pass. This proves the test is real.

3. **"Reduce surface area"** — if a 200-line file is producing confusing bugs, ask Claude Code to extract the buggy bit into its own file with a tighter interface, then re-test in isolation.

---

## Phase-by-phase tips

### Phase 1 (auth)
Don't let Claude Code skip CSRF and refresh-token rotation. Both are easy to forget and important.

### Phase 4 (EOD ingestion)
NSE has rate limits and occasionally changes bhavcopy format. Make the parser tolerant — log unexpected columns rather than crash.

### Phase 5 (signal engine) — most important
- Insist on golden-value tests: hand-pick 10 historical setups and verify the engine scores them as expected.
- After every weight change, re-run the full backtest. If win rate moves by more than 5%, that's a significant change — review intentionally.
- Use `vectorbt` for backtesting; it's 100x faster than naive loops and handles look-ahead bias correctly.

### Phase 7 (live data)
WebSocket connections drop. Plan for reconnect-with-gap-fill from day one — query historical candles to fill the gap, then resume the stream. Don't trust the broker SDK's "auto-reconnect" without testing it.

### Phase 8 (paper trading)
The 30-day rule is real. Don't enable Phase 12 unless paper trading shows actual profit *without* manual intervention. The discipline test is as important as the strategy test.

### Phase 12 (live)
Read your Kite app limits. Static IP setup is non-negotiable. Test the kill switch first, then the orders.

---

## Communication template for hand-off

When you want Claude Code to pause and you'll come back later, use this template:

> Stop here. Summarize what's done, what's in-progress, and what's next in `docs/CURRENT_STATE.md`. Include any decisions made today that future you would forget. Don't write more code until I come back.

When you come back:

> Read `docs/CURRENT_STATE.md` and continue from where we left off. Ask me before changing direction.
