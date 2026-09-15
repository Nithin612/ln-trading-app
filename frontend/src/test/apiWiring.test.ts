/// <reference types="node" />
// ⚠ File-scoped node types, for the same reason `tokenContrast.test.ts` gives: widening
// the whole app project so one test can read files would let node globals leak into
// browser code.
// ⛔ And NOT Vite's `?raw` — vitest's transform makes an import silently resolve to an
// empty string, which here would mean "zero API functions found, nothing unwired, PASS".
// The canary below exists precisely because that shape has already shipped once (§71a).
import { readFileSync, readdirSync } from 'node:fs'
import { extname, join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * V6 / A5 — the BUILT-NOT-WIRED lint.
 *
 * ⭐ WHY THIS EXISTS. It is one of the project's two recurring defect shapes: a capability
 * is written, reviewed and merged, and nothing ever calls it. `filingsApi.getGuard` is the
 * case A5 names, and the reason it went unnoticed is that every check we own was green —
 * the function typechecks, lints, and is covered by nothing that asserts it is REACHED.
 *
 * ⚠ It answers A5's "what observes this?" question mechanically for one layer: an API
 * client function nobody calls is a backend endpoint nobody reaches.
 *
 * ⛔ SCOPE, stated so it is not over-read. This is a TEXT search for the function's name
 * outside `lib/api`. It cannot see a call assembled dynamically (`api[name]()`), and a
 * name that merely COLLIDES with an unrelated identifier elsewhere will read as wired. It
 * is a tripwire for the obvious case, not proof of reachability.
 */

const API_DIR = resolve(__dirname, '../lib/api')
const SRC_DIR = resolve(__dirname, '..')

/**
 * Members whose value is a function: `name: (…) =>`, `name: async (…) =>`, `async name(…)`.
 * Two-space indent anchors them to a member of an exported `const xApi = { … }` object
 * rather than a nested helper.
 */
const FUNC_MEMBER = /^ {2}(?:async\s+)?(\w+)\s*(?::\s*(?:async\s*)?\(|\()/gm

/**
 * ⚠ SHRINK-ONLY RATCHET, the same contract as `tokenContrast.test.ts`: the failing set is
 * recorded EXACTLY, so a NEW unwired function fails the suite — and so does wiring one up
 * without deleting its line here. The list can only get shorter, deliberately.
 *
 * ⛔ These are NOT approved. They are debts with a name against them.
 */
const KNOWN_UNWIRED: Readonly<Record<string, string>> = {
  // A5's own example: the filings guard endpoint exists on the backend and nothing in the
  // UI has ever called it.
  getGuard: 'filings.ts — built, never wired; the case A5 is named after',
  // Strategy Lab can list runs but has no per-run drill-in, so the detail fetch is unused.
  getRun: 'strategy.ts — no per-run detail view exists to call it',
  // ⭐ Found BY this lint, and only once test files were excluded from the corpus:
  // `WatchlistsPage.test.tsx` mocks `rename`, so the suite asserts a MOCK while the UI
  // offers no way to rename a watchlist at all. The endpoint and the client both exist.
  // The purest instance of A5's "an acceptance test that can pass while the capability is
  // unreachable is not an acceptance test".
  rename: 'watchlists.ts — no rename control in the UI; only ever mocked in a test',
}

function readAll(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) readAll(path, out)
    else if (['.ts', '.tsx'].includes(extname(entry.name))) out.push(path)
  }
  return out
}

describe('API wiring — every client function has a caller (V6/A5)', () => {
  const apiFiles = readdirSync(API_DIR).filter((f) => f.endsWith('.ts'))
  const functions = new Map<string, string>()
  for (const file of apiFiles) {
    const text = readFileSync(join(API_DIR, file), 'utf8')
    for (const m of text.matchAll(FUNC_MEMBER)) functions.set(m[1], file)
  }

  // ⛔ `src/test` is excluded from the corpus, and that is a DESIGN DECISION, not a
  // convenience. A function called only from a test is NOT wired — it is exactly A5's
  // "an acceptance test that can pass while the capability is unreachable is not an
  // acceptance test". Counting test files would also have made this lint find its own
  // allowlist and declare every debt paid, which is how it first failed.
  const outside = readAll(SRC_DIR)
    .filter(
      (p) => !p.startsWith(join(SRC_DIR, 'lib', 'api')) && !p.startsWith(join(SRC_DIR, 'test')),
    )
    .map((p) => readFileSync(p, 'utf8'))
    .join('\n')

  it('actually parsed the API modules — the canary', () => {
    // ⛔ Without this the whole suite passes while measuring NOTHING: an empty file list,
    // a changed member shape, or a moved directory would leave `functions` empty and every
    // assertion below vacuously true. That failure has shipped in this repo before (§71a),
    // caught by the equivalent canary, which is why one is written first here.
    expect(apiFiles.length).toBeGreaterThan(10)
    expect(functions.size).toBeGreaterThan(50)
    expect(outside.length).toBeGreaterThan(100_000)
  })

  it('has no unwired function beyond the recorded debts', () => {
    const unwired = [...functions.keys()]
      .filter((name) => !new RegExp(`\\b${name}\\b`).test(outside))
      .sort()
    expect(unwired).toEqual(Object.keys(KNOWN_UNWIRED).sort())
  })

  it('records a reason for every debt, and keeps the list shrink-only', () => {
    // A name left here after it HAS been wired is the other half of the ratchet: the
    // list must shrink when the debt is paid, or it rots into an approval.
    for (const [name, reason] of Object.entries(KNOWN_UNWIRED)) {
      expect(functions.has(name), `${name} is no longer an API function — drop it`).toBe(true)
      expect(new RegExp(`\\b${name}\\b`).test(outside), `${name} is wired now — drop it`).toBe(
        false,
      )
      expect(reason.length).toBeGreaterThan(20)
    }
  })
})
